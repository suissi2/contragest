import secrets
import threading
import hashlib
from datetime import datetime, timedelta
from datetime import datetime, timedelta
from typing import Optional, Tuple, Any
from sqlalchemy import Column, Integer

# Import Core Auth
from contragest.lib.auth_core.service import AuthService as CoreAuthService
from contragest.lib.auth_core.models import UserMixin, AuditLogMixin, RoleMixin, PermissionMixin, create_auth_tables
from contragest.lib.auth_core.interfaces import EmailServiceProtocol

# Import Contragest specifics
from contragest.core.database import Base, SessionLocal, engine, AppConfig

# Define Models using Mixins
class Role(Base, RoleMixin):
    pass

class Permission(Base, PermissionMixin):
    pass

class User(Base, UserMixin):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    
    # Core UserMixin provides all fields
    def __repr__(self):
        return f"<User(username='{self.username}', role='{self.role}', active={self.is_active})>"

class AuditLog(Base, AuditLogMixin):
    __tablename__ = 'audit_logs'
    id = Column(Integer, primary_key=True)

def init_db():
    # Use helper or standard create_all
    Base.metadata.create_all(engine)

# Adapter for Email Service
class ContragestEmailAdapter(EmailServiceProtocol):
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def send_email(self, to_email: str, subject: str, body_html: str) -> bool:
        session = self.session_factory()
        try:
            config = session.query(AppConfig).first()
            if not config or not config.smtp_server:
                print("Email config missing.")
                return False
            
            # Lazy import to avoid circular dep if any
            from contragest.core.email_service import EmailService
            service = EmailService(config)
            # EmailManager logic is a bit complex in original, let's try to reuse EmailManager if possible 
            # Or use EmailService directly. 
            # Original used EmailManager().enqueue_email
            from contragest.core.email_manager import EmailManager
            EmailManager().enqueue_email(subject, body_html, to_email)
            return True
        except Exception as e:
            print(f"Adapter Env failure: {e}")
            return False
        finally:
            session.close()

# Singleton or Factory for Service
class AuthService:
    _instance = None
    _core_service = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AuthService, cls).__new__(cls)
            
            email_adapter = ContragestEmailAdapter(SessionLocal)
            
            cls._core_service = CoreAuthService(
                session_factory=SessionLocal,
                user_model=User,
                audit_model=AuditLog,
                role_model=Role,
                permission_model=Permission,
                email_service=email_adapter
            )
        return cls._instance

    # Proxy methods to Core Service
    def __getattr__(self, name):
        return getattr(self._core_service, name)

    @staticmethod
    def require_permission(screen: str, action: str):
        return CoreAuthService.require_permission(screen, action)

    # Maintain backward compatibility for static/class methods if any were used, 
    # but original was instance based mostly. 
    # Original 'activate_account' etc match core signatures mostly.
    
    # helper for specific non-core logic if any? 
    # The original _get_email_service was internal.

    # We need to expose session for some legacy direct access if generic views used it?
    # `self.session` was public in old service.
    @property
    def session(self):
        return self._core_service._get_session() 
        # CAUTION: Core service opens/closes sessions per method. 
        # Accessing .session here creates a NEW session that might need closing.
        # This is a risk for legacy code expecting a persistent session attribute.
        # Let's check usages. 
        # user_management.py used: user = self.auth_service.session.get(User, user_id)
        # So we surely need a property that returns a session.

# Re-implement legacy session access for compatibility
# Ideally we refactor consumers, but for now we patch.
    
    
if __name__ == "__main__":
    init_db()
    print("Database initialized.")
