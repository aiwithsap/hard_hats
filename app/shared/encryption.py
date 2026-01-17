"""Encryption utilities for sensitive data like RTSP credentials."""

import os
import base64
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

# Encryption key from environment
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

_fernet: Optional[Fernet] = None


def get_fernet() -> Fernet:
    """Get or create Fernet cipher."""
    global _fernet
    if _fernet is None:
        if not ENCRYPTION_KEY:
            raise ValueError(
                "ENCRYPTION_KEY environment variable is required. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _fernet = Fernet(ENCRYPTION_KEY.encode())
    return _fernet


def encrypt(data: str) -> str:
    """
    Encrypt a string.

    Args:
        data: Plain text string to encrypt

    Returns:
        Base64-encoded encrypted string
    """
    fernet = get_fernet()
    encrypted = fernet.encrypt(data.encode())
    return encrypted.decode()


def decrypt(encrypted_data: str) -> str:
    """
    Decrypt an encrypted string.

    Args:
        encrypted_data: Base64-encoded encrypted string

    Returns:
        Original plain text string

    Raises:
        InvalidToken: If decryption fails (wrong key or corrupted data)
    """
    fernet = get_fernet()
    decrypted = fernet.decrypt(encrypted_data.encode())
    return decrypted.decode()


def encrypt_credentials(username: str, password: str) -> str:
    """
    Encrypt RTSP credentials.

    Args:
        username: RTSP username
        password: RTSP password

    Returns:
        Encrypted credentials string
    """
    combined = f"{username}:{password}"
    return encrypt(combined)


def decrypt_credentials(encrypted_creds: str) -> tuple[str, str]:
    """
    Decrypt RTSP credentials.

    Args:
        encrypted_creds: Encrypted credentials string

    Returns:
        Tuple of (username, password)

    Raises:
        InvalidToken: If decryption fails
        ValueError: If credentials format is invalid
    """
    decrypted = decrypt(encrypted_creds)
    if ":" not in decrypted:
        raise ValueError("Invalid credentials format")

    username, password = decrypted.split(":", 1)
    return username, password


def safe_decrypt(encrypted_data: Optional[str]) -> Optional[str]:
    """
    Safely decrypt data, returning None on failure.

    Args:
        encrypted_data: Encrypted string or None

    Returns:
        Decrypted string or None if decryption fails
    """
    if not encrypted_data:
        return None

    try:
        return decrypt(encrypted_data)
    except (InvalidToken, ValueError):
        return None


def is_encryption_configured() -> bool:
    """Check if encryption is properly configured."""
    return bool(ENCRYPTION_KEY)
