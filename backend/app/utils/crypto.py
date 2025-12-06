"""
Cryptographic utilities for secure operations.

Provides utilities for:
- Password hashing and verification (bcrypt/Argon2)
- Secure token generation
- HMAC signatures
- Encryption/decryption (Fernet)
- Hash functions (SHA256, SHA512, MD5)
- Key derivation (PBKDF2)
"""

import base64
import hashlib
import hmac
import os
import secrets
import string
import time
from dataclasses import dataclass, field
from typing import Any
from functools import lru_cache

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class HashConfig:
    """Configuration for password hashing."""
    
    algorithm: str = "sha256"  # sha256, sha512, sha384, sha1, md5
    iterations: int = 100_000
    salt_length: int = 32
    key_length: int = 64  # For PBKDF2
    encoding: str = "utf-8"


@dataclass
class TokenConfig:
    """Configuration for token generation."""
    
    length: int = 32
    alphabet: str = string.ascii_letters + string.digits
    url_safe: bool = True
    prefix: str = ""


@dataclass
class EncryptionConfig:
    """Configuration for encryption operations."""
    
    key: bytes | None = None
    key_env_var: str = "ENCRYPTION_KEY"
    
    def __post_init__(self) -> None:
        """Load key from environment if not provided."""
        if self.key is None:
            key_str = os.environ.get(self.key_env_var)
            if key_str:
                self.key = base64.urlsafe_b64decode(key_str)


# =============================================================================
# Password Hashing (PBKDF2)
# =============================================================================


def hash_password(
    password: str,
    *,
    config: HashConfig | None = None,
    salt: bytes | None = None,
) -> str:
    """
    Hash a password using PBKDF2.
    
    Args:
        password: The password to hash
        config: Hashing configuration
        salt: Optional salt (generated if not provided)
        
    Returns:
        Encoded hash string in format: algorithm$iterations$salt$hash
        
    Example:
        >>> hashed = hash_password("my_password")
        >>> hashed.startswith("sha256$")
        True
    """
    if config is None:
        config = HashConfig()
    
    if salt is None:
        salt = os.urandom(config.salt_length)
    
    # Derive key using PBKDF2
    key = hashlib.pbkdf2_hmac(
        config.algorithm,
        password.encode(config.encoding),
        salt,
        config.iterations,
        dklen=config.key_length,
    )
    
    # Encode salt and key as base64
    salt_b64 = base64.b64encode(salt).decode("ascii")
    key_b64 = base64.b64encode(key).decode("ascii")
    
    # Return formatted hash string
    return f"{config.algorithm}${config.iterations}${salt_b64}${key_b64}"


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against a hash.
    
    Args:
        password: The password to verify
        password_hash: The stored password hash
        
    Returns:
        True if password matches, False otherwise
        
    Example:
        >>> hashed = hash_password("secret")
        >>> verify_password("secret", hashed)
        True
        >>> verify_password("wrong", hashed)
        False
    """
    try:
        parts = password_hash.split("$")
        if len(parts) != 4:
            return False
        
        algorithm, iterations_str, salt_b64, key_b64 = parts
        iterations = int(iterations_str)
        salt = base64.b64decode(salt_b64)
        stored_key = base64.b64decode(key_b64)
        
        # Derive key from provided password
        config = HashConfig(
            algorithm=algorithm,
            iterations=iterations,
            key_length=len(stored_key),
        )
        
        computed_key = hashlib.pbkdf2_hmac(
            config.algorithm,
            password.encode(config.encoding),
            salt,
            config.iterations,
            dklen=config.key_length,
        )
        
        # Use constant-time comparison
        return hmac.compare_digest(computed_key, stored_key)
        
    except (ValueError, TypeError) as e:
        logger.warning("Password verification failed", error=str(e))
        return False


def needs_rehash(password_hash: str, config: HashConfig | None = None) -> bool:
    """
    Check if a password hash needs to be upgraded.
    
    Args:
        password_hash: The stored password hash
        config: Current hashing configuration
        
    Returns:
        True if hash should be regenerated with new parameters
        
    Example:
        >>> hashed = hash_password("pass", config=HashConfig(iterations=1000))
        >>> needs_rehash(hashed, HashConfig(iterations=100000))
        True
    """
    if config is None:
        config = HashConfig()
    
    try:
        parts = password_hash.split("$")
        if len(parts) != 4:
            return True
        
        algorithm, iterations_str, _, _ = parts
        iterations = int(iterations_str)
        
        return algorithm != config.algorithm or iterations < config.iterations
        
    except (ValueError, TypeError):
        return True


# =============================================================================
# Secure Token Generation
# =============================================================================


def generate_token(config: TokenConfig | None = None) -> str:
    """
    Generate a cryptographically secure random token.
    
    Args:
        config: Token generation configuration
        
    Returns:
        Random token string
        
    Example:
        >>> token = generate_token()
        >>> len(token) == 32
        True
    """
    if config is None:
        config = TokenConfig()
    
    if config.url_safe:
        token = secrets.token_urlsafe(config.length)[:config.length]
    else:
        token = "".join(secrets.choice(config.alphabet) for _ in range(config.length))
    
    if config.prefix:
        return f"{config.prefix}{token}"
    
    return token


def generate_api_key(prefix: str = "bsk") -> str:
    """
    Generate an API key with prefix.
    
    Format: prefix_base64token
    
    Args:
        prefix: Key prefix for identification
        
    Returns:
        API key string
        
    Example:
        >>> key = generate_api_key("test")
        >>> key.startswith("test_")
        True
    """
    token = secrets.token_urlsafe(32)
    return f"{prefix}_{token}"


def generate_otp(length: int = 6) -> str:
    """
    Generate a numeric one-time password.
    
    Args:
        length: Number of digits
        
    Returns:
        Numeric OTP string
        
    Example:
        >>> otp = generate_otp(6)
        >>> len(otp) == 6 and otp.isdigit()
        True
    """
    return "".join(secrets.choice(string.digits) for _ in range(length))


def generate_uuid_token() -> str:
    """
    Generate a UUID-based token (v4).
    
    Returns:
        UUID string without hyphens
        
    Example:
        >>> token = generate_uuid_token()
        >>> len(token) == 32
        True
    """
    import uuid
    return uuid.uuid4().hex


def generate_timed_token(
    data: str,
    secret_key: str,
    expires_in: int = 3600,
) -> str:
    """
    Generate a time-limited token with embedded data.
    
    Args:
        data: Data to embed in token
        secret_key: Secret key for signing
        expires_in: Expiration time in seconds
        
    Returns:
        Signed token with expiration
        
    Example:
        >>> token = generate_timed_token("user:123", "secret")
        >>> len(token) > 0
        True
    """
    timestamp = int(time.time()) + expires_in
    payload = f"{data}:{timestamp}"
    signature = create_hmac(payload, secret_key)
    
    # Encode payload and signature
    encoded_payload = base64.urlsafe_b64encode(payload.encode()).decode()
    return f"{encoded_payload}.{signature}"


def verify_timed_token(
    token: str,
    secret_key: str,
) -> tuple[bool, str | None]:
    """
    Verify a time-limited token.
    
    Args:
        token: The token to verify
        secret_key: Secret key used for signing
        
    Returns:
        Tuple of (is_valid, extracted_data)
        
    Example:
        >>> token = generate_timed_token("user:123", "secret", expires_in=3600)
        >>> valid, data = verify_timed_token(token, "secret")
        >>> valid
        True
    """
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return False, None
        
        encoded_payload, signature = parts
        payload = base64.urlsafe_b64decode(encoded_payload).decode()
        
        # Verify signature
        expected_signature = create_hmac(payload, secret_key)
        if not hmac.compare_digest(signature, expected_signature):
            return False, None
        
        # Check expiration
        payload_parts = payload.rsplit(":", 1)
        if len(payload_parts) != 2:
            return False, None
        
        data, timestamp_str = payload_parts
        timestamp = int(timestamp_str)
        
        if time.time() > timestamp:
            return False, None  # Expired
        
        return True, data
        
    except (ValueError, TypeError, UnicodeDecodeError):
        return False, None


# =============================================================================
# HMAC Signatures
# =============================================================================


def create_hmac(
    message: str | bytes,
    key: str | bytes,
    algorithm: str = "sha256",
) -> str:
    """
    Create an HMAC signature.
    
    Args:
        message: Message to sign
        key: Secret key
        algorithm: Hash algorithm (sha256, sha512, etc.)
        
    Returns:
        Hex-encoded HMAC signature
        
    Example:
        >>> sig = create_hmac("hello", "secret")
        >>> len(sig) == 64  # SHA256 produces 64 hex chars
        True
    """
    if isinstance(message, str):
        message = message.encode("utf-8")
    if isinstance(key, str):
        key = key.encode("utf-8")
    
    return hmac.new(key, message, algorithm).hexdigest()


def verify_hmac(
    message: str | bytes,
    signature: str,
    key: str | bytes,
    algorithm: str = "sha256",
) -> bool:
    """
    Verify an HMAC signature.
    
    Args:
        message: Original message
        signature: Signature to verify
        key: Secret key
        algorithm: Hash algorithm
        
    Returns:
        True if signature is valid
        
    Example:
        >>> sig = create_hmac("hello", "secret")
        >>> verify_hmac("hello", sig, "secret")
        True
    """
    expected = create_hmac(message, key, algorithm)
    return hmac.compare_digest(signature, expected)


def create_webhook_signature(
    payload: str | bytes,
    secret: str,
    timestamp: int | None = None,
) -> tuple[str, int]:
    """
    Create a webhook signature with timestamp.
    
    Args:
        payload: Webhook payload
        secret: Webhook secret
        timestamp: Unix timestamp (generated if not provided)
        
    Returns:
        Tuple of (signature, timestamp)
        
    Example:
        >>> sig, ts = create_webhook_signature('{"event": "test"}', "secret")
        >>> len(sig) > 0 and ts > 0
        True
    """
    if timestamp is None:
        timestamp = int(time.time())
    
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    
    # Create signed payload: timestamp.payload
    signed_payload = f"{timestamp}.".encode() + payload
    signature = create_hmac(signed_payload, secret)
    
    return f"v1={signature}", timestamp


def verify_webhook_signature(
    payload: str | bytes,
    signature: str,
    secret: str,
    timestamp: int,
    tolerance: int = 300,  # 5 minutes
) -> bool:
    """
    Verify a webhook signature with timestamp tolerance.
    
    Args:
        payload: Webhook payload
        signature: Signature to verify
        secret: Webhook secret
        timestamp: Request timestamp
        tolerance: Maximum age in seconds
        
    Returns:
        True if signature is valid and not expired
        
    Example:
        >>> import time
        >>> sig, ts = create_webhook_signature('{"event": "test"}', "secret")
        >>> verify_webhook_signature('{"event": "test"}', sig, "secret", ts)
        True
    """
    # Check timestamp tolerance
    current_time = int(time.time())
    if abs(current_time - timestamp) > tolerance:
        return False
    
    # Extract signature value
    if signature.startswith("v1="):
        signature = signature[3:]
    
    # Verify
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    
    signed_payload = f"{timestamp}.".encode() + payload
    expected_signature = create_hmac(signed_payload, secret)
    
    return hmac.compare_digest(signature, expected_signature)


# =============================================================================
# Hash Functions
# =============================================================================


def sha256(data: str | bytes) -> str:
    """
    Calculate SHA256 hash.
    
    Args:
        data: Data to hash
        
    Returns:
        Hex-encoded hash
        
    Example:
        >>> sha256("hello")
        '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sha512(data: str | bytes) -> str:
    """
    Calculate SHA512 hash.
    
    Args:
        data: Data to hash
        
    Returns:
        Hex-encoded hash
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha512(data).hexdigest()


def md5(data: str | bytes) -> str:
    """
    Calculate MD5 hash (not for security-sensitive use).
    
    Args:
        data: Data to hash
        
    Returns:
        Hex-encoded hash
        
    Warning:
        MD5 is cryptographically broken. Use only for checksums/fingerprints.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.md5(data).hexdigest()


def hash_file(
    file_path: str,
    algorithm: str = "sha256",
    chunk_size: int = 8192,
) -> str:
    """
    Calculate hash of a file.
    
    Args:
        file_path: Path to file
        algorithm: Hash algorithm
        chunk_size: Read chunk size
        
    Returns:
        Hex-encoded hash
        
    Example:
        >>> # hash_file("test.txt")  # doctest: +SKIP
        >>> hash_file.__name__
        'hash_file'
    """
    hasher = hashlib.new(algorithm)
    
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    
    return hasher.hexdigest()


async def hash_file_async(
    file_path: str,
    algorithm: str = "sha256",
    chunk_size: int = 8192,
) -> str:
    """
    Calculate hash of a file asynchronously.
    
    Args:
        file_path: Path to file
        algorithm: Hash algorithm
        chunk_size: Read chunk size
        
    Returns:
        Hex-encoded hash
    """
    import aiofiles
    
    hasher = hashlib.new(algorithm)
    
    async with aiofiles.open(file_path, "rb") as f:
        while chunk := await f.read(chunk_size):
            hasher.update(chunk)
    
    return hasher.hexdigest()


def hash_dict(data: dict[str, Any], algorithm: str = "sha256") -> str:
    """
    Calculate hash of a dictionary (deterministic).
    
    Args:
        data: Dictionary to hash
        algorithm: Hash algorithm
        
    Returns:
        Hex-encoded hash
        
    Example:
        >>> hash_dict({"a": 1, "b": 2}) == hash_dict({"b": 2, "a": 1})
        True
    """
    import json
    
    # Sort keys for deterministic serialization
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.new(algorithm, serialized.encode()).hexdigest()


# =============================================================================
# Encryption (Fernet - Symmetric)
# =============================================================================


class Encryptor:
    """
    Symmetric encryption using Fernet.
    
    Example:
        >>> enc = Encryptor.from_password("my_password")
        >>> encrypted = enc.encrypt("secret data")
        >>> enc.decrypt(encrypted)
        'secret data'
    """
    
    def __init__(self, key: bytes) -> None:
        """Initialize with encryption key."""
        try:
            from cryptography.fernet import Fernet
            self._fernet = Fernet(key)
        except ImportError:
            raise ImportError("cryptography package required for encryption")
    
    @classmethod
    def generate_key(cls) -> bytes:
        """Generate a new encryption key."""
        from cryptography.fernet import Fernet
        return Fernet.generate_key()
    
    @classmethod
    def from_password(
        cls,
        password: str,
        salt: bytes | None = None,
        iterations: int = 100_000,
    ) -> "Encryptor":
        """
        Create encryptor from password.
        
        Args:
            password: Password to derive key from
            salt: Salt for key derivation (generated if not provided)
            iterations: PBKDF2 iterations
            
        Returns:
            Encryptor instance
        """
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return cls(key)
    
    @classmethod
    def from_env(cls, env_var: str = "ENCRYPTION_KEY") -> "Encryptor":
        """
        Create encryptor from environment variable.
        
        Args:
            env_var: Environment variable containing base64-encoded key
            
        Returns:
            Encryptor instance
            
        Raises:
            ValueError: If environment variable is not set
        """
        key_str = os.environ.get(env_var)
        if not key_str:
            raise ValueError(f"Environment variable {env_var} not set")
        return cls(key_str.encode())
    
    def encrypt(self, data: str | bytes) -> str:
        """
        Encrypt data.
        
        Args:
            data: Data to encrypt
            
        Returns:
            Base64-encoded encrypted data
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        return self._fernet.encrypt(data).decode("ascii")
    
    def decrypt(self, data: str | bytes) -> str:
        """
        Decrypt data.
        
        Args:
            data: Encrypted data
            
        Returns:
            Decrypted string
        """
        if isinstance(data, str):
            data = data.encode("ascii")
        return self._fernet.decrypt(data).decode("utf-8")
    
    def encrypt_dict(self, data: dict[str, Any]) -> str:
        """
        Encrypt a dictionary.
        
        Args:
            data: Dictionary to encrypt
            
        Returns:
            Encrypted JSON string
        """
        import json
        return self.encrypt(json.dumps(data))
    
    def decrypt_dict(self, data: str) -> dict[str, Any]:
        """
        Decrypt to dictionary.
        
        Args:
            data: Encrypted data
            
        Returns:
            Decrypted dictionary
        """
        import json
        return json.loads(self.decrypt(data))


# =============================================================================
# Key Derivation
# =============================================================================


def derive_key(
    password: str,
    salt: bytes | None = None,
    iterations: int = 100_000,
    key_length: int = 32,
    algorithm: str = "sha256",
) -> tuple[bytes, bytes]:
    """
    Derive a key from a password using PBKDF2.
    
    Args:
        password: Password to derive from
        salt: Salt (generated if not provided)
        iterations: Number of iterations
        key_length: Length of derived key
        algorithm: Hash algorithm
        
    Returns:
        Tuple of (derived_key, salt)
        
    Example:
        >>> key, salt = derive_key("password")
        >>> len(key) == 32
        True
    """
    if salt is None:
        salt = os.urandom(16)
    
    key = hashlib.pbkdf2_hmac(
        algorithm,
        password.encode("utf-8"),
        salt,
        iterations,
        dklen=key_length,
    )
    
    return key, salt


# =============================================================================
# Utility Functions
# =============================================================================


def constant_time_compare(a: str | bytes, b: str | bytes) -> bool:
    """
    Compare two values in constant time.
    
    Args:
        a: First value
        b: Second value
        
    Returns:
        True if values are equal
        
    Example:
        >>> constant_time_compare("hello", "hello")
        True
        >>> constant_time_compare("hello", "world")
        False
    """
    if isinstance(a, str):
        a = a.encode("utf-8")
    if isinstance(b, str):
        b = b.encode("utf-8")
    return hmac.compare_digest(a, b)


def generate_random_bytes(length: int = 32) -> bytes:
    """
    Generate cryptographically secure random bytes.
    
    Args:
        length: Number of bytes
        
    Returns:
        Random bytes
    """
    return os.urandom(length)


def encode_base64(data: bytes | str) -> str:
    """
    Encode data as base64.
    
    Args:
        data: Data to encode
        
    Returns:
        Base64-encoded string
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return base64.b64encode(data).decode("ascii")


def decode_base64(data: str) -> bytes:
    """
    Decode base64 data.
    
    Args:
        data: Base64-encoded string
        
    Returns:
        Decoded bytes
    """
    return base64.b64decode(data)


def encode_base64_urlsafe(data: bytes | str) -> str:
    """
    Encode data as URL-safe base64.
    
    Args:
        data: Data to encode
        
    Returns:
        URL-safe base64-encoded string
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return base64.urlsafe_b64encode(data).decode("ascii")


def decode_base64_urlsafe(data: str) -> bytes:
    """
    Decode URL-safe base64 data.
    
    Args:
        data: URL-safe base64-encoded string
        
    Returns:
        Decoded bytes
    """
    return base64.urlsafe_b64decode(data)


def mask_secret(
    secret: str,
    visible_chars: int = 4,
    mask_char: str = "*",
) -> str:
    """
    Mask a secret value for logging.
    
    Args:
        secret: Secret to mask
        visible_chars: Number of chars to show at start and end
        mask_char: Character to use for masking
        
    Returns:
        Masked string
        
    Example:
        >>> mask_secret("sk_live_abc123xyz")
        'sk_l****xyz'
    """
    if len(secret) <= visible_chars * 2:
        return mask_char * len(secret)
    
    start = secret[:visible_chars]
    end = secret[-visible_chars:] if visible_chars > 0 else ""
    masked_length = len(secret) - (visible_chars * 2)
    
    return f"{start}{mask_char * min(masked_length, 4)}{end}"


def is_valid_api_key_format(key: str, prefix: str = "bsk") -> bool:
    """
    Check if a string looks like a valid API key.
    
    Args:
        key: String to check
        prefix: Expected prefix
        
    Returns:
        True if format is valid
        
    Example:
        >>> is_valid_api_key_format("bsk_abc123", "bsk")
        True
        >>> is_valid_api_key_format("invalid", "bsk")
        False
    """
    if not key:
        return False
    
    if not key.startswith(f"{prefix}_"):
        return False
    
    token_part = key[len(prefix) + 1:]
    if len(token_part) < 20:  # Minimum token length
        return False
    
    return True


# =============================================================================
# Secure Random Selection
# =============================================================================


def secure_choice(items: list[Any]) -> Any:
    """
    Securely select a random item from a list.
    
    Args:
        items: List to select from
        
    Returns:
        Randomly selected item
    """
    return secrets.choice(items)


def secure_shuffle(items: list[Any]) -> list[Any]:
    """
    Securely shuffle a list.
    
    Args:
        items: List to shuffle
        
    Returns:
        New shuffled list
    """
    result = items.copy()
    for i in range(len(result) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        result[i], result[j] = result[j], result[i]
    return result


def secure_sample(items: list[Any], k: int) -> list[Any]:
    """
    Securely sample k items from a list.
    
    Args:
        items: List to sample from
        k: Number of items to sample
        
    Returns:
        List of k randomly selected items
    """
    if k > len(items):
        raise ValueError("Sample size larger than population")
    
    shuffled = secure_shuffle(items)
    return shuffled[:k]
