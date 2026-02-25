import sys
import os
import hashlib
import secrets
sys.path.append(os.getcwd())

from contragest.core.database import SessionLocal
from contragest.features.auth.service import User, AuthService
from datetime import datetime

def debug_user(username, test_otp=None):
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.username == username.lower()).first()
        if not user:
            print(f"User '{username}' not found.")
            return

        print(f"--- User info for {user.username} ---")
        print(f"ID: {user.id}")
        print(f"Email: {user.email}")
        print(f"Is Active: {user.is_active}")
        print(f"Activation Token: |{user.activation_token}| (len: {len(user.activation_token) if user.activation_token else 0})")
        print(f"OTP Created At: {user.otp_created_at}")
        print(f"OTP Attempts: {user.otp_attempts}")
        print(f"Salt: |{user.salt}| (len: {len(user.salt) if user.salt else 0})")
        print(f"Now: {datetime.now()}")
        
        if test_otp:
            # Replicate _hash_password logic from AuthService
            pwd_hash = hashlib.pbkdf2_hmac(
                'sha256', 
                test_otp.encode('utf-8'), 
                user.salt.encode('utf-8'), 
                100000
            ).hex()
            print(f"\n--- Testing Hash for OTP '{test_otp}' ---")
            print(f"Result Hash: {pwd_hash}")
            print(f"Stored Hash: {user.activation_token}")
            if pwd_hash == user.activation_token:
                print("MATCH FOUND!")
            else:
                print("NO MATCH.")
            
            # Just in case, try hashing with a salt that might have been processed differently
            # though unlikely here.
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "bouba1221"
    otp = sys.argv[2] if len(sys.argv) > 2 else None
    debug_user(target, otp)
