import hashlib
import time

def brute_force(target_hash, salt, iterations=100000):
    print(f"Brute forcing 6-digit OTP for salt {salt}...")
    start_time = time.time()
    for i in range(1000000):
        otp = f"{i:06d}"
        h = hashlib.pbkdf2_hmac('sha256', otp.encode('utf-8'), salt.encode('utf-8'), iterations).hex()
        if h == target_hash:
            print(f"\nFOUND! OTP is: {otp}")
            print(f"Time taken: {time.time() - start_time:.2f}s")
            return otp
        if i % 10000 == 0:
            elapsed = time.time() - start_time
            print(f"Checked {i} codes... ({elapsed:.2f}s)", end='\r')
    print("\nNOT FOUND.")
    return None

if __name__ == "__main__":
    target = "05e09db457036597bd54d843cb51ada84fb0f0e0cfc572a014ba3ed1d0e265e1"
    salt = "ae49cf50e914d8d4bb7089f6c36ae34f"
    brute_force(target, salt)
