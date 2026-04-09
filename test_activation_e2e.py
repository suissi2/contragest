import sys
import os
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
        
        # Get the OTP from the database (simulation of receiving email)
        session = SessionLocal()
        user_in_db = session.query(User).filter_by(username=test_user).first()
        stored_token = user_in_db.activation_token
        salt = user_in_db.salt
        session.close()
        
        print(f"Stored Token: {stored_token}")
        print(f"Salt: {salt}")
        
        # Since we can't easily see the OTP that was sent (mocked/emailed),
        # let's try to 'resend' it and capture it by mocking the email service
        print("\nBypassing resend cooldown...")
        session = SessionLocal()
        from datetime import datetime, timedelta
        user_to_fix = session.query(User).filter_by(username=test_user).first()
        user_to_fix.otp_created_at = datetime.now() - timedelta(seconds=70)
        session.commit()
        session.close()

        print("\nRequesting Resend and capturing OTP...")
        
        class MockEmailService:
            def send_email(self, email, subject, body):
                # The body contains <h1>OTP</h1>
                import re
                match = re.search(r'<h1[^>]*>(\d+)</h1>', body)
                if match:
                    self.captured_otp = match.group(1)
                else:
                    self.captured_otp = None
        
        mock_email = MockEmailService()
        core.email_service = mock_email
        
        core.resend_activation_otp(test_user)
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
