import secrets
import hashlib
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, Type, Any, Callable
from sqlalchemy.orm import joinedload, selectinload
from functools import wraps
import json
import os
from .interfaces import DatabaseSessionProtocol, EmailServiceProtocol
from contragest.core.email_templates import EmailTemplateManager

LOCAL_AUTH_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), '.local_auth.json')

def _get_local_auto_login() -> Optional[int]:
    if os.path.exists(LOCAL_AUTH_FILE):
        try:
            with open(LOCAL_AUTH_FILE, 'r') as f:
                data = json.load(f)
                return data.get('user_id')
        except Exception:
            pass
    return None

def _set_local_auto_login(user_id: Optional[int]):
    try:
        if user_id is None:
            if os.path.exists(LOCAL_AUTH_FILE):
                os.remove(LOCAL_AUTH_FILE)
        else:
            with open(LOCAL_AUTH_FILE, 'w') as f:
                json.dump({'user_id': user_id}, f)
    except Exception as e:
        print(f"Error saving local auth: {e}")

class AuthService:
    def __init__(self, session_factory, user_model: Type[Any], audit_model: Type[Any], role_model: Type[Any], permission_model: Type[Any], email_service: Optional[EmailServiceProtocol] = None):
        """
        :param session_factory: A callable that returns a new DB session.
        :param user_model: The SQLAlchemy model class for Users (must use UserMixin).
        :param audit_model: The SQLAlchemy model class for AuditLogs (must use AuditLogMixin).
        :param role_model: The SQLAlchemy model class for Roles (must use RoleMixin).
        :param permission_model: The SQLAlchemy model class for Permissions (must use PermissionMixin).
        :param email_service: Optional service to send emails.
        """
        self.session_factory = session_factory
        self.User = user_model
        self.AuditLog = audit_model
        self.Role = role_model
        self.Permission = permission_model
        self.email_service = email_service

    def _get_session(self) -> DatabaseSessionProtocol:
        return self.session_factory()

    def _hash_password(self, password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        if salt is None:
            salt = secrets.token_hex(16)
        
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256', 
            password.encode('utf-8'), 
            salt.encode('utf-8'), 
            100000
        ).hex()
        return pwd_hash, salt

    def _verify_password(self, stored_hash: str, stored_salt: str, password_input: str) -> bool:
        input_hash, _ = self._hash_password(password_input, stored_salt)
        return secrets.compare_digest(stored_hash, input_hash)

    def _validate_password_strength(self, password: str) -> Tuple[bool, str]:
        """Validate password meets minimum security requirements."""
        if len(password) < 8:
            return False, "Password must be at least 8 characters."
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter."
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter."
        if not re.search(r'[0-9]', password):
            return False, "Password must contain at least one digit."
        return True, "Password meets requirements."

    def log_action(self, user_id: int, action: str, details: Optional[str] = None, affected_entity: Optional[str] = None, entity_id: Optional[int] = None) -> None:
        session = self._get_session()
        try:
            # Get username for the log
            user = session.query(self.User).get(user_id)
            username = user.username if user else "System"
            
            log = self.AuditLog(
                user_id=user_id, 
                username=username,
                action=action, 
                details=details,
                affected_entity=affected_entity,
                entity_id=entity_id
            )
            session.add(log)
            session.commit()
        except Exception as e:
            print(f"AuthService Error logging action: {e}")
            session.rollback()
        finally:
            session.close()

    def get_all_usernames(self) -> list[str]:
        session = self._get_session()
        try:
            users = session.query(self.User).all()
            return [u.username for u in users]
        finally:
            session.close()

    def register_user(self, username: str, email: str, password: str) -> Any:
        session = self._get_session()
        try:
            username = username.strip().lower()
            email = email.strip().lower()

            # Validate password strength
            valid, msg = self._validate_password_strength(password)
            if not valid:
                raise ValueError(msg)

            existing = session.query(self.User).filter(
                (self.User.username == username) | (self.User.email == email)
            ).first()
            
            if existing:
                raise ValueError("Username or Email already registered.")

            pwd_hash, salt = self._hash_password(password)
            
            # First user is admin
            user_count = session.query(self.User).count()
            role = 'admin' if user_count == 0 else 'user'

            activation_otp = "".join([secrets.choice('0123456789') for _ in range(6)])
            otp_hash, _ = self._hash_password(activation_otp, salt)

            new_user = self.User(
                username=username,
                email=email,
                password_hash=pwd_hash,
                salt=salt,
                role=role, 
                activation_token=otp_hash,
                is_active=False,
                otp_created_at=datetime.now(),
                otp_attempts=0,
                failed_login_attempts=0,
                locked_until=None,
            )

            session.add(new_user)
            session.commit()
            
            user_id = new_user.id
            user_email = new_user.email
            
            self.log_action(user_id, "REGISTER", f"User registered as {role}", affected_entity="USER", entity_id=user_id)

            if self.email_service:
                self._send_activation_email(user_email, username, activation_otp)

            return new_user
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def authenticate_user(self, username: str, password: str) -> Tuple[Optional[Any], str]:
        session = self._get_session()
        try:
            username = username.strip().lower()
            user = session.query(self.User).filter(self.User.username == username).first()
            
            if not user:
                return None, "User not found."

            # Check account lockout
            if user.locked_until and datetime.now() < user.locked_until:
                remaining = (user.locked_until - datetime.now()).seconds // 60 + 1
                return None, f"Account temporarily locked. Try again in {remaining} min."

            # Clear expired lockout
            if user.locked_until and datetime.now() >= user.locked_until:
                user.locked_until = None
                user.failed_login_attempts = 0
                session.commit()

            if not self._verify_password(user.password_hash, user.salt, password):
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                
                if user.failed_login_attempts >= 5:
                    user.locked_until = datetime.now() + timedelta(minutes=15)
                    session.commit()
                    self.log_action(user.id, "ACCOUNT_LOCKED", "Locked after 5 failed login attempts", affected_entity="USER", entity_id=user.id)
                    return None, "Account locked due to too many failed attempts. Try again in 15 minutes."
                
                session.commit()
                self.log_action(user.id, "LOGIN_FAILED", "Invalid password attempt", affected_entity="USER", entity_id=user.id)
                remaining = 5 - user.failed_login_attempts
                return None, f"Invalid password. {remaining} attempt(s) remaining."

            if not user.is_active:
                return None, "Account not activated. Please check your email."

            # Reset failed attempts on successful login
            user.failed_login_attempts = 0
            user.locked_until = None
            session.commit()

            self.log_action(user.id, "LOGIN_SUCCESS", "User logged in", affected_entity="USER", entity_id=user.id)
            session.expunge(user)
            return user, "Success"
        finally:
            session.close()

    def activate_account(self, username: str, otp: str) -> Tuple[bool, str]:
        session = self._get_session()
        try:
            username = username.strip().lower()
            user = session.query(self.User).filter(self.User.username == username).first()
            
            if not user:
                return False, "User not found."
            
            if user.is_active:
                return True, "Account is already active."

            if user.otp_attempts >= 3:
                return False, "Account locked due to too many failed attempts. Please resend the activation code."

            # Check expiration (10 mins)
            if user.otp_created_at:
                delta = datetime.now() - user.otp_created_at
                if delta.total_seconds() > 600:
                    return False, "Activation code expired. Please request a new one."

            input_hash, _ = self._hash_password(otp, user.salt)
            if user.activation_token and secrets.compare_digest(user.activation_token, input_hash):
                user.is_active = True
                user.activation_token = None
                user.otp_attempts = 0
                session.commit()
                self.log_action(user.id, "ACTIVATION_SUCCESS", "Account activated", affected_entity="USER", entity_id=user.id)
                return True, "Account activated successfully!"
            else:
                user.otp_attempts += 1
                session.commit()
                self.log_action(user.id, "ACTIVATION_FAILED", f"Invalid OTP ({user.otp_attempts}/3)", affected_entity="USER", entity_id=user.id)
                return False, f"Invalid code. Attempts remaining: {3 - user.otp_attempts}"
        finally:
            session.close()

    def resend_activation_otp(self, username: str) -> Tuple[bool, str]:
        """Resend activation OTP with 60-second cooldown."""
        session = self._get_session()
        try:
            username = username.strip().lower()
            user = session.query(self.User).filter(self.User.username == username).first()

            if not user:
                # Generic message to prevent username enumeration
                return True, "If the account exists, a new code has been sent."

            if user.is_active:
                return False, "Account is already active."

            # Enforce 60s cooldown
            if user.otp_created_at:
                elapsed = (datetime.now() - user.otp_created_at).total_seconds()
                if elapsed < 60:
                    wait = int(60 - elapsed)
                    return False, f"Please wait {wait}s before requesting a new code."

            # Generate new OTP
            new_otp = "".join([secrets.choice('0123456789') for _ in range(6)])
            otp_hash, _ = self._hash_password(new_otp, user.salt)

            user.activation_token = otp_hash
            user.otp_created_at = datetime.now()
            user.otp_attempts = 0
            session.commit()

            self.log_action(user.id, "OTP_RESENT", "Activation OTP resent", affected_entity="USER", entity_id=user.id)

            if self.email_service:
                self._send_activation_email(user.email, user.username, new_otp)

            return True, "A new activation code has been sent to your email."
        finally:
            session.close()

    def request_password_reset(self, email: str) -> Tuple[bool, str]:
        """Request a password reset. Sends OTP to email."""
        session = self._get_session()
        try:
            email = email.strip().lower()
            user = session.query(self.User).filter(self.User.email == email).first()

            # Always return generic message to prevent email enumeration
            generic_msg = "If an account with that email exists, a reset code has been sent."

            if not user:
                return True, generic_msg

            if not user.is_active:
                return False, "Account is not activated. Please activate your account first."

            # Enforce 60s cooldown between reset requests
            if user.reset_token_created_at:
                elapsed = (datetime.now() - user.reset_token_created_at).total_seconds()
                if elapsed < 60:
                    wait = int(60 - elapsed)
                    return False, f"Please wait {wait}s before requesting another reset code."

            # Generate 6-digit OTP
            reset_otp = "".join([secrets.choice('0123456789') for _ in range(6)])
            otp_hash, _ = self._hash_password(reset_otp, user.salt)

            user.reset_token = otp_hash
            user.reset_token_created_at = datetime.now()
            user.reset_attempts = 0
            session.commit()

            self.log_action(user.id, "PASSWORD_RESET_REQUESTED", "Password reset OTP sent", affected_entity="USER", entity_id=user.id)

            if self.email_service:
                self._send_password_reset_email(user.email, user.username, reset_otp)

            return True, generic_msg
        finally:
            session.close()

    def reset_password(self, email: str, otp: str, new_password: str) -> Tuple[bool, str]:
        """Reset password using OTP sent via email."""
        session = self._get_session()
        try:
            email = email.strip().lower()
            user = session.query(self.User).filter(self.User.email == email).first()

            if not user:
                return False, "Invalid reset request."

            if not user.reset_token:
                return False, "No reset code was requested. Please request a new one."

            # Check max attempts
            if user.reset_attempts >= 3:
                user.reset_token = None
                session.commit()
                return False, "Too many failed attempts. Please request a new reset code."

            # Check expiration (10 mins)
            if user.reset_token_created_at:
                delta = datetime.now() - user.reset_token_created_at
                if delta.total_seconds() > 600:
                    user.reset_token = None
                    session.commit()
                    return False, "Reset code has expired. Please request a new one."

            # Verify OTP
            input_hash, _ = self._hash_password(otp, user.salt)
            if not secrets.compare_digest(user.reset_token, input_hash):
                user.reset_attempts += 1
                session.commit()
                self.log_action(user.id, "PASSWORD_RESET_FAILED", f"Invalid OTP ({user.reset_attempts}/3)", affected_entity="USER", entity_id=user.id)
                remaining = 3 - user.reset_attempts
                return False, f"Invalid reset code. {remaining} attempt(s) remaining."

            # Validate new password strength
            valid, msg = self._validate_password_strength(new_password)
            if not valid:
                return False, msg

            # Apply new password
            new_hash, new_salt = self._hash_password(new_password)
            user.password_hash = new_hash
            user.salt = new_salt
            user.reset_token = None
            user.reset_token_created_at = None
            user.reset_attempts = 0
            # Also clear login lockout
            user.failed_login_attempts = 0
            user.locked_until = None
            session.commit()

            self.log_action(user.id, "PASSWORD_RESET_SUCCESS", "Password reset completed", affected_entity="USER", entity_id=user.id)
            return True, "Password reset successfully! You can now log in."
        finally:
            session.close()

    def _send_activation_email(self, email: str, username: str, otp: str):
        subject = f"Activate your account, {username}!"
        body = EmailTemplateManager.render('activation', {
            'username': username,
            'otp': otp
        })
        try:
            print(f"AuthService: Initiating activation email dispatch to {email}")
            self.email_service.send_email(email, subject, body)
        except Exception as e:
            print(f"AuthService: Failed to send activation email to {email}: {e}")

    def _send_password_reset_email(self, email: str, username: str, otp: str):
        """Send password reset OTP email."""
        subject = f"Password Reset Code - {username}"
        body = EmailTemplateManager.render('password_reset', {
            'username': username,
            'otp': otp
        })
        try:
            print(f"AuthService: Initiating password reset email dispatch to {email}")
            self.email_service.send_email(email, subject, body)
        except Exception as e:
            print(f"AuthService: Failed to send reset email to {email}: {e}")

    def get_all_users(self):
        session = self._get_session()
        try:
            users = session.query(self.User).order_by(self.User.username).all()
            for u in users:
                session.expunge(u)
            return users
        finally:
            session.close()

    def update_user_role(self, target_id: int, new_role: str, admin_id: int) -> Tuple[bool, str]:
        session = self._get_session()
        try:
            user = session.query(self.User).get(target_id)
            if not user:
                return False, "User not found."
            
            old_role = user.role
            user.role = new_role
            session.commit()
            self.log_action(admin_id, "ROLE_CHANGE", f"Changed {user.username} from {old_role} to {new_role}", affected_entity="USER", entity_id=user.id)
            return True, "Role updated."
        finally:
            session.close()

    def delete_user(self, target_id: int, admin_id: int) -> Tuple[bool, str]:
         session = self._get_session()
         try:
             if target_id == admin_id:
                 return False, "Cannot delete yourself."
             
             user = session.query(self.User).get(target_id)
             if not user:
                 return False, "User not found."
             
             username = user.username
             session.delete(user)
             session.commit()
             self.log_action(admin_id, "USER_DELETED", f"Deleted {username}", affected_entity="USER", entity_id=target_id)
             return True, "User deleted."
         finally:
             session.close()

    def activate_account_direct(self, target_id: int, is_active: bool, admin_id: int) -> Tuple[bool, str]:
        session = self._get_session()
        try:
            user = session.query(self.User).get(target_id)
            if not user:
                return False, "User not found."
            
            user.is_active = is_active
            session.commit()
            
            status_text = "Activated" if is_active else "Deactivated"
            self.log_action(admin_id, "STATUS_CHANGE", f"{status_text} account for {user.username}", affected_entity="USER", entity_id=user.id)
            return True, f"Account {status_text}."
        finally:
             session.close()

    def toggle_auto_login(self, target_id: int, admin_id: int) -> Tuple[bool, str]:
        """Enable or disable auto-login for a user ON THIS MACHINE."""
        session = self._get_session()
        try:
            user = session.query(self.User).get(target_id)
            if not user:
                return False, "User not found."
            
            current_local = _get_local_auto_login()
            if current_local == target_id:
                _set_local_auto_login(None)
                status_text = "Disabled"
            else:
                _set_local_auto_login(target_id)
                status_text = "Enabled"
            
            self.log_action(admin_id, "LOCAL_AUTO_LOGIN_CHANGE", f"{status_text} local auto-login for {user.username}", affected_entity="USER", entity_id=user.id)
            return True, f"Auto-login {status_text.lower()} on this machine."
        finally:
             session.close()

    def get_local_auto_login_id(self) -> Optional[int]:
        return _get_local_auto_login()

    def get_auto_login_user(self) -> Optional[Any]:
        """Returns the user configured for local auto-login, if any."""
        local_id = _get_local_auto_login()
        if not local_id:
            return None
            
        session = self._get_session()
        try:
            user = session.query(self.User).filter(self.User.id == local_id, self.User.is_active == True).first()
            if user:
                session.expunge(user)
                return user
            return None
        finally:
            session.close()

    def search_users(self, query: str):
        """Search users by username or email (case-insensitive)."""
        session = self._get_session()
        try:
            pattern = f"%{query.strip().lower()}%"
            users = session.query(self.User).filter(
                (self.User.username.ilike(pattern)) | (self.User.email.ilike(pattern))
            ).order_by(self.User.username).all()
            for u in users:
                session.expunge(u)
            return users
        finally:
            session.close()

    def unlock_user(self, target_id: int, admin_id: int) -> Tuple[bool, str]:
        """Clear login lockout for a user."""
        session = self._get_session()
        try:
            user = session.query(self.User).get(target_id)
            if not user:
                return False, "User not found."

            if not user.locked_until and (user.failed_login_attempts or 0) == 0:
                return False, "Account is not locked."

            user.locked_until = None
            user.failed_login_attempts = 0
            session.commit()
            self.log_action(admin_id, "ACCOUNT_UNLOCKED", f"Unlocked account for {user.username}", affected_entity="USER", entity_id=user.id)
            return True, f"Account for '{user.username}' has been unlocked."
        finally:
            session.close()

    def admin_reset_password(self, target_id: int, new_password: str, admin_id: int) -> Tuple[bool, str]:
        """Admin-initiated password reset (no OTP required)."""
        session = self._get_session()
        try:
            user = session.query(self.User).get(target_id)
            if not user:
                return False, "User not found."

            valid, msg = self._validate_password_strength(new_password)
            if not valid:
                return False, msg

            new_hash, new_salt = self._hash_password(new_password)
            user.password_hash = new_hash
            user.salt = new_salt
            user.reset_token = None
            user.reset_token_created_at = None
            user.reset_attempts = 0
            user.failed_login_attempts = 0
            user.locked_until = None
            session.commit()

            self.log_action(admin_id, "ADMIN_PASSWORD_RESET", f"Reset password for {user.username}", affected_entity="USER", entity_id=user.id)
            return True, f"Password for '{user.username}' has been reset."
        finally:
            session.close()

    # ═══════════════════════════════════════════════════════════
    #  RBAC: Roles & Permissions
    # ═══════════════════════════════════════════════════════════

    def get_roles(self) -> list[Any]:
        session = self._get_session()
        try:
            # Eagerly load permissions to avoid DetachedInstanceError in the UI
            # selectinload is preferred for collections (1-to-N)
            roles = session.query(self.Role).options(selectinload(self.Role.permissions)).order_by(self.Role.name).all()
            for r in roles:
                # Access permissions to ensure they are loaded into the object before expunging
                _ = r.permissions
                session.expunge(r)
            return roles
        finally:
            session.close()

    def create_role(self, name: str, description: Optional[str] = None, admin_id: int = 0) -> Tuple[bool, str]:
        session = self._get_session()
        try:
            name = name.strip()
            if session.query(self.Role).filter_by(name=name).first():
                return False, f"Role '{name}' already exists."
            
            new_role = self.Role(name=name, description=description)
            session.add(new_role)
            session.commit()
            self.log_action(admin_id, "ROLE_CREATED", f"Created role {name}", affected_entity="ROLE", entity_id=new_role.id)
            return True, "Role created successfully."
        finally:
            session.close()

    def update_role_permissions(self, role_id: int, permissions_data: list[dict], admin_id: int = 0) -> Tuple[bool, str]:
        """
        :param permissions_data: List of dicts like {'screen': 'Contracts', 'can_view': True, ...}
        """
        session = self._get_session()
        try:
            role = session.query(self.Role).get(role_id)
            if not role:
                return False, "Role not found."
            
            # Clear existing permissions and rebuild
            session.query(self.Permission).filter_by(role_id=role_id).delete()
            
            for p in permissions_data:
                perm = self.Permission(
                    role_id=role_id,
                    screen_name=p['screen'],
                    can_view=p.get('can_view', False),
                    can_add=p.get('can_add', False),
                    can_edit=p.get('can_edit', False),
                    can_delete=p.get('can_delete', False)
                )
                session.add(perm)
            
            session.commit()
            self.log_action(admin_id, "PERMISSIONS_UPDATED", f"Updated permissions for role {role.name}", affected_entity="ROLE", entity_id=role_id)
            return True, "Permissions updated successfully."
        finally:
            session.close()

    def has_permission(self, user_id: int, screen: str, action: str) -> bool:
        """
        Checks if a user has permission for a specific action on a screen.
        action: 'view', 'add', 'edit', 'delete'
        """
        session = self._get_session()
        try:
            user = session.query(self.User).get(user_id)
            if not user:
                return False
            
            # Super-admin bypass: if they have the legacy 'admin' string
            if user.role == 'admin':
                return True
                
            if user.role_id:
                # Super-admin bypass: if they belong to a role named 'admin'
                role = session.query(self.Role).get(user.role_id)
                if role and role.name == 'admin':
                    return True
            
            # If no role_id and not legacy admin, no permission
            if not user.role_id:
                return False
            
            perm = session.query(self.Permission).filter_by(role_id=user.role_id, screen_name=screen).first()
            if not perm:
                # Default to deny if no permission entry exists for this role/screen
                return False
            
            check_map = {
                'view': perm.can_view,
                'add': perm.can_add,
                'edit': perm.can_edit,
                'delete': perm.can_delete
            }
            return check_map.get(action.lower(), False)
        finally:
            session.close()

    def sync_legacy_roles(self):
        """Seed initial roles for 'admin' and 'user' if they don't exist."""
        session = self._get_session()
        try:
            admin_role = session.query(self.Role).filter_by(name='admin').first()
            if not admin_role:
                self.create_role('admin', 'Full system access')
            
            user_role = session.query(self.Role).filter_by(name='user').first()
            if not user_role:
                self.create_role('user', 'Standard limited access')
            
            # Migrate existing users if they don't have role_id
            admin_role = session.query(self.Role).filter_by(name='admin').first()
            user_role = session.query(self.Role).filter_by(name='user').first()
            
            users = session.query(self.User).filter(self.User.role_id == None).all()
            for u in users:
                if u.role == 'admin':
                    u.role_id = admin_role.id
                else:
                    u.role_id = user_role.id
            session.commit()
        finally:
            session.close()

    def check_access(self, user_id: int, screen: str, action: str) -> bool:
        """
        Public API for permission checks.
        If user_id is 0 (System), always allow.
        """
        if user_id == 0:
            return True
        return self.has_permission(user_id, screen, action)

    @staticmethod
    def require_permission(screen: str, action: str):
        """
        Decorator for controller methods that require permission.
        Expects the first argument to be an object with an 'auth_service' and 'current_user' attribute.
        """
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(self_obj, *args, **kwargs):
                user_id = getattr(self_obj.current_user, 'id', 0)
                if self_obj.auth_service.check_access(user_id, screen, action):
                    return func(self_obj, *args, **kwargs)
                else:
                    from ttkbootstrap.dialogs import Messagebox
                    Messagebox.show_error(
                        f"Access Denied: You do not have permission to '{action}' on '{screen}'.",
                        "Security Warning"
                    )
                    return None
            return wrapper
        return decorator

