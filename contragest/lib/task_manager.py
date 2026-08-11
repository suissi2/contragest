import threading
import time
from typing import Callable, Optional, Dict, Any, List
from dataclasses import dataclass, field

@dataclass
class Task:
    id: str
    name: str
    description: str = ""
    total_steps: int = 100
    current_step: int = 0
    status: str = "pending" # pending, running, completed, failed
    error: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    on_progress: Optional[Callable[[float, str], None]] = None # (percent, text)
    on_complete: Optional[Callable[[Any], None]] = None
    on_error: Optional[Callable[[str], None]] = None

class TaskManager:
    """
    Manages concurrent and sequential tasks with thread safety and GUI integration.
    Designed for professional high-performance GUI applications.
    """
    def __init__(self, master=None):
        self.master = master # Tkinter root/master for .after calls
        self.tasks: Dict[str, Task] = {}
        self.active_tasks: List[str] = []
        self._lock = threading.Lock()

    def run_task(self, task_id: str, name: str, target: Callable, args=(), kwargs=None, **task_kwargs) -> Task:
        """
        Starts a background task and tracks its progress.
        """
        if kwargs is None: kwargs = {}
        
        with self._lock:
            # Cleanup old task if exists
            if task_id in self.tasks:
                if task_id in self.active_tasks:
                    self.active_tasks.remove(task_id)
            
            task = Task(id=task_id, name=name, **task_kwargs)
            self.tasks[task_id] = task
            self.active_tasks.append(task_id)
        
        def wrapper():
            task.status = "running"
            task.start_time = time.time()
            
            # Auto-set task name on GUI if master supports it
            if self.master and hasattr(self.master, "_set_task_name"):
                self.master.after(0, lambda: self.master._set_task_name(name))
                
            try:
                # Target function should accept a 'progress_callback' kwarg
                def internal_progress(current, total, message=""):
                    self.update_progress(task_id, current, total, message)

                # Inject progress callback into target if possible
                import inspect
                sig = inspect.signature(target)
                if 'progress_callback' in sig.parameters:
                    result = target(*args, progress_callback=internal_progress, **kwargs)
                else:
                    result = target(*args, **kwargs)
                
                with self._lock:
                    task.status = "completed"
                    task.end_time = time.time()
                    task.current_step = task.total_steps
                    if task_id in self.active_tasks:
                        self.active_tasks.remove(task_id)
                
                if task.on_complete:
                    if self.master:
                        self.master.after(0, lambda: task.on_complete(result))
                    else:
                        task.on_complete(result)
                        
            except Exception as e:
                import traceback
                print(f"Task {task_id} failed: {e}")
                traceback.print_exc()
                
                with self._lock:
                    task.status = "failed"
                    task.error = str(e)
                    task.end_time = time.time()
                    if task_id in self.active_tasks:
                        self.active_tasks.remove(task_id)
                
                if task.on_error:
                    if self.master:
                        self.master.after(0, lambda: task.on_error(str(e)))
                    else:
                        task.on_error(str(e))
        
        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
        return task

    def update_progress(self, task_id: str, current: int, total: int, message: str = ""):
        """
        Updates task progress and triggers UI callbacks.
        Includes automatic ETA calculation for better UX.
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if not task: return
            
            task.current_step = current
            task.total_steps = total
            
            # Robust percentage calculation handles both (current, total, msg) and legacy (percent, msg)
            try:
                if isinstance(total, str): # Handle legacy 2-arg calls where total received the message
                    percent = float(current)
                    message = total
                else:
                    percent = (current / total * 100) if total > 0 else 0
            except:
                percent = 0
            
            elapsed = time.time() - task.start_time
            
            eta_str = ""
            if percent > 5: # Only show ETA after some progress
                try:
                    total_est = elapsed / (percent / 100)
                    remaining = total_est - elapsed
                    if remaining > 0:
                        mins, secs = divmod(int(remaining), 60)
                        if mins > 0:
                            eta_str = f" - ETA: {mins}m {secs}s"
                        else:
                            eta_str = f" - ETA: {secs}s"
                except ZeroDivisionError:
                    pass
            
            display_text = f"{int(percent)}% {message}{eta_str}"
            
            if task.on_progress:
                if self.master:
                    self.master.after(0, lambda: task.on_progress(percent, display_text))
                else:
                    task.on_progress(percent, display_text)

    def get_aggregate_progress(self):
        """
        Returns the overall progress of all active tasks.
        """
        with self._lock:
            if not self.active_tasks:
                return 0.0, ""
            
            total_pct = 0.0
            names = []
            for tid in self.active_tasks:
                t = self.tasks[tid]
                names.append(t.name)
                if t.total_steps > 0:
                    total_pct += (t.current_step / t.total_steps * 100)
            
            avg_pct = total_pct / len(self.active_tasks)
            summary = " & ".join(names)
            return avg_pct, f"{summary}: {int(avg_pct)}%"
