"""Tests for validation utilities."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.utils.validation import (
    DateRange,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
    Validators,
    is_valid_uuid,
    mask_card_number,
    normalize_email,
    normalize_phone,
    sanitize_filename,
    slugify,
    validate_card_number,
    validate_date_range,
    validate_email,
    validate_filename,
    validate_length,
    validate_one_of,
    validate_pattern,
    validate_phone,
    validate_range,
    validate_required,
    validate_slug,
    validate_url,
    validate_uuid4,
    validate_webhook_url,
)


# =============================================================================
# Email Validation Tests
# =============================================================================

class TestValidateEmail:
    """Tests for email validation."""
    
    def test_valid_email(self):
        """Test valid email addresses."""
        assert validate_email("user@example.com") is True
        assert validate_email("user.name@example.com") is True
        assert validate_email("user+tag@example.com") is True
        assert validate_email("user@subdomain.example.com") is True
    
    def test_invalid_email_no_at(self):
        """Test email without @ symbol."""
        assert validate_email("userexample.com") is False
    
    def test_invalid_email_no_domain(self):
        """Test email without domain."""
        assert validate_email("user@") is False
    
    def test_invalid_email_no_local(self):
        """Test email without local part."""
        assert validate_email("@example.com") is False
    
    def test_empty_email(self):
        """Test empty email."""
        assert validate_email("") is False
        assert validate_email(None) is False  # type: ignore
    
    def test_email_too_long(self):
        """Test email exceeding max length."""
        long_email = "a" * 250 + "@example.com"
        assert validate_email(long_email) is False
    
    def test_disposable_email_allowed(self):
        """Test disposable emails allowed by default."""
        assert validate_email("user@mailinator.com") is True
    
    def test_disposable_email_blocked(self):
        """Test blocking disposable emails."""
        assert validate_email(
            "user@mailinator.com",
            allow_disposable=False
        ) is False
    
    def test_non_disposable_with_block(self):
        """Test non-disposable email passes block."""
        assert validate_email(
            "user@gmail.com",
            allow_disposable=False
        ) is True


class TestNormalizeEmail:
    """Tests for email normalization."""
    
    def test_lowercase_domain(self):
        """Test domain is lowercased."""
        assert normalize_email("User@EXAMPLE.COM") == "User@example.com"
    
    def test_strip_whitespace(self):
        """Test whitespace is stripped."""
        assert normalize_email("  user@example.com  ") == "user@example.com"
    
    def test_preserve_local_case(self):
        """Test local part case is preserved."""
        assert normalize_email("UserName@example.com") == "UserName@example.com"


# =============================================================================
# URL Validation Tests
# =============================================================================

class TestValidateUrl:
    """Tests for URL validation."""
    
    def test_valid_http_url(self):
        """Test valid HTTP URL."""
        assert validate_url("http://example.com") is True
    
    def test_valid_https_url(self):
        """Test valid HTTPS URL."""
        assert validate_url("https://example.com") is True
    
    def test_url_with_path(self):
        """Test URL with path."""
        assert validate_url("https://example.com/path/to/page") is True
    
    def test_url_with_query(self):
        """Test URL with query string."""
        assert validate_url("https://example.com?foo=bar") is True
    
    def test_url_with_port(self):
        """Test URL with port."""
        assert validate_url("https://example.com:8080") is True
    
    def test_invalid_url_no_scheme(self):
        """Test URL without scheme."""
        assert validate_url("example.com") is False
    
    def test_invalid_url_no_domain(self):
        """Test URL without domain."""
        assert validate_url("https://") is False
    
    def test_invalid_scheme(self):
        """Test URL with invalid scheme."""
        assert validate_url("ftp://example.com") is False
    
    def test_require_https(self):
        """Test requiring HTTPS."""
        assert validate_url("http://example.com", require_https=True) is False
        assert validate_url("https://example.com", require_https=True) is True
    
    def test_localhost(self):
        """Test localhost URL."""
        # localhost URLs don't have a dot in netloc but are allowed as special case
        assert validate_url("https://localhost:8000") is True
    
    def test_url_too_long(self):
        """Test URL exceeding max length."""
        long_url = "https://example.com/" + "a" * 2100
        assert validate_url(long_url) is False
    
    def test_empty_url(self):
        """Test empty URL."""
        assert validate_url("") is False


class TestValidateWebhookUrl:
    """Tests for webhook URL validation."""
    
    def test_valid_webhook_url(self):
        """Test valid webhook URL."""
        assert validate_webhook_url("https://api.example.com/webhook") is True
    
    def test_reject_http(self):
        """Test HTTP is rejected."""
        assert validate_webhook_url("http://example.com/webhook") is False
    
    def test_reject_localhost(self):
        """Test localhost is rejected."""
        assert validate_webhook_url("https://localhost/webhook") is False
        assert validate_webhook_url("https://127.0.0.1/webhook") is False
    
    def test_reject_private_ip(self):
        """Test private IPs are rejected."""
        assert validate_webhook_url("https://192.168.1.1/webhook") is False
        assert validate_webhook_url("https://10.0.0.1/webhook") is False
        assert validate_webhook_url("https://172.16.0.1/webhook") is False


# =============================================================================
# UUID Validation Tests
# =============================================================================

class TestUuidValidation:
    """Tests for UUID validation."""
    
    def test_valid_uuid(self):
        """Test valid UUID."""
        assert is_valid_uuid("550e8400-e29b-41d4-a716-446655440000") is True
    
    def test_valid_uuid_uppercase(self):
        """Test uppercase UUID."""
        assert is_valid_uuid("550E8400-E29B-41D4-A716-446655440000") is True
    
    def test_invalid_uuid(self):
        """Test invalid UUID."""
        assert is_valid_uuid("not-a-uuid") is False
    
    def test_uuid_with_version(self):
        """Test UUID version check."""
        uuid4 = "550e8400-e29b-41d4-a716-446655440000"
        assert is_valid_uuid(uuid4, version=4) is True
        assert is_valid_uuid(uuid4, version=1) is False
    
    def test_validate_uuid4(self):
        """Test validate_uuid4 helper."""
        assert validate_uuid4("550e8400-e29b-41d4-a716-446655440000") is True
        assert validate_uuid4("550e8400-e29b-11d4-a716-446655440000") is False  # v1


# =============================================================================
# Slug Validation Tests
# =============================================================================

class TestSlugValidation:
    """Tests for slug validation."""
    
    def test_valid_slug(self):
        """Test valid slugs."""
        assert validate_slug("my-slug") is True
        assert validate_slug("slug123") is True
        assert validate_slug("a") is True
    
    def test_invalid_slug_uppercase(self):
        """Test uppercase slug is invalid."""
        assert validate_slug("My-Slug") is False
    
    def test_invalid_slug_special_chars(self):
        """Test special characters are invalid."""
        assert validate_slug("my_slug") is False
        assert validate_slug("my.slug") is False
    
    def test_invalid_slug_leading_hyphen(self):
        """Test leading hyphen is invalid."""
        assert validate_slug("-my-slug") is False
    
    def test_invalid_slug_trailing_hyphen(self):
        """Test trailing hyphen is invalid."""
        assert validate_slug("my-slug-") is False
    
    def test_slug_length(self):
        """Test slug length constraints."""
        assert validate_slug("ab", min_length=3) is False
        assert validate_slug("abc", min_length=3) is True
        assert validate_slug("abc", max_length=2) is False


class TestSlugify:
    """Tests for slugify function."""
    
    def test_basic_slugify(self):
        """Test basic text to slug."""
        assert slugify("My Blog Post") == "my-blog-post"
    
    def test_slugify_special_chars(self):
        """Test special characters are removed."""
        assert slugify("Hello, World!") == "hello-world"
    
    def test_slugify_underscores(self):
        """Test underscores become hyphens."""
        assert slugify("my_post_title") == "my-post-title"
    
    def test_slugify_multiple_spaces(self):
        """Test multiple spaces become single hyphen."""
        assert slugify("too   many   spaces") == "too-many-spaces"
    
    def test_slugify_truncate(self):
        """Test slug truncation."""
        assert len(slugify("a" * 200, max_length=50)) <= 50


# =============================================================================
# Filename Validation Tests
# =============================================================================

class TestFilenameValidation:
    """Tests for filename validation."""
    
    def test_valid_filename(self):
        """Test valid filenames."""
        assert validate_filename("document.pdf") is True
        assert validate_filename("my-file_v2.txt") is True
    
    def test_invalid_filename_special_chars(self):
        """Test invalid characters."""
        assert validate_filename("file<name>.txt") is False
        assert validate_filename('file"name".txt') is False
        assert validate_filename("file:name.txt") is False
    
    def test_path_traversal(self):
        """Test path traversal is blocked."""
        assert validate_filename("../etc/passwd") is False
        assert validate_filename("..\\windows\\system32") is False
    
    def test_reserved_names(self):
        """Test reserved Windows names."""
        assert validate_filename("CON") is False
        assert validate_filename("PRN.txt") is False
        assert validate_filename("NUL") is False
    
    def test_allowed_extensions(self):
        """Test extension filtering."""
        assert validate_filename(
            "image.jpg",
            allowed_extensions={".jpg", ".png"}
        ) is True
        assert validate_filename(
            "script.exe",
            allowed_extensions={".jpg", ".png"}
        ) is False


class TestSanitizeFilename:
    """Tests for filename sanitization."""
    
    def test_remove_invalid_chars(self):
        """Test invalid characters are removed."""
        assert sanitize_filename("file<name>.txt") == "file_name_.txt"
    
    def test_remove_path_traversal(self):
        """Test path traversal is removed."""
        result = sanitize_filename("../secret.txt")
        assert ".." not in result
    
    def test_empty_becomes_unnamed(self):
        """Test empty filename becomes 'unnamed'."""
        # After stripping dots and spaces, if result is empty, return 'unnamed'
        assert sanitize_filename("") == "unnamed"


# =============================================================================
# Phone Validation Tests
# =============================================================================

class TestPhoneValidation:
    """Tests for phone validation."""
    
    def test_valid_e164(self):
        """Test valid E.164 format."""
        assert validate_phone("+14155551234") is True
        assert validate_phone("+442071234567") is True
    
    def test_valid_with_formatting(self):
        """Test formatted phone numbers."""
        assert validate_phone("+1 (415) 555-1234") is True
        assert validate_phone("+1-415-555-1234") is True
    
    def test_invalid_no_plus(self):
        """Test missing + is invalid."""
        assert validate_phone("14155551234") is False
    
    def test_invalid_too_short(self):
        """Test too short number."""
        assert validate_phone("+1") is False


class TestNormalizePhone:
    """Tests for phone normalization."""
    
    def test_remove_formatting(self):
        """Test formatting is removed."""
        assert normalize_phone("+1 (415) 555-1234") == "+14155551234"
    
    def test_add_plus(self):
        """Test + is added if missing."""
        assert normalize_phone("14155551234") == "+14155551234"


# =============================================================================
# Date Range Tests
# =============================================================================

class TestDateRange:
    """Tests for DateRange class."""
    
    def test_valid_range(self):
        """Test valid date range."""
        range_ = DateRange(
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
        )
        assert range_.days == 31
    
    def test_invalid_range(self):
        """Test start after end raises error."""
        with pytest.raises(ValueError):
            DateRange(
                start=date(2024, 2, 1),
                end=date(2024, 1, 1),
            )
    
    def test_contains(self):
        """Test date containment check."""
        range_ = DateRange(
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
        )
        assert range_.contains(date(2024, 1, 15)) is True
        assert range_.contains(date(2024, 2, 1)) is False
    
    def test_overlaps(self):
        """Test range overlap detection."""
        range1 = DateRange(date(2024, 1, 1), date(2024, 1, 31))
        range2 = DateRange(date(2024, 1, 15), date(2024, 2, 15))
        range3 = DateRange(date(2024, 3, 1), date(2024, 3, 31))
        
        assert range1.overlaps(range2) is True
        assert range1.overlaps(range3) is False


class TestValidateDateRange:
    """Tests for validate_date_range function."""
    
    def test_valid_range(self):
        """Test valid range passes."""
        is_valid, error = validate_date_range(
            date(2024, 1, 1),
            date(2024, 1, 31),
        )
        assert is_valid is True
        assert error is None
    
    def test_invalid_order(self):
        """Test start after end fails."""
        is_valid, error = validate_date_range(
            date(2024, 2, 1),
            date(2024, 1, 1),
        )
        assert is_valid is False
        assert "after" in error.lower()
    
    def test_max_days(self):
        """Test max days constraint."""
        is_valid, error = validate_date_range(
            date(2024, 1, 1),
            date(2024, 12, 31),
            max_days=30,
        )
        assert is_valid is False
        assert "exceeds" in error.lower()
    
    def test_string_dates(self):
        """Test string date parsing."""
        is_valid, error = validate_date_range(
            "2024-01-01",
            "2024-01-31",
        )
        assert is_valid is True
    
    def test_invalid_date_format(self):
        """Test invalid date format."""
        is_valid, error = validate_date_range(
            "not-a-date",
            "2024-01-31",
        )
        assert is_valid is False


# =============================================================================
# Credit Card Tests
# =============================================================================

class TestCreditCardValidation:
    """Tests for credit card validation."""
    
    def test_valid_card_number(self):
        """Test valid card number (Luhn check)."""
        # Test card numbers from Stripe
        assert validate_card_number("4242424242424242") is True
        assert validate_card_number("5555555555554444") is True
    
    def test_valid_with_formatting(self):
        """Test formatted card numbers."""
        assert validate_card_number("4242 4242 4242 4242") is True
        assert validate_card_number("4242-4242-4242-4242") is True
    
    def test_invalid_luhn(self):
        """Test invalid Luhn check."""
        assert validate_card_number("4242424242424241") is False
    
    def test_invalid_length(self):
        """Test invalid length."""
        assert validate_card_number("4242") is False
        assert validate_card_number("4" * 25) is False


class TestMaskCardNumber:
    """Tests for card number masking."""
    
    def test_mask_card(self):
        """Test card masking."""
        masked = mask_card_number("4242424242424242")
        assert masked.endswith("4242")
        assert "****" in masked
    
    def test_short_number(self):
        """Test short number masking."""
        assert mask_card_number("123") == "****"


# =============================================================================
# Pydantic Validator Tests
# =============================================================================

class TestValidators:
    """Tests for Pydantic validators."""
    
    def test_email_validator(self):
        """Test email validator."""
        result = Validators.email("User@EXAMPLE.COM")
        assert result == "User@example.com"
    
    def test_email_validator_invalid(self):
        """Test email validator rejects invalid."""
        with pytest.raises(ValueError):
            Validators.email("not-an-email")
    
    def test_url_validator(self):
        """Test URL validator."""
        result = Validators.url("https://example.com")
        assert result == "https://example.com"
    
    def test_https_url_validator(self):
        """Test HTTPS URL validator."""
        with pytest.raises(ValueError):
            Validators.https_url("http://example.com")
    
    def test_uuid_validator(self):
        """Test UUID validator."""
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        assert Validators.uuid(uuid) == uuid
    
    def test_slug_validator(self):
        """Test slug validator normalizes."""
        assert Validators.slug("My Blog Post") == "my-blog-post"
    
    def test_phone_validator(self):
        """Test phone validator."""
        assert Validators.phone("+1 (415) 555-1234") == "+14155551234"


# =============================================================================
# ValidationResult Tests
# =============================================================================

class TestValidationResult:
    """Tests for ValidationResult class."""
    
    def test_ok_result(self):
        """Test creating OK result."""
        result = ValidationResult.ok()
        assert result.is_valid is True
        assert len(result.issues) == 0
    
    def test_error_result(self):
        """Test creating error result."""
        result = ValidationResult.error("field", "message")
        assert result.is_valid is False
        assert len(result.errors) == 1
    
    def test_to_dict(self):
        """Test conversion to dict."""
        result = ValidationResult.error("email", "Invalid email")
        data = result.to_dict()
        
        assert data["is_valid"] is False
        assert data["error_count"] == 1
        assert len(data["issues"]) == 1


class TestValidationIssue:
    """Tests for ValidationIssue class."""
    
    def test_to_dict(self):
        """Test issue serialization."""
        issue = ValidationIssue(
            field="email",
            message="Invalid email",
            severity=ValidationSeverity.ERROR,
            code="invalid_email",
        )
        
        data = issue.to_dict()
        assert data["field"] == "email"
        assert data["message"] == "Invalid email"
        assert data["severity"] == "error"
        assert data["code"] == "invalid_email"


# =============================================================================
# Field Validation Helper Tests
# =============================================================================

class TestFieldValidationHelpers:
    """Tests for field-level validation helpers."""
    
    def test_validate_required(self):
        """Test required validation."""
        assert validate_required("value", "field") is None
        assert validate_required("", "field") is not None
        assert validate_required(None, "field") is not None
    
    def test_validate_length(self):
        """Test length validation."""
        assert validate_length("abc", "field", min_length=2) is None
        assert validate_length("a", "field", min_length=2) is not None
        assert validate_length("abcde", "field", max_length=3) is not None
    
    def test_validate_range(self):
        """Test range validation."""
        assert validate_range(5, "field", min_value=1, max_value=10) is None
        assert validate_range(0, "field", min_value=1) is not None
        assert validate_range(15, "field", max_value=10) is not None
    
    def test_validate_one_of(self):
        """Test one_of validation."""
        assert validate_one_of("a", "field", {"a", "b", "c"}) is None
        assert validate_one_of("d", "field", {"a", "b", "c"}) is not None
    
    def test_validate_pattern(self):
        """Test pattern validation."""
        assert validate_pattern("abc123", "field", r"^[a-z0-9]+$") is None
        assert validate_pattern("ABC", "field", r"^[a-z]+$") is not None
