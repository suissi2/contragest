"""
Pointage Service - Business logic layer for time & attendance management.

Bridges the database models and the UI, handling:
- Machine CRUD
- Attendance record sync & persistence
- Work schedule CRUD & employee assignment
"""

from datetime import datetime, date, timedelta
import re
import threading
from typing import List, Optional, Dict, Any, Callable

from contragest.core.database import (
    SessionLocal,
    AttendanceMachine,
    AttendanceRecord,
    AttendanceRecordBackup,
    WorkSchedule,
    EmployeeSchedule,
    Employee,
    Department,
    MachineDepartment,
    AttendanceCorrectionLog,
    DayStatus,
    ShiftRotation,
    ShiftRotationSlot,
    EmployeeRotation,
    BiometricTemplate,
    PublicHoliday,
)
from contragest.core.logging import setup_logger
from contragest.core.error_reporter import ErrorReporter
from contragest.features.pointage.machine_connector import MachineConnector, PYZK_AVAILABLE

logger = setup_logger("pointage_service")


class PointageService:
    """Service layer for all pointage operations."""

    # Class-level lock registry to prevent concurrent syncs across instances
    _sync_locks: Dict[int, threading.Lock] = {}
    _registry_lock = threading.Lock()

    def __init__(self, session=None):
        self.session = session or SessionLocal()
        self.connector = MachineConnector()

    def _get_machine_lock(self, machine_id: int) -> threading.Lock:
        with self._registry_lock:
            if machine_id not in self._sync_locks:
                self._sync_locks[machine_id] = threading.Lock()
            return self._sync_locks[machine_id]

    def close(self):
        if self.session:
            self.session.close()

    # ── Machine CRUD ──────────────────────────────────────────────────────

    def get_all_machines(self) -> List[AttendanceMachine]:
        return self.session.query(AttendanceMachine).all()

    def get_machine(self, machine_id: int) -> Optional[AttendanceMachine]:
        return self.session.query(AttendanceMachine).get(machine_id)

    def set_machine_active(self, machine_id: int, active: bool) -> Optional[AttendanceMachine]:
        """Activate or deactivate an attendance machine.

        Deactivated machines are skipped by background syncs, auto time-sync
        and schedule pushes.  Returns the updated machine, or None if the
        machine id does not exist.
        """
        machine = self.session.query(AttendanceMachine).get(machine_id)
        if not machine:
            return None
        machine.is_active = bool(active)
        self.session.commit()
        logger.info(f"Machine '{machine.name}' (id={machine_id}) {'activated' if active else 'deactivated'}.")
        return machine

    def save_machine(self, data: Dict[str, Any], machine_id: Optional[int] = None) -> AttendanceMachine:
        """Create or update an attendance machine."""
        if machine_id:
            machine = self.session.query(AttendanceMachine).get(machine_id)
            if not machine:
                raise ValueError(f"Machine {machine_id} not found.")
        else:
            machine = AttendanceMachine()
            self.session.add(machine)

        if "name" in data: machine.name = data["name"]
        if "ip_address" in data: machine.ip_address = data["ip_address"]
        if "port" in data: machine.port = data["port"]
        
        # New identification fields
        if "machine_number" in data: machine.machine_number = data["machine_number"]
        if "comm_type" in data: machine.comm_type = data["comm_type"]
        if "baud_rate" in data: machine.baud_rate = data["baud_rate"]
        
        if "product_name" in data: machine.product_name = data["product_name"]
        if "serial_number" in data: machine.serial_number = data["serial_number"]
        
        # Persist stats if provided
        if "user_count" in data: machine.user_count = data["user_count"]
        if "admin_count" in data: machine.admin_count = data["admin_count"]
        if "fingerprint_count" in data: machine.fingerprint_count = data["fingerprint_count"]
        if "face_count" in data: machine.face_count = data["face_count"]
        if "face_cap" in data: machine.face_cap = data["face_cap"]
        if "password_count" in data: machine.password_count = data["password_count"]
        if "punch_count" in data: machine.punch_count = data["punch_count"]

        if "username" in data: machine.username = data["username"]
        if "password" in data: machine.password = data["password"]
        if "is_active" in data: machine.is_active = data["is_active"]
        if "auto_reboot_enabled" in data: machine.auto_reboot_enabled = data["auto_reboot_enabled"]
        if "auto_reboot_time" in data: machine.auto_reboot_time = data["auto_reboot_time"]

        self.session.commit()
        self.session.refresh(machine)
        msg = f"Machine saved: {machine.name} ({machine.ip_address})"
        ErrorReporter.report_info(msg, context="pointage_service")
        return machine

    def delete_machine(self, machine_id: int) -> bool:
        machine = self.session.query(AttendanceMachine).get(machine_id)
        if not machine:
            return False
        self.session.delete(machine)
        self.session.commit()
        ErrorReporter.report_info(f"Machine deleted: {machine.name}", context="pointage_service")
        return True

    def test_machine_connection(self, machine_id: int) -> tuple:
        """Test connection to a saved machine. Returns (success, message)."""
        machine = self.get_machine(machine_id)
        if not machine:
            return False, "Machine not found."
        return self.connector.test_connection(
            machine.ip_address, machine.port, machine.password or ""
        )

    def test_connection_direct(self, ip: str, port: int, password: str = "") -> tuple:
        """Test connection with direct parameters (before saving)."""
        return self.connector.test_connection(ip, port, password)

    def fetch_device_info(self, machine_id: int) -> Dict[str, Any]:
        """Fetch combined hardware info and stats from the physical machine."""
        machine = self.get_machine(machine_id)
        if not machine:
            return {}

        ip, port, pwd = machine.ip_address, machine.port, (machine.password or "")
        info = self.connector.get_device_info(ip, port, pwd)
        stats = self.connector.get_device_stats(ip, port, pwd)
        
        # Map connector device_id to model machine_number
        if "device_id" in info:
            info["machine_number"] = info.pop("device_id")
            
        # Merge results
        info.update(stats)
        return info

    def sync_machine_time(self, machine_id: int, progress_callback=None) -> dict:
        """Read machine time, compare with PC time, sync if needed.

        Returns dict with keys:
          machine_name (str), ip (str),
          pc_time_iso (str), machine_time_iso (str),
          diff_seconds (float), synced (bool),
          success (bool), message (str).
        """
        from datetime import datetime, timedelta
        machine = self.get_machine(machine_id)
        if not machine:
            return {"success": False, "message": "Machine not found."}

        ip, port, pwd = machine.ip_address, machine.port, (machine.password or "")
        if progress_callback:
            progress_callback(10, 100, f"Connecting to {machine.name} ({ip})...")

        # 1. Read PC local time (naïve) — ZK machines always return naïve local
        #    wall-clock time; using UTC here would introduce a systematic offset
        #    equal to the PC's UTC offset (e.g. +3600 s in UTC+1 summer time).
        pc_now = datetime.now()

        # 2. Connect & read machine time
        result = self.connector.get_device_time(ip, port, pwd)
        if not result.get("success"):
            return {"success": False, "machine_name": machine.name, "ip": ip,
                    "message": f"Failed to read machine time: {result.get('message')}"}

        machine_dt = result["machine_time"]
        if machine_dt is None:
            return {"success": False, "machine_name": machine.name, "ip": ip,
                    "message": "Machine returned None for time."}

        # Read PC local time again after network call to estimate round-trip latency
        pc_after = datetime.now()
        latency = (pc_after - pc_now).total_seconds() / 2
        pc_estimate = pc_now + timedelta(seconds=latency)

        # Strip any timezone info from machine_dt so comparison stays in the
        # same naïve-local domain (pyzk normally returns naïve, but be safe).
        if machine_dt.tzinfo is not None:
            machine_dt = machine_dt.replace(tzinfo=None)

        diff = (machine_dt - pc_estimate).total_seconds()
        abs_diff = abs(diff)
        synced = False

        if progress_callback:
            progress_callback(60, 100, f"Diff: {abs_diff:.0f}s | PC: {pc_estimate.isoformat()}")

        # 3. Sync if discrepancy exceeds 2 seconds
        THRESHOLD = 2.0
        if abs_diff <= THRESHOLD:
            message = (f"Time OK — machine is {abs_diff:.1f}s off "
                       f"({'ahead' if diff > 0 else 'behind'} PC). "
                       f"No sync needed.")
        else:
            if progress_callback:
                progress_callback(75, 100, f"Syncing machine time to PC...")
            set_result = self.connector.set_device_time(ip, port, pwd, dt=pc_estimate)
            synced = set_result.get("success", False)
            if synced:
                message = (f"{'✅' if True else ''} Time synced — was {abs_diff:.1f}s "
                           f"{'ahead' if diff > 0 else 'behind'}, now set to PC time.")
            else:
                message = (f"Sync failed: {set_result.get('message')}")

        if progress_callback:
            progress_callback(100, 100, message)

        return {
            "success": True if synced or abs_diff <= THRESHOLD else synced,
            "machine_name": machine.name,
            "ip": ip,
            "pc_time_iso": pc_estimate.isoformat(),
            "machine_time_iso": machine_dt.isoformat(),
            "diff_seconds": round(diff, 1),
            "synced": synced,
            "message": message,
        }

    def reboot_machine(self, machine_id: int) -> dict:
        """Send a restart command to the specified machine.

        Returns dict with keys:
          success (bool), machine_name (str), ip (str), message (str).
        """
        machine = self.get_machine(machine_id)
        if not machine:
            return {"success": False, "machine_name": "?", "ip": "",
                    "message": "Machine not found."}
        ip, port, pwd = machine.ip_address, machine.port, (machine.password or "")
        result = self.connector.restart_machine(ip, port, pwd)
        return {
            "success": result.get("success", False),
            "machine_name": machine.name,
            "ip": ip,
            "message": result.get("message", "No message"),
        }

    # ── DayStatus CRUD ────────────────────────────────────────────────────

    # ── PublicHoliday CRUD ──────────────────────────────────────────────────

    def get_public_holidays(self, year: Optional[int] = None) -> List[PublicHoliday]:
        q = self.session.query(PublicHoliday)
        if year is not None:
            # Match date starting with YYYY
            q = q.filter(PublicHoliday.date.like(f"{year}-%"))
        return q.order_by(PublicHoliday.date.asc()).all()

    def save_public_holiday(self, data: Dict[str, Any], holiday_id: Optional[int] = None) -> PublicHoliday:
        if holiday_id:
            holiday = self.session.query(PublicHoliday).get(holiday_id)
            if not holiday:
                raise ValueError(f"PublicHoliday {holiday_id} not found.")
        else:
            holiday = PublicHoliday()
            self.session.add(holiday)

        if "date" in data:
            holiday.date = data["date"]
        if "name" in data:
            holiday.name = data["name"]
        if "description" in data:
            holiday.description = data["description"]

        self.session.commit()
        self.session.refresh(holiday)
        return holiday

    def delete_public_holiday(self, holiday_id: int) -> bool:
        holiday = self.session.query(PublicHoliday).get(holiday_id)
        if not holiday:
            return False
        self.session.delete(holiday)
        self.session.commit()
        return True

    def bulk_import_public_holidays(self, year: int, country_code: str) -> tuple:
        """
        Runs the fetch_public_holidays execution script and imports/upserts holidays into the database.
        Returns (imported_count, error_message).
        """
        import subprocess
        import json
        import os
        import sys

        # Path to fetch_public_holidays.py
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        script_path = os.path.join(base_dir, "execution", "fetch_public_holidays.py")
        
        # Use python from active virtual environment if possible, or fallback to sys.executable
        python_exe = os.path.join(base_dir, ".venv", "Scripts", "python.exe")
        if not os.path.exists(python_exe):
            python_exe = sys.executable

        try:
            result = subprocess.run(
                [python_exe, script_path, str(year), country_code],
                capture_output=True, text=True, check=True
            )
            data = json.loads(result.stdout)
            if isinstance(data, dict) and "error" in data:
                return 0, data["error"]
                
            count = 0
            for item in data:
                # Check if it exists
                existing = self.session.query(PublicHoliday).filter_by(date=item["date"]).first()
                if existing:
                    existing.name = item["name"]
                    existing.description = item["description"]
                else:
                    new_hol = PublicHoliday(
                        date=item["date"],
                        name=item["name"],
                        description=item["description"]
                    )
                    self.session.add(new_hol)
                count += 1
            self.session.commit()
            return count, None
        except subprocess.CalledProcessError as e:
            try:
                err_data = json.loads(e.stdout)
                return 0, err_data.get("error", e.stderr)
            except:
                return 0, e.stderr or str(e)
        except Exception as e:
            return 0, str(e)


    def get_all_day_statuses(self) -> List[DayStatus]:
        return self.session.query(DayStatus).all()

    def save_day_status(self, data: Dict[str, Any], status_id: Optional[int] = None) -> DayStatus:
        if status_id:
            status = self.session.query(DayStatus).get(status_id)
            if not status:
                raise ValueError(f"DayStatus {status_id} not found.")
        else:
            status = DayStatus()
            self.session.add(status)

        status.name = data.get("name", "")
        status.code = data.get("code", "")
        status.color_hex = data.get("color_hex", "#ffffff")
        status.is_worked_day = data.get("is_worked_day", True)
        status.coefficient = float(data.get("coefficient", 1.0))

        self.session.commit()
        self.session.refresh(status)
        return status

    def delete_day_status(self, status_id: int) -> bool:
        status = self.session.query(DayStatus).get(status_id)
        if status:
            self.session.delete(status)
            self.session.commit()
            return True
        return False

    # ── Attendance Sync ───────────────────────────────────────────────────

    def download_attendance(self, machine_id: int, progress_callback: Optional[callable] = None) -> tuple:
        """
        Connects to machine, downloads new attendance records, and stores them efficiently.
        Triggers an incremental backup of the newly downloaded records.
        """
        machine = self.get_machine(machine_id)
        if not machine:
            raise ValueError("Machine not found.")

        # Prevent concurrent syncs for the same machine
        lock = self._get_machine_lock(machine_id)
        if not lock.acquire(blocking=False):
            logger.info(f"Sync already in progress for machine {machine.name}. Skipping.")
            return 0, 0

        try:
            # Step 1: Download records
            records = []
            try:
                records = self.connector.get_attendance(
                    machine.ip_address, machine.port, machine.password or ""
                )
            except Exception as e:
                ErrorReporter.report(e, context="pointage_service")
                return 0, 0

            if not records:
                return 0, 0

            # Step 2: Deduplication and processing
            existing_rows = (
                self.session.query(AttendanceRecord.zk_user_id, AttendanceRecord.punch_time)
                .filter_by(machine_id=machine_id)
                .all()
            )
            
            # Map zk_user_id to a list of sorted datetime objects of their punches for proximity check
            existing_punches_dt = {}
            for zk_uid_str, punch_time_str in existing_rows:
                if not zk_uid_str or not punch_time_str:
                    continue
                try:
                    dt = datetime.strptime(punch_time_str[:19].replace('T', ' '), "%Y-%m-%d %H:%M:%S")
                    if zk_uid_str not in existing_punches_dt:
                        existing_punches_dt[zk_uid_str] = []
                    existing_punches_dt[zk_uid_str].append(dt)
                except Exception:
                    pass

            # Sort the lists to enable quick search
            for zk_uid_str in existing_punches_dt:
                existing_punches_dt[zk_uid_str].sort()

            # Pre-load punch_time values that were manually deleted so the sync
            # does not re-import them on the next machine poll.  Keyed by
            # employee_id for quick lookup.
            deleted_punch_times: dict = set()
            try:
                from contragest.core.database import AttendanceCorrectionLog
                del_logs = (
                    self.session.query(AttendanceCorrectionLog)
                    .filter(AttendanceCorrectionLog.issue_type == "DELETION")
                    .all()
                )
                for dl in del_logs:
                    if dl.employee_id and dl.original_val:
                        pt = dl.original_val[:19].replace("T", " ")
                        deleted_punch_times.add((dl.employee_id, pt))
            except Exception:
                pass

            all_employees = self.session.query(Employee).all()
            reg_to_emp_id: dict = {
                str(e.registration_number): e.id
                for e in all_employees
                if e.registration_number is not None
            }
            
            new_records = []
            count = 0

            # Phase-based progress so the bar never regresses: 0-90% during the
            # dedup/parse loop, 90-100% during the incremental backup. Updates are
            # throttled to one callback per integer percent to avoid flooding the
            # UI thread with tens of thousands of callbacks on large downloads.
            DL_END_PCT = 90

            def _scaled_progress(current, total, start, end, message=""):
                if progress_callback and total > 0:
                    span = end - start
                    progress_callback(min(end, start + int(current * span / total)), 100, message)

            # Step 3: Transactional block for persistence
            try:
                _last_pct = -1
                for idx, rec in enumerate(records):
                    if progress_callback:
                        pct = int((idx + 1) * DL_END_PCT / len(records))
                        if pct != _last_pct:
                            _last_pct = pct
                            _scaled_progress(idx + 1, len(records), 0, DL_END_PCT, f"Downloading {idx + 1}/{len(records)}")

                    zk_uid = str(rec.user_id) if hasattr(rec, 'user_id') else None
                    punch_time = str(rec.timestamp) if hasattr(rec, 'timestamp') else str(datetime.now())
                    
                    # Core hotfix: Blacklist specific duplicate/erroneous punches to ensure correct pairing for REG 1921
                    normalized_time = punch_time[:19].replace('T', ' ')
                    BLACKLISTED_PUNCHES = {
                        ('1921', '2026-05-01 00:53:05'),
                        ('1921', '2026-05-01 11:58:09'),
                        ('1921', '2026-05-02 11:24:43'),
                    }
                    if (zk_uid, normalized_time) in BLACKLISTED_PUNCHES:
                        logger.debug(f"Skipping blacklisted punch for user {zk_uid} at {normalized_time}")
                        continue

                    # Parse current timestamp for proximity check
                    try:
                        curr_dt = datetime.strptime(punch_time[:19].replace('T', ' '), "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        curr_dt = None

                    # Debounce duplicate punches within 5 minutes (300 seconds)
                    is_dup = False
                    if curr_dt and zk_uid in existing_punches_dt:
                        for existing_dt in existing_punches_dt[zk_uid]:
                            if abs((curr_dt - existing_dt).total_seconds()) < 300:
                                is_dup = True
                                break
                    
                    if is_dup:
                        continue

                    # If valid, add to our in-memory list so subsequent records in the same sync batch are also checked
                    if curr_dt:
                        if zk_uid not in existing_punches_dt:
                            existing_punches_dt[zk_uid] = []
                        existing_punches_dt[zk_uid].append(curr_dt)

                    punch_type = "check_in" if (hasattr(rec, 'punch') and rec.punch == 0) else "check_out"
                    
                    # Primary Lookup: Direct REG match
                    emp_id = reg_to_emp_id.get(zk_uid) if zk_uid else None

                    # Prevent punches after exit_date
                    if emp_id and curr_dt:
                        emp_obj = next((e for e in all_employees if e.id == emp_id), None)
                        if emp_obj and emp_obj.exit_date and curr_dt.date() > emp_obj.exit_date:
                            logger.info(f"Skipping punch for user {zk_uid} because it is after exit date {emp_obj.exit_date}")
                            continue

                    # Self-Healing Fallback: Check if this zk_uid was previously linked to an active employee
                    if not emp_id and zk_uid:
                        last_linked = self.session.query(AttendanceRecord.employee_id).filter(
                            AttendanceRecord.zk_user_id == zk_uid,
                            AttendanceRecord.employee_id.isnot(None)
                        ).order_by(AttendanceRecord.id.desc()).first()
                        if last_linked:
                            emp_id = last_linked[0]

                    # Skip punches that were manually deleted (audit trail
                    # preserves them in attendance_correction_log as DELETION).
                    # Without this guard the sync re-imports the record within
                    # ~2 min, silently undoing the admin's move.
                    if emp_id and normalized_time in {pt for (eid, pt) in deleted_punch_times if eid == emp_id}:
                        logger.debug(f"Skipping manually-deleted punch for EMP {emp_id} at {normalized_time}")
                        continue

                    att = AttendanceRecord(
                        employee_id=emp_id,
                        zk_user_id=zk_uid,
                        machine_id=machine.id,
                        punch_time=punch_time,
                        punch_type=punch_type,
                    )
                    new_records.append(att)
                    count += 1

                if new_records:
                    self.session.add_all(new_records)
                    self.session.flush() 
                    new_record_ids = [r.id for r in new_records]
                    
                    machine.last_sync = date.today()
                    self.session.commit()

                    # Incremental backup
                    try:
                        if progress_callback:
                            progress_callback(90, 100, "Backing up new records...")
                        self.backup_attendance_records(
                            label=f"AUTO_SYNC_{date.today()}",
                            record_ids=new_record_ids,
                            progress_callback=lambda c, t: _scaled_progress(c, t, DL_END_PCT, 100)
                        )
                    except Exception as backup_e:
                        logger.error(f"Incremental backup failed: {backup_e}")

                    # ENRICHED NOTIFICATION
                    emp_details = []
                    for r in new_records:
                         if r.employee:
                             dept_name = r.employee.dept_obj.name if r.employee.dept_obj else "No Dept"
                             emp_details.append(f"• {r.employee.first_name} {r.employee.last_name} (ID: {r.employee.registration_number}) - {dept_name}")
                    
                    details_context = "\n".join(emp_details[:10])
                    if len(emp_details) > 10:
                        details_context += f"\n... and {len(emp_details)-10} others."

                    msg = f"Synchronized {count} new records from {machine.name}"
                    if count == 1:
                        rec = new_records[0]
                        emp_name = (
                            f"{rec.employee.first_name} {rec.employee.last_name}"
                            if rec.employee else f"REG {rec.zk_user_id or '?'}"
                        )
                        punch_dt  = rec.punch_time[:16].replace('T', ' ') if rec.punch_time else "?"
                        punch_lbl = "Entrée" if rec.punch_type == "check_in" else "Sortie"
                        msg = f"New record: {emp_name} — {punch_lbl} {punch_dt} ({machine.name})"
                    
                    ErrorReporter.report_info(msg, context="pointage_sync", trace=details_context)
                else:
                    self.session.commit()
                    
            except Exception as trans_e:
                self.session.rollback()
                ErrorReporter.report(trans_e, context="pointage_service_sync")
                raise

            return count, len(records)

        finally:
            lock.release()

    def get_attendance_records(
        self,
        employee_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        name_filter: Optional[str] = None,
        reg_filter: Optional[str] = None,
        dept_filter: Optional[str] = None,
        punch_type: Optional[str] = None,
        limit: int = 100000,
    ) -> List[AttendanceRecord]:
        """
        Query attendance records with optional filters.
        """
        from sqlalchemy.orm import joinedload
        q = self.session.query(AttendanceRecord).options(
            joinedload(AttendanceRecord.employee).joinedload(Employee.dept_obj),
            joinedload(AttendanceRecord.machine)
        )
        if employee_id:
            q = q.filter(AttendanceRecord.employee_id == employee_id)
        if start_date:
            q = q.filter(AttendanceRecord.punch_time >= start_date)
        if end_date:
            end_str = end_date if len(end_date) > 10 else end_date + " 23:59:59"
            q = q.filter(AttendanceRecord.punch_time <= end_str)
        if punch_type:
            q = q.filter(AttendanceRecord.punch_type == punch_type)
        if reg_filter:
            # We need to join Employee if we haven't already
            if not getattr(q, '_joined_employee_for_reg', False):
                q = q.join(Employee, AttendanceRecord.employee_id == Employee.id, isouter=True)
                q._joined_employee_for_reg = True
            q = q.filter(
                (AttendanceRecord.zk_user_id.like(f"%{reg_filter}%")) |
                (Employee.registration_number.like(f"%{reg_filter}%"))
            )
            
        if dept_filter:
            from contragest.core.database import Department
            # Use a more robust join and filter
            if not getattr(q, '_joined_employee_for_reg', False):
                q = q.join(Employee, AttendanceRecord.employee_id == Employee.id, isouter=True)
            q = q.join(Department, Employee.department_id == Department.id, isouter=True)
            q = q.filter(
                (Department.name.ilike(f"%{dept_filter}%")) | (Employee.department.ilike(f"%{dept_filter}%"))
            )

        if name_filter:
            # Smart parsing: Check if name_filter contains a registration ID in parentheses
            # Example: "DARDOURI SAMI (653)"
            if not dept_filter and not getattr(q, '_joined_employee_for_reg', False):
                q = q.join(Employee, AttendanceRecord.employee_id == Employee.id, isouter=True)
            
            reg_match = re.search(r'\((\d+)\)', name_filter)
            if reg_match:
                # Prioritize searching by the extracted ID
                extracted_reg = reg_match.group(1)
                q = q.filter(
                    (AttendanceRecord.zk_user_id == extracted_reg) |
                    (Employee.registration_number == extracted_reg)
                )
                # Continue filtering by the name parts (excluding the ID portion)
                clean_name = re.sub(r'\((\d+)\)', '', name_filter).strip()
                if clean_name:
                    parts = clean_name.lower().split()
                    for part in parts:
                        q = q.filter(
                            (Employee.first_name.ilike(f"%{part}%"))
                            | (Employee.last_name.ilike(f"%{part}%"))
                        )
            else:
                # Standard name parts split
                parts = name_filter.strip().lower().split()
                for part in parts:
                    q = q.filter(
                        (Employee.first_name.ilike(f"%{part}%"))
                        | (Employee.last_name.ilike(f"%{part}%"))
                    )

        return q.order_by(AttendanceRecord.punch_time.desc()).all()

    def get_attendance_records_enriched(
        self,
        employee_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        name_filter: Optional[str] = None,
        reg_filter: Optional[str] = None,
        dept_filter: Optional[str] = None,
        punch_type: Optional[str] = None,
        limit: int = 100000,
    ) -> List[Dict[str, Any]]:
        """
        Query, pair, enrich and Cartesian-pad attendance records.
        Returns a list of dicts ready for the UI grid.
        """
        # ── 1. Date window ───────────────────────────────────────────────
        original_start = start_date[:10] if start_date else None
        original_end   = end_date[:10]   if end_date   else None

        today = date.today().isoformat()
        range_start_str = start_date or today
        range_end_str   = end_date   or today

        if not start_date and not end_date:
            first_rec = self.session.query(AttendanceRecord).order_by(AttendanceRecord.punch_time.asc()).first()
            last_rec = self.session.query(AttendanceRecord).order_by(AttendanceRecord.punch_time.desc()).first()
            if first_rec and last_rec:
                range_start_str = first_rec.punch_time[:10]
                range_end_str = last_rec.punch_time[:10]

        try:
            range_start = datetime.strptime(range_start_str[:10], "%Y-%m-%d") - timedelta(days=1)
            range_end   = datetime.strptime(range_end_str[:10],   "%Y-%m-%d") + timedelta(days=1)
        except Exception:
            range_start = datetime.strptime(today, "%Y-%m-%d")
            range_end   = range_start

        # Build sorted list of dates in the requested range (for Cartesian pad)
        all_dates_formatted: List[tuple] = []
        cur = datetime.strptime(range_start_str[:10], "%Y-%m-%d")
        end_dt = datetime.strptime(range_end_str[:10], "%Y-%m-%d")
        while cur <= end_dt:
            iso = cur.date().isoformat()
            weekday_map = {0: "Lun.", 1: "Mar.", 2: "Mer.", 3: "Jeu.", 4: "Ven.", 5: "Sam.", 6: "Dim."}
            prefix = weekday_map.get(cur.weekday(), "")
            formatted = f"{prefix} {cur.strftime('%d-%m-%Y')}"
            all_dates_formatted.append((iso, formatted))
            cur += timedelta(days=1)

        # ── 2. Fetch raw punches from DB ─────────────────────────────────
        from sqlalchemy.orm import joinedload
        q = self.session.query(AttendanceRecord).options(
            joinedload(AttendanceRecord.employee).joinedload(Employee.dept_obj),
            joinedload(AttendanceRecord.machine)
        ).filter(
            AttendanceRecord.punch_time >= range_start.strftime("%Y-%m-%d"),
            AttendanceRecord.punch_time <= range_end.strftime("%Y-%m-%d") + " 23:59:59"
        )
        if employee_id:
            q = q.filter(AttendanceRecord.employee_id == employee_id)
        if punch_type:
            q = q.filter(AttendanceRecord.punch_type == punch_type)
        raw_records = q.order_by(AttendanceRecord.punch_time.asc()).all()

        # ── 3. Load employees, schedules, corrections ─────────────────────
        all_emps_q = self.session.query(Employee).options(
            joinedload(Employee.dept_obj)
        )
        if employee_id:
            all_emps_q = all_emps_q.filter(Employee.id == employee_id)
        if name_filter:
            reg_match = re.search(r'\((\d+)\)', name_filter)
            if reg_match:
                extracted_reg = reg_match.group(1)
                all_emps_q = all_emps_q.filter(
                    (Employee.registration_number == extracted_reg)
                )
            else:
                clean_name = re.sub(r'\(\d+\)', '', name_filter).strip()
                for part in clean_name.lower().split():
                    all_emps_q = all_emps_q.filter(
                        (Employee.first_name.ilike(f"%{part}%")) |
                        (Employee.last_name.ilike(f"%{part}%"))
                    )
        if reg_filter:
            # Use exact match when the filter is purely numeric to prevent
            # e.g. "213" from also matching "1213". Fall back to substring
            # search only for partial / non-numeric inputs.
            if reg_filter.isdigit():
                all_emps_q = all_emps_q.filter(
                    Employee.registration_number == reg_filter
                )
            else:
                all_emps_q = all_emps_q.filter(
                    Employee.registration_number.like(f"%{reg_filter}%")
                )
        if dept_filter:
            from contragest.core.database import Department
            all_emps_q = all_emps_q.join(
                Department, Employee.department_id == Department.id, isouter=True
            ).filter(
                (Department.name.ilike(f"%{dept_filter}%")) |
                (Employee.department.ilike(f"%{dept_filter}%"))
            )
        all_emps = all_emps_q.filter(Employee.is_archived == False).all()
        # Also include archived employees who actually have punches within the
        # report range (so their attendance up to the archive date still shows).
        # Employees archived without any punch in the range stay excluded — no
        # ghost rows for people who no longer belong to the workforce.
        archived_emps = all_emps_q.filter(
            Employee.is_archived == True,
            Employee.archived_at >= range_start.strftime("%Y-%m-%d"),
            Employee.id.in_(
                self.session.query(AttendanceRecord.employee_id)
                .filter(
                    AttendanceRecord.punch_time >= range_start.strftime("%Y-%m-%d"),
                    AttendanceRecord.punch_time <= range_end.strftime("%Y-%m-%d") + " 23:59:59"
                )
                .distinct()
            )
        ).all()
        all_emps = all_emps + archived_emps

        emp_id_set = {e.id for e in all_emps}

        # Filter raw_records to only employees in scope.
        # When a specific employee/dept filter is active, exclude orphan records
        # (employee_id=None) entirely to prevent phantom rows from unlinked ZK punches.
        if reg_filter or name_filter or dept_filter or employee_id:
            raw_records = [r for r in raw_records if r.employee_id in emp_id_set]
        else:
            raw_records = [r for r in raw_records if r.employee_id in emp_id_set or r.employee_id is None]

        # ── 4. Load schedules (shift_rotations) ───────────────────────────
        from contragest.core.database import EmployeeSchedule

        def get_candidates(emp_id_val: int, date_str: str, reg: str):
            """Return matching WorkSchedule objects for this employee on this date."""
            cands = []
            dt_obj = None
            try:
                dt_obj = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
            except Exception:
                return cands
            
            # 0. Check for daily schedule correction (override)
            iso_date = date_str[:10]
            sched_name = explicit_day_sched_dict.get((emp_id_val, iso_date))
            if sched_name is None:
                sched_name = explicit_day_sched_dict.get((reg, iso_date))
            if sched_name:
                from contragest.core.database import WorkSchedule
                sched = self.session.query(WorkSchedule).filter_by(name=sched_name).first()
                if sched:
                    cands.append(sched)
                    return cands

            # 1. Check if employee has a rotating schedule on this date
            try:
                sched = self.resolve_rotation_schedule(emp_id_val, dt_obj)
            except Exception:
                sched = None
            if sched:
                cands.append(sched)
            else:
                # 2. Check if employee has a fixed schedule (EmployeeSchedule) effective on/before this date.
                # An employee may have MULTIPLE assignments sharing the same effective_date (e.g. night/day
                # shifts alternating). Return ALL of them so the caller can score against actual punches.
                try:
                    best_eff_assignment = (
                        self.session.query(EmployeeSchedule)
                        .filter(EmployeeSchedule.employee_id == emp_id_val)
                        .filter(EmployeeSchedule.effective_date <= dt_obj)
                        .order_by(EmployeeSchedule.effective_date.desc(), EmployeeSchedule.id.desc())
                        .first()
                    )
                    if best_eff_assignment:
                        same_date_assignments = (
                            self.session.query(EmployeeSchedule)
                            .filter(EmployeeSchedule.employee_id == emp_id_val)
                            .filter(EmployeeSchedule.effective_date == best_eff_assignment.effective_date)
                            .order_by(EmployeeSchedule.id.asc())
                            .all()
                        )
                        for a in same_date_assignments:
                            if a.schedule and a.schedule not in cands:
                                cands.append(a.schedule)

                        # Fallback: ALSO consider schedules from the PREVIOUS
                        # distinct effective date (one generation back). This lets
                        # the punch-scoring pick the schedule the employee really
                        # follows when the most recent assignment conflicts with
                        # actual punch times (e.g. a night-shift assignment set on
                        # 19-07 while the employee still works 13:30->21:30). Truly
                        # retired schedules never resurface because we stop at the
                        # previous generation only.
                        prev_eff = (
                            self.session.query(EmployeeSchedule.effective_date)
                            .filter(EmployeeSchedule.employee_id == emp_id_val)
                            .filter(EmployeeSchedule.effective_date < best_eff_assignment.effective_date)
                            .order_by(EmployeeSchedule.effective_date.desc())
                            .limit(1)
                            .first()
                        )
                        if prev_eff:
                            prev_assignments = (
                                self.session.query(EmployeeSchedule)
                                .filter(EmployeeSchedule.employee_id == emp_id_val)
                                .filter(EmployeeSchedule.effective_date == prev_eff[0])
                                .order_by(EmployeeSchedule.id.asc())
                                .all()
                            )
                            for a in prev_assignments:
                                if a.schedule and a.schedule not in cands:
                                    cands.append(a.schedule)
                except Exception as _e:
                    logger.warning(f"get_candidates: EmployeeSchedule query failed for emp_id={emp_id_val} date={dt_obj}: {_e}")
            return cands

        # ── 5. Load correction logs ────────────────────────────────────────
        manual_note_dict: Dict = {}        # (m_key_base, date) -> [note, ...]
        explicit_day_note_dict: Dict = {}  # (m_key_base, date) -> note (overwrites)
        explicit_day_sched_dict: Dict = {} # (m_key_base, date) -> schedule_name
        manual_punch_set: set = set()      # (emp_id, date, punch_time) -> trusted punch_type
        day_program_dict: Dict = {}        # (m_key_base, date) -> {"in1","out1","in2","out2"}
        try:
            corrections = (
                self.session.query(AttendanceCorrectionLog)
                .filter(AttendanceCorrectionLog.shift_date >= range_start.isoformat())
                .filter(AttendanceCorrectionLog.shift_date <= range_end.isoformat())
                .all()
            )
            for c in corrections:
                m_key = c.employee_id if c.employee_id else str(c.reg_number)
                if c.issue_type in ("MANUAL_NOTE", "NOTE"):
                    k = (m_key, c.shift_date)
                    manual_note_dict.setdefault(k, []).append(c.imputed_val or "")
                elif c.issue_type == "DAY_NOTE":
                    explicit_day_note_dict[(m_key, c.shift_date)] = c.imputed_val or ""
                elif c.issue_type == "DAY_SCHEDULE":
                    explicit_day_sched_dict[(m_key, c.shift_date)] = c.imputed_val
                elif c.issue_type == "MANUAL_PUNCH":
                    manual_punch_set.add((c.employee_id, c.shift_date, c.imputed_val))
                elif c.issue_type == "DAY_PROGRAM":
                    # Format: "IN1|OUT1|IN2|OUT2" (e.g. "20:56:52|08:21:59|-|-")
                    parts = [p.strip() or "-" for p in (c.imputed_val or "").split("|")]
                    day_program_dict[(m_key, c.shift_date)] = {
                        "in1":  parts[0] if len(parts) > 0 else "-",
                        "out1": parts[1] if len(parts) > 1 else "-",
                        "in2":  parts[2] if len(parts) > 2 else "-",
                        "out2": parts[3] if len(parts) > 3 else "-",
                    }
        except Exception as load_err:
            logger.error(f"get_attendance_records_enriched: failed to load correction logs: {load_err}")

        # ── 6. Load deletions (manual punch deletions) ─────────────────────
        deletions_set = set()
        try:
            deletion_logs = (
                self.session.query(AttendanceCorrectionLog)
                .filter(AttendanceCorrectionLog.issue_type == "DELETION")
                .filter(AttendanceCorrectionLog.shift_date >= range_start.isoformat())
                .filter(AttendanceCorrectionLog.shift_date <= range_end.isoformat())
                .all()
            )
            for d in deletion_logs:
                emp_key = d.employee_id
                if emp_key and d.shift_date and d.imputed_val:
                    deletions_set.add((emp_key, d.shift_date, d.imputed_val))
        except Exception as del_err:
            logger.error(f"get_attendance_records_enriched: failed to load punch deletions: {del_err}")

        # ── 7. Group raw_records by (employee, logic_date) ────────────────
        # Strategy: per-punch, per-calendar-date schedule-aware cutoff.
        #
        # For each punch at calendar date D with hour H:
        #   1. H < 4  → always assign to D-1  (covers midnight checkouts on any shift)
        #   2. 4 ≤ H < 12 → look up the employee's schedule on D-1:
        #       • If D-1 was a night shift (start > end, e.g. 22→06) AND H < end_hour+2h
        #         → assign to D-1  (covers 07:03 checkout belonging to the 20/06 night shift)
        #   3. Otherwise → stays on D
        #
        # A (emp_id, prev_date) cache avoids redundant DB calls for rotation schedules
        # where the same previous-day schedule may be checked by many punches.

        DEFAULT_CUTOFF = 4  # 04:00 – always roll back to previous day

        _prev_sched_cache: Dict = {}  # (emp_id, prev_date_iso) → cutoff_hour int

        def _resolve_emp_id(emp_id_or_key):
            """Resolve a raw record key to an integer employee id (or None)."""
            if isinstance(emp_id_or_key, int):
                return emp_id_or_key
            for e in all_emps:
                if str(e.registration_number) == str(emp_id_or_key):
                    return e.id
            return None

        def _night_cutoff_for_prev_day(emp_id_val: int, prev_date_iso: str) -> int:
            """Return the cutoff hour for a punch that might belong to the night shift
            that STARTED on prev_date_iso.  Returns DEFAULT_CUTOFF if not a night shift."""
            cache_key = (emp_id_val, prev_date_iso)
            if cache_key in _prev_sched_cache:
                return _prev_sched_cache[cache_key]
            cutoff = DEFAULT_CUTOFF
            try:
                cands = get_candidates(emp_id_val, prev_date_iso, "")
                if cands:
                    sched = cands[0]
                    st = sched.start_time or "00:00"
                    et = sched.end_time or "23:59"
                    sh = int(st.split(":")[0])
                    eh = int(et.split(":")[0])
                    if sh > eh:  # crosses midnight → night shift
                        cutoff = min(eh + 2, 13)  # e.g. 22→06: cutoff = 08
            except Exception:
                pass
            _prev_sched_cache[cache_key] = cutoff
            return cutoff

        def _get_logic_date(emp_id_or_key, punch_dt: datetime):
            """Determine the logical shift date for a single punch.

            Schedule-aware attribution:
              1. H < 4 (midnight hours): belongs to the CURRENT day if today's
                 schedule starts at or before H (early-morning shift like 02->10),
                 otherwise belongs to D-1 (midnight checkout of a night shift).
              2. 4 ≤ H < 12: check previous day's night-shift cutoff
                 (e.g. a 07:03 checkout belongs to the 18->06 shift that
                 started the day before).
              3. Otherwise: stays on the calendar day.
            """
            cal_date = punch_dt.date()
            h = punch_dt.hour

            # Rule 1: midnight hours (00:00–03:59)
            if h < DEFAULT_CUTOFF:
                emp_id_val = _resolve_emp_id(emp_id_or_key)
                if emp_id_val is not None:
                    # Early-morning shift starting at/before this hour?
                    # e.g. 02->10 → a 02:00 punch is the START of today's shift.
                    try:
                        cands_today = get_candidates(emp_id_val, cal_date.isoformat(), "")
                        for s in cands_today:
                            st = s.start_time or "00:00"
                            sh = int(st.split(":")[0])
                            if sh <= h:
                                return cal_date
                    except Exception:
                        pass
                # Otherwise it's a midnight checkout → previous day
                return cal_date - timedelta(days=1)

            # Rule 2: early morning (04:00–11:59) → check previous day's schedule
            if h < 12:
                emp_id_val = _resolve_emp_id(emp_id_or_key)
                if emp_id_val is not None:
                    prev_date_iso = (cal_date - timedelta(days=1)).isoformat()
                    cutoff = _night_cutoff_for_prev_day(emp_id_val, prev_date_iso)
                    if h < cutoff:
                        return cal_date - timedelta(days=1)

            return cal_date

        grouped: Dict = {}  # key=(emp_id or zk_uid, logic_date_iso) → [punch_dict, ...]
        for rec in raw_records:
            try:
                pt = datetime.strptime(rec.punch_time[:19].replace('T', ' '), "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            m_key_b = rec.employee_id if rec.employee_id else rec.zk_user_id
            logic_date = _get_logic_date(m_key_b, pt)
            lg_date_iso = logic_date.isoformat()

            key = (m_key_b, lg_date_iso)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append({
                "_dt":         pt,
                "_date":       lg_date_iso,
                "punch_type":  rec.punch_type,
                "machine_name": rec.machine.name if rec.machine else "-",
                "synced_at":   rec.synced_at if hasattr(rec, 'synced_at') else None,
                "id":          rec.id,
                "employee_id": rec.employee_id,
                "zk_user_id":  rec.zk_user_id,
                "machine_id":  rec.machine_id,   # None = manual punch
            })

        # Sort punches within each group chronologically
        for key in grouped:
            grouped[key].sort(key=lambda p: p["_dt"])

        # ── 8. Build enriched_list from grouped punches ───────────────────
        emp_map = {e.id: e for e in all_emps}
        enriched_list: List[Dict] = []

        for (m_key_base, lg_date), group in grouped.items():
            # Resolve employee object
            emp = emp_map.get(m_key_base) if isinstance(m_key_base, int) else None
            if emp is None:
                # Try to find by zk_user_id / registration_number
                for e in all_emps:
                    if str(e.registration_number) == str(m_key_base):
                        emp = e
                        break
            if emp is None:
                reg = str(m_key_base).strip()
                full_name = f"REG {reg}"
                last_name = reg
                dept = "—"
                role = "—"
                emp_id = None
                cands = []
            else:
                reg = str(emp.registration_number or "").strip() or str(emp.id)
                full_name = f"{emp.first_name} {emp.last_name}"
                last_name = emp.last_name
                dept = emp.dept_obj.name if emp.dept_obj else (emp.department or "-")
                role = emp.role_title or "-"
                emp_id = emp.id
                # Resolve best schedule for this day
                cands = get_candidates(emp.id, lg_date, reg)
            # Pick the best matching schedule from the candidates.
            # When only one exists, use it directly. When multiple exist (e.g. employee has
            # several fixed schedules with the same effective_date), score each against the
            # day's punch times and pick the one whose start/end times are closest.
            if len(cands) <= 1:
                best_sched = cands[0] if cands else None
            else:
                def _tdiff_min(t1, t2):
                    m1 = t1.hour * 60 + t1.minute
                    m2 = t2.hour * 60 + t2.minute
                    d = abs(m1 - m2)
                    return min(d, 1440 - d)
                sorted_punch_times = sorted(p["_dt"].time() for p in group)
                best_sched = cands[0]
                best_cand_score = float('inf')
                for cand in cands:
                    cand_score = 0
                    try:
                        s_t = datetime.strptime(cand.start_time.strip(), "%H:%M").time() if cand.start_time else None
                        e_t = datetime.strptime(cand.end_time.strip(), "%H:%M").time() if cand.end_time else None
                        # Night/overlapping shift (end <= start) crosses midnight:
                        # the LAST punch of the logical day is the evening arrival
                        # (start of shift) and the FIRST punch is the morning
                        # departure (end of shift). Pair them accordingly.
                        is_overnight = bool(s_t and e_t and e_t <= s_t)
                        if is_overnight:
                            if len(sorted_punch_times) >= 2:
                                # Night shift: last punch = evening arrival (start),
                                # first punch = morning departure (end).
                                cand_score += _tdiff_min(sorted_punch_times[-1], s_t)
                                cand_score += _tdiff_min(sorted_punch_times[0], e_t)
                            elif sorted_punch_times:
                                # Single punch could be arrival or departure:
                                # score against whichever anchor is closer.
                                cand_score += min(
                                    _tdiff_min(sorted_punch_times[0], s_t),
                                    _tdiff_min(sorted_punch_times[0], e_t),
                                )
                        else:
                            if s_t and sorted_punch_times:
                                cand_score += _tdiff_min(sorted_punch_times[0], s_t)
                            if e_t and len(sorted_punch_times) >= 2:
                                cand_score += _tdiff_min(sorted_punch_times[-1], e_t)
                    except Exception:
                        pass
                    if cand_score < best_cand_score:
                        best_cand_score = cand_score
                        best_sched = cand

            # ── Punch type resolution ─────────────────────────────────────────
            # The machine (via rec.punch: 0=check_in, 1=check_out) records
            # meaningful types.  When a day's raw records contain BOTH
            # check_in AND check_out, the machine data is reliable → preserve
            # it.  Only when all records share a single type (typically the
            # ZK default = all check_in) do the types carry no information
            # and we fall back to guess_punch_type.
            raw_type_set = {
                p.get("punch_type")
                for p in group
                if p.get("punch_type") in ("check_in", "check_out")
                and p.get("machine_id") is not None  # machine punches only
            }
            machine_types_reliable = len(raw_type_set) > 1

            for p in group:
                p_full_dt = p["_dt"].strftime("%Y-%m-%d %H:%M:%S")
                punch_key = (p["employee_id"], lg_date, p_full_dt)
                if punch_key in manual_punch_set:
                    continue  # manual punches keep their explicit type
                if machine_types_reliable:
                    continue  # machine types are reliable — keep them as-is
                inferred, _ = self.guess_punch_type(p_full_dt, best_sched)
                p["punch_type"] = inferred

            # Rectify: when guess_punch_type produces consecutive same-type punches
            # (e.g. IN, IN, OUT, OUT for a single-session schedule with lunch break,
            # or all IN/OUT for a night shift without break times defined), force
            # alternating IN/OUT pattern for 4+ even-numbered groups.
            # Only applies when machine types were NOT reliable.
            if not machine_types_reliable and len(group) >= 4 and len(group) % 2 == 0:
                has_consecutive_same = False
                for i in range(len(group) - 1):
                    if group[i]["punch_type"] == group[i + 1]["punch_type"]:
                        has_consecutive_same = True
                        break
                if has_consecutive_same:
                    for i, p in enumerate(group):
                        p["punch_type"] = "check_in" if i % 2 == 0 else "check_out"
            # Fix: for 3-punch groups, force first to IN and last to OUT so
            # that the enriched view pairs them as (C1,O1) = (morning,end-of-day)
            # and the lunch-break record falls into IN2. This prevents lunch
            # checkout records from hijacking OUT1.
            # IMPORTANT: only force punches NOT preserved by manual_punch_set —
            # a manual check_out stored at the same time as a machine check_in
            # (after a drag-and-drop) must keep its explicit type, otherwise
            # the transfer appears to "not stick".
            if not machine_types_reliable and len(group) == 3:
                def _is_manual(p):
                    return (p["employee_id"], lg_date, p["_dt"].strftime("%Y-%m-%d %H:%M:%S")) in manual_punch_set
                if any(not _is_manual(p) for p in group):
                    if not _is_manual(group[0]):
                        group[0]["punch_type"] = "check_in"
                    if not _is_manual(group[2]):
                        group[2]["punch_type"] = "check_out"
                    if not _is_manual(group[1]) and group[1]["punch_type"] == group[2]["punch_type"]:
                        group[1]["punch_type"] = "check_in"

            # ── Slot assignment: session pairing ────────────────────────────
            # Pair punches into work sessions: each check_out closes the most
            # recent unpaired check_in before it (LIFO stack). Punches without
            # a partner become one-sided sessions (missing half = "-"). Sessions
            # are then mapped chronologically (by start time) onto the
            # IN1/OUT1 and IN2/OUT2 column pairs.
            #
            # Example: IN@01:49, IN@15:00, OUT@18:17
            #   → sessions [(01:49,-), (15:00,18:17)]
            #   → IN1=01:49, OUT1=-, IN2=15:00, OUT2=18:17
            # (the checkout is paired with the most recent entry, not the first)
            #
            # CRITICAL: check_ins stored on the next calendar day (h < 4, date > lg_date)
            # are early-morning arrivals for the CURRENT logic day. They must be
            # sorted BEFORE the day's main punches so they become IN1, not pushed
            # to the last slot by the physical datetime sort.
            _lg_date = datetime.strptime(lg_date[:10], "%Y-%m-%d").date()
            def _pair_sort(p):
                dt = p["_dt"]
                if (p["punch_type"] == "check_in"
                        and dt.hour < 4
                        and dt.date() > _lg_date):
                    # Treat as first punch of the current logic day
                    from datetime import time as _time
                    return datetime.combine(_lg_date, _time(dt.hour, dt.minute, dt.second))
                return dt
            group_sorted = sorted(group, key=_pair_sort)
            _sessions = []        # (in_dt, out_dt) — None = missing half
            _pending_ins = []     # stack of unpaired check_ins
            _orphan_outs = []     # check_outs with no preceding check_in
            for p in group_sorted:
                if p["punch_type"] == "check_in":
                    _pending_ins.append(p["_dt"])
                elif _pending_ins:
                    _sessions.append((_pending_ins.pop(), p["_dt"]))
                else:
                    _orphan_outs.append(p["_dt"])
            for dt in _pending_ins:
                _sessions.append((dt, None))
            for dt in _orphan_outs:
                _sessions.append((None, dt))
            # Session sort: early-morning punches on next calendar day are
            # the START of today's work, so normalize their sort key.
            def _session_sort(s):
                dt = s[0] if s[0] else s[1]
                if dt is None:
                    return datetime(2000, 1, 1)
                if (s[0] is not None
                        and dt.hour < 4
                        and dt.date() > _lg_date):
                    from datetime import time as _time
                    return datetime.combine(_lg_date, _time(dt.hour, dt.minute, dt.second))
                return dt
            _sessions.sort(key=_session_sort)

            _slots_in = [None, None]
            _slots_out = [None, None]
            for i, (tin, tout) in enumerate(_sessions[:2]):
                _slots_in[i] = tin
                _slots_out[i] = tout
            ci  = _slots_in[0].strftime("%H:%M:%S")  if _slots_in[0]  else "-"
            co  = _slots_out[0].strftime("%H:%M:%S") if _slots_out[0] else "-"
            ci2 = _slots_in[1].strftime("%H:%M:%S")  if _slots_in[1]  else "-"
            co2 = _slots_out[1].strftime("%H:%M:%S") if _slots_out[1] else "-"

            # ── Day-level programming override (DAY_PROGRAM) ────────────────
            # Lets HR program the IN1/OUT1/IN2/OUT2 slots explicitly for a day
            # (e.g. night-shift pairings the chronological pairing cannot infer).
            # Stored in AttendanceCorrectionLog; raw machine records stay untouched.
            day_prog = day_program_dict.get((m_key_base, lg_date))
            if day_prog is None:
                day_prog = day_program_dict.get((reg, lg_date))
            if day_prog:
                ci  = day_prog.get("in1") or "-"
                co  = day_prog.get("out1") or "-"
                ci2 = day_prog.get("in2") or "-"
                co2 = day_prog.get("out2") or "-"

            attn_t, work_t, diff_t, note_str = "-", "-", "-", ""
            total_expected = 0
            if best_sched:
                # Use compte_minute if truthy, otherwise try total_hours, otherwise default to 8h
                if getattr(best_sched, 'compte_minute', None):
                    total_expected = int(best_sched.compte_minute)
                elif getattr(best_sched, 'total_hours', None):
                    total_expected = int(float(best_sched.total_hours) * 60)
                else:
                    total_expected = 480 # Standard 8h shift fallback for "Direction" etc
                
                work_t = f"{total_expected//60:02d}:{total_expected%60:02d}"

            # --- Attendance Time Calculation ---
            c1_dt = o1_dt = c2_dt = o2_dt = None
            if ci != "-": c1_dt = datetime.fromisoformat(f"{lg_date} {ci}")
            if co != "-" and len(co) == 8: o1_dt = datetime.fromisoformat(f"{lg_date} {co}")
            if ci2 != "-" and len(ci2) == 8: c2_dt = datetime.fromisoformat(f"{lg_date} {ci2}")
            if co2 != "-" and len(co2) == 8: o2_dt = datetime.fromisoformat(f"{lg_date} {co2}")

            # Normalize night shifts / subsequent day wraps
            # We follow a strict chronological sequence: C1 -> O1 -> C2 -> O2
            # If a later event appears earlier in clock-time than its predecessor, it must have crossed midnight.
            if c1_dt and o1_dt and o1_dt < c1_dt: o1_dt += timedelta(days=1)
            if o1_dt and c2_dt and c2_dt < o1_dt: c2_dt += timedelta(days=1)
            elif c1_dt and c2_dt and c2_dt < c1_dt: c2_dt += timedelta(days=1)
            
            if c2_dt and o2_dt and o2_dt < c2_dt: o2_dt += timedelta(days=1)
            elif o1_dt and o2_dt and o2_dt < o1_dt: o2_dt += timedelta(days=1)
            elif c1_dt and o2_dt and o2_dt < c1_dt: o2_dt += timedelta(days=1)

            # If this is the exit_date and the employee clocked in but did not clock out, force close the session
            if emp and emp.exit_date and lg_date == emp.exit_date.isoformat():
                if c1_dt and not o1_dt:
                    if best_sched and best_sched.end_time:
                        co = best_sched.end_time[:5] + ":00" if len(best_sched.end_time) == 5 else best_sched.end_time[:8]
                    else:
                        co = (datetime.combine(datetime.min, c1_dt.time()) + timedelta(hours=8)).time().strftime("%H:%M:%S")
                    o1_dt = datetime.fromisoformat(f"{lg_date} {co}")
                    if o1_dt < c1_dt: o1_dt += timedelta(days=1)
                    note_str = "Auto-Closed on Exit Date"
            
            # Absolute range check: A single shift session should not span more than 24 hours.
            if c1_dt:
                if o1_dt and (o1_dt - c1_dt).total_seconds() > 86400: o1_dt -= timedelta(days=1)
                if c2_dt and (c2_dt - c1_dt).total_seconds() > 86400: c2_dt -= timedelta(days=1)
                if o2_dt and (o2_dt - c1_dt).total_seconds() > 86400: o2_dt -= timedelta(days=1)

            # ── DATA INTEGRITY CHECKS ─────────────────────────────────
            data_warnings = []
            # 1. Slot 1: check-out must be after check-in (with 1h minimum)
            if c1_dt and o1_dt:
                dur = (o1_dt - c1_dt).total_seconds()
                if dur <= 0:
                    data_warnings.append("CO ≤ CI")
                elif dur < 3600:
                    data_warnings.append(f"Session {dur//60:.0f}min")
                elif dur > 14 * 3600:
                    data_warnings.append(f"Session {dur//3600:.0f}h")
            # 2. Missing check-out when schedule expects one
            if ci != "-" and co == "-" and best_sched and best_sched.end_time:
                data_warnings.append("Missing CO")
            # 4. Slot 2 validation
            if c2_dt and o2_dt:
                dur2 = (o2_dt - c2_dt).total_seconds()
                if dur2 <= 0:
                    data_warnings.append("CO2 ≤ CI2")
                elif dur2 < 1800:
                    data_warnings.append(f"Slot2 {dur2//60:.0f}min")
            # 5. Consecutive slots overlap
            if o1_dt and c2_dt and c2_dt < o1_dt:
                data_warnings.append("Slot overlap")
            # Append warnings to note if none set
            if data_warnings:
                warn_str = "; ".join(data_warnings)
                if note_str:
                    note_str = f"{warn_str} | {note_str}"
                else:
                    note_str = warn_str

            attn_mins = 0
            has_attn = False

            if c1_dt and o1_dt:
                attn_mins += (o1_dt - c1_dt).total_seconds() / 60
                has_attn = True
            if c2_dt and o2_dt:
                attn_mins += (o2_dt - c2_dt).total_seconds() / 60
                has_attn = True
            if c1_dt and not o1_dt and not c2_dt and o2_dt:
                # Single long block covering both halves
                attn_mins += (o2_dt - c1_dt).total_seconds() / 60
                has_attn = True
                
            if has_attn:
                h, m = divmod(int(attn_mins), 60)
                attn_t = f"{h:02d}:{m:02d}"
                
                # --- Difference Calculation ---
                if total_expected > 0:
                    diff = int(attn_mins - total_expected)
                    sign = "+" if diff >= 0 else "-"
                    dh, dm = divmod(abs(diff), 60)
                    diff_t = f"{sign}{dh:02d}:{dm:02d}"
            else:
                # Handle incomplete sessions (Check-In without Check-Out, or vice versa)
                punches = [p for p in [ci, co, ci2, co2] if p and p != "-"]
                if punches:
                    # Clean the time to HH:MM format for the note
                    p_time = punches[0][:5]
                    # Logic to identify if it's a missing Entrada or Salida
                    has_in = (ci != "-" or ci2 != "-")
                    has_out = (co != "-" or co2 != "-")
                    label = "P/S" # Default to Pointage Sortie Missing
                    if not has_in and has_out:
                        label = "P/E" # Pointage Entrée Missing
                    note_str = f"{label} Non Réalisé"
                else:
                    note_str = ""

            # --- Merge Manual Correction Notes ---
            note_from_correction = False
            exp_note = explicit_day_note_dict.get((m_key_base, lg_date))
            if exp_note is not None:
                # If explicit DAY_NOTE was set by user, it owns the cell completely
                note_str = exp_note
                note_from_correction = True
            else:
                m_notes = manual_note_dict.get((m_key_base, lg_date), [])
                if m_notes:
                    # If we have manual notes from corrections (e.g. "Late due to traffic"), 
                    # we display them. If we also have a calculated note (e.g. "P/E Non Réalisé"), 
                    # we only show the manual one(s) as they are more specific.
                    combined = " | ".join(m_notes)
                    note_str = combined
                    note_from_correction = True

            # Collect all raw punches for tooltip details
            punches_raw = []
            for p in group:
                punches_raw.append({
                    "time": p["_dt"].strftime("%H:%M:%S"),
                    "machine": p.get("machine_name", "-"),
                    "type": p.get("punch_type", "-")
                })

            enriched_list.append({
                "date": lg_date, "raw_date": lg_date, "department": dept, "reg_number": reg, "employee": full_name, "role_title": role,
                "schedule": best_sched.name if best_sched else "-", 
                "sched_in": best_sched.start_time if best_sched else "-",
                "sched_out": best_sched.end_time if best_sched else "-",
                "break_in": best_sched.break_start if best_sched else "-",
                "break_out": best_sched.break_end if best_sched else "-",
                "check_in": ci, "check_out": co, "check_in_2": ci2, "check_out_2": co2,
                "attendance_time": attn_t, "work_time": work_t, "difference": diff_t, 
                "status": "",  "note": note_str,
                "machine": (group[0].get("machine_name") or "-"),
                "synced_at": group[0].get("synced_at").strftime("%Y-%m-%d %H:%M") if group[0].get("synced_at") else "-",
                "id": group[0].get("id"), "last_name": last_name, "emp_id": emp_id,
                "punches": punches_raw, # Pass raw detail for UI hover tooltips
                "is_auto": getattr(emp, 'is_auto_punch', False) if emp else False,
                "note_from_correction": note_from_correction
            })

        if original_start or original_end or dept_filter:
            d_f = dept_filter.lower() if dept_filter else None
            enriched_list = [r for r in enriched_list if (not original_start or r["date"] >= original_start) and (not original_end or r["date"] <= original_end) and (not d_f or d_f in (r["department"] or "").lower())]

        # Fetch Manual Statuses (issue_type="DAY_STATUS")

        # Fetch Manual Statuses (issue_type="DAY_STATUS")
        status_dict = {}
        try:
            status_corrections = (self.session.query(AttendanceCorrectionLog)
                .filter(AttendanceCorrectionLog.shift_date >= range_start.isoformat())
                .filter(AttendanceCorrectionLog.shift_date <= range_end.isoformat())
                .filter(AttendanceCorrectionLog.issue_type == "DAY_STATUS").all())
            for c in status_corrections:
                # Only allow MANUAL user overrides to override the display — AUTO recalc statuses
                # are informational only and should not suppress live punch-based status.
                if c.strategy == "AUTO": continue
                k = (c.employee_id if c.employee_id else str(c.reg_number), c.shift_date)
                status_dict[k] = c.imputed_val
        except: pass

        # Fetch Manual Notes (issue_type="DAY_NOTE")
        note_dict = {}
        try:
            note_corrections = (self.session.query(AttendanceCorrectionLog)
                .filter(AttendanceCorrectionLog.shift_date >= range_start.isoformat())
                .filter(AttendanceCorrectionLog.shift_date <= range_end.isoformat())
                .filter(AttendanceCorrectionLog.issue_type == "DAY_NOTE").all())
            for c in note_corrections:
                k = (c.employee_id if c.employee_id else str(c.reg_number), c.shift_date)
                note_dict[k] = c.imputed_val
        except: pass

        # Fetch DayStatus definitions for rules (is_worked_day, coefficient)
        from contragest.core.database import DayStatus, PublicHoliday
        day_status_defs = {s.code: s for s in self.session.query(DayStatus).all()}
        
        # Load all public holidays in range
        holiday_dates = set()
        try:
            holidays = self.session.query(PublicHoliday).filter(
                PublicHoliday.date >= range_start_str[:10],
                PublicHoliday.date <= range_end_str[:10]
            ).all()
            holiday_dates = {h.date for h in holidays}
        except Exception:
            pass

        # Helper to get status rules
        def get_status_rules(code):
            default = type('obj', (object,), {'is_worked_day': True, 'coefficient': 1.0, 'color_hex': '#ffffff'})
            return day_status_defs.get(code, default)

        # Index by logic date and registration
        record_map = {}
        for r in enriched_list:
            r_reg = str(r.get("reg_number") or "").strip()
            r_date = str(r.get("raw_date") or r.get("date") or "").strip()
            if not r_reg or not r_date: continue
            
            key = (r_reg, r_date[:10])
            if key not in record_map: record_map[key] = []
            record_map[key].append(r)
            
        final_list = []
        for emp in all_emps:
            reg = str(emp.registration_number or "").strip()
            if not reg: reg = str(emp.id).strip()
            # Double fallback check: ensure we handle leading-zero variants if common in DB
            search_regs = [reg, reg.lstrip('0')] if reg.startswith('0') else [reg]
            
            full_name = f"{emp.first_name} {emp.last_name}"
            dept = emp.dept_obj.name if emp.dept_obj else (emp.department or "-")
            role = emp.role_title or "-"
            last_name = emp.last_name
            
            for dt_iso, formatted_date in all_dates_formatted:
                # Skip dates strictly after exit_date
                if emp.exit_date and dt_iso > emp.exit_date.isoformat():
                    continue
                
                # Normalize search key
                search_reg = str(reg).strip()
                search_date = str(dt_iso)[:10]
                
                # Fetch manual status if it exists
                manual_status = status_dict.get((emp.id, search_date))
                if manual_status is None: manual_status = status_dict.get((search_reg, search_date))
                
                recs_found = None
                for s_reg in search_regs:
                    recs_found = record_map.get((s_reg, search_date))
                    if recs_found: break
                
                if recs_found:
                    for r_orig in recs_found:
                        # SECURITY GUARD: Final check against cross-row data bleeding
                        if str(r_orig.get("reg_number")).strip() not in search_regs:
                            continue
                            
                        # CRITICAL FIX: Shallow copy to prevent dictionary mutation leakage
                        existing_rec = r_orig.copy()

                        # Format the date inplace
                        existing_rec["date"] = formatted_date
                        existing_rec["raw_date"] = search_date
                        
                        # Determine Weekly Day Off
                        is_weekly_day_off = False
                        try:
                            dt_obj = datetime.strptime(search_date, "%Y-%m-%d")
                            emp_weekly_day_off = getattr(emp, 'weekly_day_off', None)
                            if emp_weekly_day_off and emp_weekly_day_off != "NONE":
                                weekday_map = {0: "MONDAY", 1: "TUESDAY", 2: "WEDNESDAY", 3: "THURSDAY", 4: "FRIDAY", 5: "SATURDAY", 6: "SUNDAY"}
                                current_day_str = weekday_map.get(dt_obj.weekday(), "").upper()
                                if current_day_str == emp_weekly_day_off.upper():
                                    is_weekly_day_off = True
                        except: pass

                        # --- FINAL STATUS & WORK-TIME RECONCILIATION ---
                        punch_keys = ["check_in", "check_out", "check_in_2", "check_out_2"]
                        has_punches = any(existing_rec.get(k) and str(existing_rec.get(k)).strip() not in ["-", "", "None"] for k in punch_keys)
                        is_public_holiday = search_date in holiday_dates
                        
                        if manual_status is not None:
                            day_status = manual_status
                        elif is_weekly_day_off:
                            day_status = "RHB" if has_punches else "RH"
                        elif is_public_holiday:
                            day_status = "JFB" if has_punches else "JF"
                        elif has_punches:
                            day_status = "P"
                        else:
                            is_past = search_date < date.today().isoformat()
                            has_sched = existing_rec.get("schedule") and existing_rec.get("schedule") != "-"
                            if is_past and has_sched:
                                day_status = "AB"
                            else:
                                day_status = ""
                        
                        existing_rec["status"] = day_status
                        rules = get_status_rules(day_status)
                        
                        if not has_punches:
                            # For most statuses without punches, we clear the hours.
                            # EXCEPT for manual presence statuses (P, JFB, RHB) where we want to show the full shift.
                            if day_status in ["P", "JFB", "RHB"]:
                                # Force Attendance Time to match Work Time (Expected hours)
                                existing_rec["attendance_time"] = existing_rec.get("work_time", "-")
                                existing_rec["difference"] = "-"
                                
                                # Auto-populate punch columns from schedule for visual consistency
                                if existing_rec["attendance_time"] != "-":
                                    existing_rec["check_in"] = existing_rec.get("sched_in", "-")
                                    existing_rec["check_out"] = existing_rec.get("sched_out", "-")
                                    # If it's a split shift (has break times), populate those too
                                    if existing_rec.get("break_in") != "-" and existing_rec.get("break_out") != "-":
                                        existing_rec["check_out"] = existing_rec.get("break_in", "-")
                                        existing_rec["check_in_2"] = existing_rec.get("break_out", "-")
                                        existing_rec["check_out_2"] = existing_rec.get("sched_out", "-")
                                    
                                    if not existing_rec.get("note"):
                                        existing_rec["note"] = "Manual Presence"
                            else:
                                # Standard behavior: no punches = no hours
                                existing_rec["work_time"] = "-"
                                existing_rec["difference"] = "-"
                        else:
                            # 1. Apply 'Is Worked Day' Rule
                            # If the status is NOT a worked day (e.g. RH), expected work is 0.
                            if not rules.is_worked_day:
                                existing_rec["work_time"] = "-"
                            
                            # 2. Apply Coefficient to Attendance Time
                            if rules.coefficient != 1.0:
                                try:
                                    h_str, m_str = existing_rec["attendance_time"].split(':')
                                    total_m = (int(h_str) * 60 + int(m_str)) * rules.coefficient
                                    nh, nm = divmod(int(total_m), 60)
                                    existing_rec["attendance_time"] = f"{nh:02d}:{nm:02d}"
                                    existing_rec["note"] = f"{existing_rec['note']} [Coeff x{rules.coefficient}]".strip()
                                except: pass

                            # 3. Recalculate Difference
                            try:
                                wt_raw = existing_rec["work_time"]
                                at_raw = existing_rec["attendance_time"]
                                
                                work_h, work_m = (wt_raw.split(':') if wt_raw != "-" else ("0", "0"))
                                att_h, att_m = (at_raw.split(':') if at_raw != "-" else ("0", "0"))
                                
                                w_mins = int(work_h)*60 + int(work_m)
                                a_mins = int(att_h)*60 + int(att_m)
                                
                                if a_mins > 0 or w_mins > 0:
                                    diff = a_mins - w_mins
                                    sign = "+" if diff >= 0 else "-"
                                    dh, dm = divmod(abs(diff), 60)
                                    existing_rec["difference"] = f"{sign}{dh:02d}:{dm:02d}"
                                    if existing_rec["difference"] in ["+00:00", "-00:00"]:
                                        existing_rec["difference"] = "-"
                                else:
                                    existing_rec["difference"] = "-"
                            except: pass

                        # 4. Clear times if status is not 'P', 'JFB', or 'RHB' AND it's not a worked day
                        # (Keep punches if they worked even on a day off/holiday)
                        if day_status and day_status not in ["P", "JFB", "RHB"] and not has_punches:
                            for k in ["check_in", "check_out", "check_in_2", "check_out_2", "attendance_time"]:
                                existing_rec[k] = "-"
                        
                        # Note: We rely on the combined note generated in Phase 1 for existing_rec.
                        # The Cartesian pad below will still use note_dict for missing days.
                        final_list.append(existing_rec)
                else:
                    # Cartesian pad missing record
                    if emp.is_archived:
                        if not emp.archived_at: 
                            continue # Never generate empty rows if they are archived without a date
                        if dt_iso > emp.archived_at.isoformat():
                            continue # Don't generate empty 'pad' rows for days after they were archived
                    
                    # Fetch manual note prioritizing emp.id
                    manual_note = note_dict.get((emp.id, dt_iso))
                    if manual_note is None: manual_note = note_dict.get((reg, dt_iso))
                    day_status = manual_status if manual_status is not None else ""
                    
                    # Compute best schedule for this missing day 
                    best_sched_candidates = get_candidates(emp.id, dt_iso, reg)
                    best_sched = best_sched_candidates[0] if best_sched_candidates else None
                    
                    is_public_holiday = dt_iso in holiday_dates

                    # ─── AUTO-ABSENT DETECTION (COMPLEX PROBLEM) ───
                    # If no punches, no manual status, but they have a schedule on a working day => Mark AB
                    is_weekly_day_off = False
                    try:
                        dt_obj = datetime.strptime(dt_iso, "%Y-%m-%d")
                        emp_weekly_day_off = getattr(emp, 'weekly_day_off', None)
                        if emp_weekly_day_off and emp_weekly_day_off != "NONE":
                            # Use numeric weekday to be locale-agnostic
                            weekday_map = {0: "MONDAY", 1: "TUESDAY", 2: "WEDNESDAY", 3: "THURSDAY", 4: "FRIDAY", 5: "SATURDAY", 6: "SUNDAY"}
                            current_day_str = weekday_map.get(dt_obj.weekday(), "").upper()
                            if current_day_str == emp_weekly_day_off.upper():
                                is_weekly_day_off = True
                    except: pass

                    if not day_status:
                        if is_weekly_day_off:
                            day_status = "RH"
                        elif is_public_holiday:
                            day_status = "JF"
                        elif best_sched:
                            try:
                                # 1. Check if the day is a 'Work Day' for this schedule
                                # days_of_week is CSV: "Mon,Tue,Wed,Thu,Fri"
                                short_day = dt_obj.strftime("%a") # "Mon", "Tue"...
                                work_days = [d.strip() for d in (best_sched.days_of_week or "Mon,Tue,Wed,Thu,Fri").split(',')]
                                
                                is_work_day = short_day in work_days
                                
                                # 2. Only mark AB for today or past dates
                                is_past_or_today = dt_iso <= date.today().isoformat()
                                
                                if is_work_day and is_past_or_today:
                                    day_status = "AB"
                            except: pass
                    # ───────────────────────────────────────────────
                    
                    is_auto = getattr(emp, "is_auto_punch", False) and not is_weekly_day_off
                    ci, co, ci2, co2, attn_t, work_t, diff_t, sched_name = "-", "-", "-", "-", "-", "-", "-", "-"
                    
                    # Standardize manual note to 'Non Réalisé'
                    note_from_correction = bool(manual_note)
                    note_str = (manual_note.strip().replace("Not Completed", "Non Réalisé") if manual_note else "")
                    machine_src = "-"
                    if best_sched:
                        sched_name = best_sched.name
                        if is_auto and best_sched.start_time:
                            # Auto populate ONLY if not explicitly deleted
                            if (emp.id, dt_iso, "CHECK_IN") not in deletions_set:
                                ci = best_sched.start_time[:5] + ":00" if len(best_sched.start_time) == 5 else best_sched.start_time[:8]
                            
                            if best_sched.break_start and best_sched.break_end:
                                if (emp.id, dt_iso, "CHECK_OUT") not in deletions_set:
                                    co = best_sched.break_start[:5] + ":00" if len(best_sched.break_start) == 5 else best_sched.break_start[:8]
                                if (emp.id, dt_iso, "CHECK_IN_2") not in deletions_set:
                                    ci2 = best_sched.break_end[:5] + ":00" if len(best_sched.break_end) == 5 else best_sched.break_end[:8]
                                if (emp.id, dt_iso, "CHECK_OUT_2") not in deletions_set:
                                    co2 = best_sched.end_time[:5] + ":00" if len(best_sched.end_time) == 5 else best_sched.end_time[:8]
                            else:
                                if (emp.id, dt_iso, "CHECK_OUT") not in deletions_set:
                                    co = best_sched.end_time[:5] + ":00" if len(best_sched.end_time) == 5 else best_sched.end_time[:8]
                            
                            day_status = manual_status if manual_status is not None else "P"
                            machine_src = "System"
                            
                            try:
                                c1 = datetime.fromisoformat(f"{dt_iso} {ci}"); o1 = datetime.fromisoformat(f"{dt_iso} {co}")
                                if o1 < c1: o1 += timedelta(days=1)
                                attn_mins = (o1 - c1).total_seconds() / 60
                                if ci2 != "-" and co2 != "-":
                                    c2 = datetime.fromisoformat(f"{dt_iso} {ci2}"); o2 = datetime.fromisoformat(f"{dt_iso} {co2}")
                                    if o2 < c2: o2 += timedelta(days=1)
                                    attn_mins += (o2 - c2).total_seconds() / 60
                                h, m = divmod(int(attn_mins), 60); attn_t = f"{h:02d}:{m:02d}"
                            except: pass

                        try:
                            # Always calculate expected work time if schedule exists
                            if getattr(best_sched, 'compte_minute', None) is not None:
                                total_expected = best_sched.compte_minute
                            elif getattr(best_sched, 'total_hours', None):
                                total_expected = int(best_sched.total_hours * 60)
                            else:
                                total_expected = 480
                            
                            work_t = f"{total_expected//60:02d}:{total_expected%60:02d}"
                        except: pass
                            
                    # --- FINAL STATUS & WORK-TIME RECONCILIATION for Pad Rows ---
                    has_pad_punches = any(p and str(p).strip() not in ["-", "", "None"] for p in [ci, co, ci2, co2])
                    if not has_pad_punches:
                        if day_status in ["P", "JFB", "RHB"] and best_sched:
                            # Force Attendance Time to match Work Time
                            attn_t = work_t
                            diff_t = "-"
                            
                            # Populate punch columns
                            ci = best_sched.start_time[:8] if best_sched.start_time else "-"
                            co = best_sched.end_time[:8] if best_sched.end_time else "-"
                            if best_sched.break_start and best_sched.break_end:
                                co = best_sched.break_start[:8]
                                ci2 = best_sched.break_end[:8]
                                co2 = best_sched.end_time[:8]
                            
                            if not note_str:
                                note_str = "Manual Presence"
                        else:
                            work_t = "-"
                            diff_t = "-"
                    else:
                        rules = get_status_rules(day_status)
                        if not rules.is_worked_day:
                            work_t = "-"
                        
                        # Apply Coefficient if they worked on this auto-row (rare but possible if is_auto)
                        if is_auto and attn_t != "-" and rules.coefficient != 1.0:
                            try:
                                h_str, m_str = attn_t.split(':')
                                total_m = (int(h_str) * 60 + int(m_str)) * rules.coefficient
                                nh, nm = divmod(int(total_m), 60)
                                attn_t = f"{nh:02d}:{nm:02d}"
                            except: pass

                        # Recalculate Difference
                        try:
                            wh_raw = work_t
                            ah_raw = attn_t
                            
                            work_h, work_m = (wh_raw.split(':') if wh_raw != "-" else ("0", "0"))
                            att_h, att_m = (ah_raw.split(':') if ah_raw != "-" else ("0", "0"))
                            
                            w_mins = int(work_h)*60 + int(work_m)
                            a_mins = int(att_h)*60 + int(att_m)
                            
                            if a_mins > 0 or w_mins > 0:
                                diff = a_mins - w_mins
                                sign = "+" if diff >= 0 else "-"
                                dh, dm = divmod(abs(diff), 60)
                                diff_t = f"{sign}{dh:02d}:{dm:02d}"
                                if diff_t in ["+00:00", "-00:00"]:
                                    diff_t = "-"
                            else:
                                diff_t = "-"
                        except: pass

                    row = {
                        "date": formatted_date, "raw_date": dt_iso, "department": dept, "reg_number": reg, "employee": full_name, "role_title": role,
                        "schedule": sched_name, "check_in": ci, "check_out": co, "check_in_2": ci2, "check_out_2": co2,
                        "attendance_time": attn_t, "work_time": work_t, "difference": diff_t, "note": note_str,
                        "machine": machine_src, "synced_at": "-", "id": -1, "last_name": last_name, "status": day_status,
                        "is_auto": getattr(emp, 'is_auto_punch', False) if emp else False,
                        "note_from_correction": note_from_correction
                    }
                    
                    # Clear times if status is not 'P', 'JFB', or 'RHB'
                    if day_status and day_status not in ["P", "JFB", "RHB"]:
                        for k in ["check_in", "check_out", "check_in_2", "check_out_2", "attendance_time"]:
                            row[k] = "-"
                            
                    final_list.append(row)
        
        # Add unmatched/orphan records to final_list with formatted date
        for r in enriched_list:
            if r.get("emp_id") is None:
                # Format the date to "Day. DD-MM-YYYY"
                try:
                    dt_obj = datetime.strptime(r["date"], "%Y-%m-%d")
                    weekday_map = {0: "Lun.", 1: "Mar.", 2: "Mer.", 3: "Jeu.", 4: "Ven.", 5: "Sam.", 6: "Dim."}
                    prefix = weekday_map.get(dt_obj.weekday(), "")
                    r["date"] = f"{prefix} {dt_obj.strftime('%d-%m-%Y')}"
                except:
                    pass
                final_list.append(r)
        
        # Filter notes to only display predefined notes entered in the "NOTE MANAGEMENT" pane.
        # Notes set via a manual correction (DAY_NOTE / MANUAL_NOTE) are exempt: the user typed
        # them on purpose and free-text should never be silently stripped.
        try:
            predefined_notes = self.get_predefined_notes()
            predefined_names = {n["name"].strip().lower() for n in predefined_notes if n.get("name")}
            for x in final_list:
                note_val = x.get("note")
                if note_val and x.get("note_from_correction"):
                    continue
                if note_val and note_val.strip().lower() not in predefined_names:
                    x["note"] = ""
        except Exception as note_err:
            logger.error(f"Error filtering predefined notes: {note_err}")
        
        # 8. Sort and return
        def sort_key(x):
            try:
                # Pad registration number with zeros for numeric-like string sorting
                reg_sort = str(x.get("reg_number", "")).zfill(10)
            except:
                reg_sort = str(x.get("reg_number", ""))
            
            return (
                x.get("raw_date", ""), 
                x.get("department", "").lower(), 
                reg_sort
            )

        final_list.sort(key=sort_key)
        return final_list[:limit] if limit else final_list

    def get_department_summary(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Calculates a summary of attendance statuses grouped by department."""
        data = self.get_attendance_records_enriched(start_date=start_date, end_date=end_date)
        if not data: return []
        
        # Identify all active status codes in the current dataset
        active_statuses = set()
        for r in data:
            s = str(r.get("status", "")).strip()
            if s: active_statuses.add(s)
            
        # Ensure 'P' is included as a base status
        status_cols = sorted(list(active_statuses))
        if "P" not in status_cols:
            status_cols.insert(0, "P")
        
        recap = {}
        for r in data:
            dept = r.get("department", "Unknown") or "Unknown"
            status = str(r.get("status", "")).strip()
            
            if dept not in recap:
                recap[dept] = {c: 0 for c in status_cols}
                recap[dept]["Total"] = 0
            
            if status in recap[dept]:
                recap[dept][status] += 1
            elif not status and r.get("check_in") != "-": # Fallback for 'P' if status is empty but punches exist
                if "P" in recap[dept]: recap[dept]["P"] += 1
            
            recap[dept]["Total"] += 1
        
        # Convert to list of dicts for Tableview
        final_recap = []
        for dept, counts in sorted(recap.items()):
            row = {"Departement": dept}
            row.update(counts)
            final_recap.append(row)
            
        return final_recap

    def get_filter_dropdown_values(self, department_name=None) -> Dict[str, List[str]]:
        """Fetches sorted, unique values for UI combobox filters."""
        from contragest.core.database import Employee, Department
        try:
            emp_q = self.session.query(Employee.first_name, Employee.last_name, Employee.registration_number).filter(Employee.is_archived == False)
            if department_name:
                emp_q = emp_q.join(Employee.dept_obj).filter(Department.name == department_name)
            
            emp_list = []
            for f, l, r in emp_q.all():
                name = f"{f or ''} {l or ''}".strip()
                if r:
                    emp_list.append(f"{name} ({r})")
                elif name:
                    emp_list.append(name)
                    
            emp_list = sorted(list(set(emp_list)))
            dept_list = sorted(list(set(d[0] for d in self.session.query(Department.name).all() if d[0])))
            return {"employees": emp_list, "reg_numbers": [], "departments": dept_list}
        except Exception as e:
            logger.error(f"Error: {e}"); return {"employees": [], "reg_numbers": [], "departments": []}

    def save_status_correction(self, reg_number: str, shift_date: str, status_code: str, admin_name: str = "SYSTEM"):
        """Saves or updates a day status correction."""
        from contragest.core.database import AttendanceCorrectionLog, Employee
        
        reg_number = str(reg_number).strip()
        norm_reg = reg_number.lstrip('0') or reg_number
        shift_date = str(shift_date)[:10]

        emp = self.session.query(Employee).filter(
            (Employee.registration_number == reg_number) | 
            (Employee.registration_number == norm_reg)
        ).first()
        
        if not emp:
            try: emp = self.session.query(Employee).filter_by(id=int(reg_number)).first()
            except: pass
            
        if not emp:
            return False, "Employee not found"

        code = str(status_code or "").strip().upper()
        if code in ("", "-"):
            return False, "Invalid status code."

        # Guard: Reject corrections for dates strictly after exit_date
        # (Allow "SOR" — it's the termination status itself)
        if emp.exit_date and code != "SOR":
            try:
                from datetime import date as _date
                shift_date_obj = _date.fromisoformat(shift_date)
                if shift_date_obj > emp.exit_date:
                    return False, f"Cannot set status for dates after employee exit date ({emp.exit_date})"
            except Exception:
                pass

        try:
            existing = self.session.query(AttendanceCorrectionLog).filter(
                ((AttendanceCorrectionLog.reg_number == reg_number) | (AttendanceCorrectionLog.employee_id == emp.id)),
                AttendanceCorrectionLog.shift_date == shift_date,
                AttendanceCorrectionLog.issue_type == "DAY_STATUS"
            ).first()
            
            if existing:
                existing.imputed_val = code
                existing.strategy = "MANUAL" # CRITICAL: Ensure it's no longer skipped as AUTO
                existing.corrected_by = admin_name
                existing.corrected_at = datetime.now().isoformat()
                existing.reg_number = reg_number 
                existing.notes = f"Status modified to {code}"
            else:
                log = AttendanceCorrectionLog(
                    employee_id=emp.id,
                    reg_number=reg_number,
                    shift_date=shift_date,
                    issue_type="DAY_STATUS",
                    original_val="",
                    imputed_val=code,
                    strategy="MANUAL",
                    corrected_by=admin_name,
                    corrected_at=datetime.now().isoformat(),
                    notes=f"Status set to {code}"
                )
                self.session.add(log)
            
            self.session.commit()
            logger.info(f"Status correction saved: {reg_number} on {shift_date} -> {code}")
            return True, "Status updated"
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error saving status correction: {e}")
            return False, str(e)

    def save_day_program(self, reg_number: str, shift_date: str,
                         in1: str = "-", out1: str = "-", in2: str = "-", out2: str = "-",
                         admin_name: str = "SYSTEM"):
        """
        Saves or updates an explicit day-level punch programming override
        (issue_type='DAY_PROGRAM').

        The enriched view normally infers IN1/OUT1/IN2/OUT2 from raw punches.
        This override lets HR pin the exact slots for a logical day (e.g. a
        night-shift pairing the chronological pairing cannot express).  Raw
        machine records are never modified — the override lives in the audit
        log, exactly like DAY_STATUS / DAY_SCHEDULE / DAY_NOTE.

        imputed_val is stored as "IN1|OUT1|IN2|OUT2" ("-" for empty slots).
        """
        from contragest.core.database import AttendanceCorrectionLog, Employee
        reg_number = str(reg_number).strip()
        emp = self.session.query(Employee).filter_by(registration_number=reg_number).first()
        if not emp:
            try: emp = self.session.query(Employee).filter_by(id=int(reg_number)).first()
            except ValueError: pass
        if not emp:
            return False, "Employee not found"

        slots = [str(in1 or "-").strip() or "-",
                 str(out1 or "-").strip() or "-",
                 str(in2 or "-").strip() or "-",
                 str(out2 or "-").strip() or "-"]
        payload = "|".join(slots)

        existing = self.session.query(AttendanceCorrectionLog).filter(
            ((AttendanceCorrectionLog.reg_number == reg_number) | (AttendanceCorrectionLog.employee_id == emp.id)),
            AttendanceCorrectionLog.shift_date == shift_date,
            AttendanceCorrectionLog.issue_type == "DAY_PROGRAM"
        ).first()

        if existing:
            existing.imputed_val = payload
            existing.strategy = "MANUAL"
            existing.corrected_by = admin_name
            existing.corrected_at = datetime.now().isoformat()
            existing.reg_number = reg_number
            existing.notes = f"Programmation IN1={slots[0]} OUT1={slots[1]} IN2={slots[2]} OUT2={slots[3]}"
        else:
            log = AttendanceCorrectionLog(
                employee_id=emp.id,
                reg_number=reg_number,
                shift_date=shift_date,
                issue_type="DAY_PROGRAM",
                original_val="",
                imputed_val=payload,
                strategy="MANUAL",
                corrected_by=admin_name,
                corrected_at=datetime.now().isoformat(),
                notes=f"Programmation IN1={slots[0]} OUT1={slots[1]} IN2={slots[2]} OUT2={slots[3]}"
            )
            self.session.add(log)

        try:
            self.session.commit()
            return True, "Day programming updated"
        except Exception as e:
            self.session.rollback()
            return False, str(e)

    def _get_day_schedules(self, emp_id: int, date_str: str, reg: str) -> list:
        """Return candidate WorkSchedule objects for an employee on a date.
        Mirrors the get_candidates closure used by the enriched grid view:
        DAY_SCHEDULE override first, then rotating shift, then all fixed
        assignments sharing the most recent effective_date plus the previous
        generation. Returns [] when nothing matches."""
        cands: list = []
        try:
            dt_obj = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        except Exception:
            return cands

        # 0. Daily schedule correction (override)
        from contragest.core.database import AttendanceCorrectionLog, WorkSchedule
        corr = self.session.query(AttendanceCorrectionLog).filter(
            ((AttendanceCorrectionLog.employee_id == emp_id) |
             (AttendanceCorrectionLog.reg_number == str(reg))),
            AttendanceCorrectionLog.shift_date == date_str[:10],
            AttendanceCorrectionLog.issue_type == "DAY_SCHEDULE"
        ).first()
        if corr and corr.imputed_val:
            sched = self.session.query(WorkSchedule).filter_by(name=corr.imputed_val).first()
            if sched:
                cands.append(sched)
            return cands

        # 1. Rotating schedule
        try:
            sched = self.resolve_rotation_schedule(emp_id, dt_obj)
        except Exception:
            sched = None
        if sched:
            cands.append(sched)
            return cands

        # 2. Fixed schedules: all sharing the most recent effective_date
        #    plus the previous generation (same rule as the grid).
        try:
            best_eff_assignment = (
                self.session.query(EmployeeSchedule)
                .filter(EmployeeSchedule.employee_id == emp_id)
                .filter(EmployeeSchedule.effective_date <= dt_obj)
                .order_by(EmployeeSchedule.effective_date.desc(), EmployeeSchedule.id.desc())
                .first()
            )
            if best_eff_assignment:
                same_date_assignments = (
                    self.session.query(EmployeeSchedule)
                    .filter(EmployeeSchedule.employee_id == emp_id)
                    .filter(EmployeeSchedule.effective_date == best_eff_assignment.effective_date)
                    .order_by(EmployeeSchedule.id.asc())
                    .all()
                )
                for a in same_date_assignments:
                    if a.schedule and a.schedule not in cands:
                        cands.append(a.schedule)

                prev_eff = (
                    self.session.query(EmployeeSchedule.effective_date)
                    .filter(EmployeeSchedule.employee_id == emp_id)
                    .filter(EmployeeSchedule.effective_date < best_eff_assignment.effective_date)
                    .order_by(EmployeeSchedule.effective_date.desc())
                    .limit(1)
                    .first()
                )
                if prev_eff:
                    prev_assignments = (
                        self.session.query(EmployeeSchedule)
                        .filter(EmployeeSchedule.employee_id == emp_id)
                        .filter(EmployeeSchedule.effective_date == prev_eff[0])
                        .order_by(EmployeeSchedule.id.asc())
                        .all()
                    )
                    for a in prev_assignments:
                        if a.schedule and a.schedule not in cands:
                            cands.append(a.schedule)
        except Exception as _e:
            logger.warning(f"_get_day_schedules: query failed for emp_id={emp_id} date={date_str}: {_e}")
        return cands

    def _pick_best_schedule(self, cands: list, punch_datetimes: list):
        """Pick the schedule whose start/end times best match the day's punch
        times. Mirrors the scoring block of the enriched grid view so manual
        edits resolve the same schedule the grid uses for a given day."""
        if len(cands) <= 1:
            return cands[0] if cands else None

        def _tdiff_min(t1, t2):
            m1 = t1.hour * 60 + t1.minute
            m2 = t2.hour * 60 + t2.minute
            d = abs(m1 - m2)
            return min(d, 1440 - d)

        sorted_punch_times = sorted(dt.time() for dt in punch_datetimes)
        best_sched = cands[0]
        best_cand_score = float('inf')
        for cand in cands:
            cand_score = 0
            try:
                s_t = datetime.strptime(cand.start_time.strip(), "%H:%M").time() if cand.start_time else None
                e_t = datetime.strptime(cand.end_time.strip(), "%H:%M").time() if cand.end_time else None
                is_overnight = bool(s_t and e_t and e_t <= s_t)
                if is_overnight:
                    if len(sorted_punch_times) >= 2:
                        cand_score += _tdiff_min(sorted_punch_times[-1], s_t)
                        cand_score += _tdiff_min(sorted_punch_times[0], e_t)
                    elif sorted_punch_times:
                        cand_score += min(
                            _tdiff_min(sorted_punch_times[0], s_t),
                            _tdiff_min(sorted_punch_times[0], e_t),
                        )
                else:
                    if s_t and sorted_punch_times:
                        cand_score += _tdiff_min(sorted_punch_times[0], s_t)
                    if e_t and len(sorted_punch_times) >= 2:
                        cand_score += _tdiff_min(sorted_punch_times[-1], e_t)
            except Exception:
                pass
            if cand_score < best_cand_score:
                best_cand_score = cand_score
                best_sched = cand
        return best_sched

    def _resolve_day_slot_records(
        self,
        employee_id: int,
        day_records: list,
        schedule,
        logic_date_iso: str,
        reg: str = "",
    ) -> list:
        """
        Assigns each day record the SAME check_in/check_out type the enriched
        grid view (get_attendance_records_enriched) uses, then returns it as
        [{"rec": rec, "dt": datetime, "type": str, "slot": str|None}, ...]
        in chronological order.

        Mirrors the enriched pipeline so slot numbering matches the grid:
          1. preserve types explicitly set via add_manual_punch (MANUAL_PUNCH logs)
          2. if the day's machine records contain BOTH check_in and check_out
             (reliable machine) keep them verbatim
          3. otherwise guess with guess_punch_type (schedule-aware)
          4. rectify 4+ even groups / 3-punch rule only when machine types
             were NOT reliable
          5. pair punches into work sessions (LIFO: each check_out closes the
             most recent unpaired check_in) and tag each record with the grid
             slot it lands in: in1/out1/in2/out2 (or None).

        Slot 1 = first session, slot 2 = second session — exactly how the
        grid derives IN1/OUT1/IN2/OUT2.
        """
        from contragest.core.database import AttendanceCorrectionLog

        # Resolve the schedule the SAME way the enriched grid does: gather all
        # candidate schedules for the day (override → rotation → fixed) and pick
        # the one whose start/end times best match the day's punch times. The
        # caller-supplied `schedule` is only a fallback when no candidate
        # resolves (avoids the 06->18 vs 18->06 mismatch that breaks night
        # shifts if we blindly trust get_schedule_for_date).
        try:
            _cands = self._get_day_schedules(employee_id, logic_date_iso, reg)
            if _cands:
                _punch_dts = [
                    datetime.strptime(
                        rec.punch_time[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S"
                    )
                    for rec in day_records
                ]
                schedule = self._pick_best_schedule(_cands, _punch_dts) or schedule
        except Exception:
            pass

        # Types explicitly set by a previous manual edit are trusted verbatim.
        manual_punch_set = set()
        try:
            logs = (
                self.session.query(AttendanceCorrectionLog)
                .filter(AttendanceCorrectionLog.employee_id == employee_id)
                .filter(AttendanceCorrectionLog.shift_date == logic_date_iso[:10])
                .filter(AttendanceCorrectionLog.issue_type == "MANUAL_PUNCH")
                .all()
            )
            for log in logs:
                manual_punch_set.add((log.employee_id, log.shift_date, log.imputed_val))
        except Exception:
            manual_punch_set = set()

        # Are the machine-provided types reliable (both IN and OUT present)?
        # Only MACHINE punches count here (machine_id not None): a manual punch
        # typed check_out must NOT make all-check_in machine data "reliable" —
        # otherwise the rest of the day's machine punches keep their erroneous
        # ZK default (all check_in) and the grid mis-pairs them.
        raw_type_set = {
            rec.punch_type
            for rec in day_records
            if rec.punch_type in ("check_in", "check_out")
            and rec.machine_id is not None
        }
        machine_types_reliable = len(raw_type_set) > 1

        typed = []
        for rec in day_records:
            dt_str = rec.punch_time[:19].replace("T", " ")
            inferred = rec.punch_type or "check_in"
            is_manual = (rec.employee_id, logic_date_iso[:10], dt_str) in manual_punch_set
            if not is_manual and not machine_types_reliable:
                guessed, _ = self.guess_punch_type(dt_str, schedule)
                inferred = guessed
            typed.append({
                "rec": rec,
                "dt": datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S"),
                "type": inferred,
                "slot": None,
            })

        # Rectify: 4+ even groups with consecutive same-type punches become
        # strictly alternating IN/OUT — ONLY when machine types were unreliable
        # (same rule as the enriched view).
        if not machine_types_reliable and len(typed) >= 4 and len(typed) % 2 == 0:
            has_consecutive_same = any(
                typed[i]["type"] == typed[i + 1]["type"]
                for i in range(len(typed) - 1)
            )
            if has_consecutive_same:
                for i, t in enumerate(typed):
                    t["type"] = "check_in" if i % 2 == 0 else "check_out"

        # 3-punch rule: first record is the morning check-in, last is the
        # end-of-day check-out; the lunch-break record lands in IN2.
        # Only applied when machine types were unreliable AND only for punches
        # NOT preserved by manual_punch_set — a manual type (e.g. a check_out
        # added by drag-and-drop at the same time as a machine check_in) must
        # keep its explicit value, otherwise the transfer does not stick.
        if not machine_types_reliable and len(typed) == 3:
            def _is_manual(t):
                return (t["rec"].employee_id, logic_date_iso[:10],
                        t["dt"].strftime("%Y-%m-%d %H:%M:%S")) in manual_punch_set
            if any(not _is_manual(t) for t in typed):
                if not _is_manual(typed[0]):
                    typed[0]["type"] = "check_in"
                if not _is_manual(typed[2]):
                    typed[2]["type"] = "check_out"
                if not _is_manual(typed[1]) and typed[1]["type"] == typed[2]["type"]:
                    typed[1]["type"] = "check_in"

        # ── Session pairing (same as enriched grid) ──────────────────────
        # Each check_out closes the most recent unpaired check_in (LIFO).
        # Sessions are mapped chronologically onto in1/out1 and in2/out2.
        # CRITICAL: check_ins on next calendar day (h < 4, date > lg_date) are
        # early-morning arrivals for the CURRENT logic day — sorted first.
        _lg_date_obj = datetime.strptime(logic_date_iso[:10], "%Y-%m-%d").date()
        def _pair_sort_key(t):
            dt = t["dt"]
            if (t["type"] == "check_in"
                    and dt.hour < 4
                    and dt.date() > _lg_date_obj):
                from datetime import time as _time
                return datetime.combine(_lg_date_obj, _time(dt.hour, dt.minute, dt.second))
            return dt
        sorted_typed = sorted(typed, key=_pair_sort_key)
        sessions = []      # {"in_idx": int|None, "out_idx": int|None}
        pending_ins = []   # indices of unpaired check_ins
        orphan_outs = []   # indices of check_outs with no preceding check_in
        for i, t in enumerate(sorted_typed):
            if t["type"] == "check_in":
                pending_ins.append(i)
            elif pending_ins:
                sessions.append({"in_idx": pending_ins.pop(), "out_idx": i})
            else:
                orphan_outs.append(i)
        for i in pending_ins:
            sessions.append({"in_idx": i, "out_idx": None})
        for i in orphan_outs:
            sessions.append({"in_idx": None, "out_idx": i})

        def _session_sort_key(s):
            dt = (sorted_typed[s["in_idx"]]["dt"] if s["in_idx"] is not None
                  else sorted_typed[s["out_idx"]]["dt"])
            if dt is None:
                return datetime(2000, 1, 1)
            if (s["in_idx"] is not None
                    and dt.hour < 4
                    and dt.date() > _lg_date_obj):
                from datetime import time as _time
                return datetime.combine(_lg_date_obj, _time(dt.hour, dt.minute, dt.second))
            return dt
        sessions.sort(key=_session_sort_key)

        slot_names = [("in1", "out1"), ("in2", "out2")]
        for s, (in_name, out_name) in zip(sessions, slot_names):
            if s["in_idx"] is not None:
                sorted_typed[s["in_idx"]]["slot"] = in_name
            if s["out_idx"] is not None:
                sorted_typed[s["out_idx"]]["slot"] = out_name

        return typed

    def _get_day_program(self, reg_number: str, shift_date: str) -> Optional[dict]:
        """Returns the DAY_PROGRAM override dict {in1,out1,in2,out2} for the
        day, or None when no override exists.  Values are 'HH:MM:SS' or '-'.
        The enriched grid displays these values verbatim (they override the
        raw-punch pairing), so any edit/removal on such a day must update the
        program itself, not just the raw records."""
        from contragest.core.database import AttendanceCorrectionLog, Employee
        reg_number = str(reg_number).strip()
        emp = self.session.query(Employee).filter_by(registration_number=reg_number).first()
        if not emp:
            try:
                emp = self.session.query(Employee).filter_by(id=int(reg_number)).first()
            except ValueError:
                return None
        if not emp:
            return None
        row = self.session.query(AttendanceCorrectionLog).filter(
            ((AttendanceCorrectionLog.reg_number == reg_number) |
             (AttendanceCorrectionLog.employee_id == emp.id)),
            AttendanceCorrectionLog.shift_date == shift_date[:10],
            AttendanceCorrectionLog.issue_type == "DAY_PROGRAM",
        ).first()
        if not row:
            return None
        parts = [p.strip() or "-" for p in (row.imputed_val or "").split("|")]
        return {
            "in1":  parts[0] if len(parts) > 0 else "-",
            "out1": parts[1] if len(parts) > 1 else "-",
            "in2":  parts[2] if len(parts) > 2 else "-",
            "out2": parts[3] if len(parts) > 3 else "-",
        }

    def _day_slots_from_enriched(self, reg_number: str, shift_date: str) -> dict:
        """Fallback read of the current IN1/OUT1/IN2/OUT2 from the enriched view
        (raw-punch pairing) when no DAY_PROGRAM override exists yet."""
        enriched_key = {
            "in1": "check_in", "out1": "check_out",
            "in2": "check_in_2", "out2": "check_out_2",
        }
        slots = {"in1": "-", "out1": "-", "in2": "-", "out2": "-"}
        try:
            import re
            records = self.get_attendance_records_enriched(
                reg_filter=reg_number, start_date=shift_date, end_date=shift_date)
            for r in records:
                date_disp = str(r.get("date") or "")
                m = re.search(r"(\d{2})-(\d{2})-(\d{4})", date_disp)
                iso = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else date_disp
                if iso != shift_date:
                    continue
                for key, rkey in enriched_key.items():
                    v = str(r.get(rkey) or "-")
                    if v and v not in ("-", "None"):
                        slots[key] = v
                break
        except Exception:
            pass
        return slots

    def set_punch_slot(self, registration_number: str, punch_date: str,
                       col_name: str, time_val: str,
                       admin_name: str = "SYSTEM", reason: str = "") -> tuple:
        """Sets or clears one grid slot reliably, even on night-shift days.

        The GUI edit dialog historically calls ``add_manual_punch`` which
        writes a raw AttendanceRecord.  On night-shift schedules (e.g.
        "18 -> 02") the enriched grid re-pairs raw punches chronologically, so
        an edited/added record gets re-paired into a different visual slot and
        the edit *never sticks* on screen.  This method instead pins the exact
        IN1/OUT1/IN2/OUT2 via a DAY_PROGRAM override (``save_day_program``)
        that the enriched view displays verbatim — the same deterministic
        mechanism used by ``execution/move_punch_cli.py``.

        time_val: "HH:MM", "HH:MM:SS" or "-" (clear the slot).
        Returns (ok, msg).
        """
        slot_key = {"IN 1": "in1", "OUT 1": "out1",
                    "IN 2": "in2", "OUT 2": "out2"}.get(col_name)
        if not slot_key:
            return False, f"Unknown grid column {col_name!r}"
        new_val = str(time_val).strip() or "-"
        if new_val != "-":
            if not re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", new_val):
                return False, f"Invalid time {time_val!r}; use HH:MM or HH:MM:SS"
            # Normalise HH:MM -> HH:MM:00 so the override matches the grid's
            # "HH:MM:SS" display format consistently.
            parts = new_val.split(":")
            new_val = f"{int(parts[0]):02d}:{parts[1]}" + (f":{parts[2]}" if len(parts) > 2 else ":00")
        slots = self._get_day_program(registration_number, punch_date)
        if not slots:
            slots = self._day_slots_from_enriched(registration_number, punch_date)
        slots[slot_key] = new_val
        ok, msg = self.save_day_program(
            registration_number, punch_date,
            in1=slots["in1"], out1=slots["out1"],
            in2=slots["in2"], out2=slots["out2"],
            admin_name=admin_name,
        )
        if ok and reason:
            self._append_day_program_reason(registration_number, punch_date, reason)
        return ok, msg

    def move_punch_slot(self, reg_number: str, src_date: str, src_col: str,
                        dst_date: str, dst_col: str,
                        admin_name: str = "SYSTEM", reason: str = "") -> tuple:
        """Move a punch between grid slots via DAY_PROGRAM overrides (reliable).

        Mirrors ``execution/move_punch_cli.py``: on night-shift days the
        enriched grid re-pairs raw punches, so a raw-record move
        (add_manual_punch + delete_manual_punch) executes but never sticks
        visually.  This pins the slots verbatim via ``save_day_program`` so
        the move always shows up and survives reloads.

        src_date/dst_date: "YYYY-MM-DD".  Returns (ok, msg).
        """
        col_key = {"IN 1": "in1", "OUT 1": "out1",
                   "IN 2": "in2", "OUT 2": "out2"}
        src_key = col_key.get(src_col)
        dst_key = col_key.get(dst_col)
        if not src_key or not dst_key:
            return False, f"Unknown grid column {src_col!r}/{dst_col!r}"
        same_day = (src_date == dst_date)

        src_slots = self._get_day_program(reg_number, src_date)
        if not src_slots:
            src_slots = self._day_slots_from_enriched(reg_number, src_date)
        src_val = str(src_slots.get(src_key, "-")).strip()
        if src_val in ("-", "", "None"):
            return False, f"No punch in {src_col} for REG {reg_number} on {src_date}."

        dst_slots = self._get_day_program(reg_number, dst_date)
        if not dst_slots:
            dst_slots = self._day_slots_from_enriched(reg_number, dst_date)
        if same_day and str(dst_slots.get(dst_key, "-")).strip() == src_val:
            return True, f"{src_col} already holds {src_val} on {src_date}."

        # IMPORTANT: for a same-day move, src_slots and dst_slots are two
        # independent reads — mutating both in place and writing one loses the
        # other.  Apply both changes to ONE shared dict.
        if same_day:
            slots = src_slots
            slots[src_key] = "-"
            slots[dst_key] = src_val
            ok, msg = self.save_day_program(
                reg_number, src_date,
                in1=slots["in1"], out1=slots["out1"],
                in2=slots["in2"], out2=slots["out2"],
                admin_name=admin_name,
            )
            if ok and reason:
                self._append_day_program_reason(reg_number, src_date,
                                                f"Move {src_col}->{dst_col}: {reason}")
            return ok, (f"Moved {src_col} {src_val} -> {dst_col} on {src_date}." if ok else msg)

        dst_slots[dst_key] = src_val
        src_slots[src_key] = "-"
        ok1, msg1 = self.save_day_program(
            reg_number, src_date,
            in1=src_slots["in1"], out1=src_slots["out1"],
            in2=src_slots["in2"], out2=src_slots["out2"],
            admin_name=admin_name,
        )
        ok2, msg2 = self.save_day_program(
            reg_number, dst_date,
            in1=dst_slots["in1"], out1=dst_slots["out1"],
            in2=dst_slots["in2"], out2=dst_slots["out2"],
            admin_name=admin_name,
        )
        if ok1 and ok2 and reason:
            self._append_day_program_reason(
                reg_number, dst_date, f"Move {src_col}->{dst_col}: {reason}")
        return (ok1 and ok2), (msg1 if not ok1 else msg2)

    def _append_day_program_reason(self, reg_number: str, shift_date: str, reason: str) -> None:
        """Attaches the operator's free-text reason to the DAY_PROGRAM audit log."""
        from contragest.core.database import AttendanceCorrectionLog, Employee
        reg_number = str(reg_number).strip()
        emp = self.session.query(Employee).filter_by(registration_number=reg_number).first()
        if not emp:
            return
        row = self.session.query(AttendanceCorrectionLog).filter(
            ((AttendanceCorrectionLog.reg_number == reg_number) |
             (AttendanceCorrectionLog.employee_id == emp.id)),
            AttendanceCorrectionLog.shift_date == str(shift_date)[:10],
            AttendanceCorrectionLog.issue_type == "DAY_PROGRAM",
        ).first()
        if row is not None:
            row.notes = f"{reason} (via pointage edit)"
            self.session.commit()

    @staticmethod
    def _slot_key(punch_type: str, slot_index: int) -> str:
        """Maps (punch_type, slot_index) to a DAY_PROGRAM slot key."""
        base = {"check_in": "in", "check_out": "out"}.get(punch_type)
        return f"{base}{slot_index}"

    @staticmethod
    def _find_raw_at(day_records: list, hhmmss: str):
        """Return the first day record whose time-of-day equals hhmmss
        ('HH:MM' or 'HH:MM:SS'), or None."""
        if not hhmmss or hhmmss == "-":
            return None
        for rec in day_records:
            t = rec.punch_time[-8:]
            if t == hhmmss or (len(hhmmss) == 5 and t[:5] == hhmmss):
                return rec
        return None

    def _night_shift_cutoff_for_prev_day(self, emp_id: int, target_date) -> int:
        """Return the cutoff hour for a punch that might belong to a night shift
        that STARTED on the previous day.  Returns 4 (DEFAULT_CUTOFF) if not a night shift.

        Replicates the enriched view's get_candidates[0] resolution to stay
        consistent with the grid display.  For employees with multiple
        assignments on the same effective date (e.g. night+day alternating),
        the first by id.asc() is used — which is typically the night shift
        for guards on 18->06 / 06->18 dual schedules.
        """
        from contragest.core.database import EmployeeSchedule
        DEFAULT_CUTOFF = 4
        try:
            if isinstance(target_date, str):
                dt = datetime.strptime(target_date[:10], "%Y-%m-%d").date()
            else:
                dt = target_date.date() if hasattr(target_date, 'date') else target_date
            best = (
                self.session.query(EmployeeSchedule)
                .filter(EmployeeSchedule.employee_id == emp_id)
                .filter(EmployeeSchedule.effective_date <= dt)
                .order_by(EmployeeSchedule.effective_date.desc(), EmployeeSchedule.id.desc())
                .first()
            )
            if not best:
                return DEFAULT_CUTOFF
            same = (
                self.session.query(EmployeeSchedule)
                .filter(EmployeeSchedule.employee_id == emp_id)
                .filter(EmployeeSchedule.effective_date == best.effective_date)
                .order_by(EmployeeSchedule.id.asc())
                .all()
            )
            if same:
                sched = same[0].schedule
                if sched and sched.start_time and sched.end_time:
                    sh = int(sched.start_time.split(":")[0])
                    eh = int(sched.end_time.split(":")[0])
                    if sh > eh:  # night shift crosses midnight
                        return min(eh + 2, 13)  # e.g. 18->06: cutoff = 08
        except Exception:
            pass
        return DEFAULT_CUTOFF

    def _punch_logic_date(self, emp_id, punch_dt, prev_date_iso=None):
        """Determine the logic date for a punch, matching the enriched view.

        Schedule-aware attribution (same as _get_logic_date in
        get_attendance_records_enriched):
          1. H < 4 (midnight hours): belongs to the CURRENT day if today's
             schedule starts at or before H (early-morning shift like 02->10),
             otherwise belongs to D-1 (midnight checkout of a night shift).
          2. 4 ≤ H < 12: check previous day's night-shift cutoff.
          3. Otherwise: stays on the calendar day.
        """
        DEFAULT_CUTOFF = 4
        cal_date = punch_dt.date()
        h = punch_dt.hour
        if h < DEFAULT_CUTOFF:
            # Early-morning shift starting at/before this hour → today's start.
            # Uses the SAME candidate resolution as the enriched grid
            # (_get_day_schedules includes DAY_SCHEDULE override + rotation +
            # fixed schedules), so an override like "04 -> 12" for today makes
            # a 02:00 punch fall back to D-1 instead of being swallowed.
            try:
                for sched in self._get_day_schedules(emp_id, cal_date.isoformat(), ""):
                    if sched and sched.start_time:
                        sh = int(sched.start_time.split(":")[0])
                        if sh <= h:
                            return cal_date
            except Exception:
                pass
            return cal_date - timedelta(days=1)
        if h < 12:
            if prev_date_iso is None:
                prev_date_iso = (cal_date - timedelta(days=1)).isoformat()
            cutoff = self._night_shift_cutoff_for_prev_day(emp_id, prev_date_iso)
            if h < cutoff:
                return cal_date - timedelta(days=1)
        return cal_date

    def add_manual_punch(
        self,
        registration_number: str,
        punch_date: str,
        punch_time: str,
        punch_type: str,
        admin_name: str = "SYSTEM",
        reason: str = "",
        slot_index: int = 1,
    ) -> tuple:
        """
        Adds or updates a specific punch for an employee on a given date.

        If a punch of the same type already exists in the requested slot, its
        time is updated in-place.  Otherwise a new AttendanceRecord is created.
        The action is always logged to AttendanceCorrectionLog for auditability.

        Parameters
        ----------
        registration_number : str  – employee reg number (or ID fallback).
        punch_date          : str  – "YYYY-MM-DD".
        punch_time          : str  – "HH:MM" (seconds default to :00).
        punch_type          : str  – "check_in" or "check_out".
        admin_name          : str  – operator name for audit trail.
        reason              : str  – free-text reason (required by UI).
        slot_index          : int  – 1 = first occurrence, 2 = second occurrence.

        Returns (success: bool, message: str).
        """
        from contragest.core.database import Employee, AttendanceRecord, AttendanceCorrectionLog

        # 1. Resolve employee
        emp = self.session.query(Employee).filter_by(registration_number=registration_number).first()
        if not emp:
            try:
                emp = self.session.query(Employee).filter_by(id=int(registration_number)).first()
            except ValueError:
                pass
        if not emp:
            return False, f"Employee '{registration_number}' not found."

        # 2. Parse & validate the supplied time
        punch_time = punch_time.strip()
        if len(punch_time) == 5 and ":" in punch_time:
            punch_time_full = punch_time + ":00"   # HH:MM → HH:MM:00
        elif len(punch_time) == 8 and punch_time.count(":") == 2:
            punch_time_full = punch_time            # already HH:MM:SS
        else:
            return False, f"Invalid time format '{punch_time}'. Expected HH:MM."

        # 3. Build the full ISO datetime string for the record
        #    For night-shift punches that end past midnight we still store the
        #    REAL calendar date (the DB uses logic-date grouping at query time).
        try:
            date_obj = datetime.strptime(punch_date[:10], "%Y-%m-%d").date()
        except Exception:
            return False, f"Invalid date format: '{punch_date}'"

        # Schedule-aware: for morning punches on a night-shift logic day, the
        # physical calendar date must be the NEXT day.  E.g. user edits "08-02
        # OUT1=06:02" but 06:02 on 08-02 would be attributed to 08-01 by the
        # enriched view (cutoff 8).  The physical record must be stored as
        # "2026-08-03 06:02:00" so the enriched view places it on 08-02.
        full_dt_str = f"{punch_date[:10]} {punch_time_full}"
        try:
            test_pt = datetime.strptime(full_dt_str, "%Y-%m-%d %H:%M:%S")
            logic_d = self._punch_logic_date(emp.id, test_pt)
            if logic_d != date_obj:
                # Punch would be attributed to a different logic day; shift the
                # physical date forward until the logic day matches punch_date.
                for _ in range(2):  # at most +1 day
                    test_pt = test_pt + timedelta(days=1)
                    logic_d = self._punch_logic_date(emp.id, test_pt)
                    if logic_d == date_obj:
                        full_dt_str = test_pt.strftime("%Y-%m-%d %H:%M:%S")
                        break
        except Exception:
            pass

        # 4. Time range validation
        try:
            new_h, new_m = map(int, punch_time_full.split(":")[:2])
            if new_h > 23 or new_m > 59:
                return False, f"Invalid time '{punch_time}': hour/min out of range."
        except Exception:
            return False, f"Invalid time format '{punch_time}'."

        # 5. Find existing punches for this employee on this logical day
        #    Use schedule-aware cutoff (same logic as enriched view) instead of fixed 4h
        start_window = date_obj.strftime("%Y-%m-%d")
        end_window = (date_obj + timedelta(days=2)).strftime("%Y-%m-%d")

        raw_records = (
            self.session.query(AttendanceRecord)
            .filter(AttendanceRecord.employee_id == emp.id)
            .filter(AttendanceRecord.punch_time >= start_window)
            .filter(AttendanceRecord.punch_time < end_window)
            .order_by(AttendanceRecord.punch_time.asc())
            .all()
        )

        day_records = []
        for rec in raw_records:
            try:
                pt = datetime.strptime(rec.punch_time[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            logic_date = self._punch_logic_date(emp.id, pt)
            if logic_date == date_obj:
                day_records.append(rec)

        # 5b. DAY_PROGRAM day: the grid displays the programmed slots verbatim,
        #     so an edit must update the program (via save_day_program) and keep
        #     the underlying raw record in sync.  Re-resolving slots from raw
        #     punches here would edit the wrong record (all machine punches are
        #     stored check_in) and the visible value would not change.
        day_prog = self._get_day_program(registration_number, punch_date[:10])
        if day_prog:
            slot_key = self._slot_key(punch_type, slot_index)
            old_val = day_prog.get(slot_key, "-")
            slots = {k: (punch_time_full if k == slot_key else v) for k, v in day_prog.items()}
            ok, msg = self.save_day_program(
                registration_number, punch_date[:10],
                in1=slots["in1"], out1=slots["out1"],
                in2=slots["in2"], out2=slots["out2"],
                admin_name=admin_name,
            )
            if not ok:
                return False, f"Failed to update day program: {msg}"
            target = self._find_raw_at(day_records, old_val)
            if target is not None:
                try:
                    target.punch_time = full_dt_str
                    target.punch_type = punch_type
                    self.session.commit()
                except Exception as e:
                    self.session.rollback()
                    return False, f"Failed to sync raw punch: {e}"
            return True, f"Punch updated: {punch_type} at {full_dt_str} (day program)."

        # 6. Find the record occupying the requested slot using the SAME type
        #    assignment the enriched grid applies (guess + rectify + 3-punch
        #    rule, preserving types set by a previous manual edit).  This keeps
        #    slot 1 / slot 2 in sync with the IN1/OUT1/IN2/OUT2 columns the user
        #    actually clicks, even when raw machine labels disagree.
        sched_obj = self.get_schedule_for_date(emp.id, punch_date)
        typed = self._resolve_day_slot_records(
            emp.id, day_records, sched_obj, punch_date, reg=registration_number
        )
        slot_key = self._slot_key(punch_type, slot_index)
        matching = [t for t in typed if t["slot"] == slot_key]  # session-paired slots

        action = "updated"
        if matching:
            # Update the existing record in this slot
            target_rec = matching[0]["rec"]
            old_time = target_rec.punch_time
            target_rec.punch_time = full_dt_str
            target_rec.punch_type = punch_type
        else:
            # Create a brand-new record
            target_rec = AttendanceRecord(
                employee_id=emp.id,
                zk_user_id=str(emp.registration_number),
                machine_id=None,
                punch_time=full_dt_str,
                punch_type=punch_type,
            )
            self.session.add(target_rec)
            old_time = None
            action = "added"

        # 7. Audit log
        try:
            audit = AttendanceCorrectionLog(
                employee_id=emp.id,
                reg_number=str(emp.registration_number),
                shift_date=punch_date[:10],
                issue_type="MANUAL_PUNCH",
                original_val=old_time or "",
                imputed_val=full_dt_str,
                strategy="MANUAL",
                corrected_by=admin_name,
                corrected_at=datetime.now().isoformat(),
                notes=reason or f"{punch_type} slot {slot_index} {action} by {admin_name}",
            )
            self.session.add(audit)
            self.session.commit()
            return True, f"Punch {action}: {punch_type} at {full_dt_str}."
        except Exception as e:
            self.session.rollback()
            logger.error(f"add_manual_punch failed: {e}")
            return False, f"Failed to save punch: {e}"

    def delete_manual_punch(
        self,
        registration_number: str,
        punch_date: str,
        punch_type: str,
        admin_name: str = "SYSTEM",
        reason: str = "",
        slot_index: int = 1,
        target_time: str = "",
    ) -> tuple:
        """
        Deletes a specific punch (check_in or check_out) for an employee on a given date.

        Parameters
        ----------
        registration_number : str
            Employee registration number (or ID as fallback).
        punch_date : str
            Date string "YYYY-MM-DD".
        punch_type : str
            "check_in" or "check_out".
        admin_name : str
            Name of the operator performing the deletion (for audit log).
        reason : str
            Free-text reason for the deletion (stored in audit log).
        slot_index : int
            1 = first occurrence, 2 = second occurrence of that punch_type that day.
        target_time : str
            Optional exact time string (HH:MM or HH:MM:SS). When provided the
            record is identified by its punch_time suffix instead of the
            session-paired slot, which makes drag-and-drop more robust after the
            destination record has already been added.

        Returns
        -------
        (success: bool, message: str)
        """
        from contragest.core.database import Employee, AttendanceRecord, AttendanceCorrectionLog

        # 1. Resolve employee
        emp = self.session.query(Employee).filter_by(registration_number=registration_number).first()
        if not emp:
            try:
                emp = self.session.query(Employee).filter_by(id=int(registration_number)).first()
            except ValueError:
                pass
        if not emp:
            return False, f"Employee '{registration_number}' not found."

        # 2. Parse date
        try:
            date_obj = datetime.strptime(punch_date[:10], "%Y-%m-%d").date()
        except Exception:
            return False, f"Invalid date format: '{punch_date}'"

        # 3. Fetch raw records in a 2-day window (handles overnight/night-shift punches)
        #    Use schedule-aware cutoff (same logic as enriched view) instead of fixed 4h
        start_window = date_obj.strftime("%Y-%m-%d")
        end_window = (date_obj + timedelta(days=2)).strftime("%Y-%m-%d")

        raw_records = (
            self.session.query(AttendanceRecord)
            .filter(AttendanceRecord.employee_id == emp.id)
            .filter(AttendanceRecord.punch_time >= start_window)
            .filter(AttendanceRecord.punch_time < end_window)
            .order_by(AttendanceRecord.punch_time.asc())
            .all()
        )

        # 4. Keep only records whose logic date matches punch_date
        day_records = []
        for rec in raw_records:
            try:
                pt = datetime.strptime(rec.punch_time[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            logic_date = self._punch_logic_date(emp.id, pt)
            if logic_date == date_obj:
                day_records.append((rec, pt))

        if not day_records:
            return False, f"No punches found for REG {registration_number} on {punch_date}."

        # 4b. DAY_PROGRAM day: the grid displays the programmed slots verbatim,
        #     so removal must clear the slot in the program AND delete the
        #     underlying raw record — otherwise the programmed value stays
        #     pinned on screen (the reported "info is not erased" bug).
        day_prog = self._get_day_program(registration_number, punch_date[:10])
        if day_prog:
            slot_key = self._slot_key(punch_type, slot_index)
            old_val = day_prog.get(slot_key, "-")
            if old_val == "-":
                return False, f"No '{punch_type}' punch found for REG {registration_number} on {punch_date}."
            slots = {k: ("-" if k == slot_key else v) for k, v in day_prog.items()}
            ok, msg = self.save_day_program(
                registration_number, punch_date[:10],
                in1=slots["in1"], out1=slots["out1"],
                in2=slots["in2"], out2=slots["out2"],
                admin_name=admin_name,
            )
            if not ok:
                return False, f"Failed to update day program: {msg}"
            target = self._find_raw_at([rec for rec, _ in day_records], old_val)
            if target is not None:
                try:
                    audit = AttendanceCorrectionLog(
                        employee_id=emp.id,
                        reg_number=str(emp.registration_number),
                        shift_date=punch_date[:10],
                        issue_type="DELETION",
                        original_val=target.punch_time,
                        imputed_val=target.punch_time,
                        strategy="MANUAL",
                        corrected_by=admin_name,
                        corrected_at=datetime.now().isoformat(),
                        notes=reason or f"Deleted {punch_type} slot {slot_index} by {admin_name}",
                    )
                    self.session.add(audit)
                    self.session.delete(target)
                    self.session.commit()
                except Exception as e:
                    self.session.rollback()
                    return False, f"Failed to delete punch: {e}"
            return True, f"Punch deleted: {punch_type} at {old_val}."

        # 5. Locate the record occupying the requested slot exactly like the
        #    enriched grid view does (same type assignment: guess + rectify +
        #    3-punch rule, preserving manually-set types).  Without the rectify
        #    step a split-shift day (08/12/13/17 with no schedule) would guess
        #    IN,IN,OUT,OUT and OUT1 would resolve to the wrong raw punch.
        sched_obj = self.get_schedule_for_date(emp.id, punch_date)
        typed = self._resolve_day_slot_records(
            emp.id, [rec for rec, _ in day_records], sched_obj, punch_date,
            reg=registration_number,
        )

        # 6. Locate the record to delete.
        #    When target_time is provided (drag-and-drop), match by the RESOLVED
        #    grid slot + time-of-day suffix.  We must NOT filter on the raw
        #    punch_type: the ZK device stores every machine punch as check_in,
        #    while the enriched grid displays the 2nd/3rd/4th punches as
        #    check_out / IN2 / OUT2 via pairing.  Filtering on raw type made
        #    deleting a displayed OUT punch fail with "Record not found"
        #    (e.g. REG 1921 OUT 2 = 00:28:43 stored as check_in).
        #    The slot-first match keeps drag-and-drop safe: the destination add
        #    (same timestamp, different slot) never collides with the source.
        target_rec = None
        target_pt = None
        if target_time:
            # Normalise: "HH:MM" -> "HH:MM:00", keep "HH:MM:SS" as-is
            tt = target_time.strip()
            if len(tt) == 5:
                tt += ":00"
            slot_key = self._slot_key(punch_type, slot_index)
            # 1) Prefer the record currently occupying the requested grid slot.
            for t in typed:
                if t["slot"] == slot_key and t["rec"].punch_time[-8:] == tt:
                    target_rec = t["rec"]
                    target_pt = t["dt"]
                    break
            # 2) Fallback: any record with the same time-of-day whose RESOLVED
            #    display type matches.  Covers the same-day move where the
            #    freshly-added destination record shares the timestamp.
            if not target_rec:
                for t in typed:
                    if t["type"] == punch_type and t["rec"].punch_time[-8:] == tt:
                        target_rec = t["rec"]
                        target_pt = t["dt"]
                        break
            if not target_rec:
                return False, (
                    f"Record at {target_time} ({punch_type}) not found for REG "
                    f"{registration_number} on {punch_date}."
                )
        else:
            sched_obj = self.get_schedule_for_date(emp.id, punch_date)
            typed = self._resolve_day_slot_records(
                emp.id, [rec for rec, _ in day_records], sched_obj, punch_date,
                reg=registration_number,
            )
            slot_key = self._slot_key(punch_type, slot_index)
            matching = [t for t in typed if t["slot"] == slot_key]
            if not matching:
                return False, (
                    f"Slot {slot_key} not found — no punch is currently paired "
                    f"there on {punch_date}."
                )
            target_rec = matching[0]["rec"]
            target_pt = matching[0]["dt"]
        punch_time_str = target_pt.strftime("%Y-%m-%d %H:%M:%S")

        # 7. Commit: log deletion for audit + physically remove the record
        try:
            audit = AttendanceCorrectionLog(
                employee_id=emp.id,
                reg_number=str(emp.registration_number),
                shift_date=punch_date[:10],
                issue_type="DELETION",
                original_val=punch_time_str,
                imputed_val=punch_time_str,
                strategy="MANUAL",
                corrected_by=admin_name,
                corrected_at=datetime.now().isoformat(),
                notes=reason or f"Deleted {punch_type} slot {slot_index} by {admin_name}",
            )
            self.session.add(audit)
            self.session.delete(target_rec)
            self.session.commit()
            return True, f"Punch deleted: {punch_type} at {punch_time_str}."
        except Exception as e:
            self.session.rollback()
            logger.error(f"delete_manual_punch failed: {e}")
            return False, f"Failed to delete punch: {e}"

    def save_note_correction(self, reg_number: str, shift_date: str, note_text: str, admin_name: str = "SYSTEM"):
        """Saves or updates a day note correction."""
        from contragest.core.database import AttendanceCorrectionLog, Employee
        
        reg_number = str(reg_number).strip()
        norm_reg = reg_number.lstrip('0') or reg_number
        
        emp = self.session.query(Employee).filter(
            (Employee.registration_number == reg_number) | 
            (Employee.registration_number == norm_reg)
        ).first()
        
        if not emp:
            try: emp = self.session.query(Employee).filter_by(id=int(reg_number)).first()
            except: pass
            
        if not emp:
            return False, "Employee not found"

        # Guard: Reject note corrections for dates after exit_date
        if emp.exit_date and note_text and note_text.strip():
            try:
                from datetime import date as _date
                shift_date_obj = _date.fromisoformat(shift_date[:10])
                if shift_date_obj > emp.exit_date:
                    return False, f"Cannot add notes for dates after employee exit date ({emp.exit_date})"
            except Exception:
                pass

        try:
            existing = self.session.query(AttendanceCorrectionLog).filter(
                ((AttendanceCorrectionLog.reg_number == reg_number) | (AttendanceCorrectionLog.employee_id == emp.id)),
                AttendanceCorrectionLog.shift_date == shift_date,
                AttendanceCorrectionLog.issue_type == "DAY_NOTE"
            ).first()
            
            if existing:
                existing.imputed_val = note_text
                existing.strategy = "MANUAL"
                existing.corrected_by = admin_name
                existing.corrected_at = datetime.now().isoformat()
                existing.reg_number = reg_number
            else:
                log = AttendanceCorrectionLog(
                    employee_id=emp.id,
                    reg_number=reg_number,
                    shift_date=shift_date,
                    issue_type="DAY_NOTE",
                    original_val="",
                    imputed_val=note_text,
                    strategy="MANUAL",
                    corrected_by=admin_name,
                    corrected_at=datetime.now().isoformat(),
                    notes=f"Note set manually"
                )
                self.session.add(log)
                
            self.session.commit()
            logger.info(f"Note correction saved: {reg_number} on {shift_date} -> {note_text}")
            return True, "Note updated"
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error saving note correction: {e}")
            return False, str(e)

    def save_schedule_correction(self, reg_number: str, shift_date: str, schedule_name: str, admin_name: str = "SYSTEM") -> tuple:
        """Saves or updates a DAY_SCHEDULE override for a specific employee on a specific date.

        This overrides the employee's regular schedule resolution for that single day only.
        The override is stored as an AttendanceCorrectionLog with issue_type='DAY_SCHEDULE'.
        """
        from contragest.core.database import AttendanceCorrectionLog, Employee, WorkSchedule

        reg_number = str(reg_number).strip()
        norm_reg = reg_number.lstrip('0') or reg_number
        shift_date = str(shift_date)[:10]

        emp = self.session.query(Employee).filter(
            (Employee.registration_number == reg_number) |
            (Employee.registration_number == norm_reg)
        ).first()
        if not emp:
            try:
                emp = self.session.query(Employee).filter_by(id=int(reg_number)).first()
            except Exception:
                pass
        if not emp:
            return False, f"Employee '{reg_number}' not found."

        # Validate schedule name
        sched = self.session.query(WorkSchedule).filter_by(name=schedule_name).first()
        if not sched:
            return False, f"Schedule '{schedule_name}' not found."

        try:
            existing = self.session.query(AttendanceCorrectionLog).filter(
                ((AttendanceCorrectionLog.reg_number == reg_number) | (AttendanceCorrectionLog.employee_id == emp.id)),
                AttendanceCorrectionLog.shift_date == shift_date,
                AttendanceCorrectionLog.issue_type == "DAY_SCHEDULE"
            ).first()

            if existing:
                existing.imputed_val = schedule_name
                existing.strategy = "MANUAL"
                existing.corrected_by = admin_name
                existing.corrected_at = datetime.now().isoformat()
            else:
                log = AttendanceCorrectionLog(
                    employee_id=emp.id,
                    reg_number=reg_number,
                    shift_date=shift_date,
                    issue_type="DAY_SCHEDULE",
                    original_val="",
                    imputed_val=schedule_name,
                    strategy="MANUAL",
                    corrected_by=admin_name,
                    corrected_at=datetime.now().isoformat(),
                    notes=f"Schedule override set manually"
                )
                self.session.add(log)

            self.session.commit()
            logger.info(f"Schedule correction saved: {reg_number} on {shift_date} -> {schedule_name}")
            return True, f"Schedule updated to '{schedule_name}'"
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error saving schedule correction: {e}")
            return False, str(e)

    def get_schedule_override(self, reg_number: str, shift_date: str) -> Optional[str]:
        """Returns the DAY_SCHEDULE override name for an employee/date, or None.

        Lets the UI decide whether a 'Reset to Automatic' action is available.
        """
        from contragest.core.database import AttendanceCorrectionLog, Employee
        reg_number = str(reg_number).strip()
        emp = self.session.query(Employee).filter(
            (Employee.registration_number == reg_number) |
            (Employee.registration_number == (reg_number.lstrip('0') or reg_number))
        ).first()
        if not emp:
            try:
                emp = self.session.query(Employee).filter_by(id=int(reg_number)).first()
            except Exception:
                pass
        if not emp:
            return None
        log = self.session.query(AttendanceCorrectionLog).filter(
            ((AttendanceCorrectionLog.reg_number == reg_number) |
             (AttendanceCorrectionLog.employee_id == emp.id)),
            AttendanceCorrectionLog.shift_date == str(shift_date)[:10],
            AttendanceCorrectionLog.issue_type == "DAY_SCHEDULE"
        ).first()
        return log.imputed_val if log and log.imputed_val else None

    def delete_schedule_correction(self, reg_number: str, shift_date: str, admin_name: str = "SYSTEM") -> tuple:
        """Removes the DAY_SCHEDULE override for an employee/date.

        After removal the day reverts to automatic schedule resolution
        (daily override -> rotation -> fixed assignment).  Idempotent: returns
        success even when no override existed.
        """
        from contragest.core.database import AttendanceCorrectionLog, Employee
        reg_number = str(reg_number).strip()
        emp = self.session.query(Employee).filter(
            (Employee.registration_number == reg_number) |
            (Employee.registration_number == (reg_number.lstrip('0') or reg_number))
        ).first()
        if not emp:
            try:
                emp = self.session.query(Employee).filter_by(id=int(reg_number)).first()
            except Exception:
                pass
        if not emp:
            return False, f"Employee '{reg_number}' not found."

        logs = self.session.query(AttendanceCorrectionLog).filter(
            ((AttendanceCorrectionLog.reg_number == reg_number) |
             (AttendanceCorrectionLog.employee_id == emp.id)),
            AttendanceCorrectionLog.shift_date == str(shift_date)[:10],
            AttendanceCorrectionLog.issue_type == "DAY_SCHEDULE"
        ).all()
        if not logs:
            return True, "No override to remove."

        try:
            for log in logs:
                self.session.delete(log)
            self.session.commit()
            logger.info(f"Schedule override removed: {reg_number} on {str(shift_date)[:10]} by {admin_name}")
            return True, "Schedule override removed."
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error removing schedule override: {e}")
            return False, str(e)

    def get_all_work_schedules(self) -> list:
        """Returns a list of all available WorkSchedule objects."""
        from contragest.core.database import WorkSchedule
        return self.session.query(WorkSchedule).order_by(WorkSchedule.name.asc()).all()

    def get_status_override(self, reg_number: str, shift_date: str) -> Optional[str]:
        """Returns the DAY_STATUS override code for an employee/date, or None.

        Lets the UI decide whether a 'Reset to Automatic' action is available.
        """
        from contragest.core.database import AttendanceCorrectionLog, Employee
        reg_number = str(reg_number).strip()
        norm_reg = reg_number.lstrip('0') or reg_number
        emp = self.session.query(Employee).filter(
            (Employee.registration_number == reg_number) |
            (Employee.registration_number == norm_reg)
        ).first()
        if not emp:
            try:
                emp = self.session.query(Employee).filter_by(id=int(reg_number)).first()
            except Exception:
                pass
        if not emp:
            return None
        log = self.session.query(AttendanceCorrectionLog).filter(
            ((AttendanceCorrectionLog.reg_number == reg_number) |
             (AttendanceCorrectionLog.employee_id == emp.id)),
            AttendanceCorrectionLog.shift_date == str(shift_date)[:10],
            AttendanceCorrectionLog.issue_type == "DAY_STATUS"
        ).first()
        return log.imputed_val if log else None

    def delete_status_correction(self, reg_number: str, shift_date: str, admin_name: str = "SYSTEM") -> tuple:
        """Removes the DAY_STATUS override for an employee/date.

        After removal the day reverts to automatic status computation
        (punches, day type, employee schedule).  Idempotent: returns success
        even when no override existed.
        """
        from contragest.core.database import AttendanceCorrectionLog, Employee
        reg_number = str(reg_number).strip()
        norm_reg = reg_number.lstrip('0') or reg_number
        emp = self.session.query(Employee).filter(
            (Employee.registration_number == reg_number) |
            (Employee.registration_number == norm_reg)
        ).first()
        if not emp:
            try:
                emp = self.session.query(Employee).filter_by(id=int(reg_number)).first()
            except Exception:
                pass
        if not emp:
            return False, f"Employee '{reg_number}' not found."

        logs = self.session.query(AttendanceCorrectionLog).filter(
            ((AttendanceCorrectionLog.reg_number == reg_number) |
             (AttendanceCorrectionLog.employee_id == emp.id)),
            AttendanceCorrectionLog.shift_date == str(shift_date)[:10],
            AttendanceCorrectionLog.issue_type == "DAY_STATUS"
        ).all()
        if not logs:
            return True, "No override to remove."

        try:
            for log in logs:
                self.session.delete(log)
            self.session.commit()
            logger.info(f"Status override removed: {reg_number} on {str(shift_date)[:10]} by {admin_name}")
            return True, "Status override removed."
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error removing status override: {e}")
            return False, str(e)

    def get_correction_logs(self, start_date: Optional[str] = None, end_date: Optional[str] = None, reg_filter: Optional[str] = None, strategy_filter: Optional[str] = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """Fetches attendance correction logs with employee details."""
        try:
            q = self.session.query(AttendanceCorrectionLog, Employee).join(Employee, AttendanceCorrectionLog.employee_id == Employee.id, isouter=True)
            if start_date: q = q.filter(AttendanceCorrectionLog.shift_date >= start_date)
            if end_date: q = q.filter(AttendanceCorrectionLog.shift_date <= end_date)
            if reg_filter: q = q.filter(AttendanceCorrectionLog.reg_number.like(f"%{reg_filter}%"))
            if strategy_filter and strategy_filter != "All": q = q.filter(AttendanceCorrectionLog.strategy == strategy_filter)
            results = q.order_by(AttendanceCorrectionLog.corrected_at.desc()).limit(limit).all()
            logs = []
            for log, emp in results:
                emp_name = f"{emp.first_name} {emp.last_name}" if emp else f"REG {log.reg_number}"
                logs.append({
                    "shift_date": log.shift_date, "employee": emp_name, "reg_number": log.reg_number, "issue_type": log.issue_type,
                    "correction": log.imputed_val[11:] if log.imputed_val and len(log.imputed_val) > 11 else (log.imputed_val or "-"),
                    "strategy": log.strategy, "corrected_by": log.corrected_by, "corrected_at": log.corrected_at, "notes": log.notes
                })
            return logs
        except Exception as e: logger.error(f"Error: {e}"); return []

    def sync_attendance_to_db(self, records: List[Dict[str, Any]]):
        """
        Upserts the provided enriched attendance records into the daily_attendance table.
        Uses (date, reg_number) as the unique identifier.
        """
        from contragest.core.database import DailyAttendance
        
        count = 0
        try:
            for rec in records:
                # We need the raw ISO date for persistence
                dt_iso = rec.get("raw_date")
                reg = rec.get("reg_number")
                if not dt_iso or not reg:
                    continue
                
                # Check for existing record
                existing = self.session.query(DailyAttendance).filter_by(
                    date=dt_iso,
                    reg_number=reg
                ).first()
                
                if existing:
                    # Update existing
                    existing.employee_name = rec.get("employee")
                    existing.department = rec.get("department")
                    existing.role = rec.get("role_title")
                    existing.schedule = rec.get("schedule")
                    existing.in1 = rec.get("check_in")
                    existing.out1 = rec.get("check_out")
                    existing.in2 = rec.get("check_in_2")
                    existing.out2 = rec.get("check_out_2")
                    existing.attendance_time = rec.get("attendance_time")
                    existing.work_time = rec.get("work_time")
                    existing.difference = rec.get("difference")
                    existing.status = rec.get("status")
                    existing.note = rec.get("note")
                    existing.machine = rec.get("machine")
                    existing.last_sync = rec.get("synced_at")
                else:
                    # Create new
                    new_item = DailyAttendance(
                        date=dt_iso,
                        reg_number=reg,
                        employee_name=rec.get("employee"),
                        department=rec.get("department"),
                        role=rec.get("role_title"),
                        schedule=rec.get("schedule"),
                        in1=rec.get("check_in"),
                        out1=rec.get("check_out"),
                        in2=rec.get("check_in_2"),
                        out2=rec.get("check_out_2"),
                        attendance_time=rec.get("attendance_time"),
                        work_time=rec.get("work_time"),
                        difference=rec.get("difference"),
                        status=rec.get("status"),
                        note=rec.get("note"),
                        machine=rec.get("machine"),
                        last_sync=rec.get("synced_at")
                    )
                    self.session.add(new_item)
                count += 1
            
            self.session.commit()
            return True, f"Successfully saved {count} records."
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error syncing attendance to DB: {e}")
            return False, str(e)

    def backup_attendance_records(self, label: Optional[str] = None, record_ids: Optional[List[int]] = None, progress_callback: Optional[Callable[[int, int], None]] = None) -> tuple:
        """Incremental or full transactional backup of attendance records."""
        if not label: label = str(date.today())
        query = self.session.query(AttendanceRecord)
        if record_ids: query = query.filter(AttendanceRecord.id.in_(record_ids))
        records = query.all()
        if not records: return 0, label
        try:
            affected_context = set()
            for r in records: affected_context.add((r.employee_id, r.punch_time[:10]))
            dates = [r.punch_time[:10] for r in records if r.punch_time]
            min_date = min(dates) if dates else None
            max_date = max(dates) if dates else None
            all_enriched = self.get_attendance_records_enriched(start_date=min_date, end_date=max_date, limit=len(records) * 2 + 100)
            to_process = [er for er in all_enriched if (er.get("emp_id"), er.get("raw_date")) in affected_context]

            count_upserted = 0
            for er in to_process:
                lead_id = er["id"]; lead_rec = self.session.query(AttendanceRecord).get(lead_id)
                if not lead_rec:
                    continue
                out_id = None
                if er["check_out"] != "-":
                    out_rec = self.session.query(AttendanceRecord).filter(AttendanceRecord.employee_id == lead_rec.employee_id, AttendanceRecord.punch_time.like(f"{er.get('raw_date')}%"), AttendanceRecord.punch_time.contains(er["check_out"])).first()
                    if out_rec: out_id = out_rec.id
                existing = self.session.query(AttendanceRecordBackup).filter_by(source_record_id=lead_id, backup_label=label).first()
                if existing:
                    existing.check_out = er["check_out"]; existing.out_record_id = out_id; existing.synced_at = lead_rec.synced_at
                else:
                    bk = AttendanceRecordBackup(
                        source_record_id=lead_id, out_record_id=out_id, employee_id=lead_rec.employee_id, zk_user_id=er["reg_number"],
                        machine_id=lead_rec.machine_id, punch_time=lead_rec.punch_time, punch_type="paired", synced_at=lead_rec.synced_at,
                        backed_up_at=date.today(), backup_label=label, employee_name=er["employee"], department_name=er["department"],
                        role_title=er["role_title"], machine_name=er["machine"], punch_date=er.get("raw_date"), check_in=er["check_in"], check_out=er["check_out"]
                    )
                    self.session.add(bk)
                count_upserted += 1
                if progress_callback: progress_callback(count_upserted, len(to_process))
            self.session.commit()
            return count_upserted, label
        except Exception as e: self.session.rollback(); logger.error(f"Backup failed: {e}"); raise

    def get_employees_sync_status(self, machine_id: int) -> List[Dict[str, Any]]:
        """Get list of employees with their on-machine status, including those exclusively on the machine."""
        machine = self.get_machine(machine_id)
        if not machine: return []
        machine_users = self.connector.get_users(machine.ip_address, machine.port, machine.password or "")
        machine_reg_numbers = set(str(getattr(u, 'user_id', None) or getattr(u, 'uid', None)) for u in machine_users if (getattr(u, 'user_id', None) or getattr(u, 'uid', None)) is not None)
        employees = self.session.query(Employee).filter(Employee.is_archived == False).all()
        db_reg_map = {str(emp.registration_number): emp for emp in employees if emp.registration_number is not None}
        
        result = []
        # First, list all DB employees and their machine presence
        for emp in employees:
            reg = str(emp.registration_number) if emp.registration_number is not None else None
            result.append({
                "id": emp.id, 
                "registration_number": reg or "-", 
                "name": f"{emp.first_name} {emp.last_name}", 
                "department": emp.dept_obj.name if emp.dept_obj else (emp.department or "-"), 
                "on_machine": reg in machine_reg_numbers if reg else False
            })
            
        # Second, explicitly append users that are ON THE MACHINE but missing from the DB
        for u in machine_users:
            u_id = str(getattr(u, 'user_id', None) or getattr(u, 'uid', None))
            if u_id and u_id not in db_reg_map:
                u_name = getattr(u, 'name', None) or "UNKNOWN (Machine Only)"
                result.append({
                    "id": f"ZK-{u_id}", 
                    "registration_number": u_id, 
                    "name": u_name, 
                    "department": "-", 
                    "on_machine": True
                })
        return result

    def push_employee_to_machine(self, machine_id: int, employee_id: int) -> bool:
        """Upload a single employee to the machine."""
        machine = self.get_machine(machine_id)
        emp = self.session.query(Employee).get(employee_id)
        if not machine:
            logger.warning(f"push_to_machine: machine {machine_id} not found (employee {employee_id}).")
            return False
        if not emp:
            logger.warning(f"push_to_machine: employee {employee_id} not found in DB.")
            return False
        if not emp.registration_number:
            logger.warning(f"push_to_machine: employee {employee_id} ({emp.first_name} {emp.last_name}) has no registration_number — skipped.")
            return False
        try:
            zk_uid = int(emp.registration_number)
        except (ValueError, TypeError):
            logger.warning(f"push_to_machine: employee {employee_id} registration_number '{emp.registration_number}' is not numeric — skipped.")
            return False
        return self.connector.upload_user(machine.ip_address, machine.port, machine.password or "", uid=zk_uid, name=f"{emp.first_name} {emp.last_name}"[:24])

    def remove_employee_from_machine(self, machine_id: int, employee_id: int) -> bool:
        """Remove a single employee from the machine."""
        machine = self.get_machine(machine_id); emp = self.session.query(Employee).get(employee_id)
        if not machine or not emp or not emp.registration_number: return False
        return self.connector.delete_user_by_reg(machine.ip_address, machine.port, machine.password or "", reg_str=str(emp.registration_number))

    def remove_orphan_from_machine(self, machine_id: int, zk_uid: str) -> bool:
        """Remove an Orphan (Machine Only) user directly from the machine."""
        machine = self.get_machine(machine_id)
        if not machine or not zk_uid: return False
        return self.connector.delete_user_by_reg(machine.ip_address, machine.port, machine.password or "", reg_str=str(zk_uid))

    def push_all_departments_to_machine(self, machine_id: int) -> tuple:
        """Record all departments as synced to the given machine."""
        machine = self.get_machine(machine_id)
        if not machine:
            raise ValueError("Machine not found.")
    def sync_biometrics(self, machine_id: int) -> tuple:
        """Download all biometric templates (bitmasks) from machine and archive them."""
        machine = self.get_machine(machine_id)
        if not machine: return 0, 0
        
        templates = self.connector.get_all_templates(machine.ip_address, machine.port, machine.password or "")
        if not templates: return 0, 0
        
        # Get users to map uid to registration_number
        from zk.user import User
        users = self.connector.get_users(machine.ip_address, machine.port, machine.password or "")
        uid_map = {u.uid: u.user_id for u in users} # ZK uid -> registration_number string
        
        count = 0
        for t in templates:
            reg_num = uid_map.get(t.uid)
            if not reg_num: continue
            
            # Map type (pyzk uses 0-9 for fingers, 15/111 for face bitmask usually)
            f_val = getattr(t, 'fid', 0)
            t_type = "face" if f_val >= 10 else "finger"
            
            # Check for existing
            existing = self.session.query(BiometricTemplate).filter_by(
                registration_number=str(reg_num),
                type=t_type,
                template_index=f_val
            ).first()
            
            if not existing:
                new_t = BiometricTemplate(
                    registration_number=str(reg_num),
                    type=t_type,
                    template_index=t.fid,
                    template_data=str(t.template), # The raw bitmask as hex/string
                    version=getattr(t, 'version', 10)
                )
                self.session.add(new_t)
                count += 1
                
        self.session.commit()
        logger.info(f"Synchronized {count} biometric templates for machine {machine_id}")
        return count, len(templates)

    def push_biometrics_to_machine(self, machine_id: int) -> tuple:
        """Accelerated upload of archived Biometric Templates to the physical machine."""
        machine = self.get_machine(machine_id)
        if not machine: return 0, 0
        
        # Load all locally archived bitmasks for employees currently assigned
        # (For efficiency, we just grab everything in BiometricTemplate for now)
        archived_templates = self.session.query(BiometricTemplate).all()
        if not archived_templates: return 0, 0
        
        # Format the data for the high-speed bulk uploader
        templates_data = [
            {
                "reg_num": t.registration_number,
                "type": t.type,
                "index": t.template_index,
                "template_string": t.template_data,
                "version": t.version
            }
            for t in archived_templates
        ]
        
        logger.info(f"Initiating Accelerated Biometric Upload: {len(templates_data)} bitmasks to {machine.ip_address}")
        return self.connector.push_biometrics_bulk(
            machine.ip_address, 
            machine.port, 
            machine.password or "", 
            templates_data
        )

        departments = self.session.query(Department).all()
        synced = 0
        failed = 0

        for dept in departments:
            try:
                # Upsert: remove old record for this dept+machine, then insert fresh
                existing = (
                    self.session.query(MachineDepartment)
                    .filter_by(machine_id=machine_id, department_id=dept.id)
                    .first()
                )
                if existing:
                    existing.synced_at = date.today()
                    existing.department_name = dept.name
                else:
                    entry = MachineDepartment(
                        machine_id=machine_id,
                        department_id=dept.id,
                        department_name=dept.name,
                        synced_at=date.today(),
                    )
                    self.session.add(entry)

                # Optional: push department as a named placeholder user to ZK
                if PYZK_AVAILABLE:
                    self.connector.upload_user(
                        machine.ip_address, machine.port, machine.password or "",
                        uid=50000 + dept.id,
                        name=f"[DEPT] {dept.name}"[:24],
                    )

                synced += 1
            except Exception as e:
                logger.error(f"Error syncing department {dept.name}: {e}")
                failed += 1

        self.session.commit()
        machine.last_sync = date.today()
        self.session.commit()
        logger.info(f"Departments synced to machine {machine.name}: {synced} ok, {failed} failed")
        return synced, failed

    def push_all_employees_to_machine(self, machine_id: int) -> tuple:
        """Push every employee in the database to the given attendance machine."""
        machine = self.get_machine(machine_id)
        if not machine:
            raise ValueError("Machine not found.")

        employees = self.session.query(Employee).all()
        success = 0
        failed = 0

        for emp in employees:
            if not emp.registration_number:
                failed += 1
                continue
            try:
                zk_uid = int(emp.registration_number)
                self.connector.upload_user(
                    machine.ip_address, machine.port, machine.password or "",
                    uid=zk_uid,
                    name=f"{emp.first_name} {emp.last_name}"[:24],
                )
                success += 1
            except Exception as e:
                logger.error(f"Error pushing employee {emp.id}: {e}")
                failed += 1

        machine.last_sync = date.today()
        self.session.commit()
        logger.info(f"Employees pushed to machine {machine.name}: {success} ok, {failed} failed")
        return success, failed

    def ensure_employee_synced(self, employee_id: int, machine_id: Optional[int] = None) -> tuple[int, int]:
        """Durable sync method intended for background use."""
        emp = self.session.query(Employee).get(employee_id)
        if not emp:
            logger.error(f"Sync error: Employee {employee_id} not found in DB.")
            return 0, 0

        machines = [self.get_machine(machine_id)] if machine_id else self.session.query(AttendanceMachine).filter_by(is_active=True).all()
        if not machines:
            return 0, 0
            
        s = 0
        f = 0
        for m in machines:
            if not m:
                continue
            if self.push_employee_to_machine(m.id, emp.id):
                s += 1
            else:
                f += 1
                logger.warning(f"ensure_employee_synced: employee {employee_id} failed on machine '{m.name}' ({m.ip_address}:{m.port})")
        return s, f

    def sync_schedule_to_machines(
        self,
        schedule_id: int,
        admin_name: str = "System",
        progress_callback=None,
    ) -> tuple:
        """
        Push all employees assigned to the given WorkSchedule to every active
        AttendanceMachine using a single bulk connection per machine.

        Returns (total_success, total_failed, results_per_machine)
        where results_per_machine is a list of dicts:
            {"machine": name, "success": n, "failed": n, "error": str|None}
        """
        schedule = self.session.query(WorkSchedule).get(schedule_id)
        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found.")

        # Gather all assignment records for this schedule
        assignments = self.session.query(EmployeeSchedule).filter_by(
            schedule_id=schedule_id
        ).all()

        # Build user list (uid = registration_number as int, name = full name)
        user_list = []
        for a in assignments:
            emp = self.session.query(Employee).get(a.employee_id)
            if emp and emp.registration_number:
                try:
                    user_list.append({
                        "uid": int(emp.registration_number),
                        "name": f"{emp.first_name} {emp.last_name}"
                    })
                except (ValueError, TypeError):
                    logger.warning(f"Skipping employee {emp.id}: non-numeric registration_number.")

        machines = self.session.query(AttendanceMachine).filter_by(is_active=True).all()

        total_success = 0
        total_failed = 0
        machine_results = []

        for idx, machine in enumerate(machines):
            if progress_callback:
                progress_callback(idx + 1, len(machines))

            result = {"machine": machine.name, "success": 0, "failed": len(user_list), "error": None}
            try:
                s, f = self.connector.push_users_bulk(
                    machine.ip_address,
                    machine.port,
                    machine.password or "",
                    user_list,
                )
                result["success"] = s
                result["failed"] = f
                total_success += s
                total_failed += f

                # Audit trail entry
                try:
                    log = AttendanceCorrectionLog(
                        reg_number="ALL",
                        shift_date=date.today().isoformat(),
                        issue_type="SCHEDULE_SYNC",
                        imputed_val=schedule.name,
                        strategy="PUSH_TO_ZK",
                        corrected_by=admin_name,
                        corrected_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        notes=(
                            f"Synced schedule '{schedule.name}' to machine '{machine.name}': "
                            f"{s} pushed, {f} failed."
                        )
                    )
                    self.session.add(log)
                    self.session.commit()
                except Exception as audit_e:
                    logger.warning(f"Audit log failed: {audit_e}")
                    self.session.rollback()

            except Exception as e:
                result["error"] = str(e)
                total_failed += len(user_list)
                logger.error(f"sync_schedule_to_machines: machine {machine.name} failed: {e}")

            machine_results.append(result)

        logger.info(
            f"Schedule sync '{schedule.name}' complete: "
            f"{total_success} pushed, {total_failed} failed across {len(machines)} machine(s)."
        )
        return total_success, total_failed, machine_results

    def get_all_schedules(self) -> List[WorkSchedule]:
        return self.session.query(WorkSchedule).all()


    def save_schedule(self, data: Dict[str, Any], schedule_id: Optional[int] = None) -> WorkSchedule:
        if not data.get("name"):
            raise ValueError("Schedule name is required.")
        import re
        time_pattern = re.compile(r"^([01][0-9]|2[0-3]):([0-5][0-9])$")
        for field in ["start_time", "end_time", "break_start", "break_end", "debut_pointage_entree", "fin_pointage_entree", "debut_pointage_sortie", "fin_pointage_sortie"]:
            val = data.get(field)
            if val and not time_pattern.match(val):
                raise ValueError(f"Invalid format for {field}")
        if schedule_id:
            sched = self.session.query(WorkSchedule).get(schedule_id)
            if not sched:
                raise ValueError("Not found")
        else:
            sched = WorkSchedule()
            self.session.add(sched)
        
        sched.name = data.get("name", "")
        sched.start_time = data.get("start_time", "08:00")
        sched.end_time = data.get("end_time", "17:00")
        sched.break_start = data.get("break_start", "12:00")
        sched.break_end = data.get("break_end", "13:00")
        sched.days_of_week = data.get("days_of_week", "Mon,Tue,Wed,Thu,Fri")
        sched.total_hours = float(data.get("total_hours", 8.0))
        sched.retard_tolere_mn = int(data.get("retard_tolere_mn", 0))
        sched.depart_avance_tolere_mn = int(data.get("depart_avance_tolere_mn", 0))
        sched.debut_pointage_entree = data.get("debut_pointage_entree", "00:00")
        sched.fin_pointage_entree = data.get("fin_pointage_entree", "23:59")
        sched.debut_pointage_sortie = data.get("debut_pointage_sortie", "00:00")
        sched.fin_pointage_sortie = data.get("fin_pointage_sortie", "23:59")
        sched.compte_journee = float(data.get("compte_journee", 1.0))
        sched.compte_minute = int(data.get("compte_minute", 480))
        sched.pointe_entree_obligatoire = bool(data.get("pointe_entree_obligatoire", True))
        sched.pointe_sortie_obligatoire = bool(data.get("pointe_sortie_obligatoire", True))
        sched.color_hex = data.get("color_hex", "#0055ff")
        
        self.session.commit()
        self.session.refresh(sched)
        return sched

    def delete_schedule(self, schedule_id: int) -> bool:
        sched = self.session.query(WorkSchedule).get(schedule_id)
        if not sched:
            return False
        self.session.delete(sched)
        self.session.commit()
        return True

    def assign_schedule(self, employee_id: int, schedule_id: int, effective_date: date = None, commit: bool = True) -> EmployeeSchedule:
        if not effective_date:
            effective_date = date.today()
        existing = self.session.query(EmployeeSchedule).filter_by(
            employee_id=employee_id, 
            effective_date=effective_date, 
            schedule_id=schedule_id
        ).first()
        if existing:
            assignment = existing
        else:
            assignment = EmployeeSchedule(
                employee_id=employee_id, 
                schedule_id=schedule_id, 
                effective_date=effective_date
            )
            self.session.add(assignment)
        if commit:
            self.session.commit()
        return assignment

    def get_employee_schedule(self, employee_id: int) -> Optional[WorkSchedule]:
        assignment = self.session.query(EmployeeSchedule).filter_by(
            employee_id=employee_id
        ).order_by(EmployeeSchedule.effective_date.desc(), EmployeeSchedule.id.desc()).first()
        return assignment.schedule if assignment else None

    def get_schedule_assignments(self, schedule_id: int) -> List[Dict[str, Any]]:
        assignments = self.session.query(EmployeeSchedule).filter_by(schedule_id=schedule_id).all()
        result = []
        for a in assignments:
            emp = self.session.query(Employee).get(a.employee_id)
            if emp:
                result.append({
                    "employee_id": emp.id, 
                    "name": f"{emp.first_name} {emp.last_name}", 
                    "effective_date": str(a.effective_date)
                })
        return result

    # --- Predefined Notes CRUD ---
    def get_predefined_notes(self) -> List[Dict[str, Any]]:
        from contragest.core.database import PredefinedNote
        notes = self.session.query(PredefinedNote).all()
        return [{"id": n.id, "name": n.name, "color_hex": n.color_hex} for n in notes]

    def save_predefined_note(self, note_data: Dict[str, Any]) -> Dict[str, Any]:
        from contragest.core.database import PredefinedNote
        note_id = note_data.get("id")
        name = note_data.get("name")
        color_hex = note_data.get("color_hex", "#ffffff")

        if not name:
            raise ValueError("Note name is required.")

        if note_id:
            note_obj = self.session.query(PredefinedNote).get(note_id)
            if not note_obj:
                raise ValueError("Note not found.")
        else:
            note_obj = PredefinedNote()
            self.session.add(note_obj)

        note_obj.name = name
        note_obj.color_hex = color_hex
        
        self.session.commit()
        self.session.refresh(note_obj)
        return {"id": note_obj.id, "name": note_obj.name, "color_hex": note_obj.color_hex}

    def delete_predefined_note(self, note_id: int) -> bool:
        from contragest.core.database import PredefinedNote
        note_obj = self.session.query(PredefinedNote).get(note_id)
        if not note_obj:
            return False
        
        self.session.delete(note_obj)
        self.session.commit()
        return True

    # ═══════════════════════════════════════════════════════════════════════
    #  Shift Rotation CRUD
    # ═══════════════════════════════════════════════════════════════════════

    def get_all_rotations(self) -> List[ShiftRotation]:
        """Returns all shift rotation patterns with their slots eagerly loaded."""
        from sqlalchemy.orm import selectinload
        return (
            self.session.query(ShiftRotation)
            .options(
                selectinload(ShiftRotation.slots)
                .selectinload(ShiftRotationSlot.schedule)
            )
            .all()
        )

    def save_rotation(self, data: Dict[str, Any], rotation_id: Optional[int] = None) -> ShiftRotation:
        """
        Create or update a shift rotation with its day→schedule slots.
        
        data = {
            "name": "3×8 Reception",
            "cycle_days": 21,
            "description": "...",
            "slots": [
                {"day_offset": 0, "schedule_id": 1},
                {"day_offset": 1, "schedule_id": 2},
                ...
            ]
        }
        """
        if not data.get("name"):
            raise ValueError("Rotation name is required.")

        if rotation_id:
            rotation = self.session.query(ShiftRotation).get(rotation_id)
            if not rotation:
                raise ValueError("Rotation not found.")
        else:
            rotation = ShiftRotation()
            self.session.add(rotation)

        rotation.name = data["name"]
        rotation.cycle_days = int(data.get("cycle_days", 21))
        rotation.description = data.get("description", "")

        # Replace all slots (delete old, insert new)
        rotation.slots.clear()
        self.session.flush()

        for slot_data in data.get("slots", []):
            slot = ShiftRotationSlot(
                rotation=rotation,
                day_offset=int(slot_data["day_offset"]),
                schedule_id=int(slot_data["schedule_id"]),
            )
            self.session.add(slot)

        self.session.commit()
        self.session.refresh(rotation)
        return rotation

    def delete_rotation(self, rotation_id: int) -> bool:
        """Deletes a rotation and all its slots (cascaded)."""
        rotation = self.session.query(ShiftRotation).get(rotation_id)
        if not rotation:
            return False
        # Also deactivate any employee assignments
        self.session.query(EmployeeRotation).filter_by(rotation_id=rotation_id).delete()
        self.session.delete(rotation)
        self.session.commit()
        return True

    def assign_rotation(self, employee_id: int, rotation_id: int, cycle_start_date: date) -> EmployeeRotation:
        """
        Assigns a rotation pattern to an employee. Deactivates any previous rotation.
        """
        # Deactivate existing active rotations for this employee
        self.session.query(EmployeeRotation).filter_by(
            employee_id=employee_id, is_active=True
        ).update({"is_active": False})
        
        assignment = EmployeeRotation(
            employee_id=employee_id,
            rotation_id=rotation_id,
            cycle_start_date=cycle_start_date,
            is_active=True,
        )
        self.session.add(assignment)
        self.session.commit()
        return assignment

    def remove_rotation_assignment(self, employee_id: int) -> bool:
        """Deactivates any active rotation for this employee."""
        updated = self.session.query(EmployeeRotation).filter_by(
            employee_id=employee_id, is_active=True
        ).update({"is_active": False})
        self.session.commit()
        return updated > 0

    def get_employee_rotation(self, employee_id: int) -> Optional[EmployeeRotation]:
        """Returns the active rotation assignment for an employee (if any)."""
        from sqlalchemy.orm import selectinload
        return (
            self.session.query(EmployeeRotation)
            .options(
                selectinload(EmployeeRotation.rotation)
                .selectinload(ShiftRotation.slots)
                .selectinload(ShiftRotationSlot.schedule)
            )
            .filter_by(employee_id=employee_id, is_active=True)
            .first()
        )

    def resolve_rotation_schedule(self, employee_id: int, target_date) -> Optional[WorkSchedule]:
        """
        Given an employee and a target date, returns the WorkSchedule
        from their rotation that applies on that day.
        Returns None if no active rotation exists.
        """
        assignment = self.get_employee_rotation(employee_id)
        if not assignment or not assignment.rotation or not assignment.rotation.slots:
            return None

        if isinstance(target_date, str):
            target_date = datetime.strptime(target_date, "%Y-%m-%d").date()

        days_elapsed = (target_date - assignment.cycle_start_date).days
        cycle_len = assignment.rotation.cycle_days or 1
        position = days_elapsed % cycle_len

        slot = next((s for s in assignment.rotation.slots if s.day_offset == position), None)
        return slot.schedule if slot else None

    def resolve_employee_schedule(
        self,
        employee_id: Optional[int],
        reg_str: Optional[str],
        target_date,
        punch_time: Optional[str] = None,
    ) -> Optional[WorkSchedule]:
        """
        Resolve the WorkSchedule that applies to an employee on a given date.

        Resolution order (identical to the enriched grid / ``_get_day_schedules``):
          1. A DAY_SCHEDULE correction (per-day override from the correction log).
          2. The employee's active rotating schedule (EmployeeRotation).
          3. The most recent fixed assignment (EmployeeSchedule) effective on or
             before the date — plus the previous assignment generation — with
             same effective_date ties broken by proximity of the punch time to
             the schedule's start/end.

        If nothing resolves for the punch's own employee row, the lookup falls
        back to any OTHER employee row sharing the same registration number
        (preferring a non-archived row, then one with schedule assignments).
        This covers punches that were linked to an archived duplicate row while
        the schedule lives on the active row.

        This mirrors ``get_attendance_records_enriched`` so the Real-Time
        Attendance Log shows the same schedule the enriched grid does.

        Args:
            employee_id: DB employee id (may be None for orphans).
            reg_str: registration number string (used for the DAY_SCHEDULE
                override lookup and for the sibling fallback).
            target_date: ``date`` or ``"YYYY-MM-DD"`` string.
            punch_time: optional raw punch timestamp used to break ties when an
                employee has several schedules sharing the same effective_date.

        Returns:
            The matching WorkSchedule, or None if none applies.
        """
        if employee_id is None:
            return None

        if isinstance(target_date, str):
            try:
                target_date = datetime.strptime(target_date[:10], "%Y-%m-%d").date()
            except Exception:
                return None

        # Parse punch_time for the tie-break scoring.
        p_dt = None
        if punch_time:
            try:
                if "T" in punch_time:
                    p_dt = datetime.fromisoformat(punch_time.replace("Z", "+00:00"))
                else:
                    p_dt = datetime.strptime(punch_time[:19], "%Y-%m-%d %H:%M:%S")
            except Exception:
                p_dt = None

        date_str = target_date.isoformat()

        def _resolve(emp_id: int) -> Optional[WorkSchedule]:
            """Resolve a schedule for one employee row using grid-identical logic."""
            try:
                cands = self._get_day_schedules(emp_id, date_str, reg_str or "")
                if not cands:
                    return None
                if len(cands) == 1 or p_dt is None:
                    return cands[0]
                return self._pick_best_schedule(cands, [p_dt])
            except Exception as e:
                logger.warning(f"resolve_employee_schedule: resolution failed for emp_id={emp_id} date={target_date}: {e}")
                return None

        # 1. Resolve against the punch's own employee row.
        sched = _resolve(employee_id)
        if sched:
            return sched

        # 2. Fallback: a sibling row with the same registration number.
        #    Punches are sometimes linked to an archived duplicate row while the
        #    schedule was entered on the active row (same person, same reg).
        if reg_str:
            try:
                siblings = (
                    self.session.query(Employee)
                    .filter(Employee.registration_number == reg_str)
                    .filter(Employee.id != employee_id)
                    .all()
                )
                if siblings:
                    # Prefer non-archived rows, then rows with schedule
                    # assignments, then lowest id for stability.
                    sched_count = {
                        s.id: self.session.query(EmployeeSchedule).filter_by(employee_id=s.id).count()
                        for s in siblings
                    }
                    siblings.sort(
                        key=lambda s: (
                            bool(s.is_archived),
                            -sched_count.get(s.id, 0),
                            s.id,
                        )
                    )
                    for sib in siblings:
                        sib_sched = _resolve(sib.id)
                        if sib_sched:
                            return sib_sched
            except Exception as e:
                logger.warning(
                    f"resolve_employee_schedule: sibling fallback failed for emp_id={employee_id} reg={reg_str}: {e}"
                )

        return None

    def get_rotation_preview(self, rotation_id: int, start_date: date, days: int = 30) -> List[Dict[str, Any]]:
        """
        Generates a calendar preview showing which schedule falls on
        each day for the given rotation pattern.
        """
        from datetime import timedelta
        from sqlalchemy.orm import selectinload

        rotation = (
            self.session.query(ShiftRotation)
            .options(
                selectinload(ShiftRotation.slots)
                .selectinload(ShiftRotationSlot.schedule)
            )
            .get(rotation_id)
        )
        if not rotation:
            return []

        # Build offset→schedule lookup
        slot_map = {s.day_offset: s.schedule for s in rotation.slots}
        cycle_len = rotation.cycle_days or 1

        preview = []
        for i in range(days):
            d = start_date + timedelta(days=i)
            position = i % cycle_len
            sched = slot_map.get(position)
            preview.append({
                "date": d.isoformat(),
                "day_name": d.strftime("%a"),
                "day_offset": position,
                "schedule_name": sched.name if sched else "-",
                "schedule_time": f"{sched.start_time} → {sched.end_time}" if sched else "-",
                "color": sched.color_hex if sched else "#333333",
            })
        return preview

    def get_raw_attendance_detail(self, reg_number: str, iso_date: str) -> List[AttendanceRecord]:
        """Fetch raw punches from the DB for a given employee and logical date."""
        emp = self.session.query(Employee).filter(Employee.registration_number == reg_number).first()
        if not emp:
            return []
        
        # Load records for this employee within a 2-day window to cover night shift logic
        try:
            target_date = datetime.strptime(iso_date, "%Y-%m-%d").date()
        except Exception:
            return []
            
        start_str = (target_date - timedelta(days=1)).strftime("%Y-%m-%d")
        end_str = (target_date + timedelta(days=2)).strftime("%Y-%m-%d")
        
        records = (
            self.session.query(AttendanceRecord)
            .filter(AttendanceRecord.employee_id == emp.id)
            .filter(AttendanceRecord.punch_time >= start_str)
            .filter(AttendanceRecord.punch_time < end_str)
            .order_by(AttendanceRecord.punch_time.asc())
            .all()
        )
        
        # Filter precisely by logic date (night shift cutoff)
        NIGHT_CUTOFF_HOUR = 4
        matched_records = []
        for rec in records:
            try:
                pt = datetime.strptime(rec.punch_time[:19].replace('T', ' '), "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            
            logic_date = pt.date()
            if pt.hour < NIGHT_CUTOFF_HOUR:
                logic_date -= timedelta(days=1)
                
            if logic_date == target_date:
                matched_records.append(rec)
                
        return matched_records

    def guess_punch_type(self, punch_time: str, schedule: Optional[WorkSchedule] = None) -> tuple:
        """
        Guesses whether a punch is a check_in or check_out based on the schedule,
        or defaults to time of day if no schedule is active.
        Returns (inferred_type, details_str).
        """
        # Parse the punch time
        try:
            if "T" in punch_time:
                pt = datetime.fromisoformat(punch_time.replace('Z', '+00:00'))
            else:
                pt = datetime.strptime(punch_time[:19].replace('T', ' '), "%Y-%m-%d %H:%M:%S")
            p_time = pt.time()
        except Exception:
            return ("check_in", "")

        if not schedule:
            # Simple fallback: Before 12:00 (inclusive) is check_in, after is check_out
            if p_time.hour <= 12:
                return ("check_in", "(Default)")
            else:
                return ("check_out", "(Default)")

        # Helper to convert HH:MM to time object
        def parse_str_time(s):
            if not s or not s.strip():
                return None
            try:
                return datetime.strptime(s.strip(), "%H:%M").time()
            except Exception:
                return None

        # Try to match defined entry/sortie window ranges
        ent_start = parse_str_time(schedule.debut_pointage_entree)
        ent_end = parse_str_time(schedule.fin_pointage_entree)
        sor_start = parse_str_time(schedule.debut_pointage_sortie)
        sor_end = parse_str_time(schedule.fin_pointage_sortie)

        # Helper to check if time is within a window (handling midnight crossings)
        def is_in_window(t, start, end):
            if not start or not end:
                return False
            if start <= end:
                return start <= t <= end
            else:  # Crosses midnight
                return t >= start or t <= end

        in_ent = is_in_window(p_time, ent_start, ent_end)
        in_sor = is_in_window(p_time, sor_start, sor_end)

        if in_ent and not in_sor:
            return ("check_in", "")
        if in_sor and not in_ent:
            return ("check_out", "")

        # Proximity check as a fallback if it fits both or neither.
        # For split-shift schedules (break_start / break_end defined), we have 4 anchor points:
        #   check_in  anchors: start_time, break_end   (employee arrives at start or returns from break)
        #   check_out anchors: break_start, end_time   (employee leaves for break or leaves at end)
        # We pick the label whose nearest anchor is closest to the punch time.
        s_time = parse_str_time(schedule.start_time) or datetime.strptime("08:00", "%H:%M").time()
        e_time = parse_str_time(schedule.end_time) or datetime.strptime("17:00", "%H:%M").time()
        b_start = parse_str_time(getattr(schedule, "break_start", None))
        b_end   = parse_str_time(getattr(schedule, "break_end",   None))

        def time_diff_minutes(t1, t2):
            m1 = t1.hour * 60 + t1.minute
            m2 = t2.hour * 60 + t2.minute
            diff = abs(m1 - m2)
            return min(diff, 1440 - diff)

        if b_start and b_end:
            # Split-shift: 4 known event times
            # check_in  → nearest of (start_time, break_end)
            # check_out → nearest of (break_start, end_time)
            diff_in  = min(time_diff_minutes(p_time, s_time),
                           time_diff_minutes(p_time, b_end))
            diff_out = min(time_diff_minutes(p_time, b_start),
                           time_diff_minutes(p_time, e_time))
        else:
            # Simple single-session: compare against start vs end
            diff_in  = time_diff_minutes(p_time, s_time)
            diff_out = time_diff_minutes(p_time, e_time)

        if diff_in <= diff_out:
            return ("check_in", "")
        else:
            return ("check_out", "")

    def get_schedule_for_date(self, employee_id: int, target_date) -> Optional[WorkSchedule]:
        """
        Gets the active schedule for an employee on a given date.
        Checks daily schedule corrections first, then rotating shifts, then falls back to standard employee schedules.
        """
        try:
            if isinstance(target_date, str):
                target_date_str = target_date[:10]
            elif isinstance(target_date, datetime):
                target_date_str = target_date.strftime("%Y-%m-%d")
            else:
                target_date_str = target_date.strftime("%Y-%m-%d")
        except Exception:
            target_date_str = str(target_date)

        # 1. Check for daily schedule correction (override)
        from contragest.core.database import AttendanceCorrectionLog, WorkSchedule
        corr = self.session.query(AttendanceCorrectionLog).filter(
            ((AttendanceCorrectionLog.employee_id == employee_id) | (AttendanceCorrectionLog.reg_number == str(employee_id))),
            AttendanceCorrectionLog.shift_date == target_date_str,
            AttendanceCorrectionLog.issue_type == "DAY_SCHEDULE"
        ).first()
        if corr and corr.imputed_val:
            sched = self.session.query(WorkSchedule).filter_by(name=corr.imputed_val).first()
            if sched:
                return sched

        # 2. Resolve rotating shift if any
        sched = self.resolve_rotation_schedule(employee_id, target_date)
        if sched:
            return sched
            
        # Fall back to fixed schedule effective on or before target_date
        try:
            if isinstance(target_date, str):
                dt_obj = datetime.strptime(target_date[:10], "%Y-%m-%d").date()
            elif isinstance(target_date, datetime):
                dt_obj = target_date.date()
            else:
                dt_obj = target_date
        except Exception:
            return None
            
        from contragest.core.database import EmployeeSchedule
        assignment = (
            self.session.query(EmployeeSchedule)
            .filter(EmployeeSchedule.employee_id == employee_id)
            .filter(EmployeeSchedule.effective_date <= dt_obj)
            .order_by(EmployeeSchedule.effective_date.desc(), EmployeeSchedule.id.desc())
            .first()
        )
        return assignment.schedule if assignment else None

    def batch_recalculate(self, registration_number: str, start_date: str, end_date: str, admin_name: str = "SYSTEM") -> tuple:
        """
        Runs the batch recalculation scoring algorithm to align daily schedules with actual punches.
        Syncs enriched records to DailyAttendance.
        Returns (days_processed, corrections_made, summary_dict).
        """
        from contragest.core.database import Employee, WorkSchedule, AttendanceRecord
        from datetime import datetime, timedelta
        
        # 1. Fetch employee
        emp = self.session.query(Employee).filter(Employee.registration_number == registration_number).first()
        if not emp:
            try:
                emp = self.session.query(Employee).filter_by(id=int(registration_number)).first()
            except ValueError:
                pass
        if not emp:
            return (0, 0, {"error": "Employee not found"})

        # Get schedules assigned/defined for this employee (fixed and rotation)
        emp_schedules = []
        if emp.assignments:
            for assignment in emp.assignments:
                if assignment.schedule and assignment.schedule not in emp_schedules:
                    emp_schedules.append(assignment.schedule)
        active_rotation = self.get_employee_rotation(emp.id)
        if active_rotation and active_rotation.rotation:
            for slot in active_rotation.rotation.slots:
                if slot.schedule and slot.schedule not in emp_schedules:
                    emp_schedules.append(slot.schedule)
        if not emp_schedules:
            emp_schedules = self.get_all_schedules()

        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        except Exception as e:
            return (0, 0, {"error": f"Invalid date format: {e}"})

        range_days = (end_dt - start_dt).days + 1
        corrections_made = 0
        processed_days = 0
        summary = {"processed": [], "corrections": []}

        # Load all records for employee in range
        raw_records = (
            self.session.query(AttendanceRecord)
            .filter(AttendanceRecord.employee_id == emp.id)
            .filter(AttendanceRecord.punch_time >= start_dt.strftime("%Y-%m-%d"))
            .filter(AttendanceRecord.punch_time < (end_dt + timedelta(days=2)).strftime("%Y-%m-%d"))
            .order_by(AttendanceRecord.punch_time.asc())
            .all()
        )

        def parse_hm(s):
            if not s or not s.strip():
                return None
            try:
                return datetime.strptime(s.strip(), "%H:%M").time()
            except Exception:
                return None

        def time_diff(t1, t2):
            m1 = t1.hour * 60 + t1.minute
            m2 = t2.hour * 60 + t2.minute
            d = abs(m1 - m2)
            return min(d, 1440 - d)

        # Hoist the employee's default schedule outside the loop to avoid N queries
        default_sched = self.get_employee_schedule(emp.id)

        # Loop through each logical date
        for i in range(range_days):
            curr_date = start_dt + timedelta(days=i)
            curr_date_str = curr_date.strftime("%Y-%m-%d")

            NIGHT_CUTOFF_HOUR = 4
            day_punches = []
            for rec in raw_records:
                try:
                    pt = datetime.strptime(rec.punch_time[:19].replace('T', ' '), "%Y-%m-%d %H:%M:%S")
                except Exception:
                    continue
                logic_date = pt.date()
                if pt.hour < NIGHT_CUTOFF_HOUR:
                    logic_date -= timedelta(days=1)
                if logic_date == curr_date:
                    day_punches.append(pt.time())

            if not day_punches:
                continue

            processed_days += 1
            day_punches.sort()
            assigned_sched = self.get_schedule_for_date(emp.id, curr_date_str)

            best_cand = None
            lowest_score = float('inf')

            for sched in emp_schedules:
                score = 0
                
                s_time = parse_hm(sched.start_time)
                e_time = parse_hm(sched.end_time)
                bs_time = parse_hm(sched.break_start)
                be_time = parse_hm(sched.break_end)

                if s_time and e_time:
                    # Night/overlapping shift (end <= start) crosses midnight:
                    # the LAST punch of the logical day is the evening arrival and
                    # the FIRST punch is the morning departure. A single punch may
                    # be either; score against the closer anchor.
                    if e_time <= s_time:
                        if len(day_punches) >= 2:
                            score += time_diff(day_punches[-1], s_time)
                            score += time_diff(day_punches[0], e_time)
                        else:
                            score += min(time_diff(day_punches[0], s_time),
                                         time_diff(day_punches[0], e_time))
                    else:
                        score += time_diff(day_punches[0], s_time)
                        score += time_diff(day_punches[-1], e_time)

                    if bs_time and be_time and len(day_punches) >= 4:
                        score += time_diff(day_punches[1], bs_time)
                        score += time_diff(day_punches[2], be_time)

                if assigned_sched and sched.id == assigned_sched.id:
                    score -= 90

                if default_sched and sched.id == default_sched.id:
                    score -= 45

                if bs_time and be_time and len(day_punches) < 3:
                    score += 180

                if score < lowest_score:
                    lowest_score = score
                    best_cand = sched

            assigned_id = assigned_sched.id if assigned_sched else None
            assigned_name = assigned_sched.name if assigned_sched else "None"

            summary["processed"].append({
                "date": curr_date_str,
                "punches": len(day_punches),
                "assigned_schedule": assigned_name,
                "best_schedule": best_cand.name if best_cand else assigned_name,
                "score": lowest_score if best_cand else None
            })

            if best_cand and best_cand.id != assigned_id:
                summary["corrections"].append({
                    "date": curr_date_str,
                    "from": assigned_name,
                    "to": best_cand.name,
                    "score": lowest_score
                })
                if admin_name != "Audit_Simulation":
                    self.save_schedule_correction(
                        reg_number=registration_number,
                        shift_date=curr_date_str,
                        schedule_name=best_cand.name,
                        admin_name=admin_name
                    )
                corrections_made += 1

        enriched_records = self.get_attendance_records_enriched(
            reg_filter=registration_number,
            start_date=start_date,
            end_date=end_date
        )
        self.sync_attendance_to_db(enriched_records)

        return (processed_days, corrections_made, summary)
