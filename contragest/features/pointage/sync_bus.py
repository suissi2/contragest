import queue
import threading
import time
from typing import Optional, Callable
from contragest.core.logging import setup_logger
from contragest.core.error_reporter import ErrorReporter

logger = setup_logger("sync_bus")

class SyncBus:
    """
    Singleton Background Worker for synchronization tasks.
    
    Handles a queue of employee sync requests to avoid blocking the main thread
    during machine communication.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SyncBus, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        self._initialized = True
        logger.info("SyncBus initialized and worker thread started.")

    def publish_employee_update(self, employee_id: int, machine_id: Optional[int] = None):
        """Queue an employee synchronization task (fire-and-forget)."""
        logger.info(f"Queueing sync for employee_id={employee_id}")
        self.queue.put({
            "type": "employee_sync",
            "employee_id": employee_id,
            "machine_id": machine_id,
            "retry_count": 0,
            "callback": None
        })

    def publish_employee_export(self, employee_id: int, callback: Optional[Callable] = None,
                                  tk_root=None):
        """
        Queue an employee sync intended to be triggered by the UI EXPORT button.
        
        Args:
            employee_id: The employee DB id
            callback: A callable(success: bool, message: str) to invoke after sync.
            tk_root: The Tkinter root/toplevel to schedule `callback` on the main thread.
        """
        logger.info(f"Queueing EXPORT sync for employee_id={employee_id}")
        self.queue.put({
            "type": "employee_export",
            "employee_id": employee_id,
            "machine_id": None,
            "retry_count": 0,
            "callback": callback,
            "tk_root": tk_root
        })

    def _worker(self):
        """Background loop processing synchronization tasks."""
        # Defer import to avoid circular dependency
        from contragest.features.pointage.service import PointageService
        
        service = PointageService()
        
        while True:
            task = self.queue.get()
            try:
                if task["type"] == "employee_sync":
                    self._handle_employee_sync(service, task)
                elif task["type"] == "employee_export":
                    self._handle_employee_export(service, task)
            except Exception as e:
                ErrorReporter.report(e, context="sync_bus_worker")
            finally:
                self.queue.task_done()

    def _handle_employee_sync(self, service, task):
        """Process a single employee sync task with retry logic."""
        emp_id = task["employee_id"]
        m_id = task["machine_id"]
        retries = task["retry_count"]
        
        success = False
        try:
            success_count, failed_count = service.ensure_employee_synced(emp_id, m_id)
            success = (failed_count == 0) # Only consider fully successful if no failures, for retry purposes
            if not success:
                logger.warning(f"Sync partial for employee {emp_id}: {success_count} ok, {failed_count} failed")
        except Exception as e:
            logger.error(f"Sync failed for employee {emp_id}: {e}")
        
        if not success and retries < 3:
            # Exponential backoff: 5s, 30s, 2m
            delay = (5, 30, 120)[retries]
            logger.info(f"Retrying sync for employee {emp_id} in {delay}s (Attempt {retries + 1}/3)")
            
            # Use a timer thread for delay to not block the worker queue processing other tasks
            threading.Timer(delay, self._requeue_task, args=[task]).start()
        elif not success:
            logger.error(f"Sync failed for employee {emp_id} after maximum retries.")
        else:
            logger.info(f"Successfully synced employee {emp_id}.")

    def _handle_employee_export(self, service, task):
        """Process an EXPORT task and invoke UI callback when done."""
        emp_id = task["employee_id"]
        callback = task.get("callback")
        tk_root = task.get("tk_root")

        success = False
        message = ""
        try:
            from contragest.core.database import SessionLocal, Employee, AttendanceMachine
            session = SessionLocal()
            emp = session.query(Employee).get(emp_id)
            
            if not emp:
                message = f"Employee {emp_id} not found."
            elif not emp.registration_number:
                message = "no_reg_number"
            else:
                machine_count = session.query(AttendanceMachine).filter_by(is_active=True).count()
                success_count, failed_count = service.ensure_employee_synced(emp_id, None)
                emp_name = f"{emp.first_name} {emp.last_name}"
                
                # Treat as success if at least one machine succeeded (or no active machines)
                if success_count > 0 or machine_count == 0:
                    success = True
                    message = f"export_success|{emp_name}|{success_count}"
                    logger.info(f"EXPORT complete: {emp_name} → {success_count}/{machine_count} machine(s)")
                else:
                    message = f"export_failed|{emp_name}|All machines failed to sync"
                    ErrorReporter.report_warning(f"EXPORT failed: {emp_name} on all machines", context="sync_bus_export")
            session.close()
        except Exception as e:
            message = f"export_failed|employee|{str(e)}"
            logger.error(f"EXPORT error for employee {emp_id}: {e}")
        
        if callback:
            if tk_root:
                # Schedule on main thread for Tkinter thread safety
                try:
                    tk_root.after(0, lambda: callback(success, message))
                except Exception:
                    callback(success, message)
            else:
                callback(success, message)

    def _requeue_task(self, task):
        """Increment retry count and put back into queue."""
        task["retry_count"] += 1
        self.queue.put(task)

# Convenience instance
sync_bus = SyncBus()
