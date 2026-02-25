import threading
import time
from datetime import datetime, timedelta
from contragest.core.database import SessionLocal, AppConfig
from contragest.logic.alerts import AlertManager
from contragest.core.system_info import get_location_and_weather

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
            
            # 2. Check Environmental Data (Periodic)
            if time.time() - self._last_env_check > self.env_interval:
                self._update_environmental_data()
                self._last_env_check = time.time()

            # High-resolution sleep for precision
            time.sleep(1)

    def _check_alerts(self, now):
        try:
            session = SessionLocal()
            config = session.query(AppConfig).first()
            if not config or not config.automatic_alerts_enabled:
                session.close()
                return

            today_date = now.date()
            
            # Check if an alert was already sent today
            if config.last_alert_date == today_date:
                # We skip log spam every second, but helpful if we are at the scheduled time
                try:
                    alert_time = datetime.strptime(config.alert_time, "%H:%M").time()
                    if now.hour == alert_time.hour and now.minute == alert_time.minute and now.second == 0:
                        print(f"DEBUG: Alert already sent today ({today_date}). Skipping scheduled trigger.")
                except:
                    pass
                session.close()
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
                        # Schedule UI update on the main thread
                        self.ui_callback_alert(count, sent_success)
                    
            except Exception as e:
                print(f"ERROR in background alert check: {e}")
            finally:
                session.close()
        except Exception as e:
            print(f"ERROR in background scheduler DB access: {e}")

    def _update_environmental_data(self):
        try:
            print("DEBUG: Background thread updating environmental data...")
            location, temp = get_location_and_weather()
            if self.ui_callback_info:
                self.ui_callback_info(location, temp)
        except Exception as e:
            print(f"ERROR in background env update: {e}")
