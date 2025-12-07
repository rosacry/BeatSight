"""
Two-Factor Authentication (TOTP) service.

Provides TOTP (Time-based One-Time Password) functionality for 2FA.
Uses pyotp for TOTP generation and verification.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pyotp
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging import get_logger
from app.utils.crypto import hash_password, verify_password

if TYPE_CHECKING:
    from app.models.user import User

logger = get_logger(__name__)
settings = get_settings()


def _get_encryption_key() -> bytes:
    """
    Derive a Fernet encryption key from the app's secret key.
    
    Returns:
        32-byte base64-encoded key for Fernet encryption
    """
    # Use SHA-256 to derive a key from the secret
    key = hashlib.sha256(settings.secret_key.encode()).digest()
    return base64.urlsafe_b64encode(key)


def _encrypt_secret(secret: str) -> str:
    """Encrypt a TOTP secret for storage."""
    fernet = Fernet(_get_encryption_key())
    return fernet.encrypt(secret.encode()).decode()


def _decrypt_secret(encrypted: str) -> str:
    """Decrypt a stored TOTP secret."""
    fernet = Fernet(_get_encryption_key())
    return fernet.decrypt(encrypted.encode()).decode()


def generate_totp_secret() -> str:
    """
    Generate a new TOTP secret.
    
    Returns:
        A random 32-character base32 secret
    """
    return pyotp.random_base32(length=32)


def get_totp_provisioning_uri(secret: str, email: str) -> str:
    """
    Generate a provisioning URI for TOTP apps.
    
    Args:
        secret: The TOTP secret
        email: The user's email (used as account name)
    
    Returns:
        otpauth:// URI for QR code generation
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(
        name=email,
        issuer_name="BeatSight"
    )


def verify_totp_code(secret: str, code: str) -> bool:
    """
    Verify a TOTP code.
    
    Args:
        secret: The TOTP secret
        code: The 6-digit code to verify
    
    Returns:
        True if the code is valid
    """
    totp = pyotp.TOTP(secret)
    # Allow 1 step tolerance for clock drift
    return totp.verify(code, valid_window=1)


def generate_backup_codes(count: int = 10) -> list[str]:
    """
    Generate a set of backup codes.
    
    Args:
        count: Number of backup codes to generate
    
    Returns:
        List of 8-character alphanumeric codes
    """
    codes = []
    for _ in range(count):
        # Generate 8-character codes with dashes for readability
        code = secrets.token_hex(4).upper()
        formatted = f"{code[:4]}-{code[4:]}"
        codes.append(formatted)
    return codes


def hash_backup_codes(codes: list[str]) -> str:
    """
    Hash backup codes for secure storage.
    
    Args:
        codes: List of plain backup codes
    
    Returns:
        JSON string of hashed codes
    """
    hashed = []
    for code in codes:
        # Remove dashes for hashing
        clean_code = code.replace("-", "")
        hashed.append(hash_password(clean_code))
    return json.dumps(hashed)


def verify_backup_code(stored_hashes_json: str, code: str) -> tuple[bool, str | None]:
    """
    Verify a backup code and return remaining codes if valid.
    
    Args:
        stored_hashes_json: JSON string of hashed backup codes
        code: The backup code to verify
    
    Returns:
        Tuple of (is_valid, new_hashes_json_or_none)
        If valid, returns new JSON with the used code removed
    """
    try:
        hashes = json.loads(stored_hashes_json)
    except json.JSONDecodeError:
        return False, None
    
    clean_code = code.replace("-", "").upper()
    
    for i, stored_hash in enumerate(hashes):
        if verify_password(clean_code, stored_hash):
            # Remove the used code
            remaining = hashes[:i] + hashes[i+1:]
            return True, json.dumps(remaining)
    
    return False, None


async def setup_totp(
    db: AsyncSession,
    user: "User",
) -> tuple[str, str, list[str]]:
    """
    Set up TOTP for a user (but don't enable it yet).
    
    Args:
        db: Database session
        user: The user to set up TOTP for
    
    Returns:
        Tuple of (secret, provisioning_uri, backup_codes)
    """
    # Generate new secret
    secret = generate_totp_secret()
    provisioning_uri = get_totp_provisioning_uri(secret, user.email)
    backup_codes = generate_backup_codes()
    
    # Store encrypted secret (but don't enable yet)
    user.totp_secret = _encrypt_secret(secret)
    
    # Store hashed backup codes
    user.totp_backup_codes = hash_backup_codes(backup_codes)
    
    await db.commit()
    
    logger.info(
        "TOTP setup initiated",
        user_id=str(user.id),
    )
    
    return secret, provisioning_uri, backup_codes


async def enable_totp(
    db: AsyncSession,
    user: "User",
    verification_code: str,
) -> bool:
    """
    Enable TOTP after verifying the user can generate valid codes.
    
    Args:
        db: Database session
        user: The user to enable TOTP for
        verification_code: A TOTP code to verify setup
    
    Returns:
        True if TOTP was enabled successfully
    """
    if not user.totp_secret:
        return False
    
    # Decrypt and verify
    try:
        secret = _decrypt_secret(user.totp_secret)
    except Exception:
        logger.error("Failed to decrypt TOTP secret", user_id=str(user.id))
        return False
    
    if not verify_totp_code(secret, verification_code):
        return False
    
    # Enable TOTP
    user.totp_enabled = True
    user.totp_enabled_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    logger.info(
        "TOTP enabled",
        user_id=str(user.id),
    )
    
    return True


async def disable_totp(
    db: AsyncSession,
    user: "User",
) -> None:
    """
    Disable TOTP for a user.
    
    Args:
        db: Database session
        user: The user to disable TOTP for
    """
    user.totp_enabled = False
    user.totp_secret = None
    user.totp_backup_codes = None
    user.totp_enabled_at = None
    
    await db.commit()
    
    logger.info(
        "TOTP disabled",
        user_id=str(user.id),
    )


async def verify_totp_for_login(
    db: AsyncSession,
    user: "User",
    code: str,
) -> tuple[bool, str | None]:
    """
    Verify TOTP code for login (supports both TOTP and backup codes).
    
    Args:
        db: Database session
        user: The user to verify
        code: TOTP code or backup code
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not user.totp_enabled or not user.totp_secret:
        return True, None  # 2FA not enabled
    
    # Clean the code
    clean_code = code.replace("-", "").replace(" ", "")
    
    # Try TOTP first (6 digits)
    if len(clean_code) == 6 and clean_code.isdigit():
        try:
            secret = _decrypt_secret(user.totp_secret)
            if verify_totp_code(secret, clean_code):
                return True, None
        except Exception:
            logger.error("Failed to verify TOTP", user_id=str(user.id))
    
    # Try backup code (8 characters)
    if user.totp_backup_codes:
        is_valid, new_hashes = verify_backup_code(user.totp_backup_codes, code)
        if is_valid:
            # Update remaining backup codes
            user.totp_backup_codes = new_hashes
            await db.commit()
            
            logger.info(
                "Backup code used for login",
                user_id=str(user.id),
            )
            
            return True, None
    
    return False, "Invalid verification code"


async def regenerate_backup_codes(
    db: AsyncSession,
    user: "User",
) -> list[str]:
    """
    Regenerate backup codes for a user.
    
    Args:
        db: Database session
        user: The user to regenerate codes for
    
    Returns:
        List of new backup codes
    """
    backup_codes = generate_backup_codes()
    user.totp_backup_codes = hash_backup_codes(backup_codes)
    
    await db.commit()
    
    logger.info(
        "Backup codes regenerated",
        user_id=str(user.id),
    )
    
    return backup_codes


def get_remaining_backup_codes_count(stored_hashes_json: str | None) -> int:
    """
    Get the number of remaining backup codes.
    
    Args:
        stored_hashes_json: JSON string of hashed backup codes
    
    Returns:
        Number of remaining codes
    """
    if not stored_hashes_json:
        return 0
    
    try:
        hashes = json.loads(stored_hashes_json)
        return len(hashes)
    except json.JSONDecodeError:
        return 0
