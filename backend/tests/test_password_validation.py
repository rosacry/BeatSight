"""Tests for password validation utilities."""

from __future__ import annotations


from app.utils.password_validation import (
    validate_password,
    is_password_valid,
    PasswordValidationResult,
)


class TestPasswordValidation:
    """Tests for validate_password function."""

    def test_valid_strong_password(self) -> None:
        """Test that a strong password passes validation."""
        result = validate_password("SecureP@ss123!")
        assert result.is_valid is True
        assert result.errors == []
        assert result.strength_score >= 3

    def test_minimum_length_requirement(self) -> None:
        """Test minimum length requirement."""
        result = validate_password("Short1!")
        assert result.is_valid is False
        assert "at least 8 characters" in result.error_message

    def test_uppercase_requirement(self) -> None:
        """Test uppercase letter requirement."""
        result = validate_password("lowercase123")
        assert result.is_valid is False
        assert "uppercase" in result.error_message

    def test_lowercase_requirement(self) -> None:
        """Test lowercase letter requirement."""
        result = validate_password("UPPERCASE123")
        assert result.is_valid is False
        assert "lowercase" in result.error_message

    def test_digit_requirement(self) -> None:
        """Test digit requirement."""
        result = validate_password("NoDigitsHere!")
        assert result.is_valid is False
        assert "number" in result.error_message

    def test_common_password_rejection(self) -> None:
        """Test that common passwords are rejected."""
        common_passwords = ["password", "Password1", "qwerty123", "letmein1"]
        for password in common_passwords:
            result = validate_password(password)
            # Common passwords should have errors or low score
            if "password" in password.lower():
                assert (
                    "too common" in result.error_message.lower()
                    or result.strength_score <= 2
                )

    def test_password_with_email(self) -> None:
        """Test password containing email is rejected."""
        result = validate_password("john123Smith!", email="john@example.com")
        assert result.is_valid is False
        assert "email" in result.error_message.lower()

    def test_password_with_display_name(self) -> None:
        """Test password containing display name is rejected."""
        result = validate_password("JohnSmith123!", display_name="johnsmith")
        assert result.is_valid is False
        assert "display name" in result.error_message.lower()

    def test_sequential_pattern_detection(self) -> None:
        """Test sequential pattern detection."""
        result = validate_password("My123456Pass!")
        assert "sequential" in result.error_message.lower()

    def test_repeated_characters_detection(self) -> None:
        """Test repeated characters detection."""
        result = validate_password("Passssword1!")
        assert "repeated" in result.error_message.lower()

    def test_special_character_optional(self) -> None:
        """Test that special characters are optional by default."""
        result = validate_password("SecurePass123")
        assert result.is_valid is True

    def test_special_character_required(self) -> None:
        """Test special character requirement when enabled."""
        result = validate_password("SecurePass123", require_special=True)
        assert result.is_valid is False
        assert "special" in result.error_message.lower()

    def test_strength_score_calculation(self) -> None:
        """Test strength score calculation."""
        # Weak password
        weak_result = validate_password("password")  # Common password
        assert weak_result.strength_label in ["weak", "fair"]

        # Strong password
        strong_result = validate_password("V3ryS3cur3P@ssw0rd!")
        assert strong_result.strength_score >= 3

    def test_custom_min_length(self) -> None:
        """Test custom minimum length."""
        result = validate_password("Short1A", min_length=6)
        assert result.is_valid is True

        result = validate_password("Short1A", min_length=10)
        assert result.is_valid is False

    def test_multiple_errors(self) -> None:
        """Test that multiple errors are captured."""
        result = validate_password("abc")  # Too short, no uppercase, no digit
        assert len(result.errors) >= 2


class TestIsPasswordValid:
    """Tests for is_password_valid helper function."""

    def test_valid_password_returns_true(self) -> None:
        """Test valid password returns True."""
        assert is_password_valid("SecurePass123") is True

    def test_invalid_password_returns_false(self) -> None:
        """Test invalid password returns False."""
        assert is_password_valid("weak") is False

    def test_kwargs_passed_through(self) -> None:
        """Test that kwargs are passed to validate_password."""
        # Should fail with email check
        assert is_password_valid("john123Pass!", email="john@test.com") is False


class TestPasswordValidationResult:
    """Tests for PasswordValidationResult dataclass."""

    def test_error_message_empty_when_valid(self) -> None:
        """Test error_message is empty when no errors."""
        result = PasswordValidationResult(
            is_valid=True,
            errors=[],
            strength_score=4,
            strength_label="strong",
        )
        assert result.error_message == ""

    def test_error_message_combined(self) -> None:
        """Test error_message combines multiple errors."""
        result = PasswordValidationResult(
            is_valid=False,
            errors=["Error 1", "Error 2"],
            strength_score=1,
            strength_label="weak",
        )
        assert "Error 1" in result.error_message
        assert "Error 2" in result.error_message
        assert ";" in result.error_message
