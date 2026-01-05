# shared/crypto.py
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC  # ✓ CORRECT!


class Crypto:
    def __init__(self):
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            raise ValueError(
                "ENCRYPTION_KEY not set. Add it in root .env file"
            )
        
        # Minimum length check
        if len(key) < 32:
            raise ValueError("ENCRYPTION_KEY must be at least 32 characters")
        
        # Convert any string to valid Fernet key using PBKDF2HMAC
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'telegram_bot_farm_salt',  # Fixed salt for consistency
            iterations=100000,
        )
        
        # Derive a proper 32-byte key and encode as base64
        derived_key = kdf.derive(key.encode())
        self.key = base64.urlsafe_b64encode(derived_key)
        self.fernet = Fernet(self.key)
    
    def encrypt(self, text: str) -> str:
        """Encrypt plain text to encrypted token"""
        return self.fernet.encrypt(text.encode()).decode()
    
    def decrypt(self, token: str) -> str:
        """Decrypt encrypted token to plain text"""
        return self.fernet.decrypt(token.encode()).decode()


def generate_encryption_key() -> str:
    """Generate a secure encryption key for .env file"""
    return Fernet.generate_key().decode()


# Example usage:
if __name__ == "__main__":
    print("Generated Key:", generate_encryption_key())