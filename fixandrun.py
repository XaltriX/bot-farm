"""
Direct run karo: python fix_and_run.py
Yeh automatically cache clear karke bot start karega
"""

import os
import sys
import shutil
import subprocess

print("🔄 Fixing cache issues...")

# Clear Python cache
cache_dirs = [
    "__pycache__",
    "admin_bot/__pycache__",
    "worker/__pycache__",
    "shared/__pycache__"
]

for cache_dir in cache_dirs:
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
        print(f"✅ Cleared {cache_dir}")

print("\n🚀 Starting admin bot...")
print("="*50)

# Run admin bot
subprocess.run([sys.executable, "-m", "admin_bot.main"])