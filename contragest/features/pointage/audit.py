"""
contragest/features/pointage/audit.py
======================================
Attendance Audit Module - detects, validates and reports missing check-in/out records.
Run automatically every morning via the BackgroundScheduler.
"""
import logging
from datetime import date, datetime, timedelta
from collections import Counter
from typing import List, Dict, Optional

logger = logging.getLogger("attendance_audit")


# ---------------------------------------------------------------------------
# 1. Data Identification
# ---------------------------------------------------------------------------

def find_missing_check_ins(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    reg_filter: Optional[str] = None,
    limit: int = 5000,
) -> List[Dict]:
    """
    Finds all bursts where Check-Out exists but Check-In is missing (-).
    Returns a list of anomaly dicts ready for logging or email.
    """
    from contragest.features.pointage.service import PointageService
    service = PointageService()
    try:
        records = service.get_attendance_records_enriched(
            start_date=start_date,
            end_date=end_date,
            reg_filter=reg_filter,
            limit=limit,
        )
        anomalies = []
        for r in records:
            if r["check_in"] == "-" and r["check_out"] != "-":
                anomalies.append({
                    "employee":    r["employee"],
                    "reg_number":  r["reg_number"],
                    "department":  r["department"],
                    "shift_date":  r["date"],
                    "check_out":   r["check_out"],
                    "issue_type":  "MISSING_CHECK_IN",
                    "machine":     r.get("machine", "-"),
                })
        return anomalies
    finally:
        service.close()


def find_missing_check_outs(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    reg_filter: Optional[str] = None,
    limit: int = 5000,
) -> List[Dict]:
    """
    Finds all bursts where Check-In exists but Check-Out is missing (-).
    """
    from contragest.features.pointage.service import PointageService
    service = PointageService()
    try:
        records = service.get_attendance_records_enriched(
            start_date=start_date,
            end_date=end_date,
            reg_filter=reg_filter,
            limit=limit,
        )
        anomalies = []
        for r in records:
            if r["check_out"] == "-" and r["check_in"] != "-":
                # Only flag if shift is "closed" (not today's ongoing shifts)
                today = date.today().isoformat()
                if r["date"] < today:
                    anomalies.append({
                        "employee":   r["employee"],
                        "reg_number": r["reg_number"],
                        "department": r["department"],
                        "shift_date": r["date"],
                        "check_in":   r["check_in"],
                        "issue_type": "MISSING_CHECK_OUT",
                        "machine":    r.get("machine", "-"),
                    })
        return anomalies
    finally:
        service.close()


# ---------------------------------------------------------------------------
# 2. Data Validation
# ---------------------------------------------------------------------------

def validate_attendance_integrity(start_date: str, end_date: str) -> Dict:
    """
    Full integrity report for a date range.
    Returns department-breakdown, repeat offenders and summary counts.
    """
    missing_in  = find_missing_check_ins(start_date, end_date)
    missing_out = find_missing_check_outs(start_date, end_date)
    all_issues  = missing_in + missing_out

    emp_counts  = Counter(r["reg_number"] for r in all_issues)
    dept_counts = Counter(r["department"] for r in all_issues)

    report = {
        "range":               f"{start_date} → {end_date}",
        "total_missing_in":    len(missing_in),
        "total_missing_out":   len(missing_out),
        "total_anomalies":     len(all_issues),
        "by_department":       dict(dept_counts.most_common()),
        "repeated_offenders":  {reg: cnt for reg, cnt in emp_counts.items() if cnt > 2},
        "details":             all_issues,
    }
    return report


# ---------------------------------------------------------------------------
# 3. Error Logging & Alerts
# ---------------------------------------------------------------------------

def _send_alert_email(anomalies: List[Dict], date_label: str):
    """Sends an email alert using the existing AppConfig SMTP settings."""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from contragest.core.database import SessionLocal, AppConfig

        session = SessionLocal()
        try:
            cfg = session.query(AppConfig).first()
            if not cfg or not cfg.notification_email or not cfg.smtp_user:
                return
        finally:
            session.close()

        lines = [
            f"  • REG {a['reg_number']:>6}  {a['employee']:<30}  "
            f"({a['department']:<25})  {a['issue_type']}"
            for a in anomalies
        ]
        body = (
            f"Attendance Audit Report - {date_label}\n"
            f"{'='*60}\n\n"
            f"Total anomalies found: {len(anomalies)}\n\n"
            f"Details:\n" + "\n".join(lines) +
            f"\n\n{'='*60}\n"
            f"This is an automated message from Contragest.\n"
            f"Missing check-ins should be reviewed and corrected.\n"
        )
        msg = MIMEMultipart()
        msg["From"]    = cfg.smtp_user
        msg["To"]      = cfg.notification_email
        msg["Subject"] = f"[Contragest] ⚠ {len(anomalies)} Missing Attendance Punches - {date_label}"
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(cfg.smtp_server, cfg.smtp_port) as server:
            if cfg.smtp_ssl_verify:
                server.starttls()
            server.login(cfg.smtp_user, cfg.smtp_password)
            server.sendmail(cfg.smtp_user, cfg.notification_email, msg.as_string())

        logger.info(f"[AUDIT] Alert email sent to {cfg.notification_email} for {date_label}.")
    except Exception as e:
        logger.warning(f"[AUDIT] Could not send alert email: {e}")


def run_daily_audit_and_alert(target_date: Optional[str] = None, is_automated: bool = False):
    """
    Entry point called by BackgroundScheduler every morning at 06:30.
    1. Scans yesterday's attendance for missing punches.
    2. Logs each anomaly.
    3. Writes them to AttendanceCorrectionLog (as PENDING entries).
    4. Sends email alert if configured.
    """
    from contragest.core.database import SessionLocal, AppConfig
    
    if not target_date:
        target_date = (date.today() - timedelta(days=1)).isoformat()

    logger.info(f"[AUDIT] Running daily audit for {target_date} ...")

    missing_in  = find_missing_check_ins(start_date=target_date, end_date=target_date)
    missing_out = find_missing_check_outs(start_date=target_date, end_date=target_date)
    all_issues  = missing_in + missing_out

    if not all_issues:
        logger.info(f"[AUDIT] {target_date}: No anomalies. ✓")
        if is_automated:
            _update_last_audit_state()
        return

    # Log each anomaly
    for a in all_issues:
        logger.warning(
            f"[AUDIT] {a['issue_type']} | {a['shift_date']} | "
            f"REG {a['reg_number']:>6} {a['employee']} | Dept: {a['department']}"
        )

    # Persist to DB (as PENDING entries for corrector to resolve)
    _persist_anomalies_to_db(all_issues)

    # Balloon notification via the tray agent (works even when the app is
    # closed to the tray)
    _notify_tray_anomalies(all_issues, target_date)

    # Email alert
    _send_alert_email(all_issues, target_date)
    
    if is_automated:
        _update_last_audit_state()
        
    logger.info(f"[AUDIT] Audit complete: {len(all_issues)} anomalies logged for {target_date}.")


def _notify_tray_anomalies(anomalies: List[Dict], target_date: str):
    """Writes a summary notification event for the tray agent to display.

    One summary event per audited date (dedup key ``ATTENDANCE:<date>``) so
    the desktop app and the service, which can both run the audit, never
    produce duplicate balloons.
    """
    try:
        from contragest.logic.notifications import NotificationFeed

        missing_in  = sum(1 for a in anomalies if a["issue_type"] == "MISSING_CHECK_IN")
        missing_out = sum(1 for a in anomalies if a["issue_type"] == "MISSING_CHECK_OUT")

        parts = []
        if missing_in:
            parts.append(f"{missing_in} check-in manquant(s)")
        if missing_out:
            parts.append(f"{missing_out} check-out manquant(s)")

        examples = [f"REG {a['reg_number']} {a['employee']}" for a in anomalies[:3]]
        detail = ", ".join(examples)
        if len(anomalies) > 3:
            detail += f" (+{len(anomalies) - 3} autres)"

        NotificationFeed().append(
            "ATTENDANCE",
            "Pointage — anomalies détectées",
            f"{target_date} : " + ", ".join(parts) + ". " + detail,
            dedup_key=f"ATTENDANCE:{target_date}",
        )
    except Exception as e:  # never break the audit on notification errors
        logger.warning(f"[AUDIT] Could not notify tray: {e}")


def _update_last_audit_state():
    """Sets today's date in AppConfig.last_audit_date to mark completion."""
    from contragest.core.database import SessionLocal, AppConfig
    session = SessionLocal()
    try:
        cfg = session.query(AppConfig).first()
        if cfg:
            cfg.last_audit_date = date.today()
            session.commit()
    except Exception as e:
        logger.warning(f"[AUDIT] Could not update last_audit_date: {e}")
    finally:
        session.close()


def _persist_anomalies_to_db(anomalies: List[Dict]):
    """Writes each anomaly as a PENDING row in AttendanceCorrectionLog."""
    from contragest.core.database import SessionLocal, AttendanceCorrectionLog, Employee
    session = SessionLocal()
    try:
        for a in anomalies:
            # Avoid duplicates - skip if already logged
            existing = (
                session.query(AttendanceCorrectionLog)
                .filter_by(reg_number=a["reg_number"], shift_date=a["shift_date"], issue_type=a["issue_type"])
                .first()
            )
            if existing:
                continue

            emp = session.query(Employee).filter_by(registration_number=a["reg_number"]).first()
            entry = AttendanceCorrectionLog(
                employee_id  = emp.id if emp else None,
                reg_number   = a["reg_number"],
                shift_date   = a["shift_date"],
                issue_type   = a["issue_type"],
                original_val  = None,
                imputed_val   = None,
                strategy      = "PENDING",
                corrected_by  = "SYSTEM",
                corrected_at  = datetime.now().isoformat(),
                notes         = f"Auto-detected. Check-Out: {a.get('check_out', a.get('check_in', '-'))}",
            )
            session.add(entry)
        session.commit()
    except Exception as e:
        logger.warning(f"[AUDIT] DB persist error: {e}")
        session.rollback()
    finally:
        session.close()
