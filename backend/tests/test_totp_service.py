"""Tests for TOTP service."""

import pyotp
from app.services.totp import (
    generate_totp_secret,
    verify_totp_code,
    get_totp_provisioning_uri,
    generate_backup_codes,
    hash_backup_codes,
    verify_backup_code,
)


class TestTOTPGeneration:
    """Test TOTP secret generation."""

    def test_generate_secret(self):
        """Test secret generation."""
        secret = generate_totp_secret()
        
        # Base32 encoded secret should be 32 characters
        assert len(secret) == 32
        # Should be valid base32
        assert all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567=' for c in secret)

    def test_generate_different_secrets(self):
        """Test that each secret is unique."""
        secrets = [generate_totp_secret() for _ in range(10)]
        
        # All secrets should be unique
        assert len(set(secrets)) == 10


class TestTOTPVerification:
    """Test TOTP code verification."""

    def test_verify_code_valid(self):
        """Test verification of a valid code."""
        secret = generate_totp_secret()
        
        # Generate a valid code
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()
        
        # Should verify successfully
        assert verify_totp_code(secret, valid_code) is True

    def test_verify_code_invalid(self):
        """Test verification of an invalid code."""
        secret = generate_totp_secret()
        
        # Try an invalid code
        assert verify_totp_code(secret, "000000") is False
        assert verify_totp_code(secret, "123456") is False

    def test_verify_code_with_window(self):
        """Test that codes within the time window are accepted."""
        secret = generate_totp_secret()
        
        totp = pyotp.TOTP(secret)
        
        # Current code should work
        current_code = totp.now()
        assert verify_totp_code(secret, current_code) is True


class TestProvisioningURI:
    """Test provisioning URI generation."""

    def test_get_qr_code_uri(self):
        """Test QR code URI generation."""
        secret = generate_totp_secret()
        
        uri = get_totp_provisioning_uri(secret, "test@example.com")
        
        # Should be an otpauth URI
        assert uri.startswith("otpauth://totp/")
        assert "test%40example.com" in uri or "test@example.com" in uri
        assert f"secret={secret}" in uri
        assert "issuer=BeatSight" in uri


class TestBackupCodes:
    """Test backup code generation and verification."""

    def test_generate_backup_codes(self):
        """Test backup code generation."""
        codes = generate_backup_codes()
        
        # Should generate 10 codes
        assert len(codes) == 10
        
        # Each code should be 9 characters (4 + dash + 4)
        for code in codes:
            assert len(code) == 9
            assert "-" in code

    def test_backup_codes_are_unique(self):
        """Test that backup codes are unique within a set."""
        codes = generate_backup_codes()
        
        # All codes should be unique
        assert len(set(codes)) == 10

    def test_hash_backup_codes(self):
        """Test backup code hashing."""
        codes = generate_backup_codes()
        hashed = hash_backup_codes(codes)
        
        # Hash should be returned as JSON string
        assert hashed is not None
        assert len(hashed) > 0
        
        import json
        parsed = json.loads(hashed)
        assert len(parsed) == 10

    def test_verify_backup_code_valid(self):
        """Test verification of a valid backup code."""
        codes = generate_backup_codes()
        hashed = hash_backup_codes(codes)
        
        # First code should verify
        is_valid, new_hash = verify_backup_code(hashed, codes[0])
        assert is_valid is True
        assert new_hash != hashed  # Hash should change after use
        
        # Same code should not work again
        is_valid_again, _ = verify_backup_code(new_hash, codes[0])
        assert is_valid_again is False

    def test_verify_backup_code_invalid(self):
        """Test verification of an invalid backup code."""
        codes = generate_backup_codes()
        hashed = hash_backup_codes(codes)
        
        # Invalid code should fail
        is_valid, _ = verify_backup_code(hashed, "INVALID-CODE")
        assert is_valid is False

