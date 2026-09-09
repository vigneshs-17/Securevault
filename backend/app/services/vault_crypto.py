from cryptography.fernet import Fernet

from app.core.config import settings


def get_fernet() -> Fernet:
    return Fernet(settings.vault_encryption_key.encode())


def encrypt_value(value: str) -> str:
    fernet = get_fernet()
    return fernet.encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    fernet = get_fernet()
    return fernet.decrypt(value.encode()).decode()