"""Validation utilities for common data validation patterns.

Provides reusable validators for:
- Email addresses
- URLs
- Phone numbers
- UUIDs
- Slugs
- File names
- Credit card numbers (format only)
- Date ranges

Usage:
    from app.utils.validation import (
        validate_email,
        validate_url,
        is_valid_uuid,
        Validators,
    )

    # Direct validation
    if validate_email("user@example.com"):
        print("Valid email")
    
    # Use validators in Pydantic models
    class MyModel(BaseModel):
        email: str
        
        _validate_email = field_validator("email")(Validators.email)
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Callable
from urllib.parse import urlparse

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Email validation
# =============================================================================

# RFC 5322 inspired email regex (simplified but practical)
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$",
    re.IGNORECASE,
)

# Common disposable email domains
DISPOSABLE_EMAIL_DOMAINS = frozenset({
    "mailinator.com", "guerrillamail.com", "10minutemail.com",
    "tempmail.com", "throwaway.email", "fakeinbox.com",
    "temp-mail.org", "dispostable.com", "mailnesia.com",
    "trashmail.com", "maildrop.cc", "yopmail.com",
})


def validate_email(
    email: str,
    *,
    allow_disposable: bool = True,
    max_length: int = 254,
) -> bool:
    """Validate email address format.
    
    Args:
        email: Email address to validate
        allow_disposable: Whether to allow disposable email domains
        max_length: Maximum allowed length
        
    Returns:
        True if valid
    """
    if not email or len(email) > max_length:
        return False
    
    if not EMAIL_REGEX.match(email):
        return False
    
    if not allow_disposable:
        domain = email.split("@")[-1].lower()
        if domain in DISPOSABLE_EMAIL_DOMAINS:
            return False
    
    return True


def normalize_email(email: str) -> str:
    """Normalize email address.
    
    - Lowercase the domain
    - Strip whitespace
    
    Args:
        email: Email address to normalize
        
    Returns:
        Normalized email
    """
    email = email.strip()
    if "@" in email:
        local, domain = email.rsplit("@", 1)
        return f"{local}@{domain.lower()}"
    return email


# =============================================================================
# URL validation
# =============================================================================

VALID_URL_SCHEMES = frozenset({"http", "https"})


def validate_url(
    url: str,
    *,
    require_https: bool = False,
    allowed_schemes: frozenset[str] | None = None,
    max_length: int = 2048,
) -> bool:
    """Validate URL format.
    
    Args:
        url: URL to validate
        require_https: Require HTTPS scheme
        allowed_schemes: Set of allowed schemes
        max_length: Maximum allowed length
        
    Returns:
        True if valid
    """
    if not url or len(url) > max_length:
        return False
    
    try:
        parsed = urlparse(url)
        
        if not parsed.scheme or not parsed.netloc:
            return False
        
        if require_https and parsed.scheme != "https":
            return False
        
        schemes = allowed_schemes or VALID_URL_SCHEMES
        if parsed.scheme not in schemes:
            return False
        
        # Basic netloc validation (must have at least one dot for domain)
        # Allow localhost (with or without port)
        hostname = parsed.hostname or ""
        if "." not in hostname and hostname != "localhost":
            return False
        
        return True
        
    except Exception:
        return False


def validate_webhook_url(url: str) -> bool:
    """Validate URL is suitable for webhooks.
    
    Requires HTTPS and disallows localhost/private IPs.
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid for webhooks
    """
    if not validate_url(url, require_https=True):
        return False
    
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        
        # Disallow localhost
        if host in ("localhost", "127.0.0.1", "::1"):
            return False
        
        # Disallow private IP ranges
        if host.startswith(("10.", "192.168.", "172.16.", "172.17.",
                           "172.18.", "172.19.", "172.20.", "172.21.",
                           "172.22.", "172.23.", "172.24.", "172.25.",
                           "172.26.", "172.27.", "172.28.", "172.29.",
                           "172.30.", "172.31.")):
            return False
        
        return True
        
    except Exception:
        return False


# =============================================================================
# UUID validation
# =============================================================================

def is_valid_uuid(value: str, version: int | None = None) -> bool:
    """Check if string is a valid UUID.
    
    Args:
        value: String to validate
        version: Required UUID version (1, 3, 4, or 5)
        
    Returns:
        True if valid UUID
    """
    try:
        parsed = uuid.UUID(value)
        if version and parsed.version != version:
            return False
        return True
    except (ValueError, AttributeError):
        return False


def validate_uuid4(value: str) -> bool:
    """Validate UUID version 4.
    
    Args:
        value: String to validate
        
    Returns:
        True if valid UUID v4
    """
    return is_valid_uuid(value, version=4)


# =============================================================================
# Slug validation
# =============================================================================

SLUG_REGEX = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_slug(
    slug: str,
    *,
    min_length: int = 1,
    max_length: int = 100,
) -> bool:
    """Validate URL slug format.
    
    Valid slugs contain only lowercase letters, numbers, and hyphens.
    Must start and end with alphanumeric character.
    
    Args:
        slug: Slug to validate
        min_length: Minimum length
        max_length: Maximum length
        
    Returns:
        True if valid
    """
    if not slug:
        return False
    
    if len(slug) < min_length or len(slug) > max_length:
        return False
    
    return bool(SLUG_REGEX.match(slug))


def slugify(text: str, max_length: int = 100) -> str:
    """Convert text to URL-safe slug.
    
    Args:
        text: Text to convert
        max_length: Maximum length
        
    Returns:
        URL-safe slug
    """
    # Lowercase and strip
    slug = text.lower().strip()
    
    # Replace spaces and underscores with hyphens
    slug = re.sub(r"[\s_]+", "-", slug)
    
    # Remove non-alphanumeric except hyphens
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)
    
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    
    # Truncate
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    
    return slug


# =============================================================================
# File name validation
# =============================================================================

# Characters not allowed in filenames
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Reserved Windows filenames
RESERVED_FILENAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
})


def validate_filename(
    filename: str,
    *,
    allowed_extensions: set[str] | None = None,
    max_length: int = 255,
) -> bool:
    """Validate filename for security.
    
    Args:
        filename: Filename to validate
        allowed_extensions: Set of allowed extensions (e.g., {".jpg", ".png"})
        max_length: Maximum length
        
    Returns:
        True if valid and safe
    """
    if not filename or len(filename) > max_length:
        return False
    
    # Check for invalid characters
    if INVALID_FILENAME_CHARS.search(filename):
        return False
    
    # Check for path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        return False
    
    # Check for reserved names
    name_without_ext = filename.rsplit(".", 1)[0].upper()
    if name_without_ext in RESERVED_FILENAMES:
        return False
    
    # Check extension if required
    if allowed_extensions:
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()
        if ext not in allowed_extensions:
            return False
    
    return True


def sanitize_filename(filename: str, replacement: str = "_") -> str:
    """Sanitize filename by removing invalid characters.
    
    Args:
        filename: Filename to sanitize
        replacement: Character to replace invalid chars
        
    Returns:
        Sanitized filename
    """
    # Replace invalid characters
    filename = INVALID_FILENAME_CHARS.sub(replacement, filename)
    
    # Remove path traversal
    filename = filename.replace("..", replacement)
    
    # Collapse multiple replacements
    if replacement:
        pattern = re.escape(replacement) + "+"
        filename = re.sub(pattern, replacement, filename)
    
    # Strip leading/trailing spaces and dots
    filename = filename.strip(". ")
    
    return filename or "unnamed"


# =============================================================================
# Phone number validation
# =============================================================================

# Basic phone validation (E.164 format)
PHONE_REGEX = re.compile(r"^\+[1-9]\d{1,14}$")


def validate_phone(phone: str) -> bool:
    """Validate phone number in E.164 format.
    
    Args:
        phone: Phone number to validate (e.g., +14155551234)
        
    Returns:
        True if valid E.164 format
    """
    if not phone:
        return False
    
    # Remove common formatting
    cleaned = re.sub(r"[\s\-.()\[\]]", "", phone)
    
    return bool(PHONE_REGEX.match(cleaned))


def normalize_phone(phone: str) -> str:
    """Normalize phone number to E.164 format.
    
    Args:
        phone: Phone number to normalize
        
    Returns:
        Normalized phone number
    """
    # Remove formatting
    cleaned = re.sub(r"[\s\-.()\[\]]", "", phone)
    
    # Ensure it starts with +
    if cleaned and not cleaned.startswith("+"):
        cleaned = "+" + cleaned
    
    return cleaned


# =============================================================================
# Date range validation
# =============================================================================

@dataclass
class DateRange:
    """Date range with validation."""
    
    start: date
    end: date
    
    def __post_init__(self):
        if self.start > self.end:
            raise ValueError("Start date must not be after end date")
    
    @property
    def days(self) -> int:
        """Number of days in range."""
        return (self.end - self.start).days + 1
    
    def contains(self, dt: date) -> bool:
        """Check if date is within range."""
        return self.start <= dt <= self.end
    
    def overlaps(self, other: "DateRange") -> bool:
        """Check if ranges overlap."""
        return self.start <= other.end and other.start <= self.end


def validate_date_range(
    start_date: date | str,
    end_date: date | str,
    *,
    max_days: int | None = None,
    allow_future: bool = True,
    allow_past: bool = True,
) -> tuple[bool, str | None]:
    """Validate a date range.
    
    Args:
        start_date: Start date
        end_date: End date
        max_days: Maximum allowed range in days
        allow_future: Allow future dates
        allow_past: Allow past dates
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Parse strings if needed
    if isinstance(start_date, str):
        try:
            start_date = date.fromisoformat(start_date)
        except ValueError:
            return False, "Invalid start date format"
    
    if isinstance(end_date, str):
        try:
            end_date = date.fromisoformat(end_date)
        except ValueError:
            return False, "Invalid end date format"
    
    # Check order
    if start_date > end_date:
        return False, "Start date must not be after end date"
    
    # Check max days
    if max_days:
        days = (end_date - start_date).days + 1
        if days > max_days:
            return False, f"Date range exceeds maximum of {max_days} days"
    
    today = date.today()
    
    # Check future dates
    if not allow_future:
        if start_date > today or end_date > today:
            return False, "Future dates are not allowed"
    
    # Check past dates
    if not allow_past:
        if start_date < today or end_date < today:
            return False, "Past dates are not allowed"
    
    return True, None


# =============================================================================
# Credit card validation (format only, not verification)
# =============================================================================

def validate_card_number(number: str) -> bool:
    """Validate credit card number using Luhn algorithm.
    
    NOTE: This only validates format, not that the card is real.
    
    Args:
        number: Card number to validate
        
    Returns:
        True if valid format
    """
    # Remove spaces and dashes
    digits = re.sub(r"[\s-]", "", number)
    
    # Check length and digits only
    if not digits.isdigit() or len(digits) < 13 or len(digits) > 19:
        return False
    
    # Luhn algorithm
    total = 0
    for i, digit in enumerate(reversed(digits)):
        d = int(digit)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    
    return total % 10 == 0


def mask_card_number(number: str) -> str:
    """Mask credit card number showing only last 4 digits.
    
    Args:
        number: Card number to mask
        
    Returns:
        Masked card number (e.g., "****-****-****-1234")
    """
    digits = re.sub(r"[\s-]", "", number)
    
    if len(digits) < 4:
        return "****"
    
    last_four = digits[-4:]
    masked_groups = ["****"] * ((len(digits) - 4) // 4)
    masked_groups.append(last_four)
    
    return "-".join(masked_groups)


# =============================================================================
# Generic validators for Pydantic
# =============================================================================

class Validators:
    """Pydantic field validators for common validations.
    
    Usage:
        class MyModel(BaseModel):
            email: str
            
            _validate_email = field_validator("email")(Validators.email)
    """
    
    @staticmethod
    def email(value: str) -> str:
        """Validate email field."""
        if not validate_email(value):
            raise ValueError("Invalid email address")
        return normalize_email(value)
    
    @staticmethod
    def email_strict(value: str) -> str:
        """Validate email field (no disposable domains)."""
        if not validate_email(value, allow_disposable=False):
            raise ValueError("Invalid email address or disposable domain")
        return normalize_email(value)
    
    @staticmethod
    def url(value: str) -> str:
        """Validate URL field."""
        if not validate_url(value):
            raise ValueError("Invalid URL")
        return value
    
    @staticmethod
    def https_url(value: str) -> str:
        """Validate HTTPS URL field."""
        if not validate_url(value, require_https=True):
            raise ValueError("Invalid URL (HTTPS required)")
        return value
    
    @staticmethod
    def webhook_url(value: str) -> str:
        """Validate webhook URL field."""
        if not validate_webhook_url(value):
            raise ValueError("Invalid webhook URL")
        return value
    
    @staticmethod
    def uuid(value: str) -> str:
        """Validate UUID field."""
        if not is_valid_uuid(value):
            raise ValueError("Invalid UUID")
        return value
    
    @staticmethod
    def uuid4(value: str) -> str:
        """Validate UUID v4 field."""
        if not validate_uuid4(value):
            raise ValueError("Invalid UUID v4")
        return value
    
    @staticmethod
    def slug(value: str) -> str:
        """Validate and normalize slug field."""
        slug = slugify(value)
        if not validate_slug(slug):
            raise ValueError("Invalid slug")
        return slug
    
    @staticmethod
    def phone(value: str) -> str:
        """Validate phone field."""
        if not validate_phone(value):
            raise ValueError("Invalid phone number (E.164 format required)")
        return normalize_phone(value)
    
    @staticmethod
    def filename(value: str) -> str:
        """Validate filename field."""
        if not validate_filename(value):
            raise ValueError("Invalid filename")
        return value


# =============================================================================
# Validation result types
# =============================================================================

class ValidationSeverity(str, Enum):
    """Severity level for validation issues."""
    
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """A single validation issue."""
    
    field: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    code: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "field": self.field,
            "message": self.message,
            "severity": self.severity.value,
            "code": self.code,
        }


@dataclass
class ValidationResult:
    """Result of validation with multiple issues."""
    
    issues: list[ValidationIssue]
    
    @property
    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return not any(i.severity == ValidationSeverity.ERROR for i in self.issues)
    
    @property
    def errors(self) -> list[ValidationIssue]:
        """Get error-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]
    
    @property
    def warnings(self) -> list[ValidationIssue]:
        """Get warning-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "issues": [i.to_dict() for i in self.issues],
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }
    
    @classmethod
    def ok(cls) -> "ValidationResult":
        """Create a passing validation result."""
        return cls(issues=[])
    
    @classmethod
    def error(
        cls,
        field: str,
        message: str,
        code: str | None = None,
    ) -> "ValidationResult":
        """Create a failing validation result with single error."""
        return cls(issues=[
            ValidationIssue(
                field=field,
                message=message,
                severity=ValidationSeverity.ERROR,
                code=code,
            )
        ])


# =============================================================================
# Field-level validation helpers
# =============================================================================

def validate_required(value: Any, field_name: str) -> ValidationIssue | None:
    """Validate that a required field is present."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return ValidationIssue(
            field=field_name,
            message=f"{field_name} is required",
            code="required",
        )
    return None


def validate_length(
    value: str,
    field_name: str,
    *,
    min_length: int | None = None,
    max_length: int | None = None,
) -> ValidationIssue | None:
    """Validate string length."""
    if min_length and len(value) < min_length:
        return ValidationIssue(
            field=field_name,
            message=f"{field_name} must be at least {min_length} characters",
            code="min_length",
        )
    if max_length and len(value) > max_length:
        return ValidationIssue(
            field=field_name,
            message=f"{field_name} must not exceed {max_length} characters",
            code="max_length",
        )
    return None


def validate_range(
    value: int | float,
    field_name: str,
    *,
    min_value: int | float | None = None,
    max_value: int | float | None = None,
) -> ValidationIssue | None:
    """Validate numeric range."""
    if min_value is not None and value < min_value:
        return ValidationIssue(
            field=field_name,
            message=f"{field_name} must be at least {min_value}",
            code="min_value",
        )
    if max_value is not None and value > max_value:
        return ValidationIssue(
            field=field_name,
            message=f"{field_name} must not exceed {max_value}",
            code="max_value",
        )
    return None


def validate_one_of(
    value: Any,
    field_name: str,
    allowed_values: set[Any],
) -> ValidationIssue | None:
    """Validate value is in allowed set."""
    if value not in allowed_values:
        return ValidationIssue(
            field=field_name,
            message=f"{field_name} must be one of: {', '.join(str(v) for v in allowed_values)}",
            code="invalid_choice",
        )
    return None


def validate_pattern(
    value: str,
    field_name: str,
    pattern: re.Pattern | str,
    message: str | None = None,
) -> ValidationIssue | None:
    """Validate string matches pattern."""
    if isinstance(pattern, str):
        pattern = re.compile(pattern)
    
    if not pattern.match(value):
        return ValidationIssue(
            field=field_name,
            message=message or f"{field_name} format is invalid",
            code="pattern",
        )
    return None
