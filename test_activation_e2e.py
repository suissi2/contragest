import sys
import os
from datetime import datetime, timedelta
sys.path.append(os.getcwd())

from contragest.core.database import SessionLocal
from contragest.features.auth.service import AuthService, User
import secrets

def test_full_cycle():
    auth_service = AuthService()
    core = auth_service._core_service
    
    test_user = f"debug_user_{secrets.token_hex(4)}"
    test_email = f"debug_{test_user}@example.com"
    test_pass = "SecurePass123!"
    
    print(f"Registering {test_user}...")
    try:
        user = core.register_user(test_user, test_email, test_pass)
        print(f"User registered with ID {user.id}")
        
        # Bypass cooldown
        session = SessionLocal()
        u = session.query(User).filter_by(username=test_user).first()
        u.otp_created_at = datetime.now() - timedelta(seconds=70)
        session.commit()
        session.close()

        print("\nRequesting Resend and capturing OTP...")
        
        class MockEmailService:
            def __init__(self):
                self.captured_otp = None

            def send_email(self, email, subject, body):
                # The body contains <h1>OTP</h1>
                import re
                match = re.search(r'<h1[^>]*>(\d+)</h1>', body)
                if match:
                    self.captured_otp = match.group(1)
        
        mock_email = MockEmailService()
        core.email_service = mock_email
        
        success_resend, msg_resend = core.resend_activation_otp(test_user)
        print(f"Resend success: {success_resend}, Message: {msg_resend}")
        captured_otp = mock_email.captured_otp
        
        print(f"Captured OTP from 'email': {captured_otp}")
        
        if not captured_otp:
            print("FAILED to capture OTP.")
            return

        print(f"Attempting activation with {captured_otp}...")
        success, msg = core.activate_account(test_user, captured_otp)
        
        print(f"Activation Success: {success}")
        print(f"Message: {msg}")
        
        if success:
            print("\nRESULT: SUCCESS! Logic is working.")
        else:
            print("\nRESULT: FAILED! Logic is BROKEN.")
            
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_full_cycle()
