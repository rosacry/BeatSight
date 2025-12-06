"""Configuration utilities for type-safe settings management.

Provides utilities for:
- Environment variable parsing with type coercion
- Feature flags with gradual rollout support
- Configuration validation
- Secret management helpers

Usage:
    from app.utils.config import (
        get_env,
        get_env_int,
        get_env_bool,
        require_env,
        FeatureFlags,
    )

    # Get environment variables with defaults
    debug = get_env_bool("DEBUG", default=False)
    port = get_env_int("PORT", default=8000)

    # Require environment variables
    database_url = require_env("DATABASE_URL")

    # Feature flags
    flags = FeatureFlags()
    if flags.is_enabled("new_ui", user_id="user-123"):
        show_new_ui()
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")


# =============================================================================
# Environment variable helpers
# =============================================================================


class ConfigurationError(Exception):
    """Exception raised for configuration errors."""

    pass


def get_env(
    key: str,
    default: str | None = None,
    *,
    prefix: str = "",
) -> str | None:
    """Get environment variable with optional prefix.

    Args:
        key: Environment variable name
        default: Default value if not set
        prefix: Prefix to prepend to key

    Returns:
        Environment variable value or default
    """
    full_key = f"{prefix}{key}" if prefix else key
    return os.environ.get(full_key, default)


def get_env_str(
    key: str,
    default: str = "",
    *,
    prefix: str = "",
    strip: bool = True,
) -> str:
    """Get environment variable as string.

    Args:
        key: Environment variable name
        default: Default value
        prefix: Prefix to prepend to key
        strip: Strip whitespace from value

    Returns:
        String value
    """
    value = get_env(key, default, prefix=prefix)
    if value is None:
        return default
    return value.strip() if strip else value


def get_env_int(
    key: str,
    default: int = 0,
    *,
    prefix: str = "",
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    """Get environment variable as integer.

    Args:
        key: Environment variable name
        default: Default value
        prefix: Prefix to prepend to key
        min_value: Minimum allowed value
        max_value: Maximum allowed value

    Returns:
        Integer value

    Raises:
        ConfigurationError: If value is not a valid integer or out of range
    """
    value = get_env(key, prefix=prefix)

    if value is None:
        return default

    try:
        result = int(value)
    except ValueError:
        raise ConfigurationError(
            f"Environment variable {key} must be an integer, got: {value}"
        )

    if min_value is not None and result < min_value:
        raise ConfigurationError(
            f"Environment variable {key} must be >= {min_value}, got: {result}"
        )

    if max_value is not None and result > max_value:
        raise ConfigurationError(
            f"Environment variable {key} must be <= {max_value}, got: {result}"
        )

    return result


def get_env_float(
    key: str,
    default: float = 0.0,
    *,
    prefix: str = "",
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    """Get environment variable as float.

    Args:
        key: Environment variable name
        default: Default value
        prefix: Prefix to prepend to key
        min_value: Minimum allowed value
        max_value: Maximum allowed value

    Returns:
        Float value

    Raises:
        ConfigurationError: If value is not a valid float or out of range
    """
    value = get_env(key, prefix=prefix)

    if value is None:
        return default

    try:
        result = float(value)
    except ValueError:
        raise ConfigurationError(
            f"Environment variable {key} must be a number, got: {value}"
        )

    if min_value is not None and result < min_value:
        raise ConfigurationError(
            f"Environment variable {key} must be >= {min_value}, got: {result}"
        )

    if max_value is not None and result > max_value:
        raise ConfigurationError(
            f"Environment variable {key} must be <= {max_value}, got: {result}"
        )

    return result


def get_env_bool(
    key: str,
    default: bool = False,
    *,
    prefix: str = "",
) -> bool:
    """Get environment variable as boolean.

    Truthy values: "true", "1", "yes", "on" (case-insensitive)
    Falsy values: "false", "0", "no", "off", "" (case-insensitive)

    Args:
        key: Environment variable name
        default: Default value
        prefix: Prefix to prepend to key

    Returns:
        Boolean value
    """
    value = get_env(key, prefix=prefix)

    if value is None:
        return default

    value = value.lower().strip()

    if value in ("true", "1", "yes", "on"):
        return True
    if value in ("false", "0", "no", "off", ""):
        return False

    # Default to truthy for any other non-empty value
    return bool(value)


def get_env_list(
    key: str,
    default: list[str] | None = None,
    *,
    prefix: str = "",
    separator: str = ",",
    strip_items: bool = True,
) -> list[str]:
    """Get environment variable as list of strings.

    Args:
        key: Environment variable name
        default: Default value
        prefix: Prefix to prepend to key
        separator: Item separator
        strip_items: Strip whitespace from each item

    Returns:
        List of strings
    """
    value = get_env(key, prefix=prefix)

    if value is None:
        return default or []

    if not value.strip():
        return []

    items = value.split(separator)
    if strip_items:
        items = [item.strip() for item in items if item.strip()]

    return items


def get_env_json(
    key: str,
    default: Any = None,
    *,
    prefix: str = "",
) -> Any:
    """Get environment variable as JSON-parsed value.

    Args:
        key: Environment variable name
        default: Default value
        prefix: Prefix to prepend to key

    Returns:
        Parsed JSON value

    Raises:
        ConfigurationError: If value is not valid JSON
    """
    value = get_env(key, prefix=prefix)

    if value is None:
        return default

    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Environment variable {key} must be valid JSON: {e}")


def require_env(
    key: str,
    *,
    prefix: str = "",
    message: str | None = None,
) -> str:
    """Require an environment variable to be set.

    Args:
        key: Environment variable name
        prefix: Prefix to prepend to key
        message: Custom error message

    Returns:
        Environment variable value

    Raises:
        ConfigurationError: If variable is not set
    """
    value = get_env(key, prefix=prefix)

    if value is None or value.strip() == "":
        full_key = f"{prefix}{key}" if prefix else key
        error_msg = message or f"Required environment variable {full_key} is not set"
        raise ConfigurationError(error_msg)

    return value


def get_env_url(
    key: str,
    default: str | None = None,
    *,
    prefix: str = "",
    require_https: bool = False,
) -> str | None:
    """Get environment variable as URL.

    Args:
        key: Environment variable name
        default: Default value
        prefix: Prefix to prepend to key
        require_https: Require HTTPS scheme

    Returns:
        URL string

    Raises:
        ConfigurationError: If URL is invalid
    """
    value = get_env(key, prefix=prefix)

    if value is None:
        return default

    value = value.strip().rstrip("/")

    if not value:
        return default

    # Basic URL validation
    if not value.startswith(("http://", "https://")):
        raise ConfigurationError(
            f"Environment variable {key} must be a valid URL, got: {value}"
        )

    if require_https and not value.startswith("https://"):
        raise ConfigurationError(
            f"Environment variable {key} must use HTTPS, got: {value}"
        )

    return value


# =============================================================================
# Feature flags
# =============================================================================


class FeatureFlagStatus(str, Enum):
    """Status of a feature flag."""

    DISABLED = "disabled"
    ENABLED = "enabled"
    PERCENTAGE = "percentage"
    ALLOWLIST = "allowlist"
    BLOCKLIST = "blocklist"


@dataclass
class FeatureFlag:
    """Configuration for a single feature flag."""

    name: str
    status: FeatureFlagStatus = FeatureFlagStatus.DISABLED
    percentage: int = 0  # 0-100 for percentage rollout
    allowlist: set[str] = field(default_factory=set)
    blocklist: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_enabled_for(self, identifier: str | None = None) -> bool:
        """Check if flag is enabled for identifier.

        Args:
            identifier: User ID or other identifier for targeting

        Returns:
            True if flag is enabled
        """
        if self.status == FeatureFlagStatus.DISABLED:
            return False

        if self.status == FeatureFlagStatus.ENABLED:
            return True

        if identifier is None:
            # No identifier provided, use percentage or default
            if self.status == FeatureFlagStatus.PERCENTAGE:
                return False  # Can't do percentage without identifier
            return False

        # Check blocklist first
        if identifier in self.blocklist:
            return False

        # Check allowlist
        if self.status == FeatureFlagStatus.ALLOWLIST:
            return identifier in self.allowlist

        if self.status == FeatureFlagStatus.BLOCKLIST:
            return True  # Not in blocklist, so enabled

        # Percentage rollout
        if self.status == FeatureFlagStatus.PERCENTAGE:
            return self._hash_to_percentage(identifier) < self.percentage

        return False

    def _hash_to_percentage(self, identifier: str) -> int:
        """Convert identifier to consistent percentage 0-99.

        Args:
            identifier: User identifier

        Returns:
            Percentage value 0-99
        """
        hash_input = f"{self.name}:{identifier}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()
        return int(hash_value[:8], 16) % 100


class FeatureFlags:
    """Feature flag management."""

    def __init__(self, flags: dict[str, FeatureFlag] | None = None):
        """Initialize feature flags.

        Args:
            flags: Dictionary of flag name to FeatureFlag
        """
        self._flags: dict[str, FeatureFlag] = flags or {}

    def register(self, flag: FeatureFlag) -> None:
        """Register a feature flag.

        Args:
            flag: Feature flag to register
        """
        self._flags[flag.name] = flag
        logger.debug("Feature flag registered", flag_name=flag.name)

    def unregister(self, name: str) -> bool:
        """Unregister a feature flag.

        Args:
            name: Flag name to unregister

        Returns:
            True if flag was unregistered
        """
        if name in self._flags:
            del self._flags[name]
            return True
        return False

    def get(self, name: str) -> FeatureFlag | None:
        """Get a feature flag by name.

        Args:
            name: Flag name

        Returns:
            FeatureFlag or None
        """
        return self._flags.get(name)

    def is_enabled(
        self,
        name: str,
        *,
        user_id: str | None = None,
        default: bool = False,
    ) -> bool:
        """Check if a feature flag is enabled.

        Args:
            name: Flag name
            user_id: User identifier for targeting
            default: Default if flag not found

        Returns:
            True if enabled
        """
        flag = self._flags.get(name)

        if flag is None:
            return default

        return flag.is_enabled_for(user_id)

    def all_flags(self) -> dict[str, bool]:
        """Get all flags and their default status.

        Returns:
            Dictionary of flag name to enabled status
        """
        return {name: flag.is_enabled_for(None) for name, flag in self._flags.items()}

    def flags_for_user(self, user_id: str) -> dict[str, bool]:
        """Get all flags for a specific user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary of flag name to enabled status
        """
        return {
            name: flag.is_enabled_for(user_id) for name, flag in self._flags.items()
        }

    @classmethod
    def from_env(cls, prefix: str = "FF_") -> "FeatureFlags":
        """Create feature flags from environment variables.

        Environment variable format:
        - {prefix}{FLAG_NAME}=true/false for simple enable/disable
        - {prefix}{FLAG_NAME}=percentage:50 for percentage rollout
        - {prefix}{FLAG_NAME}=allowlist:user1,user2 for allowlist

        Args:
            prefix: Environment variable prefix

        Returns:
            FeatureFlags instance
        """
        flags = {}

        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue

            flag_name = key[len(prefix) :].lower().replace("_", "-")

            if value.lower() in ("true", "1", "yes"):
                flags[flag_name] = FeatureFlag(
                    name=flag_name,
                    status=FeatureFlagStatus.ENABLED,
                )
            elif value.lower() in ("false", "0", "no"):
                flags[flag_name] = FeatureFlag(
                    name=flag_name,
                    status=FeatureFlagStatus.DISABLED,
                )
            elif value.startswith("percentage:"):
                try:
                    pct = int(value.split(":", 1)[1])
                    flags[flag_name] = FeatureFlag(
                        name=flag_name,
                        status=FeatureFlagStatus.PERCENTAGE,
                        percentage=min(100, max(0, pct)),
                    )
                except ValueError:
                    logger.warning(
                        "Invalid percentage for feature flag",
                        flag_name=flag_name,
                        value=value,
                    )
            elif value.startswith("allowlist:"):
                users = value.split(":", 1)[1].split(",")
                flags[flag_name] = FeatureFlag(
                    name=flag_name,
                    status=FeatureFlagStatus.ALLOWLIST,
                    allowlist=set(u.strip() for u in users if u.strip()),
                )

        return cls(flags)


# =============================================================================
# Configuration validation
# =============================================================================


@dataclass
class ConfigValidationError:
    """A single configuration validation error."""

    key: str
    message: str
    value: Any = None


@dataclass
class ConfigValidationResult:
    """Result of configuration validation."""

    errors: list[ConfigValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Check if validation passed."""
        return len(self.errors) == 0

    def add_error(
        self,
        key: str,
        message: str,
        value: Any = None,
    ) -> None:
        """Add a validation error."""
        self.errors.append(ConfigValidationError(key, message, value))


def validate_config(
    required_vars: list[str] | None = None,
    optional_vars: dict[str, Any] | None = None,
) -> ConfigValidationResult:
    """Validate configuration environment variables.

    Args:
        required_vars: List of required environment variable names
        optional_vars: Dict of optional vars with their default values

    Returns:
        ConfigValidationResult
    """
    result = ConfigValidationResult()

    # Check required variables
    for var in required_vars or []:
        value = os.environ.get(var)
        if not value or not value.strip():
            result.add_error(var, f"Required variable {var} is not set")

    return result


# =============================================================================
# Secret management helpers
# =============================================================================


def mask_secret(
    value: str,
    visible_chars: int = 4,
    mask_char: str = "*",
) -> str:
    """Mask a secret value for logging.

    Args:
        value: Secret value
        visible_chars: Number of visible characters at end
        mask_char: Character to use for masking

    Returns:
        Masked value
    """
    if not value:
        return ""

    if len(value) <= visible_chars:
        return mask_char * len(value)

    masked_length = len(value) - visible_chars
    return mask_char * masked_length + value[-visible_chars:]


def is_secret_key(key: str) -> bool:
    """Check if environment variable name likely contains a secret.

    Args:
        key: Variable name

    Returns:
        True if likely a secret
    """
    secret_patterns = [
        "password",
        "secret",
        "key",
        "token",
        "api_key",
        "apikey",
        "auth",
        "credential",
        "private",
    ]
    key_lower = key.lower()
    return any(pattern in key_lower for pattern in secret_patterns)


def get_safe_config_dict(
    include_secrets: bool = False,
    prefix: str = "",
) -> dict[str, str]:
    """Get configuration as dictionary, masking secrets.

    Args:
        include_secrets: Include secret values (masked)
        prefix: Only include variables with this prefix

    Returns:
        Dictionary of configuration values
    """
    result = {}

    for key, value in os.environ.items():
        if prefix and not key.startswith(prefix):
            continue

        if is_secret_key(key):
            if include_secrets:
                result[key] = mask_secret(value)
            # Skip secrets entirely if not including
        else:
            result[key] = value

    return result


# =============================================================================
# App environment detection
# =============================================================================


class Environment(str, Enum):
    """Application environment."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


def get_environment(
    key: str = "ENVIRONMENT",
    default: Environment = Environment.DEVELOPMENT,
) -> Environment:
    """Get current application environment.

    Args:
        key: Environment variable name
        default: Default environment

    Returns:
        Environment enum value
    """
    value = os.environ.get(key, "").lower().strip()

    env_map = {
        "dev": Environment.DEVELOPMENT,
        "development": Environment.DEVELOPMENT,
        "test": Environment.TESTING,
        "testing": Environment.TESTING,
        "stage": Environment.STAGING,
        "staging": Environment.STAGING,
        "prod": Environment.PRODUCTION,
        "production": Environment.PRODUCTION,
    }

    return env_map.get(value, default)


def is_development() -> bool:
    """Check if running in development environment."""
    return get_environment() == Environment.DEVELOPMENT


def is_testing() -> bool:
    """Check if running in testing environment."""
    return get_environment() == Environment.TESTING


def is_staging() -> bool:
    """Check if running in staging environment."""
    return get_environment() == Environment.STAGING


def is_production() -> bool:
    """Check if running in production environment."""
    return get_environment() == Environment.PRODUCTION
