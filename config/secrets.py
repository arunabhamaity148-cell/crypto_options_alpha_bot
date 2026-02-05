"""
Secret Management
"""

from cryptography.fernet import Fernet
import os

class SecretManager:
    def __init__(self):
        key = os.getenv('ENCRYPTION_KEY')
        if not key:
            key = Fernet.generate_key().decode()
        self.cipher = Fernet(key.encode())
    
    def encrypt(self, data: str) -> str:
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, token: str) -> str:
        return self.cipher.decrypt(token.encode()).decode()

secret_manager = SecretManager()
