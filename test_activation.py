import sys
import os
sys.path.append(os.getcwd())

from contragest.features.auth.service import AuthService

def test_activation(username, otp):
    auth = AuthService() # This is the adapter that uses CoreAuthService
    print(f"Testing activation for {username} with OTP {otp}...")
    success, msg = auth.activate_account(username, otp)
    print(f"Success: {success}")
    print(f"Message: {msg}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_activation.py <username> <otp>")
        sys.exit(1)
    
    test_activation(sys.argv[1], sys.argv[2])
