import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from contragest.core.database import SessionLocal, AppConfig
from contragest.core.email_service import EmailService

def mask_password(pwd):
    if not pwd:
        return "Not Set"
    if len(pwd) <= 4:
        return "****"
    return pwd[:2] + "****" + pwd[-2:]

def diagnose_email():
    session = SessionLocal()
    try:
        config = session.query(AppConfig).first()
        if not config:
            print("ERROR: No AppConfig found in database.")
            return

        print("--- SMTP Configuration ---")
        print(f"Server: {config.smtp_server}")
        print(f"Port: {config.smtp_port}")
        print(f"User: {config.smtp_user}")
        print(f"Password: {mask_password(config.smtp_password)}")
        print(f"SSL Verify: {config.smtp_ssl_verify}")
        print(f"Notification Email: {config.notification_email}")
        print(f"Auto Alerts Enabled: {config.automatic_alerts_enabled}")
        print(f"Alert Threshold Days: {config.alert_threshold_days}")
        print(f"Last Alert Date (Before Reset): {config.last_alert_date}")
        
        # RESET logic for testing
        from datetime import datetime, timedelta
        yesterday = (datetime.now() - timedelta(days=1)).date()
        config.last_alert_date = yesterday
        session.commit()
        print(f"Last Alert Date (Reset to): {config.last_alert_date}")
        
        print("--------------------------")

        # Check for expiring contracts
        threshold_days = config.alert_threshold_days
        from datetime import datetime, timedelta
        target_date = datetime.now().date() + timedelta(days=threshold_days)
        today = datetime.now().date()
        
        from contragest.core.database import Contract
        expiring_contracts = session.query(Contract).filter(
            Contract.end_date != None,
            Contract.end_date <= target_date,
            Contract.end_date >= today
        ).all()
        
        print(f"\nFound {len(expiring_contracts)} expiring contracts between {today} and {target_date}.")
        for c in expiring_contracts:
            print(f" - {c.employee.first_name} {c.employee.last_name}: Ends {c.end_date}")

        if not config.smtp_server or not config.smtp_user or not config.smtp_password:
            print("FAILURE: Missing required SMTP configuration.")
            return

        service = EmailService(config)
        print("\nTesting Connection...")
        success, msg = service.test_connection()
        if success:
            print("SUCCESS: Connection and Authentication working.")
        else:
            print(f"FAILURE: Connection/Auth failed: {msg}")
            return

        print("\nAttempting to send test email...")
        recipient = config.notification_email
        if not recipient:
            print("WARNING: No notification email configured. using smtp_user as recipient.")
            recipient = config.smtp_user

        success, msg = service.send_email(
            subject="Contragest Diagnostic Test",
            body="<h1>Test Email</h1><p>This is a diagnostic email from Contragest.</p>",
            recipient=recipient
        )
        
        if success:
            print(f"SUCCESS: Email sent to {recipient}.")
        else:
            print(f"FAILURE: Email sending failed: {msg}")

    except Exception as e:
        print(f"EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    diagnose_email()
