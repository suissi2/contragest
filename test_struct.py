
import struct
import sys

def test_pack():
    uid = 10
    priv = 0
    pw = b'12345678'
    name = b'A' * 24
    card = b'1234'
    group = b'1234567'
    user = b'B' * 24
    
    fmt = 'HB8s24s4sx7sx24s'
    print(f"Testing format: {fmt}")
    print(f"Argument types: uid:{type(uid)}, priv:{type(priv)}, pw:{type(pw)}, name:{type(name)}, card:{type(card)}, group:{type(group)}, user:{type(user)}")
    
    try:
        # Test 1: Full pack
        res = struct.pack(fmt, uid, priv, pw, name, card, group, user)
        print("Test 1 (Full): SUCCESS")
    except Exception as e:
        print(f"Test 1 (Full): FAILED - {e}")

    try:
        # Test 2: Without padding chars
        fmt2 = 'HB8s24s4s7s24s'
        res = struct.pack(fmt2, uid, priv, pw, name, card, group, user)
        print("Test 2 (No x): SUCCESS")
    except Exception as e:
        print(f"Test 2 (No x): FAILED - {e}")

    try:
        # Test 3: Standard alignment
        fmt3 = '<HB8s24s4sx7sx24s'
        res = struct.pack(fmt3, uid, priv, pw, name, card, group, user)
        print("Test 3 (With <): SUCCESS")
    except Exception as e:
        print(f"Test 3 (With <): FAILED - {e}")

    # Test individual components
    for char in ['H', 'B', '8s', '24s', '4s', '7s', '24s']:
        try:
            val = uid if char == 'H' else priv if char == 'B' else pw if char == '8s' else name if char == '24s' else card if char == '4s' else group if char == '7s' else user
            struct.pack(char, val)
            print(f"Pack '{char}': SUCCESS")
        except Exception as e:
            print(f"Pack '{char}' with {type(val)}: FAILED - {e}")

if __name__ == "__main__":
    test_pack()
