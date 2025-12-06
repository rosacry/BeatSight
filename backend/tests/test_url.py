"""Tests for URL utilities."""

import pytest

from app.utils.url import (
    # URL Building
    URLBuilder,
    build_url,
    join_url,
    # Query String
    parse_query_string,
    parse_query_string_flat,
    build_query_string,
    add_query_params,
    remove_query_params,
    get_query_param,
    get_all_query_params,
    # URL Parsing
    ParsedURL,
    parse_url,
    get_domain,
    get_base_url,
    get_path,
    get_path_segments,
    # URL Validation
    is_valid_url,
    is_absolute_url,
    is_relative_url,
    is_same_origin,
    # URL Encoding
    url_encode,
    url_decode,
    url_encode_plus,
    url_decode_plus,
    # URL Manipulation
    normalize_url,
    make_absolute,
    strip_query_and_fragment,
    replace_path,
    replace_host,
    append_path,
    # Utility Functions
    extract_urls,
    is_internal_url,
    slugify_path,
)


class TestURLBuilder:
    """Tests for URLBuilder class."""
    
    def test_basic_build(self):
        """Test basic URL building."""
        url = URLBuilder("https://example.com").build()
        assert url == "https://example.com"
    
    def test_add_path(self):
        """Test adding path segments."""
        url = URLBuilder("https://example.com").path("api", "users").build()
        assert url == "https://example.com/api/users"
    
    def test_add_path_with_int(self):
        """Test adding integer path segments."""
        url = URLBuilder("https://example.com").path("users", 123).build()
        assert url == "https://example.com/users/123"
    
    def test_add_param(self):
        """Test adding query parameter."""
        url = URLBuilder("https://example.com").param("key", "value").build()
        assert url == "https://example.com?key=value"
    
    def test_add_bool_param(self):
        """Test adding boolean parameter."""
        url = URLBuilder("https://example.com").param("active", True).build()
        assert url == "https://example.com?active=true"
    
    def test_add_list_param(self):
        """Test adding list parameter."""
        url = URLBuilder("https://example.com").param("ids", [1, 2, 3]).build()
        assert "ids=1" in url
        assert "ids=2" in url
        assert "ids=3" in url
    
    def test_add_none_param(self):
        """Test adding None parameter (ignored)."""
        url = URLBuilder("https://example.com").param("key", None).build()
        assert url == "https://example.com"
    
    def test_add_multiple_params(self):
        """Test adding multiple parameters."""
        url = (
            URLBuilder("https://example.com")
            .params({"a": 1, "b": 2})
            .build()
        )
        assert "a=1" in url
        assert "b=2" in url
    
    def test_add_fragment(self):
        """Test adding fragment."""
        url = URLBuilder("https://example.com").fragment("section").build()
        assert url == "https://example.com#section"
    
    def test_preserve_existing_query(self):
        """Test preserving existing query parameters."""
        url = URLBuilder("https://example.com?a=1").param("b", 2).build()
        assert "a=1" in url
        assert "b=2" in url
    
    def test_full_url_building(self):
        """Test building complete URL."""
        url = (
            URLBuilder("https://api.example.com")
            .path("v1", "users", 123)
            .param("include", "profile")
            .param("fields", ["name", "email"])
            .fragment("section")
            .build()
        )
        assert "https://api.example.com/v1/users/123" in url
        assert "include=profile" in url
        assert "#section" in url


class TestBuildUrl:
    """Tests for build_url function."""
    
    def test_basic(self):
        """Test basic URL building."""
        url = build_url("https://example.com")
        assert url == "https://example.com"
    
    def test_with_path(self):
        """Test with path segments."""
        url = build_url("https://example.com", "api", "users")
        assert url == "https://example.com/api/users"
    
    def test_with_params(self):
        """Test with parameters."""
        url = build_url("https://example.com", params={"key": "value"})
        assert url == "https://example.com?key=value"
    
    def test_with_fragment(self):
        """Test with fragment."""
        url = build_url("https://example.com", fragment="section")
        assert url == "https://example.com#section"


class TestJoinUrl:
    """Tests for join_url function."""
    
    def test_basic_join(self):
        """Test basic URL joining."""
        url = join_url("https://example.com", "api", "users")
        assert url == "https://example.com/api/users"
    
    def test_strips_slashes(self):
        """Test that extra slashes are stripped."""
        url = join_url("https://example.com/", "/api/", "/users")
        assert url == "https://example.com/api/users"
    
    def test_empty_parts(self):
        """Test with empty parts."""
        url = join_url("https://example.com", "", "api")
        assert url == "https://example.com/api"
    
    def test_empty_input(self):
        """Test with no parts."""
        assert join_url() == ""


class TestQueryStringParsing:
    """Tests for query string parsing."""
    
    def test_parse_query_string_basic(self):
        """Test basic parsing."""
        result = parse_query_string("a=1&b=2")
        assert result == {"a": ["1"], "b": ["2"]}
    
    def test_parse_query_string_multiple_values(self):
        """Test parsing multiple values for same key."""
        result = parse_query_string("a=1&a=2&a=3")
        assert result == {"a": ["1", "2", "3"]}
    
    def test_parse_query_string_with_question_mark(self):
        """Test parsing with leading ?."""
        result = parse_query_string("?a=1")
        assert result == {"a": ["1"]}
    
    def test_parse_query_string_flat(self):
        """Test flat parsing (last value wins)."""
        result = parse_query_string_flat("a=1&b=2&a=3")
        assert result == {"a": "3", "b": "2"}
    
    def test_build_query_string_basic(self):
        """Test building query string."""
        result = build_query_string({"a": 1, "b": 2})
        assert "a=1" in result
        assert "b=2" in result
    
    def test_build_query_string_list(self):
        """Test building with list values."""
        result = build_query_string({"ids": [1, 2, 3]})
        assert result == "ids=1&ids=2&ids=3"
    
    def test_build_query_string_bool(self):
        """Test building with boolean values."""
        result = build_query_string({"active": True, "deleted": False})
        assert "active=true" in result
        assert "deleted=false" in result
    
    def test_build_query_string_none(self):
        """Test building with None (excluded)."""
        result = build_query_string({"a": 1, "b": None})
        assert result == "a=1"


class TestQueryParamManipulation:
    """Tests for query parameter manipulation."""
    
    def test_add_query_params(self):
        """Test adding query parameters."""
        url = add_query_params("https://example.com?a=1", {"b": 2})
        assert "a=1" in url
        assert "b=2" in url
    
    def test_remove_query_params(self):
        """Test removing query parameters."""
        url = remove_query_params("https://example.com?a=1&b=2&c=3", "b")
        assert "a=1" in url
        assert "b=2" not in url
        assert "c=3" in url
    
    def test_get_query_param(self):
        """Test getting single query parameter."""
        result = get_query_param("https://example.com?a=1&b=2", "a")
        assert result == "1"
    
    def test_get_query_param_not_found(self):
        """Test getting missing parameter."""
        result = get_query_param("https://example.com?a=1", "b", default="default")
        assert result == "default"
    
    def test_get_all_query_params(self):
        """Test getting all values for parameter."""
        result = get_all_query_params("https://example.com?a=1&a=2&a=3", "a")
        assert result == ["1", "2", "3"]
    
    def test_get_all_query_params_not_found(self):
        """Test getting all values for missing parameter."""
        result = get_all_query_params("https://example.com?a=1", "b")
        assert result == []


class TestParsedURL:
    """Tests for ParsedURL class."""
    
    def test_parse_basic_url(self):
        """Test parsing basic URL."""
        parsed = parse_url("https://example.com/path")
        assert parsed.scheme == "https"
        assert parsed.host == "example.com"
        assert parsed.path == "/path"
    
    def test_parse_url_with_port(self):
        """Test parsing URL with port."""
        parsed = parse_url("https://example.com:8080/path")
        assert parsed.port == 8080
        assert parsed.netloc == "example.com:8080"
    
    def test_parse_url_with_auth(self):
        """Test parsing URL with authentication."""
        parsed = parse_url("https://user:pass@example.com/path")
        assert parsed.username == "user"
        assert parsed.password == "pass"
    
    def test_parse_url_with_query_and_fragment(self):
        """Test parsing URL with query and fragment."""
        parsed = parse_url("https://example.com/path?q=1#section")
        assert parsed.query == "q=1"
        assert parsed.fragment == "section"
    
    def test_parsed_url_origin(self):
        """Test origin property."""
        parsed = parse_url("https://example.com:8080/path?q=1")
        assert parsed.origin == "https://example.com:8080"
    
    def test_parsed_url_is_secure(self):
        """Test is_secure property."""
        assert parse_url("https://example.com").is_secure is True
        assert parse_url("http://example.com").is_secure is False
    
    def test_parsed_url_query_params(self):
        """Test query_params property."""
        parsed = parse_url("https://example.com?a=1&b=2")
        assert parsed.query_params == {"a": ["1"], "b": ["2"]}
    
    def test_parsed_url_to_url(self):
        """Test reconstructing URL."""
        original = "https://example.com/path?q=1#section"
        parsed = parse_url(original)
        assert parsed.to_url() == original


class TestDomainExtraction:
    """Tests for domain extraction."""
    
    def test_get_domain_basic(self):
        """Test basic domain extraction."""
        domain = get_domain("https://www.example.com/path")
        assert domain == "www.example.com"
    
    def test_get_domain_without_subdomain(self):
        """Test domain extraction without subdomain."""
        domain = get_domain("https://www.example.com/path", include_subdomain=False)
        assert domain == "example.com"
    
    def test_get_base_url(self):
        """Test base URL extraction."""
        base = get_base_url("https://example.com:8080/path?q=1")
        assert base == "https://example.com:8080"
    
    def test_get_path(self):
        """Test path extraction."""
        path = get_path("https://example.com/api/users?id=1")
        assert path == "/api/users"
    
    def test_get_path_segments(self):
        """Test path segments extraction."""
        segments = get_path_segments("https://example.com/api/users/123")
        assert segments == ["api", "users", "123"]


class TestURLValidation:
    """Tests for URL validation."""
    
    def test_is_valid_url_valid(self):
        """Test valid URLs."""
        assert is_valid_url("https://example.com") is True
        assert is_valid_url("http://localhost:8080") is True
        assert is_valid_url("https://example.com/path?q=1") is True
    
    def test_is_valid_url_invalid(self):
        """Test invalid URLs."""
        assert is_valid_url("not a url") is False
        assert is_valid_url("") is False
        assert is_valid_url("example.com") is False  # No scheme
    
    def test_is_absolute_url(self):
        """Test absolute URL detection."""
        assert is_absolute_url("https://example.com") is True
        assert is_absolute_url("/path/to/resource") is False
    
    def test_is_relative_url(self):
        """Test relative URL detection."""
        assert is_relative_url("/path/to/resource") is True
        assert is_relative_url("https://example.com") is False
    
    def test_is_same_origin(self):
        """Test same origin detection."""
        assert is_same_origin(
            "https://example.com/a",
            "https://example.com/b"
        ) is True
        assert is_same_origin(
            "https://example.com",
            "http://example.com"
        ) is False
        assert is_same_origin(
            "https://example.com",
            "https://other.com"
        ) is False


class TestURLEncoding:
    """Tests for URL encoding."""
    
    def test_url_encode(self):
        """Test URL encoding."""
        assert url_encode("hello world") == "hello%20world"
        assert url_encode("a=b&c=d") == "a%3Db%26c%3Dd"
    
    def test_url_decode(self):
        """Test URL decoding."""
        assert url_decode("hello%20world") == "hello world"
    
    def test_url_encode_plus(self):
        """Test URL encoding with plus for spaces."""
        assert url_encode_plus("hello world") == "hello+world"
    
    def test_url_decode_plus(self):
        """Test URL decoding with plus for spaces."""
        assert url_decode_plus("hello+world") == "hello world"


class TestURLManipulation:
    """Tests for URL manipulation."""
    
    def test_normalize_url(self):
        """Test URL normalization."""
        assert normalize_url("HTTPS://EXAMPLE.COM/Path") == "https://example.com/Path"
    
    def test_normalize_url_removes_default_port(self):
        """Test removing default ports."""
        assert normalize_url("https://example.com:443/path") == "https://example.com/path"
        assert normalize_url("http://example.com:80/path") == "http://example.com/path"
    
    def test_make_absolute(self):
        """Test making relative URLs absolute."""
        result = make_absolute("/path/to/page", "https://example.com/other")
        assert result == "https://example.com/path/to/page"
    
    def test_strip_query_and_fragment(self):
        """Test stripping query and fragment."""
        result = strip_query_and_fragment("https://example.com/path?q=1#section")
        assert result == "https://example.com/path"
    
    def test_replace_path(self):
        """Test path replacement."""
        result = replace_path("https://example.com/old/path?q=1", "/new/path")
        assert result == "https://example.com/new/path?q=1"
    
    def test_replace_host(self):
        """Test host replacement."""
        result = replace_host("https://old.example.com/path", "new.example.com")
        assert result == "https://new.example.com/path"
    
    def test_append_path(self):
        """Test path appending."""
        result = append_path("https://example.com/api", "users", "123")
        assert result == "https://example.com/api/users/123"


class TestUtilityFunctions:
    """Tests for utility functions."""
    
    def test_extract_urls(self):
        """Test URL extraction from text."""
        text = "Visit https://example.com or http://test.com for more info"
        urls = extract_urls(text)
        assert "https://example.com" in urls
        assert "http://test.com" in urls
    
    def test_is_internal_url_relative(self):
        """Test internal URL detection for relative URLs."""
        assert is_internal_url("/path", "https://example.com") is True
    
    def test_is_internal_url_same_domain(self):
        """Test internal URL detection for same domain."""
        assert is_internal_url(
            "https://example.com/other",
            "https://example.com"
        ) is True
    
    def test_is_internal_url_different_domain(self):
        """Test internal URL detection for different domain."""
        assert is_internal_url(
            "https://other.com/path",
            "https://example.com"
        ) is False
    
    def test_slugify_path(self):
        """Test path slugification."""
        assert slugify_path("Hello World") == "hello-world"
        assert slugify_path("Hello World/Test Page") == "hello-world/test-page"
        assert slugify_path("Special!@#Characters") == "specialcharacters"
