"""
Run this to debug which file is accessing ENCRYPTION_KEY before .env loads
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
BASE_DIR = Path(__file__).resolve().parent
env_file = BASE_DIR / ".env"
print(f"Loading .env from: {env_file}")
print(f".env exists: {env_file.exists()}")

load_dotenv(env_file)

print(f"\n✓ ENCRYPTION_KEY after load_dotenv: {os.getenv('ENCRYPTION_KEY')}")
print(f"✓ MONGODB_URI: {os.getenv('MONGODB_URI')[:30]}...")

# Now test importing shared modules one by one
print("\n--- Testing imports ---")

try:
    print("1. Importing Database...")
    from shared.database import Database
    print("   ✓ Database imported successfully")
except Exception as e:
    print(f"   ✗ Database import failed: {e}")

try:
    print("2. Importing RedisClient...")
    from shared.redis_client import RedisClient
    print("   ✓ RedisClient imported successfully")
except Exception as e:
    print(f"   ✗ RedisClient import failed: {e}")

try:
    print("3. Importing Crypto...")
    from shared.crypto import Crypto
    print("   ✓ Crypto class imported successfully")
except Exception as e:
    print(f"   ✗ Crypto import failed: {e}")

try:
    print("4. Creating Crypto instance...")
    crypto = Crypto()
    print("   ✓ Crypto instance created successfully")
except Exception as e:
    print(f"   ✗ Crypto instance creation failed: {e}")

try:
    print("5. Importing shared/__init__.py...")
    import shared
    print("   ✓ shared module imported successfully")
except Exception as e:
    print(f"   ✗ shared import failed: {e}")
    import traceback
    traceback.print_exc()

print("\n--- All tests completed ---")