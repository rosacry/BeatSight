"""Tests for feature flag dependencies."""

import pytest
from fastapi import HTTPException
from unittest.mock import patch, MagicMock

from app.api.deps import (
    require_feature,
    require_beta,
    require_community,
    require_karma,
    require_cloud_sync,
)


class TestRequireFeature:
    """Tests for the generic require_feature dependency factory."""

    def test_require_feature_enabled(self):
        """Test that enabled features pass through."""
        mock_settings = MagicMock()
        mock_settings.feature_test = True

        with patch("app.api.deps.get_settings", return_value=mock_settings):
            check = require_feature("test")
            # Should not raise
            check()

    def test_require_feature_disabled(self):
        """Test that disabled features raise 404."""
        mock_settings = MagicMock()
        mock_settings.feature_test = False

        with patch("app.api.deps.get_settings", return_value=mock_settings):
            check = require_feature("test")
            with pytest.raises(HTTPException) as exc_info:
                check()
            assert exc_info.value.status_code == 404
            assert "not currently available" in exc_info.value.detail

    def test_require_feature_missing(self):
        """Test that missing features default to disabled."""
        mock_settings = MagicMock(spec=[])  # No attributes

        with patch("app.api.deps.get_settings", return_value=mock_settings):
            check = require_feature("nonexistent")
            with pytest.raises(HTTPException) as exc_info:
                check()
            assert exc_info.value.status_code == 404


class TestRequireBeta:
    """Tests for the require_beta dependency."""

    def test_beta_enabled(self):
        """Test that beta features pass when enabled."""
        mock_settings = MagicMock()
        mock_settings.feature_beta = True

        with patch("app.api.deps.get_settings", return_value=mock_settings):
            # Should not raise
            require_beta()

    def test_beta_disabled(self):
        """Test that beta features raise 404 when disabled."""
        mock_settings = MagicMock()
        mock_settings.feature_beta = False

        with patch("app.api.deps.get_settings", return_value=mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                require_beta()
            assert exc_info.value.status_code == 404
            assert "beta" in exc_info.value.detail.lower()


class TestRequireCommunity:
    """Tests for the require_community dependency."""

    def test_community_enabled(self):
        """Test that community features pass when enabled."""
        mock_settings = MagicMock()
        mock_settings.feature_community = True

        with patch("app.api.deps.get_settings", return_value=mock_settings):
            # Should not raise
            require_community()

    def test_community_disabled(self):
        """Test that community features raise 404 when disabled."""
        mock_settings = MagicMock()
        mock_settings.feature_community = False

        with patch("app.api.deps.get_settings", return_value=mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                require_community()
            assert exc_info.value.status_code == 404
            assert "community" in exc_info.value.detail.lower()


class TestRequireKarma:
    """Tests for the require_karma dependency."""

    def test_karma_enabled(self):
        """Test that karma features pass when enabled."""
        mock_settings = MagicMock()
        mock_settings.feature_karma = True

        with patch("app.api.deps.get_settings", return_value=mock_settings):
            # Should not raise
            require_karma()

    def test_karma_disabled(self):
        """Test that karma features raise 404 when disabled."""
        mock_settings = MagicMock()
        mock_settings.feature_karma = False

        with patch("app.api.deps.get_settings", return_value=mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                require_karma()
            assert exc_info.value.status_code == 404
            assert "karma" in exc_info.value.detail.lower()


class TestRequireCloudSync:
    """Tests for the require_cloud_sync dependency."""

    def test_cloud_sync_enabled(self):
        """Test that cloud sync features pass when enabled."""
        mock_settings = MagicMock()
        mock_settings.feature_cloud_sync = True

        with patch("app.api.deps.get_settings", return_value=mock_settings):
            # Should not raise
            require_cloud_sync()

    def test_cloud_sync_disabled(self):
        """Test that cloud sync features raise 404 when disabled."""
        mock_settings = MagicMock()
        mock_settings.feature_cloud_sync = False

        with patch("app.api.deps.get_settings", return_value=mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                require_cloud_sync()
            assert exc_info.value.status_code == 404
            assert "cloud sync" in exc_info.value.detail.lower()
