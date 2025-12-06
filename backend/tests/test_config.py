"""Tests for configuration utilities."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app.utils.config import (
    ConfigurationError,
    ConfigValidationResult,
    Environment,
    FeatureFlag,
    FeatureFlagStatus,
    FeatureFlags,
    get_env,
    get_env_bool,
    get_env_float,
    get_env_int,
    get_env_json,
    get_env_list,
    get_env_str,
    get_env_url,
    get_environment,
    get_safe_config_dict,
    is_development,
    is_production,
    is_secret_key,
    mask_secret,
    require_env,
    validate_config,
)


# =============================================================================
# get_env Tests
# =============================================================================

class TestGetEnv:
    """Tests for get_env function."""
    
    def test_get_existing_var(self):
        """Test getting existing variable."""
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            assert get_env("TEST_VAR") == "test_value"
    
    def test_get_missing_var_default(self):
        """Test getting missing variable returns default."""
        assert get_env("NONEXISTENT_VAR", "default") == "default"
    
    def test_get_missing_var_none(self):
        """Test getting missing variable returns None."""
        assert get_env("NONEXISTENT_VAR") is None
    
    def test_get_with_prefix(self):
        """Test getting variable with prefix."""
        with patch.dict(os.environ, {"APP_TEST_VAR": "value"}):
            assert get_env("TEST_VAR", prefix="APP_") == "value"


class TestGetEnvStr:
    """Tests for get_env_str function."""
    
    def test_get_string(self):
        """Test getting string value."""
        with patch.dict(os.environ, {"TEST": "hello"}):
            assert get_env_str("TEST") == "hello"
    
    def test_strips_whitespace(self):
        """Test whitespace is stripped."""
        with patch.dict(os.environ, {"TEST": "  hello  "}):
            assert get_env_str("TEST") == "hello"
    
    def test_no_strip(self):
        """Test preserving whitespace."""
        with patch.dict(os.environ, {"TEST": "  hello  "}):
            assert get_env_str("TEST", strip=False) == "  hello  "
    
    def test_default_empty_string(self):
        """Test default is empty string."""
        assert get_env_str("NONEXISTENT") == ""


class TestGetEnvInt:
    """Tests for get_env_int function."""
    
    def test_get_integer(self):
        """Test getting integer value."""
        with patch.dict(os.environ, {"PORT": "8080"}):
            assert get_env_int("PORT") == 8080
    
    def test_default_value(self):
        """Test default value."""
        assert get_env_int("NONEXISTENT", default=3000) == 3000
    
    def test_invalid_integer(self):
        """Test invalid integer raises error."""
        with patch.dict(os.environ, {"PORT": "not_a_number"}):
            with pytest.raises(ConfigurationError) as exc:
                get_env_int("PORT")
            assert "must be an integer" in str(exc.value)
    
    def test_min_value(self):
        """Test minimum value constraint."""
        with patch.dict(os.environ, {"PORT": "100"}):
            with pytest.raises(ConfigurationError) as exc:
                get_env_int("PORT", min_value=1000)
            assert ">=" in str(exc.value)
    
    def test_max_value(self):
        """Test maximum value constraint."""
        with patch.dict(os.environ, {"PORT": "99999"}):
            with pytest.raises(ConfigurationError) as exc:
                get_env_int("PORT", max_value=65535)
            assert "<=" in str(exc.value)


class TestGetEnvFloat:
    """Tests for get_env_float function."""
    
    def test_get_float(self):
        """Test getting float value."""
        with patch.dict(os.environ, {"RATE": "0.5"}):
            assert get_env_float("RATE") == 0.5
    
    def test_integer_as_float(self):
        """Test integer parses as float."""
        with patch.dict(os.environ, {"RATE": "10"}):
            assert get_env_float("RATE") == 10.0
    
    def test_invalid_float(self):
        """Test invalid float raises error."""
        with patch.dict(os.environ, {"RATE": "not_a_number"}):
            with pytest.raises(ConfigurationError):
                get_env_float("RATE")


class TestGetEnvBool:
    """Tests for get_env_bool function."""
    
    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "1", "yes", "on"])
    def test_truthy_values(self, value):
        """Test truthy values."""
        with patch.dict(os.environ, {"FLAG": value}):
            assert get_env_bool("FLAG") is True
    
    @pytest.mark.parametrize("value", ["false", "False", "FALSE", "0", "no", "off", ""])
    def test_falsy_values(self, value):
        """Test falsy values."""
        with patch.dict(os.environ, {"FLAG": value}):
            assert get_env_bool("FLAG") is False
    
    def test_default_false(self):
        """Test default is False."""
        assert get_env_bool("NONEXISTENT") is False
    
    def test_custom_default(self):
        """Test custom default."""
        assert get_env_bool("NONEXISTENT", default=True) is True


class TestGetEnvList:
    """Tests for get_env_list function."""
    
    def test_comma_separated(self):
        """Test comma-separated list."""
        with patch.dict(os.environ, {"HOSTS": "host1,host2,host3"}):
            result = get_env_list("HOSTS")
            assert result == ["host1", "host2", "host3"]
    
    def test_strips_items(self):
        """Test whitespace is stripped from items."""
        with patch.dict(os.environ, {"HOSTS": "host1 , host2 , host3"}):
            result = get_env_list("HOSTS")
            assert result == ["host1", "host2", "host3"]
    
    def test_custom_separator(self):
        """Test custom separator."""
        with patch.dict(os.environ, {"HOSTS": "host1;host2;host3"}):
            result = get_env_list("HOSTS", separator=";")
            assert result == ["host1", "host2", "host3"]
    
    def test_empty_value(self):
        """Test empty value returns empty list."""
        with patch.dict(os.environ, {"HOSTS": ""}):
            assert get_env_list("HOSTS") == []
    
    def test_default_list(self):
        """Test default list."""
        assert get_env_list("NONEXISTENT", default=["a", "b"]) == ["a", "b"]


class TestGetEnvJson:
    """Tests for get_env_json function."""
    
    def test_parse_object(self):
        """Test parsing JSON object."""
        with patch.dict(os.environ, {"CONFIG": '{"key": "value"}'}):
            result = get_env_json("CONFIG")
            assert result == {"key": "value"}
    
    def test_parse_array(self):
        """Test parsing JSON array."""
        with patch.dict(os.environ, {"LIST": '[1, 2, 3]'}):
            result = get_env_json("LIST")
            assert result == [1, 2, 3]
    
    def test_invalid_json(self):
        """Test invalid JSON raises error."""
        with patch.dict(os.environ, {"CONFIG": "not json"}):
            with pytest.raises(ConfigurationError) as exc:
                get_env_json("CONFIG")
            assert "valid JSON" in str(exc.value)
    
    def test_default_value(self):
        """Test default value."""
        assert get_env_json("NONEXISTENT", default={"a": 1}) == {"a": 1}


class TestRequireEnv:
    """Tests for require_env function."""
    
    def test_existing_variable(self):
        """Test getting existing variable."""
        with patch.dict(os.environ, {"REQUIRED": "value"}):
            assert require_env("REQUIRED") == "value"
    
    def test_missing_variable(self):
        """Test missing variable raises error."""
        with pytest.raises(ConfigurationError) as exc:
            require_env("DEFINITELY_NOT_SET_12345")
        assert "not set" in str(exc.value)
    
    def test_empty_variable(self):
        """Test empty variable raises error."""
        with patch.dict(os.environ, {"REQUIRED": "   "}):
            with pytest.raises(ConfigurationError):
                require_env("REQUIRED")
    
    def test_custom_message(self):
        """Test custom error message."""
        with pytest.raises(ConfigurationError) as exc:
            require_env("MISSING", message="Custom error!")
        assert "Custom error!" in str(exc.value)


class TestGetEnvUrl:
    """Tests for get_env_url function."""
    
    def test_valid_http_url(self):
        """Test valid HTTP URL."""
        with patch.dict(os.environ, {"URL": "http://example.com"}):
            assert get_env_url("URL") == "http://example.com"
    
    def test_valid_https_url(self):
        """Test valid HTTPS URL."""
        with patch.dict(os.environ, {"URL": "https://example.com/"}):
            # Should strip trailing slash
            assert get_env_url("URL") == "https://example.com"
    
    def test_invalid_url(self):
        """Test invalid URL raises error."""
        with patch.dict(os.environ, {"URL": "not-a-url"}):
            with pytest.raises(ConfigurationError):
                get_env_url("URL")
    
    def test_require_https(self):
        """Test HTTPS requirement."""
        with patch.dict(os.environ, {"URL": "http://example.com"}):
            with pytest.raises(ConfigurationError) as exc:
                get_env_url("URL", require_https=True)
            assert "HTTPS" in str(exc.value)


# =============================================================================
# FeatureFlag Tests
# =============================================================================

class TestFeatureFlag:
    """Tests for FeatureFlag class."""
    
    def test_disabled_flag(self):
        """Test disabled flag."""
        flag = FeatureFlag(name="test", status=FeatureFlagStatus.DISABLED)
        assert flag.is_enabled_for("user123") is False
    
    def test_enabled_flag(self):
        """Test enabled flag."""
        flag = FeatureFlag(name="test", status=FeatureFlagStatus.ENABLED)
        assert flag.is_enabled_for("user123") is True
    
    def test_percentage_rollout(self):
        """Test percentage rollout is consistent."""
        flag = FeatureFlag(
            name="test",
            status=FeatureFlagStatus.PERCENTAGE,
            percentage=50,
        )
        
        # Same user should always get same result
        result1 = flag.is_enabled_for("user123")
        result2 = flag.is_enabled_for("user123")
        assert result1 == result2
    
    def test_percentage_distribution(self):
        """Test percentage roughly matches target."""
        flag = FeatureFlag(
            name="test",
            status=FeatureFlagStatus.PERCENTAGE,
            percentage=50,
        )
        
        enabled_count = sum(
            1 for i in range(1000)
            if flag.is_enabled_for(f"user{i}")
        )
        
        # Should be roughly 50% (+/- 10%)
        assert 400 < enabled_count < 600
    
    def test_allowlist(self):
        """Test allowlist targeting."""
        flag = FeatureFlag(
            name="test",
            status=FeatureFlagStatus.ALLOWLIST,
            allowlist={"user1", "user2"},
        )
        
        assert flag.is_enabled_for("user1") is True
        assert flag.is_enabled_for("user2") is True
        assert flag.is_enabled_for("user3") is False
    
    def test_blocklist(self):
        """Test blocklist targeting."""
        flag = FeatureFlag(
            name="test",
            status=FeatureFlagStatus.BLOCKLIST,
            blocklist={"blocked_user"},
        )
        
        assert flag.is_enabled_for("normal_user") is True
        assert flag.is_enabled_for("blocked_user") is False
    
    def test_blocklist_overrides_percentage(self):
        """Test blocklist takes precedence."""
        flag = FeatureFlag(
            name="test",
            status=FeatureFlagStatus.PERCENTAGE,
            percentage=100,
            blocklist={"blocked_user"},
        )
        
        assert flag.is_enabled_for("blocked_user") is False


class TestFeatureFlags:
    """Tests for FeatureFlags class."""
    
    def test_register_flag(self):
        """Test registering a flag."""
        flags = FeatureFlags()
        flag = FeatureFlag(name="new-feature", status=FeatureFlagStatus.ENABLED)
        
        flags.register(flag)
        
        assert flags.is_enabled("new-feature") is True
    
    def test_unregister_flag(self):
        """Test unregistering a flag."""
        flag = FeatureFlag(name="test", status=FeatureFlagStatus.ENABLED)
        flags = FeatureFlags({"test": flag})
        
        assert flags.unregister("test") is True
        assert flags.get("test") is None
    
    def test_is_enabled_unknown_flag(self):
        """Test checking unknown flag."""
        flags = FeatureFlags()
        
        assert flags.is_enabled("unknown") is False
        assert flags.is_enabled("unknown", default=True) is True
    
    def test_is_enabled_with_user(self):
        """Test checking flag with user targeting."""
        flag = FeatureFlag(
            name="beta",
            status=FeatureFlagStatus.ALLOWLIST,
            allowlist={"beta_user"},
        )
        flags = FeatureFlags({"beta": flag})
        
        assert flags.is_enabled("beta", user_id="beta_user") is True
        assert flags.is_enabled("beta", user_id="normal_user") is False
    
    def test_all_flags(self):
        """Test getting all flags."""
        flags = FeatureFlags({
            "enabled": FeatureFlag(name="enabled", status=FeatureFlagStatus.ENABLED),
            "disabled": FeatureFlag(name="disabled", status=FeatureFlagStatus.DISABLED),
        })
        
        all_flags = flags.all_flags()
        
        assert all_flags["enabled"] is True
        assert all_flags["disabled"] is False
    
    def test_flags_for_user(self):
        """Test getting flags for specific user."""
        flags = FeatureFlags({
            "beta": FeatureFlag(
                name="beta",
                status=FeatureFlagStatus.ALLOWLIST,
                allowlist={"user1"},
            ),
        })
        
        user1_flags = flags.flags_for_user("user1")
        user2_flags = flags.flags_for_user("user2")
        
        assert user1_flags["beta"] is True
        assert user2_flags["beta"] is False
    
    def test_from_env(self):
        """Test loading flags from environment."""
        env_vars = {
            "FF_NEW_FEATURE": "true",
            "FF_OLD_FEATURE": "false",
            "FF_BETA_FEATURE": "percentage:50",
            "FF_VIP_FEATURE": "allowlist:user1,user2",
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            flags = FeatureFlags.from_env("FF_")
        
        assert flags.is_enabled("new-feature") is True
        assert flags.is_enabled("old-feature") is False
        assert flags.get("beta-feature").percentage == 50
        assert "user1" in flags.get("vip-feature").allowlist


# =============================================================================
# Config Validation Tests
# =============================================================================

class TestValidateConfig:
    """Tests for validate_config function."""
    
    def test_valid_config(self):
        """Test valid configuration."""
        with patch.dict(os.environ, {"REQUIRED_VAR": "value"}):
            result = validate_config(required_vars=["REQUIRED_VAR"])
            assert result.is_valid is True
    
    def test_missing_required(self):
        """Test missing required variable."""
        result = validate_config(required_vars=["DEFINITELY_MISSING_123"])
        
        assert result.is_valid is False
        assert len(result.errors) == 1


class TestConfigValidationResult:
    """Tests for ConfigValidationResult class."""
    
    def test_empty_is_valid(self):
        """Test empty result is valid."""
        result = ConfigValidationResult()
        assert result.is_valid is True
    
    def test_with_error_is_invalid(self):
        """Test result with error is invalid."""
        result = ConfigValidationResult()
        result.add_error("KEY", "message")
        assert result.is_valid is False


# =============================================================================
# Secret Management Tests
# =============================================================================

class TestMaskSecret:
    """Tests for mask_secret function."""
    
    def test_mask_long_secret(self):
        """Test masking long secret."""
        masked = mask_secret("my_secret_key_123")
        assert masked.endswith("_123")
        assert masked.startswith("*")
    
    def test_mask_short_secret(self):
        """Test masking short secret."""
        masked = mask_secret("abc")
        assert masked == "***"
    
    def test_custom_visible_chars(self):
        """Test custom visible characters."""
        masked = mask_secret("secret123", visible_chars=6)
        assert masked == "***ret123"
    
    def test_empty_secret(self):
        """Test empty secret."""
        assert mask_secret("") == ""


class TestIsSecretKey:
    """Tests for is_secret_key function."""
    
    @pytest.mark.parametrize("key", [
        "DATABASE_PASSWORD",
        "API_KEY",
        "SECRET_TOKEN",
        "AUTH_SECRET",
        "PRIVATE_KEY",
    ])
    def test_detects_secrets(self, key):
        """Test detecting secret keys."""
        assert is_secret_key(key) is True
    
    @pytest.mark.parametrize("key", [
        "DATABASE_HOST",
        "PORT",
        "LOG_LEVEL",
        "APP_NAME",
    ])
    def test_non_secret_keys(self, key):
        """Test non-secret keys."""
        assert is_secret_key(key) is False


class TestGetSafeConfigDict:
    """Tests for get_safe_config_dict function."""
    
    def test_excludes_secrets_by_default(self):
        """Test secrets are excluded by default."""
        with patch.dict(os.environ, {
            "APP_HOST": "localhost",
            "APP_PASSWORD": "secret123",
        }, clear=True):
            config = get_safe_config_dict(prefix="APP_")
            
            assert "APP_HOST" in config
            assert "APP_PASSWORD" not in config
    
    def test_masks_secrets_when_included(self):
        """Test secrets are masked when included."""
        with patch.dict(os.environ, {
            "APP_PASSWORD": "secret123",
        }, clear=True):
            config = get_safe_config_dict(prefix="APP_", include_secrets=True)
            
            assert "APP_PASSWORD" in config
            assert config["APP_PASSWORD"] != "secret123"
            assert "123" in config["APP_PASSWORD"]  # Last 4 visible


# =============================================================================
# Environment Detection Tests
# =============================================================================

class TestGetEnvironment:
    """Tests for get_environment function."""
    
    @pytest.mark.parametrize("value,expected", [
        ("development", Environment.DEVELOPMENT),
        ("dev", Environment.DEVELOPMENT),
        ("production", Environment.PRODUCTION),
        ("prod", Environment.PRODUCTION),
        ("staging", Environment.STAGING),
        ("stage", Environment.STAGING),
        ("testing", Environment.TESTING),
        ("test", Environment.TESTING),
    ])
    def test_environment_detection(self, value, expected):
        """Test environment detection."""
        with patch.dict(os.environ, {"ENVIRONMENT": value}):
            assert get_environment() == expected
    
    def test_default_environment(self):
        """Test default environment."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_environment() == Environment.DEVELOPMENT
    
    def test_custom_key(self):
        """Test custom environment key."""
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            assert get_environment(key="APP_ENV") == Environment.PRODUCTION


class TestEnvironmentHelpers:
    """Tests for environment helper functions."""
    
    def test_is_development(self):
        """Test is_development."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            assert is_development() is True
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            assert is_development() is False
    
    def test_is_production(self):
        """Test is_production."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            assert is_production() is True
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            assert is_production() is False
