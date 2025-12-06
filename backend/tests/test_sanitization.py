"""Tests for input sanitization utilities."""

from __future__ import annotations

import pytest

from app.utils.sanitization import (
    sanitize_html,
    strip_html_tags,
    sanitize_filename,
    sanitize_email,
    sanitize_display_name,
    sanitize_search_query,
    sanitize_url,
    sanitize_dict,
    is_safe_redirect_url,
)


class TestSanitizeHtml:
    """Tests for sanitize_html function."""

    def test_escapes_script_tags(self) -> None:
        """Test that script tags are escaped."""
        result = sanitize_html("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_escapes_html_entities(self) -> None:
        """Test that HTML entities are escaped."""
        result = sanitize_html("<div onclick='evil()'>Click me</div>")
        assert "<div" not in result
        assert "&lt;div" in result

    def test_preserves_plain_text(self) -> None:
        """Test that plain text is preserved."""
        result = sanitize_html("Hello World")
        assert result == "Hello World"

    def test_escapes_ampersand(self) -> None:
        """Test that ampersand is escaped."""
        result = sanitize_html("Fish & Chips")
        assert result == "Fish &amp; Chips"


class TestStripHtmlTags:
    """Tests for strip_html_tags function."""

    def test_removes_simple_tags(self) -> None:
        """Test removing simple HTML tags."""
        result = strip_html_tags("<p>Hello</p>")
        assert result == "Hello"

    def test_removes_nested_tags(self) -> None:
        """Test removing nested HTML tags."""
        result = strip_html_tags("<div><p>Hello <b>World</b></p></div>")
        assert result == "Hello World"

    def test_preserves_text_content(self) -> None:
        """Test that text content is preserved."""
        result = strip_html_tags("No HTML here")
        assert result == "No HTML here"


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_removes_path_traversal(self) -> None:
        """Test removal of path traversal attempts."""
        result = sanitize_filename("../../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_removes_dangerous_characters(self) -> None:
        """Test removal of dangerous characters."""
        result = sanitize_filename('file<name>:test?.txt')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert "?" not in result

    def test_truncates_long_names(self) -> None:
        """Test truncation of long filenames."""
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name, max_length=50)
        assert len(result) <= 50
        assert result.endswith(".txt")

    def test_preserves_extension(self) -> None:
        """Test that file extension is preserved."""
        result = sanitize_filename("document.pdf")
        assert result.endswith(".pdf")

    def test_handles_empty_filename(self) -> None:
        """Test handling of empty filename."""
        result = sanitize_filename("")
        assert result == "unnamed"


class TestSanitizeEmail:
    """Tests for sanitize_email function."""

    def test_lowercases_email(self) -> None:
        """Test email is lowercased."""
        result = sanitize_email("John.Doe@Example.COM")
        assert result == "john.doe@example.com"

    def test_strips_whitespace(self) -> None:
        """Test whitespace is stripped."""
        result = sanitize_email("  user@example.com  ")
        assert result == "user@example.com"


class TestSanitizeDisplayName:
    """Tests for sanitize_display_name function."""

    def test_normalizes_whitespace(self) -> None:
        """Test whitespace normalization."""
        result = sanitize_display_name("John    Doe")
        assert result == "John Doe"

    def test_removes_control_characters(self) -> None:
        """Test removal of control characters."""
        result = sanitize_display_name("John\x00Doe")
        assert "\x00" not in result

    def test_truncates_long_names(self) -> None:
        """Test truncation of long names."""
        long_name = "A" * 200
        result = sanitize_display_name(long_name, max_length=50)
        assert len(result) <= 50


class TestSanitizeSearchQuery:
    """Tests for sanitize_search_query function."""

    def test_removes_sql_injection(self) -> None:
        """Test removal of SQL injection characters."""
        result = sanitize_search_query("'; DROP TABLE users; --")
        assert ";" not in result
        assert "'" not in result

    def test_normalizes_whitespace(self) -> None:
        """Test whitespace normalization."""
        result = sanitize_search_query("hello    world")
        assert result == "hello world"

    def test_truncates_long_queries(self) -> None:
        """Test truncation of long queries."""
        long_query = "word " * 100
        result = sanitize_search_query(long_query, max_length=50)
        assert len(result) <= 50


class TestSanitizeUrl:
    """Tests for sanitize_url function."""

    def test_allows_valid_https(self) -> None:
        """Test valid HTTPS URLs are allowed."""
        result = sanitize_url("https://example.com/path")
        assert result == "https://example.com/path"

    def test_allows_valid_http(self) -> None:
        """Test valid HTTP URLs are allowed."""
        result = sanitize_url("http://example.com")
        assert result == "http://example.com"

    def test_rejects_javascript_urls(self) -> None:
        """Test javascript URLs are rejected."""
        result = sanitize_url("javascript:alert('xss')")
        assert result is None

    def test_rejects_data_urls(self) -> None:
        """Test data URLs are rejected."""
        result = sanitize_url("data:text/html,<script>alert('xss')</script>")
        assert result is None

    def test_removes_dangerous_characters(self) -> None:
        """Test dangerous characters are removed."""
        result = sanitize_url("https://example.com/<script>")
        assert "<" not in (result or "")


class TestSanitizeDict:
    """Tests for sanitize_dict function."""

    def test_sanitizes_nested_dict(self) -> None:
        """Test nested dictionary sanitization."""
        data = {
            "name": "  John  ",
            "bio": "<script>evil()</script>",
            "nested": {"value": "  test  "}
        }
        result = sanitize_dict(data, html_fields=["bio"])
        assert result["name"] == "John"
        assert "<script>" not in result["bio"]
        assert result["nested"]["value"] == "test"

    def test_sanitizes_lists(self) -> None:
        """Test list sanitization."""
        data = {"tags": ["  tag1  ", "  tag2  "]}
        result = sanitize_dict(data)
        assert result["tags"] == ["tag1", "tag2"]


class TestIsSafeRedirectUrl:
    """Tests for is_safe_redirect_url function."""

    def test_allows_relative_urls(self) -> None:
        """Test relative URLs are allowed."""
        assert is_safe_redirect_url("/dashboard", []) is True

    def test_blocks_protocol_relative_urls(self) -> None:
        """Test protocol-relative URLs are blocked."""
        assert is_safe_redirect_url("//evil.com", []) is False

    def test_allows_whitelisted_hosts(self) -> None:
        """Test whitelisted hosts are allowed."""
        allowed = ["example.com", "api.example.com"]
        assert is_safe_redirect_url("https://example.com/path", allowed) is True
        assert is_safe_redirect_url("https://api.example.com", allowed) is True

    def test_blocks_non_whitelisted_hosts(self) -> None:
        """Test non-whitelisted hosts are blocked."""
        allowed = ["example.com"]
        assert is_safe_redirect_url("https://evil.com/path", allowed) is False
