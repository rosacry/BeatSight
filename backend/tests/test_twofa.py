"""Tests for Two-Factor Authentication functionality.

Note: Full integration tests for 2FA API endpoints require proper database fixtures.
These tests focus on the TOTP service unit tests.
For API integration tests, see test_totp_service.py
"""

import pytest
import pyotp

from app.services.totp import (
    generate_totp_secret,
    verify_totp_code,
    get_totp_provisioning_uri,
    generate_backup_codes,
    hash_backup_codes,
    verify_backup_code,
)


class TestTOTPIntegration:
    """Integration tests for TOTP functionality."""

    def test_full_totp_flow(self):
        """Test the complete TOTP setup and verification flow."""
        # 1. Generate secret
        secret = generate_totp_secret()
        assert len(secret) == 32
        
        # 2. Get provisioning URI
        uri = get_totp_provisioning_uri(secret, "test@example.com")
        assert "otpauth://totp/" in uri
        assert secret in uri
        assert "BeatSight" in uri
        
        # 3. Generate a code using pyotp directly (simulating authenticator app)
        totp = pyotp.TOTP(secret)
        code = totp.now()
        
        # 4. Verify the code
        assert verify_totp_code(secret, code) is True
        
        # 5. Verify invalid codes fail
        assert verify_totp_code(secret, "000000") is False
        assert verify_totp_code(secret, "123456") is False

    def test_full_backup_code_flow(self):
        """Test the complete backup code generation and verification flow."""
        # 1. Generate backup codes
        codes = generate_backup_codes(count=10)
        assert len(codes) == 10
        
        # 2. Hash them for storage
        hashed = hash_backup_codes(codes)
        assert hashed is not None
        
        # 3. Verify first code works
        is_valid, new_hash = verify_backup_code(hashed, codes[0])
        assert is_valid is True
        assert new_hash != hashed  # Hash changes after use
        
        # 4. First code no longer works
        is_valid_again, _ = verify_backup_code(new_hash, codes[0])
        assert is_valid_again is False
        
        # 5. Second code still works
        is_valid_second, newer_hash = verify_backup_code(new_hash, codes[1])
        assert is_valid_second is True
        
        # 6. Invalid codes don't work
        is_valid_invalid, _ = verify_backup_code(newer_hash, "INVALID-CODE")
        assert is_valid_invalid is False

    def test_totp_window_tolerance(self):
        """Test that TOTP allows for small time drift."""
        secret = generate_totp_secret()
        
        # Get current code
        totp = pyotp.TOTP(secret)
        current_code = totp.now()
        
        # Should accept current code
        assert verify_totp_code(secret, current_code) is True

    def test_backup_code_format(self):
        """Test backup code format is user-friendly."""
        codes = generate_backup_codes()
        
        for code in codes:
            # Should have format XXXX-XXXX
            parts = code.split("-")
            assert len(parts) == 2
            assert len(parts[0]) == 4
            assert len(parts[1]) == 4
            # All parts should be alphanumeric (hex)
            assert parts[0].isalnum()
            assert parts[1].isalnum()


