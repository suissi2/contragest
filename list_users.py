import sys
import os
sys.path.append(os.getcwd())

from contragest.core.database import SessionLocal
from contragest.features.auth.service import User

def list_users():
    session = SessionLocal()
    try:
        users = session.query(User).all()
        print(f"{'ID':<4} {'Username':<15} {'Email':<25} {'Active':<8} {'OTP Hash (prefix)':<20}")
        print("-" * 75)
        for u in users:
            otp_prefix = (u.activation_token[:15] + "...") if u.activation_token else "None"
            print(f"{u.id:<4} {u.username:<15} {u.email:<25} {str(u.is_active):<8} {otp_prefix:<20}")
    finally:
        session.close()

if __name__ == "__main__":
    list_users()
