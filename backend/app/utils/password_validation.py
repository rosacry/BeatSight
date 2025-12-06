"""Password validation utilities for secure authentication.

Provides comprehensive password strength validation to protect
users from weak passwords that could be easily compromised.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


@dataclass
class PasswordValidationResult:
    """Result of password validation."""

    is_valid: bool
    errors: List[str]
    strength_score: int  # 0-5 scale
    strength_label: str  # weak, fair, good, strong, excellent

    @property
    def error_message(self) -> str:
        """Get combined error message."""
        return "; ".join(self.errors) if self.errors else ""


# Common weak passwords that should be rejected
COMMON_PASSWORDS = {
    "password",
    "password1",
    "password123",
    "123456",
    "12345678",
    "qwerty",
    "qwerty123",
    "abc123",
    "letmein",
    "welcome",
    "admin",
    "login",
    "passw0rd",
    "master",
    "hello",
    "shadow",
    "sunshine",
    "princess",
    "dragon",
    "monkey",
    "iloveyou",
    "trustno1",
    "1234567890",
    "football",
    "baseball",
    "password1!",
    "password123!",
    "qwertyuiop",
    "asdfghjkl",
    "beatsight",
    "beatsight123",
    "drums",
    "drummer",
    "music",
}


def validate_password(
    password: str,
    email: str | None = None,
    display_name: str | None = None,
    min_length: int = 8,
    require_uppercase: bool = True,
    require_lowercase: bool = True,
    require_digit: bool = True,
    require_special: bool = False,
) -> PasswordValidationResult:
    """Validate password strength and return detailed result.

    Args:
        password: The password to validate
        email: Optional email to check password doesn't contain it
        display_name: Optional display name to check password doesn't contain it
        min_length: Minimum password length (default 8)
        require_uppercase: Require at least one uppercase letter
        require_lowercase: Require at least one lowercase letter
        require_digit: Require at least one digit
        require_special: Require at least one special character

    Returns:
        PasswordValidationResult with validation status and details
    """
    errors: List[str] = []
    score = 0

    # Length check
    if len(password) < min_length:
        errors.append(f"Password must be at least {min_length} characters")
    else:
        score += 1
        if len(password) >= 12:
            score += 1  # Bonus for longer passwords

    # Character type checks
    has_upper = bool(re.search(r"[A-Z]", password))
    has_lower = bool(re.search(r"[a-z]", password))
    has_digit = bool(re.search(r"\d", password))
    has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;\'`~]', password))

    if require_uppercase and not has_upper:
        errors.append("Password must contain at least one uppercase letter")
    elif has_upper:
        score += 0.5

    if require_lowercase and not has_lower:
        errors.append("Password must contain at least one lowercase letter")
    elif has_lower:
        score += 0.5

    if require_digit and not has_digit:
        errors.append("Password must contain at least one number")
    elif has_digit:
        score += 0.5

    if require_special and not has_special:
        errors.append("Password must contain at least one special character")
    elif has_special:
        score += 0.5

    # Check for common passwords
    if password.lower() in COMMON_PASSWORDS:
        errors.append(
            "This password is too common. Please choose a more unique password"
        )
        score = max(0, score - 2)

    # Check for sequential patterns
    sequential_patterns = [
        "123456",
        "234567",
        "345678",
        "456789",
        "567890",
        "abcdef",
        "bcdefg",
        "cdefgh",
        "qwerty",
        "asdfgh",
    ]
    lower_password = password.lower()
    for pattern in sequential_patterns:
        if pattern in lower_password:
            errors.append("Password contains a sequential pattern")
            score = max(0, score - 1)
            break

    # Check for repeated characters
    if re.search(r"(.)\1{2,}", password):
        errors.append("Password contains too many repeated characters")
        score = max(0, score - 1)

    # Check password doesn't contain email or username
    if email:
        email_local = email.split("@")[0].lower()
        if len(email_local) >= 3 and email_local in password.lower():
            errors.append("Password should not contain your email address")
            score = max(0, score - 1)

    if display_name:
        name_lower = display_name.lower()
        if len(name_lower) >= 3 and name_lower in password.lower():
            errors.append("Password should not contain your display name")
            score = max(0, score - 1)

    # Calculate strength label
    score = min(5, max(0, int(score)))
    strength_labels = {
        0: "weak",
        1: "weak",
        2: "fair",
        3: "good",
        4: "strong",
        5: "excellent",
    }

    is_valid = len(errors) == 0

    return PasswordValidationResult(
        is_valid=is_valid,
        errors=errors,
        strength_score=score,
        strength_label=strength_labels.get(score, "weak"),
    )


def is_password_valid(password: str, **kwargs) -> bool:
    """Simple boolean check if password is valid.

    Use validate_password() for detailed results.
    """
    result = validate_password(password, **kwargs)
    return result.is_valid
