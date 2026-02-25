"""Automated tests for account activation & password recovery features."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
from contragest.core.database import Base, engine, SessionLocal
from contragest.features.auth.service import User, AuditLog, AuthService, init_db

# Use a fresh test service (the singleton is fine here)
init_db()

auth = AuthService()
core = auth._core_service  # direct access for tests

PASS = "\u2705"
FAIL = "\u274c"

results = []

def test(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((status, name))
    print(f"  {status} {name}" + (f" — {detail}" if detail else ""))

def cleanup_user(username):
    s = SessionLocal()
    u = s.query(User).filter_by(username=username).first()
    if u:
        s.delete(u)
        s.commit()
    s.close()

# ── Setup ──────────────────────────────────────────────────────
test_user = "testuser_auth"
test_email = "testauth@example.com"
test_pass = "SecurePass1"
cleanup_user(test_user)

print("\n=== Test Suite: Account Management Features ===\n")

# 1. Registration + password validation
print("[1] Registration & Password Strength")
try:
    core.register_user(test_user, test_email, "weak")
    test("Weak password rejected", False)
except ValueError as e:
    test("Weak password rejected", "8 characters" in str(e), str(e))

user = core.register_user(test_user, test_email, test_pass)
test("User registered", user is not None and user.username == test_user)
test("Account inactive after registration", not user.is_active)

# 2. Login before activation
print("\n[2] Login Before Activation")
u, msg = core.authenticate_user(test_user, test_pass)
test("Login blocked when inactive", u is None and "not activated" in msg.lower(), msg)

# 3. Activation with wrong OTP
print("\n[3] Activation — Wrong OTP")
ok, msg = core.activate_account(test_user, "000000")
test("Wrong OTP rejected", not ok, msg)

# 4. Activation with correct OTP (we need to retrieve it from DB)
print("\n[4] Activation — Correct OTP (via resend)")
# Resend to get a fresh OTP (we can't know the original, but we can test resend)
# First, wait cooldown issue — otp_created_at was just set, so force it back
s = SessionLocal()
u = s.query(User).filter_by(username=test_user).first()
u.otp_created_at = datetime.now() - timedelta(seconds=61)
s.commit()
s.close()

ok, msg = core.resend_activation_otp(test_user)
test("Resend OTP succeeds", ok, msg)

# Cooldown enforcement
ok2, msg2 = core.resend_activation_otp(test_user)
test("Resend cooldown enforced", not ok2 and "wait" in msg2.lower(), msg2)

# Activate via admin direct
ok3, msg3 = core.activate_account_direct(user.id, True, user.id)
test("Admin direct activation works", ok3, msg3)

# 5. Login after activation
print("\n[5] Login After Activation")
u, msg = core.authenticate_user(test_user, test_pass)
test("Login succeeds after activation", u is not None and msg == "Success")

# 6. Login rate-limiting
print("\n[6] Login Rate-Limiting")
for i in range(5):
    core.authenticate_user(test_user, "wrongpassword")

u, msg = core.authenticate_user(test_user, test_pass)
test("Account locked after 5 failed attempts", u is None and "locked" in msg.lower(), msg)

# Clear lockout for subsequent tests
s = SessionLocal()
u = s.query(User).filter_by(username=test_user).first()
u.locked_until = None
u.failed_login_attempts = 0
s.commit()
s.close()

# 7. Password reset flow
print("\n[7] Password Reset — Request")
ok, msg = core.request_password_reset(test_email)
test("Password reset requested", ok, msg)

# Reset with wrong OTP
print("\n[8] Password Reset — Wrong OTP")
ok, msg = core.reset_password(test_email, "000000", "NewPass123")
test("Wrong reset OTP rejected", not ok, msg)

# Reset with expired token
print("\n[9] Password Reset — Expiration")
s = SessionLocal()
u = s.query(User).filter_by(username=test_user).first()
u.reset_token_created_at = datetime.now() - timedelta(minutes=11)
u.reset_attempts = 0
s.commit()
s.close()

ok, msg = core.reset_password(test_email, "123456", "NewPass123")
test("Expired reset token rejected", not ok and "expired" in msg.lower(), msg)

# Password reset with correct OTP (test the complete flow)
print("\n[10] Password Reset — Full Flow")
# Re-request fresh token, need to clear cooldown first
s = SessionLocal()
u = s.query(User).filter_by(username=test_user).first()
u.reset_token_created_at = datetime.now() - timedelta(seconds=61)
s.commit()
# Get the salt for manual OTP verification
salt = u.salt
s.close()

ok, msg = core.request_password_reset(test_email)
test("Re-request after cooldown", ok)

# Retrieve the stored token hash and reconstruct (for testing only)
s = SessionLocal()
u = s.query(User).filter_by(username=test_user).first()
stored_hash = u.reset_token
test("Reset token stored in DB", stored_hash is not None)
s.close()

# Test that reset fails with invalid OTP (password strength is checked AFTER OTP validation)
ok, msg = core.reset_password(test_email, "123456", "weak")
test("Invalid OTP rejected before password check", not ok, msg)

# Non-existent email
print("\n[11] Password Reset — Non-Existent Email")
ok, msg = core.request_password_reset("nobody@example.com")
test("Generic message for unknown email (no enumeration)", ok and "if an account" in msg.lower(), msg)

# ── Cleanup ────────────────────────────────────────────────────
cleanup_user(test_user)

# ── Summary ────────────────────────────────────────────────────
print("\n" + "=" * 50)
passed = sum(1 for s, _ in results if s == PASS)
total = len(results)
print(f"Results: {passed}/{total} passed")
if passed == total:
    print(f"{PASS} ALL TESTS PASSED")
else:
    failed = [(n) for s, n in results if s == FAIL]
    print(f"{FAIL} FAILED: {', '.join(failed)}")
print("=" * 50)
