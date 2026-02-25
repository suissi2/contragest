import os
import smtplib
import ssl
import socket
from typing import Optional, Tuple, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.utils import formatdate, make_msgid
from contragest.core.logging import setup_logger
from contragest.core.exceptions import (
    EmailError, EmailConnectionError, EmailAuthenticationError, EmailSendingError, EmailConfigError
)

logger = setup_logger("email_service")

class EmailService:
    """
    Low-level wrapper for SMTP interactions.
    Handles connection, authentication, and sending of single messages.
    Does NOT handle retries or queuing (handled by EmailManager).
    """
    def __init__(self, config: Any):
        self.config = config

    def connect(self) -> smtplib.SMTP:
        """
        Establishes and returns a connected/authenticated SMTP server instance.
        Raises EmailConnectionError, EmailAuthenticationError, EmailConfigError.
        """
        if not self.config.smtp_server:
            raise EmailConfigError("SMTP Server is not configured.")
        
        if "@" in self.config.smtp_server:
             raise EmailConfigError(
                f"Invalid SMTP Server: '{self.config.smtp_server}'. Looks like an email address."
            )

        try:
            # Context for SSL/TLS
            if getattr(self.config, 'smtp_ssl_verify', True):
                context = ssl.create_default_context()
            else:
                context = ssl._create_unverified_context()
            
            # Connect
            if self.config.smtp_port == 465:
                # Implicit SSL
                server = smtplib.SMTP_SSL(self.config.smtp_server, self.config.smtp_port, context=context, timeout=12)
                server.ehlo()
            else:
                # Explicit SSL/STARTTLS
                server = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port, timeout=12)
                server.ehlo()
                if server.has_extn("STARTTLS"):
                    server.starttls(context=context)
                    server.ehlo()
            
            # Login
            if self.config.smtp_user and self.config.smtp_password:
                clean_password = self.config.smtp_password.strip().replace(" ", "")
                try:
                    server.login(self.config.smtp_user, clean_password)
                except smtplib.SMTPAuthenticationError as e:
                    raise EmailAuthenticationError(f"Authentication failed for {self.config.smtp_user}: {e}")
                
            return server
            
        except (smtplib.SMTPConnectError, ConnectionRefusedError, socket.error) as e:
            raise EmailConnectionError(f"Failed to connect to {self.config.smtp_server}:{self.config.smtp_port}: {e}")
        except EmailError:
            raise
        except Exception as e:
            raise EmailConnectionError(f"Unexpected SMTP error: {e}")

    def send_message(self, server: smtplib.SMTP, subject: str, body: str, recipient: str, sender: Optional[str] = None, logo_path: Optional[str] = None) -> bool:
        """
        Sends a message using an existing connected server instance.
        Supports CID image embedding for logos.
        """
        sender_email = sender or self.config.smtp_user
        if not sender_email:
             raise EmailConfigError("No sender email configured via config or argument.")

        try:
            msg = MIMEMultipart('related')
            # Use a display name if possible, or just the email
            display_name = "Contragest Notification"
            msg['From'] = f"{display_name} <{sender_email}>"
            msg['To'] = recipient
            msg['Subject'] = subject
            msg['Date'] = formatdate(localtime=True)
            
            # Message-ID should have a proper domain part
            try:
                domain = self.config.smtp_server.split('.')[-2] + '.' + self.config.smtp_server.split('.')[-1]
            except (ValueError, IndexError):
                domain = 'contragest.local'
            
            msg['Message-ID'] = make_msgid(domain=domain)
            
            # Attach HTML part
            msg_alternative = MIMEMultipart('alternative')
            msg.attach(msg_alternative)
            msg_alternative.attach(MIMEText(body, 'html'))
            
            # Attach Logo as CID if provided
            if logo_path and os.path.exists(logo_path):
                try:
                    with open(logo_path, 'rb') as f:
                        img_data = f.read()
                        img = MIMEImage(img_data)
                        img.add_header('Content-ID', '<company_logo>')
                        img.add_header('Content-Disposition', 'inline', filename=os.path.basename(logo_path))
                        msg.attach(img)
                except Exception as e:
                    logger.error(f"Failed to attach logo {logo_path}: {e}")
            
            server.send_message(msg)
            return True
        except Exception as e:
            raise EmailSendingError(f"Failed to send message to {recipient}: {e}")

    def test_connection(self) -> Tuple[bool, str]:
        """Tests the SMTP connection and returns (Success: bool, Message: str)"""
        try:
            server = self.connect()
            server.quit()
            return True, "Connection and Authentication Successful!"
        except EmailError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected Error: {e}"

    def send_email(self, subject: str, body: str, recipient: Optional[str] = None) -> Tuple[bool, str]:
        """
        Convenience method to connect, send, and quit.
        Useful for one-off sends or diagnostics.
        """
        try:
            recipient = recipient or self.config.notification_email
            server = self.connect()
            try:
                self.send_message(server, subject, body, recipient)
                return True, ""
            except EmailError as e:
                return False, str(e)
            finally:
                try:
                    server.quit()
                except:
                    pass
        except Exception as e:
            return False, str(e)
