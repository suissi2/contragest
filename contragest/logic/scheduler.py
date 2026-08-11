import threading
import time
from datetime import datetime, timedelta
from contragest.core.database import SessionLocal, AppConfig
from contragest.logic.alerts import AlertManager
from contragest.core.system_info import get_location_and_weather

# Audit times
_AUDIT_HOUR   = 6
_AUDIT_MINUTE = 30
_CORR_MINUTE  = 35  # corrector runs 5 min after audit

class BackgroundScheduler:
    def __init__(self, ui_callback_info=None, ui_callback_alert=None):
        """
        :param ui_callback_info: function(location, temp) to update status bar
        :param ui_callback_alert: function(count, success) to show Messagebox
        """
        self.ui_callback_info = ui_callback_info
        self.ui_callback_alert = ui_callback_alert
        self.running = False
        self.thread = None
        self._last_env_check = 0
        self.env_interval = 900  # 15 minutes
        self._audit_done_today = None  # date string of last audit
        self._corr_done_today  = None  # date string of last auto-correction
        self._clock_sync_done_today = None
        self._startup_sync_done = False   # fire once on first run regardless of hour
        self._reboot_done_today = {}      # machine_id -> date string


    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        print("DEBUG: BackgroundScheduler started.")

    def stop(self):
        self.running = False

    def _run(self):
        while self.running:
            now = datetime.now()
            
            # 1. Check Scheduled Alerts (High Precision)
            self._check_alerts(now)

            # 2. Daily Attendance Audit (06:30) and Auto-Correction (06:35)
            self._check_attendance_audit(now)

            # 3. Daily Automatic Clock Sync (06:15)
            self._sync_clocks_daily(now)

            # 4. Automatic Machine Reboot is disabled — manual only via the REBOOT button
            
            # 5. Check Environmental Data (Periodic)
            if time.time() - self._last_env_check > self.env_interval:
                self._update_environmental_data()
                self._last_env_check = time.time()

            # High-resolution sleep for precision
            time.sleep(1)

    def _check_attendance_audit(self, now):
        """Runs the daily attendance audit at 06:30 and auto-correction at 06:35."""
        today_str = now.strftime("%Y-%m-%d")
        
        # 1. Quick memory-only exit
        if self._audit_done_today == today_str and getattr(self, '_corr_done_today', None) == today_str:
            return

        # 2. Time-window exit (Reduce check frequency to once per minute or when in window)
        is_audit_minute = (now.hour == _AUDIT_HOUR and now.minute == _AUDIT_MINUTE)
        is_corr_minute = (now.hour == _AUDIT_HOUR and now.minute == _CORR_MINUTE)
        
        if not is_audit_minute and not is_corr_minute:
             return

        # 3. DB Check
        session = SessionLocal()
        try:
            config = session.query(AppConfig).first()
            if not config:
                return

            today_date = now.date()

            # Audit at 06:30
            if is_audit_minute and config.last_audit_date != today_date and self._audit_done_today != today_str:
                try:
                    print(f"DEBUG: Running automated daily attendance audit (Today: {today_str})...")
                    from contragest.features.pointage.audit import run_daily_audit_and_alert
                    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
                    run_daily_audit_and_alert(target_date=yesterday, is_automated=True)
                    self._audit_done_today = today_str
                except Exception as e:
                    print(f"ERROR in attendance audit: {e}")

            # Corrector at 06:35
            if is_corr_minute and config.last_correction_date != today_date and getattr(self, '_corr_done_today', None) != today_str:
                try:
                    print(f"DEBUG: Running automated attendance auto-correction (Today: {today_str})...")
                    from contragest.features.pointage.corrector import apply_corrections
                    count = apply_corrections(corrected_by="SYSTEM", is_automated=True)
                    print(f"DEBUG: Auto-correction complete: {count} record(s) imputed.")
                    self._corr_done_today = today_str
                except Exception as e:
                    print(f"ERROR in attendance corrector: {e}")
        except Exception as e:
            err_msg = str(e).lower()
            print(f"ERROR in background scheduler DB access (audit): {e}")
            if "disk i/o error" in err_msg or "database is locked" in err_msg:
                time.sleep(30)
        finally:
            session.close()

    def _check_alerts(self, now):
        # Optimization: Only check alerts at the start of a minute to avoid DB hammering
        if now.second != 0:
            return

        session = SessionLocal()
        try:
            config = session.query(AppConfig).first()
            if not config or not config.automatic_alerts_enabled:
                return

            today_date = now.date()
            
            # Check if an alert was already sent today
            if config.last_alert_date == today_date:
                # Precise trigger logging
                try:
                    alert_time = datetime.strptime(config.alert_time, "%H:%M").time()
                    if now.hour == alert_time.hour and now.minute == alert_time.minute:
                        print(f"DEBUG: Alert already sent today ({today_date}). Skipping scheduled trigger.")
                except:
                    pass
                return

            # Check if the current time is at or after the scheduled alert time
            try:
                alert_time = datetime.strptime(config.alert_time, "%H:%M").time()
                scheduled_datetime = datetime.combine(today_date, alert_time)
                
                if now >= scheduled_datetime:
                    print(f"DEBUG: Background thread triggering EXACT alert (Scheduled: {config.alert_time}, Now: {now.strftime('%H:%M:%S')})")
                    alert_manager = AlertManager()
                    count, sent_success = alert_manager.check_and_notify(is_automated=True)
                    
                    if count > 0 and self.ui_callback_alert:
                        self.ui_callback_alert(count, sent_success)
            except Exception as e:
                print(f"ERROR in background alert check: {e}")
        except Exception as e:
            err_msg = str(e).lower()
            print(f"ERROR in background scheduler DB access (alerts): {e}")
            if "disk i/o error" in err_msg or "database is locked" in err_msg:
                time.sleep(30) # Backoff for network/locking issues
        finally:
            session.close()

    def _update_environmental_data(self):
        try:
            print("DEBUG: Background thread updating environmental data...")
            location, temp = get_location_and_weather()
            if self.ui_callback_info:
                self.ui_callback_info(location, temp)
        except Exception as e:
            print(f"ERROR in background env update: {e}")

    def _sync_clocks_daily(self, now):
        """Synchronizes all active machines' clocks to PC local time.

        Fires:
          • Once on startup (within the first 30 s of the thread running),
            regardless of the time of day — catches restarts after 06:15.
          • Every day after 06:15 local time if not yet done today.

        Uses local naïve datetimes to match the ZK protocol (machines never
        carry timezone information in their time responses).
        """
        today_str = now.strftime("%Y-%m-%d")

        # Determine whether we should run:
        #   (a) Startup pass — fire once regardless of hour
        #   (b) Daily window — any time at/after 06:15 if not done today
        startup_needed = not self._startup_sync_done
        daily_needed = (
            self._clock_sync_done_today != today_str
            and (now.hour > 6 or (now.hour == 6 and now.minute >= 15))
        )

        if not startup_needed and not daily_needed:
            return

        trigger = "Startup" if startup_needed else "Daily (06:15 window)"

        session = SessionLocal()
        try:
            print(f"DEBUG: Running automated clock synchronization [{trigger}] (Today: {today_str})...")
            from contragest.features.pointage.service import PointageService
            from contragest.core.database import AttendanceMachine
            svc = PointageService(session)
            machines = session.query(AttendanceMachine).filter_by(is_active=True).all()
            for m in machines:
                try:
                    res = svc.sync_machine_time(m.id)
                    status_icon = "✅" if res.get("success") else "❌"
                    pc_t = res.get("pc_time_iso", "")
                    mach_t = res.get("machine_time_iso", "")
                    detail = res.get("message", "No message")
                    if res.get("synced"):
                        detail += " (synced)"

                    # Format log detail with local time strings
                    if pc_t and mach_t:
                        try:
                            # pc_time_iso and machine_time_iso are now both
                            # naïve-local ISO strings (no +HH:MM suffix)
                            pc_time_str = pc_t.split("T")[1][:8]
                            mach_time_str = mach_t.split("T")[1][:8]
                            detail = f"Clock={mach_time_str} | PC={pc_time_str} | {detail}"
                        except Exception:
                            pass

                    # Log using the pointage_service logger
                    from contragest.core.logging import setup_logger
                    logger = setup_logger("pointage_service")
                    logger.info(f"Auto-Sync Time [{trigger}] - {status_icon} {m.name}: {detail}")
                except Exception as ex:
                    print(f"ERROR syncing clock for machine {m.name}: {ex}")

            # Mark both flags to avoid double-firing
            self._startup_sync_done = True
            self._clock_sync_done_today = today_str
        except Exception as e:
            print(f"ERROR in clock synchronization scheduler: {e}")
        finally:
            session.close()

    def _check_auto_reboot(self, now):
        """Check machines at startup and reboot if their configured time has passed today.

        Runs ONCE at application startup (not polled every minute).
        If the configured auto_reboot_time has already passed today, the machine
        reboots now as a catch-up. Subsequent startup checks within the same day
        are skipped via _reboot_done_today.
        """
        today_str = now.strftime("%Y-%m-%d")
        session = SessionLocal()
        try:
            from contragest.features.pointage.service import PointageService
            from contragest.core.database import AttendanceMachine
            svc = PointageService(session)
            machines = session.query(AttendanceMachine).filter_by(
                is_active=True, auto_reboot_enabled=True).all()
            if not machines:
                return
            for m in machines:
                if self._reboot_done_today.get(m.id) == today_str:
                    continue
                reboot_time = m.auto_reboot_time or "03:00"
                try:
                    target_hour, target_min = map(int, reboot_time.split(":"))
                    # Reboot if current time >= configured time
                    if now.hour > target_hour or (now.hour == target_hour and now.minute >= target_min):
                        print(f"Auto-rebooting machine '{m.name}' ({m.ip_address}) — scheduled {reboot_time}, now {now.strftime('%H:%M')}")
                        res = svc.reboot_machine(m.id)
                        status_icon = "✅" if res.get("success") else "❌"
                        detail = res.get("message", "No message")
                        from contragest.core.logging import setup_logger
                        logger = setup_logger("pointage_service")
                        logger.info(f"Auto-Reboot - {status_icon} {m.name}: {detail}")
                        self._reboot_done_today[m.id] = today_str
                except Exception as ex:
                    print(f"ERROR auto-rebooting machine {m.name}: {ex}")
                    self._reboot_done_today[m.id] = today_str
        except Exception as e:
            print(f"ERROR in auto-reboot scheduler: {e}")
        finally:
            session.close()

