"""
contragest/features/pointage/corrector.py
==========================================
Attendance Correction Module - imputes missing punches using schedule / history data.
Corrections are written to AttendanceCorrectionLog; raw machine records are never modified.
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional

logger = logging.getLogger("attendance_corrector")


# ---------------------------------------------------------------------------
# Core imputation engine
# ---------------------------------------------------------------------------

def impute_check_in(reg_number: str, shift_date: str) -> Optional[str]:
    """
    Attempts to impute a missing check-in timestamp using a tiered strategy:
      1. Employee's assigned schedule start_time  (most authoritative)
      2. Median check-in time over the last 30 working days
      3. Returns None if insufficient data

    Returns an ISO-formatted timestamp string like '2026-03-07 23:00:00'
    (without the [IMPUTED-*] tag - that lives in the strategy column).
    """
    from contragest.core.database import SessionLocal, Employee, EmployeeSchedule, AttendanceRecord

    session = SessionLocal()
    try:
        emp = session.query(Employee).filter_by(registration_number=reg_number).first()
        if not emp:
            return None, None

        # --- Strategy 1: Schedule start_time ---
        assignment = (
            session.query(EmployeeSchedule)
            .filter_by(employee_id=emp.id)
            .order_by(EmployeeSchedule.effective_date.desc(), EmployeeSchedule.id.desc())
            .first()
        )
        if assignment and assignment.schedule:
            s_time = assignment.schedule.start_time  # e.g. "23:00"
            try:
                h, m = map(int, s_time.split(":")[:2])
                return f"{shift_date} {h:02d}:{m:02d}:00", "SCHEDULE"
            except Exception:
                pass

        # --- Strategy 2: Median of last-30-day check-ins ---
        cutoff = (datetime.strptime(shift_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
        history = (
            session.query(AttendanceRecord)
            .filter(
                AttendanceRecord.employee_id == emp.id,
                AttendanceRecord.punch_time >= cutoff,
                AttendanceRecord.punch_time < shift_date,
            )
            .order_by(AttendanceRecord.punch_time.asc())
            .all()
        )

        # Collect check-in candidates: punches before 14:00 (entry-like)
        morning_punches = []
        for r in history:
            try:
                dt = datetime.fromisoformat(r.punch_time.replace("Z", "+00:00"))
                if dt.hour < 14:
                    morning_punches.append(dt.hour * 60 + dt.minute)
            except Exception:
                continue

        if morning_punches:
            morning_punches.sort()
            median_min = morning_punches[len(morning_punches) // 2]
            h, m = divmod(median_min, 60)
            return f"{shift_date} {h:02d}:{m:02d}:00", "HISTORY"

        return None, None
    finally:
        session.close()


def impute_check_out(reg_number: str, shift_date: str) -> Optional[str]:
    """
    Attempts to impute a missing check-out timestamp using:
      1. Schedule end_time
      2. Median of last-30-day check-outs
    """
    from contragest.core.database import SessionLocal, Employee, EmployeeSchedule, AttendanceRecord

    session = SessionLocal()
    try:
        emp = session.query(Employee).filter_by(registration_number=reg_number).first()
        if not emp:
            return None, None

        assignment = (
            session.query(EmployeeSchedule)
            .filter_by(employee_id=emp.id)
            .order_by(EmployeeSchedule.effective_date.desc(), EmployeeSchedule.id.desc())
            .first()
        )
        if assignment and assignment.schedule:
            e_time = assignment.schedule.end_time
            try:
                h, m = map(int, e_time.split(":")[:2])
                return f"{shift_date} {h:02d}:{m:02d}:00", "SCHEDULE"
            except Exception:
                pass

        cutoff = (datetime.strptime(shift_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
        history = (
            session.query(AttendanceRecord)
            .filter(
                AttendanceRecord.employee_id == emp.id,
                AttendanceRecord.punch_time >= cutoff,
                AttendanceRecord.punch_time < shift_date,
            )
            .order_by(AttendanceRecord.punch_time.asc())
            .all()
        )

        evening_punches = []
        for r in history:
            try:
                dt = datetime.fromisoformat(r.punch_time.replace("Z", "+00:00"))
                if dt.hour >= 14:
                    evening_punches.append(dt.hour * 60 + dt.minute)
            except Exception:
                continue

        if evening_punches:
            evening_punches.sort()
            median_min = evening_punches[len(evening_punches) // 2]
            h, m = divmod(median_min, 60)
            return f"{shift_date} {h:02d}:{m:02d}:00", "HISTORY"

        return None, None
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Batch apply corrections for all PENDING log entries
# ---------------------------------------------------------------------------

def apply_corrections(corrected_by: str = "SYSTEM", is_automated: bool = False) -> int:
    """
    Processes all PENDING entries in AttendanceCorrectionLog.
    Attempts imputation and updates each entry with the result.
    Returns the count of successfully imputed records.
    """
    from contragest.core.database import SessionLocal, AttendanceCorrectionLog, AppConfig

    session = SessionLocal()
    count = 0
    try:
        pending = (
            session.query(AttendanceCorrectionLog)
            .filter_by(strategy="PENDING")
            .all()
        )
        logger.info(f"[CORRECTOR] Processing {len(pending)} pending correction(s).")

        for entry in pending:
            try:
                if entry.issue_type == "MISSING_CHECK_IN":
                    result, strategy = impute_check_in(entry.reg_number, entry.shift_date)
                else:
                    result, strategy = impute_check_out(entry.reg_number, entry.shift_date)

                if result:
                    entry.imputed_val  = result
                    entry.strategy     = strategy
                    entry.corrected_by = corrected_by
                    entry.corrected_at = datetime.now().isoformat()
                    entry.notes        = (entry.notes or "") + f" | Imputed via {strategy}"
                    count += 1
                    logger.info(
                        f"[CORRECTOR] ✓ REG {entry.reg_number} | {entry.shift_date} | "
                        f"{entry.issue_type} → {result} ({strategy})"
                    )
                else:
                    entry.strategy = "UNRESOLVED"
                    entry.notes    = (entry.notes or "") + " | No data for imputation."
                    logger.warning(
                        f"[CORRECTOR] ✗ REG {entry.reg_number} | {entry.shift_date} | "
                        f"Could not impute."
                    )
            except Exception as e:
                logger.error(f"[CORRECTOR] Error processing entry {entry.id}: {e}")

        session.commit()
        
        if is_automated:
            _update_last_correction_state()
            
    except Exception as e:
        logger.error(f"[CORRECTOR] Batch error: {e}")
        session.rollback()
    finally:
        session.close()

    logger.info(f"[CORRECTOR] Done. {count} record(s) imputed.")
    return count


def _update_last_correction_state():
    """Sets today's date in AppConfig.last_correction_date to mark completion."""
    from contragest.core.database import SessionLocal, AppConfig
    session = SessionLocal()
    try:
        from datetime import date
        cfg = session.query(AppConfig).first()
        if cfg:
            cfg.last_correction_date = date.today()
            session.commit()
    except Exception as e:
        logger.warning(f"[CORRECTOR] Could not update last_correction_date: {e}")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Manual override (HR user sets the check-in/out explicitly)
# ---------------------------------------------------------------------------

def manual_correction(
    reg_number: str,
    shift_date: str,
    issue_type: str,
    corrected_value: str,
    corrected_by: str,
    notes: str = "",
) -> bool:
    """
    Records a manual HR correction in AttendanceCorrectionLog.
    Used from the UI when a supervisor knows the actual time.
    """
    from contragest.core.database import SessionLocal, AttendanceCorrectionLog, Employee

    session = SessionLocal()
    try:
        emp = session.query(Employee).filter_by(registration_number=reg_number).first()

        # Guard: Reject manual punch corrections after employee's exit date
        # (Allow deletions / empty values — those are still permitted for cleanup)
        if emp and emp.exit_date and corrected_value and corrected_value.strip():
            try:
                from datetime import date as _date
                shift_date_obj = _date.fromisoformat(shift_date[:10])
                if shift_date_obj > emp.exit_date:
                    logger.warning(
                        f"[CORRECTOR] Blocked manual correction for REG {reg_number} on {shift_date} "
                        f"(after exit date {emp.exit_date})"
                    )
                    return False
            except Exception:
                pass  # If date parsing fails, allow through rather than blocking

        # Update existing entry if present
        existing = (
            session.query(AttendanceCorrectionLog)
            .filter_by(reg_number=reg_number, shift_date=shift_date, issue_type=issue_type)
            .first()
        )
        if existing:
            existing.imputed_val  = corrected_value
            existing.strategy     = "MANUAL"
            existing.corrected_by = corrected_by
            existing.corrected_at = datetime.now().isoformat()
            existing.notes        = notes
        else:
            entry = AttendanceCorrectionLog(
                employee_id   = emp.id if emp else None,
                reg_number    = reg_number,
                shift_date    = shift_date,
                issue_type    = issue_type,
                original_val  = None,
                imputed_val   = corrected_value,
                strategy      = "MANUAL",
                corrected_by  = corrected_by,
                corrected_at  = datetime.now().isoformat(),
                notes         = notes,
            )
            session.add(entry)
        session.commit()
        logger.info(f"[CORRECTOR] Manual override: REG {reg_number} | {shift_date} | {issue_type} → {corrected_value}")
        return True
    except Exception as e:
        logger.error(f"[CORRECTOR] Manual correction error: {e}")
        session.rollback()
        return False
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Query: get imputed value for a given shift to display in UI
# ---------------------------------------------------------------------------

def get_imputed_value(reg_number: str, shift_date: str, issue_type: str) -> Optional[str]:
    """
    Returns the imputed/corrected value for a shift, if one exists.
    Used by the enriched view to show corrected times in the UI.
    """
    from contragest.core.database import SessionLocal, AttendanceCorrectionLog
    session = SessionLocal()
    try:
        entry = (
            session.query(AttendanceCorrectionLog)
            .filter_by(reg_number=reg_number, shift_date=shift_date, issue_type=issue_type)
            .filter(AttendanceCorrectionLog.strategy != "PENDING")
            .order_by(AttendanceCorrectionLog.corrected_at.desc())
            .first()
        )
        if entry and entry.imputed_val:
            raw = entry.imputed_val
            # Return just the HH:MM:SS portion for display
            parts = raw.strip().split()
            return parts[1][:8] if len(parts) > 1 else raw[:8]
        return None
    finally:
        session.close()
