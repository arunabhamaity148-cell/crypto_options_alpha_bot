"""
Secret Management - Encrypt sensitive data
"""

from cryptography.fernet import Fernet
import os

class SecretManager:
    def __init__(self):
        self.key = os.getenv('ENCRYPTION_KEY', Fernet.generate_key())
        self.cipher = Fernet(self.key)
    
    def encrypt(self, data: str) -> bytes:
        return self.cipher.encrypt(data.encode())
    
    def decrypt(self, token: bytes) -> str:
        return self.cipher.decrypt(token).decode()

# Initialize
secret_manager = SecretManager()
