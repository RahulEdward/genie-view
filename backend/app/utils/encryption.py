"""
Encryption Utility
Simple encryption for storing sensitive credentials in database
"""

import base64
import hashlib
from cryptography.fernet import Fernet
from app.config import settings


def _get_key() -> bytes:
    """Generate encryption key from secret"""
    # Use SECRET_KEY to derive encryption key
    secret = settings.SECRET_KEY.encode()
    # Create 32-byte key using SHA256
    key = hashlib.sha256(secret).digest()
    # Fernet requires base64-encoded 32-byte key
    return base64.urlsafe_b64encode(key)


def encrypt(plaintext: str) -> str:
    """Encrypt a string"""
    if not plaintext:
        return ""
    fernet = Fernet(_get_key())
    encrypted = fernet.encrypt(plaintext.encode())
    return encrypted.decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a string"""
    if not ciphertext:
        return ""
    fernet = Fernet(_get_key())
    decrypted = fernet.decrypt(ciphertext.encode())
    return decrypted.decode()
