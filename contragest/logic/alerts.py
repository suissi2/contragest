import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from contragest.core.database import SessionLocal, Contract, Employee, AppConfig
from contragest.core.logging import setup_logger

logger = setup_logger("alerts")

from contragest.core.email_manager import EmailManager
from contragest.core.email_templates import EmailTemplateManager

class AlertManager:
    def check_and_notify(self, is_automated=False):
        """
        Checks for contracts expiring within 15 days or already expired.
        Sends a professional consolidated email if any are found.
        """
        session = SessionLocal()
        try:
            config = session.query(AppConfig).first()
            if not config:
                logger.error("AppConfig not found during check_and_notify")
                return 0, False

            today = datetime.now().date()
            target_date = today + timedelta(days=15)
            
            logger.info(f"Starting alert check. TODAY={today}, TARGET_15D={target_date}")

            # 1. Expiring soon (Today to Today+15)
            expiring = session.query(Contract).filter(
                Contract.end_date != None,
                Contract.end_date >= today,
                Contract.end_date <= target_date
            ).all()

            # 2. Already Expired (Before Today)
            expired = session.query(Contract).filter(
                Contract.end_date != None,
                Contract.end_date < today
            ).all()

            total_found = len(expiring) + len(expired)
            logger.info(f"Found {len(expiring)} expiring and {len(expired)} expired contracts.")

            success = False
            if total_found > 0:
                success = self._send_alert_email(config, expiring, expired)
            
            if is_automated:
                if total_found == 0 or success:
                    config.last_alert_date = today
                    session.commit()
                    logger.info(f"Automated check complete. Recorded last_alert_date={today}")
            
            return total_found, success
        except Exception as e:
            logger.error(f"Error in check_and_notify: {e}", exc_info=True)
            return 0, False
        finally:
            session.close()

    def _send_alert_email(self, config, expiring, expired):
        sections_html = ""
        
        # Helper to build table rows
        def build_table(contracts, section_name, status_class, status_label):
            if not contracts:
                return ""
            
            html = f"""
            <div class="section-title section-{section_name.lower()}">{section_name}</div>
            <table>
                <thead>
                    <tr>
                        <th>Contract ID</th>
                        <th>Client/Employee Name</th>
                        <th>Expiration Date</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
            """
            for c in contracts:
                name = f"{c.employee.first_name} {c.employee.last_name}"
                html += f"""
                <tr>
                    <td>#{c.id}</td>
                    <td><strong>{name}</strong></td>
                    <td>{c.end_date}</td>
                    <td><span class="status-pill {status_class}">{status_label}</span></td>
                </tr>
                """
            html += "</tbody></table>"
            return html

        sections_html += build_table(expired, "Already Expired", "bg-danger", "Expired")
        sections_html += build_table(expiring, "Expiring Within 15 Days", "bg-warning", "Expiring Soon")

        body = EmailTemplateManager.render('alert', {
            'sections': sections_html,
            'year': datetime.now().year
        })
        
        recipient = config.notification_email
        if recipient:
            EmailManager().enqueue_email(
                subject=f"Contragest Alert: {len(expiring) + len(expired)} Contracts Pending Action", 
                body=body, 
                recipient=recipient,
                logo_path=config.company_logo_path
            )
            return True
        else:
            logger.warning("No notification email configured. Skipping alert.")
            return False
