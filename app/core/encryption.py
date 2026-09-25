from cryptography.fernet import Fernet

from app.core.config import settings

class EncryptionService:
    """Symmetric encryption for sensitive data at rest (e.g. KYC document
    numbers, Section 15). Deliberately does NOT handle passwords — that's
    security.py's job (§7.3); one algorithm, one place, per concern."""

    @staticmethod
    def _get_cipher() -> Fernet:
        return Fernet(settings.ENCRYPTION_KEY.encode())

    @staticmethod
    def encrypt(plaintext: str) -> str:
        return EncryptionService._get_cipher().encrypt(plaintext.encode()).decode()

    @staticmethod
    def decrypt(ciphertext: str) -> str:
        return EncryptionService._get_cipher().decrypt(ciphertext.encode()).decode()
