"""Tests for crypto utilities."""

import os
import time
from unittest import mock

import pytest

from app.utils.crypto import (
    # Password hashing
    hash_password,
    verify_password,
    needs_rehash,
    HashConfig,
    # Token generation
    generate_token,
    generate_api_key,
    generate_otp,
    generate_uuid_token,
    generate_timed_token,
    verify_timed_token,
    TokenConfig,
    # HMAC
    create_hmac,
    verify_hmac,
    create_webhook_signature,
    verify_webhook_signature,
    # Hash functions
    sha256,
    sha512,
    md5,
    hash_file,
    hash_dict,
    # Key derivation
    derive_key,
    # Utilities
    constant_time_compare,
    generate_random_bytes,
    encode_base64,
    decode_base64,
    encode_base64_urlsafe,
    decode_base64_urlsafe,
    mask_secret,
    is_valid_api_key_format,
    # Secure random
    secure_choice,
    secure_shuffle,
    secure_sample,
)


class TestPasswordHashing:
    """Tests for password hashing functions."""
    
    def test_hash_password_default(self):
        """Test basic password hashing."""
        hashed = hash_password("my_password")
        assert hashed.startswith("sha256$")
        parts = hashed.split("$")
        assert len(parts) == 4
    
    def test_hash_password_custom_config(self):
        """Test password hashing with custom config."""
        config = HashConfig(algorithm="sha512", iterations=50000)
        hashed = hash_password("my_password", config=config)
        assert hashed.startswith("sha512$50000$")
    
    def test_hash_password_with_salt(self):
        """Test password hashing with provided salt."""
        salt = b"fixed_salt_16_by"
        hashed1 = hash_password("password", salt=salt)
        hashed2 = hash_password("password", salt=salt)
        assert hashed1 == hashed2
    
    def test_hash_password_different_passwords(self):
        """Test different passwords produce different hashes."""
        hashed1 = hash_password("password1")
        hashed2 = hash_password("password2")
        assert hashed1 != hashed2
    
    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        hashed = hash_password("secret_password")
        assert verify_password("secret_password", hashed) is True
    
    def test_verify_password_wrong(self):
        """Test password verification with wrong password."""
        hashed = hash_password("secret_password")
        assert verify_password("wrong_password", hashed) is False
    
    def test_verify_password_invalid_hash_format(self):
        """Test verification with invalid hash format."""
        assert verify_password("password", "invalid_hash") is False
        assert verify_password("password", "only$two$parts") is False
        assert verify_password("password", "") is False
    
    def test_verify_password_invalid_base64(self):
        """Test verification with invalid base64 in hash."""
        assert verify_password("password", "sha256$100000$!!!$!!!") is False
    
    def test_needs_rehash_same_params(self):
        """Test needs_rehash with same parameters."""
        config = HashConfig()
        hashed = hash_password("password", config=config)
        assert needs_rehash(hashed, config) is False
    
    def test_needs_rehash_different_algorithm(self):
        """Test needs_rehash with different algorithm."""
        hashed = hash_password("password", config=HashConfig(algorithm="sha256"))
        assert needs_rehash(hashed, HashConfig(algorithm="sha512")) is True
    
    def test_needs_rehash_fewer_iterations(self):
        """Test needs_rehash with fewer iterations."""
        hashed = hash_password("password", config=HashConfig(iterations=50000))
        assert needs_rehash(hashed, HashConfig(iterations=100000)) is True
    
    def test_needs_rehash_more_iterations(self):
        """Test needs_rehash with more iterations (no rehash needed)."""
        hashed = hash_password("password", config=HashConfig(iterations=100000))
        assert needs_rehash(hashed, HashConfig(iterations=50000)) is False
    
    def test_needs_rehash_invalid_format(self):
        """Test needs_rehash with invalid hash format."""
        assert needs_rehash("invalid") is True
        assert needs_rehash("") is True


class TestTokenGeneration:
    """Tests for token generation functions."""
    
    def test_generate_token_default(self):
        """Test default token generation."""
        token = generate_token()
        assert len(token) == 32
        assert token.isalnum() or "-" in token or "_" in token
    
    def test_generate_token_custom_length(self):
        """Test token with custom length."""
        config = TokenConfig(length=64)
        token = generate_token(config)
        assert len(token) == 64
    
    def test_generate_token_with_prefix(self):
        """Test token with prefix."""
        config = TokenConfig(prefix="test_")
        token = generate_token(config)
        assert token.startswith("test_")
    
    def test_generate_token_not_url_safe(self):
        """Test non-URL-safe token."""
        config = TokenConfig(url_safe=False, length=100)
        token = generate_token(config)
        assert len(token) == 100
    
    def test_generate_token_uniqueness(self):
        """Test tokens are unique."""
        tokens = {generate_token() for _ in range(100)}
        assert len(tokens) == 100
    
    def test_generate_api_key_default(self):
        """Test API key generation with default prefix."""
        key = generate_api_key()
        assert key.startswith("bsk_")
        assert len(key) > 40
    
    def test_generate_api_key_custom_prefix(self):
        """Test API key with custom prefix."""
        key = generate_api_key(prefix="test")
        assert key.startswith("test_")
    
    def test_generate_otp_default(self):
        """Test OTP generation with default length."""
        otp = generate_otp()
        assert len(otp) == 6
        assert otp.isdigit()
    
    def test_generate_otp_custom_length(self):
        """Test OTP with custom length."""
        otp = generate_otp(8)
        assert len(otp) == 8
        assert otp.isdigit()
    
    def test_generate_uuid_token(self):
        """Test UUID token generation."""
        token = generate_uuid_token()
        assert len(token) == 32
        assert all(c in "0123456789abcdef" for c in token)


class TestTimedTokens:
    """Tests for timed token functions."""
    
    def test_generate_timed_token(self):
        """Test timed token generation."""
        token = generate_timed_token("user:123", "secret_key")
        assert "." in token
        parts = token.split(".")
        assert len(parts) == 2
    
    def test_verify_timed_token_valid(self):
        """Test valid timed token verification."""
        token = generate_timed_token("user:123", "secret_key", expires_in=3600)
        valid, data = verify_timed_token(token, "secret_key")
        assert valid is True
        assert data == "user:123"
    
    def test_verify_timed_token_expired(self):
        """Test expired token verification."""
        # Create token that expires immediately
        token = generate_timed_token("user:123", "secret_key", expires_in=-1)
        valid, data = verify_timed_token(token, "secret_key")
        assert valid is False
        assert data is None
    
    def test_verify_timed_token_wrong_key(self):
        """Test token with wrong key."""
        token = generate_timed_token("user:123", "secret_key")
        valid, data = verify_timed_token(token, "wrong_key")
        assert valid is False
        assert data is None
    
    def test_verify_timed_token_invalid_format(self):
        """Test invalid token format."""
        valid, data = verify_timed_token("invalid_token", "secret_key")
        assert valid is False
        assert data is None
    
    def test_verify_timed_token_tampered(self):
        """Test tampered token."""
        token = generate_timed_token("user:123", "secret_key")
        tampered = token[:-5] + "xxxxx"
        valid, data = verify_timed_token(tampered, "secret_key")
        assert valid is False


class TestHMAC:
    """Tests for HMAC functions."""
    
    def test_create_hmac_string(self):
        """Test HMAC creation with string."""
        sig = create_hmac("hello", "secret")
        assert len(sig) == 64  # SHA256 hex
    
    def test_create_hmac_bytes(self):
        """Test HMAC creation with bytes."""
        sig = create_hmac(b"hello", b"secret")
        assert len(sig) == 64
    
    def test_create_hmac_different_algorithms(self):
        """Test HMAC with different algorithms."""
        sha256_sig = create_hmac("hello", "secret", "sha256")
        sha512_sig = create_hmac("hello", "secret", "sha512")
        assert len(sha256_sig) == 64
        assert len(sha512_sig) == 128
    
    def test_verify_hmac_valid(self):
        """Test valid HMAC verification."""
        sig = create_hmac("hello", "secret")
        assert verify_hmac("hello", sig, "secret") is True
    
    def test_verify_hmac_invalid(self):
        """Test invalid HMAC verification."""
        sig = create_hmac("hello", "secret")
        assert verify_hmac("hello", sig, "wrong") is False
        assert verify_hmac("world", sig, "secret") is False
    
    def test_create_webhook_signature(self):
        """Test webhook signature creation."""
        sig, ts = create_webhook_signature('{"event": "test"}', "webhook_secret")
        assert sig.startswith("v1=")
        assert ts > 0
    
    def test_create_webhook_signature_with_timestamp(self):
        """Test webhook signature with specific timestamp."""
        sig, ts = create_webhook_signature('{"event": "test"}', "secret", timestamp=1234567890)
        assert ts == 1234567890
    
    def test_verify_webhook_signature_valid(self):
        """Test valid webhook signature verification."""
        payload = '{"event": "test"}'
        sig, ts = create_webhook_signature(payload, "webhook_secret")
        assert verify_webhook_signature(payload, sig, "webhook_secret", ts) is True
    
    def test_verify_webhook_signature_expired(self):
        """Test expired webhook signature."""
        payload = '{"event": "test"}'
        old_timestamp = int(time.time()) - 600  # 10 minutes ago
        sig, _ = create_webhook_signature(payload, "secret", timestamp=old_timestamp)
        assert verify_webhook_signature(payload, sig, "secret", old_timestamp, tolerance=300) is False
    
    def test_verify_webhook_signature_wrong_secret(self):
        """Test webhook with wrong secret."""
        payload = '{"event": "test"}'
        sig, ts = create_webhook_signature(payload, "secret")
        assert verify_webhook_signature(payload, sig, "wrong_secret", ts) is False


class TestHashFunctions:
    """Tests for hash functions."""
    
    def test_sha256(self):
        """Test SHA256 hash."""
        result = sha256("hello")
        assert result == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    
    def test_sha256_bytes(self):
        """Test SHA256 with bytes input."""
        result = sha256(b"hello")
        assert result == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    
    def test_sha512(self):
        """Test SHA512 hash."""
        result = sha512("hello")
        assert len(result) == 128
    
    def test_md5(self):
        """Test MD5 hash."""
        result = md5("hello")
        assert result == "5d41402abc4b2a76b9719d911017c592"
    
    def test_hash_file(self, tmp_path):
        """Test file hashing."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")
        
        result = hash_file(str(test_file))
        assert len(result) == 64  # SHA256
    
    def test_hash_file_different_algorithm(self, tmp_path):
        """Test file hashing with different algorithm."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")
        
        result = hash_file(str(test_file), algorithm="md5")
        assert len(result) == 32  # MD5
    
    def test_hash_dict_deterministic(self):
        """Test dict hashing is deterministic."""
        dict1 = {"a": 1, "b": 2}
        dict2 = {"b": 2, "a": 1}  # Different order
        assert hash_dict(dict1) == hash_dict(dict2)
    
    def test_hash_dict_different_values(self):
        """Test different dicts produce different hashes."""
        dict1 = {"a": 1}
        dict2 = {"a": 2}
        assert hash_dict(dict1) != hash_dict(dict2)


class TestKeyDerivation:
    """Tests for key derivation functions."""
    
    def test_derive_key_default(self):
        """Test key derivation with defaults."""
        key, salt = derive_key("password")
        assert len(key) == 32
        assert len(salt) == 16
    
    def test_derive_key_custom_length(self):
        """Test key derivation with custom length."""
        key, salt = derive_key("password", key_length=64)
        assert len(key) == 64
    
    def test_derive_key_with_salt(self):
        """Test key derivation with provided salt."""
        salt = b"fixed_salt_16_by"
        key1, _ = derive_key("password", salt=salt)
        key2, _ = derive_key("password", salt=salt)
        assert key1 == key2
    
    def test_derive_key_deterministic(self):
        """Test key derivation is deterministic with same inputs."""
        salt = b"test_salt_123456"
        key1, _ = derive_key("password", salt=salt, iterations=1000)
        key2, _ = derive_key("password", salt=salt, iterations=1000)
        assert key1 == key2


class TestUtilityFunctions:
    """Tests for utility functions."""
    
    def test_constant_time_compare_equal(self):
        """Test constant time compare with equal values."""
        assert constant_time_compare("hello", "hello") is True
        assert constant_time_compare(b"hello", b"hello") is True
    
    def test_constant_time_compare_different(self):
        """Test constant time compare with different values."""
        assert constant_time_compare("hello", "world") is False
        assert constant_time_compare(b"hello", b"world") is False
    
    def test_constant_time_compare_mixed_types(self):
        """Test constant time compare with mixed types."""
        assert constant_time_compare("hello", b"hello") is True
    
    def test_generate_random_bytes(self):
        """Test random bytes generation."""
        bytes1 = generate_random_bytes(32)
        bytes2 = generate_random_bytes(32)
        assert len(bytes1) == 32
        assert bytes1 != bytes2
    
    def test_encode_decode_base64(self):
        """Test base64 encoding/decoding."""
        original = b"hello world"
        encoded = encode_base64(original)
        decoded = decode_base64(encoded)
        assert decoded == original
    
    def test_encode_base64_string(self):
        """Test base64 encoding with string input."""
        encoded = encode_base64("hello")
        decoded = decode_base64(encoded)
        assert decoded == b"hello"
    
    def test_encode_decode_base64_urlsafe(self):
        """Test URL-safe base64."""
        original = b"hello+world/test"
        encoded = encode_base64_urlsafe(original)
        assert "+" not in encoded
        assert "/" not in encoded
        decoded = decode_base64_urlsafe(encoded)
        assert decoded == original
    
    def test_mask_secret(self):
        """Test secret masking."""
        # "sk_live_abc123xyz" has 17 chars, visible_chars=4 shows first 4 and last 4
        assert mask_secret("sk_live_abc123xyz") == "sk_l****3xyz"
        assert mask_secret("short") == "*****"  # Too short (5 chars <= 4*2)
    
    def test_mask_secret_custom_chars(self):
        """Test masking with custom visible chars."""
        result = mask_secret("1234567890", visible_chars=2)
        assert result == "12****90"
    
    def test_is_valid_api_key_format_valid(self):
        """Test valid API key format."""
        assert is_valid_api_key_format("bsk_abcdefghijklmnopqrstuvwxyz") is True
    
    def test_is_valid_api_key_format_invalid(self):
        """Test invalid API key formats."""
        assert is_valid_api_key_format("invalid") is False
        assert is_valid_api_key_format("bsk_short") is False  # Too short
        assert is_valid_api_key_format("") is False
        assert is_valid_api_key_format("wrong_prefix_abc123") is False


class TestSecureRandom:
    """Tests for secure random functions."""
    
    def test_secure_choice(self):
        """Test secure choice."""
        items = [1, 2, 3, 4, 5]
        for _ in range(10):
            choice = secure_choice(items)
            assert choice in items
    
    def test_secure_shuffle(self):
        """Test secure shuffle."""
        items = [1, 2, 3, 4, 5]
        shuffled = secure_shuffle(items)
        
        # Original unchanged
        assert items == [1, 2, 3, 4, 5]
        
        # Same elements
        assert sorted(shuffled) == items
    
    def test_secure_shuffle_randomness(self):
        """Test shuffle produces different orders."""
        items = list(range(10))
        results = [tuple(secure_shuffle(items)) for _ in range(5)]
        # At least some should be different
        assert len(set(results)) > 1
    
    def test_secure_sample(self):
        """Test secure sample."""
        items = [1, 2, 3, 4, 5]
        sample = secure_sample(items, 3)
        assert len(sample) == 3
        assert all(item in items for item in sample)
    
    def test_secure_sample_too_large(self):
        """Test sample larger than population."""
        items = [1, 2, 3]
        with pytest.raises(ValueError):
            secure_sample(items, 5)


class TestEncryptor:
    """Tests for Encryptor class."""
    
    @pytest.fixture
    def encryptor(self):
        """Create encryptor with generated key."""
        from app.utils.crypto import Encryptor
        key = Encryptor.generate_key()
        return Encryptor(key)
    
    def test_encrypt_decrypt_string(self, encryptor):
        """Test string encryption/decryption."""
        original = "secret data"
        encrypted = encryptor.encrypt(original)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == original
    
    def test_encrypt_decrypt_bytes(self, encryptor):
        """Test bytes encryption/decryption."""
        original = b"secret data"
        encrypted = encryptor.encrypt(original)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == original.decode()
    
    def test_encrypt_dict(self, encryptor):
        """Test dict encryption/decryption."""
        original = {"key": "value", "number": 123}
        encrypted = encryptor.encrypt_dict(original)
        decrypted = encryptor.decrypt_dict(encrypted)
        assert decrypted == original
    
    def test_from_password(self):
        """Test encryptor from password."""
        from app.utils.crypto import Encryptor
        salt = b"fixed_salt_16_by"
        
        enc1 = Encryptor.from_password("password", salt=salt)
        enc2 = Encryptor.from_password("password", salt=salt)
        
        encrypted = enc1.encrypt("secret")
        decrypted = enc2.decrypt(encrypted)
        assert decrypted == "secret"
    
    def test_from_env(self, monkeypatch):
        """Test encryptor from environment variable."""
        from app.utils.crypto import Encryptor
        
        # Generate a valid key and set it
        key = Encryptor.generate_key()
        monkeypatch.setenv("TEST_ENCRYPTION_KEY", key.decode())
        
        enc = Encryptor.from_env("TEST_ENCRYPTION_KEY")
        encrypted = enc.encrypt("test")
        decrypted = enc.decrypt(encrypted)
        assert decrypted == "test"
    
    def test_from_env_not_set(self):
        """Test encryptor from unset environment variable."""
        from app.utils.crypto import Encryptor
        
        with pytest.raises(ValueError, match="not set"):
            Encryptor.from_env("NONEXISTENT_KEY_VAR")
    
    def test_different_keys_fail(self):
        """Test decryption fails with different key."""
        from app.utils.crypto import Encryptor
        from cryptography.fernet import InvalidToken
        
        enc1 = Encryptor(Encryptor.generate_key())
        enc2 = Encryptor(Encryptor.generate_key())
        
        encrypted = enc1.encrypt("secret")
        with pytest.raises(InvalidToken):
            enc2.decrypt(encrypted)


class TestHashFileAsync:
    """Tests for async file hashing."""
    
    @pytest.mark.asyncio
    async def test_hash_file_async(self, tmp_path):
        """Test async file hashing."""
        from app.utils.crypto import hash_file_async
        
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")
        
        result = await hash_file_async(str(test_file))
        sync_result = hash_file(str(test_file))
        
        assert result == sync_result
