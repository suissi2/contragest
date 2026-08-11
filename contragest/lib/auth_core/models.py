from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship, declared_attr
from typing import Optional

class RoleMixin:
    """Mixin for Role model."""
    __tablename__ = 'auth_roles'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    
    @declared_attr
    def permissions(cls):
        return relationship("Permission", back_populates="role", cascade="all, delete-orphan")
    
    @declared_attr
    def users(cls):
        return relationship("User", back_populates="role_obj")

class PermissionMixin:
    """Mixin for Permission model."""
    __tablename__ = 'auth_permissions'
    id = Column(Integer, primary_key=True)
    role_id = Column(Integer, ForeignKey('auth_roles.id'), nullable=False)
    screen_name = Column(String, nullable=False)
    
    can_view = Column(Boolean, default=False)
    can_add = Column(Boolean, default=False)
    can_edit = Column(Boolean, default=False)
    can_delete = Column(Boolean, default=False)
    
    @declared_attr
    def role(cls):
        return relationship("Role", back_populates="permissions")

class UserMixin:
    """
    Mixin to add authentication fields to a SQLAlchemy model.
    Host application should inherit from (Base, UserMixin).
    """
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    salt = Column(String, nullable=False)
    role = Column(String, default='user') # 'admin' or 'user' (Legacy)
    role_id = Column(Integer, ForeignKey('auth_roles.id'), nullable=True)
    is_active = Column(Boolean, default=False)
    auto_login = Column(Boolean, default=False)

    
    @declared_attr
    def role_obj(cls):
        return relationship("Role", back_populates="users")
    
    # 6-digit OTP stored as hash (activation)
    activation_token = Column(String, nullable=True) 
    otp_attempts = Column(Integer, default=0)
    otp_created_at = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)

    # Password reset fields
    reset_token = Column(String, nullable=True)
    reset_token_created_at = Column(DateTime, nullable=True)
    reset_attempts = Column(Integer, default=0)

    # Login rate-limiting
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)

    def is_admin(self) -> bool:
        return self.role == 'admin'

class AuditLogMixin:
    """
    Mixin for Audit Logs.
    """
    user_id = Column(Integer, nullable=False)
    username = Column(String, nullable=True) # For easier display
    action = Column(String, nullable=False) # e.g., 'LOGIN', 'CONTRACT_DELETED'
    affected_entity = Column(String, nullable=True) # e.g., 'CONTRACT', 'USER'
    entity_id = Column(Integer, nullable=True)
    details = Column(String, nullable=True) # JSON store for before/after states
    timestamp = Column(DateTime, default=datetime.now)

def create_auth_tables(engine, base):
    """
    Helper to create tables if the host app uses a dedicated Base for auth.
    If using a shared Base, the host app's migration/create_all should handle it.
    """
    base.metadata.create_all(engine)
