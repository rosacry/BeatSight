"""
URL utilities for building, parsing, and manipulating URLs.

Provides utilities for:
- URL building and manipulation
- Query string handling
- URL parsing and validation
- Path manipulation
- Domain extraction
"""

import re
from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import (
    parse_qs,
    parse_qsl,
    quote,
    quote_plus,
    unquote,
    unquote_plus,
    urlencode,
    urljoin,
    urlparse,
    urlunparse,
)

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# URL Building
# =============================================================================


@dataclass
class URLBuilder:
    """
    Fluent URL builder.

    Example:
        >>> url = (
        ...     URLBuilder("https://api.example.com")
        ...     .path("users", "123")
        ...     .param("include", "profile")
        ...     .param("fields", ["name", "email"])
        ...     .build()
        ... )
        >>> url
        'https://api.example.com/users/123?include=profile&fields=name&fields=email'
    """

    base_url: str
    _paths: list[str] = field(default_factory=list)
    _params: list[tuple[str, str]] = field(default_factory=list)
    _fragment: str = ""

    def path(self, *segments: str | int) -> "URLBuilder":
        """
        Add path segments.

        Args:
            *segments: Path segments to add

        Returns:
            Self for chaining
        """
        for segment in segments:
            segment_str = str(segment).strip("/")
            if segment_str:
                self._paths.append(segment_str)
        return self

    def param(
        self,
        key: str,
        value: str | int | float | bool | list[Any] | None,
    ) -> "URLBuilder":
        """
        Add a query parameter.

        Args:
            key: Parameter key
            value: Parameter value (lists become multiple params)

        Returns:
            Self for chaining
        """
        if value is None:
            return self

        if isinstance(value, bool):
            self._params.append((key, str(value).lower()))
        elif isinstance(value, (list, tuple)):
            for v in value:
                self._params.append((key, str(v)))
        else:
            self._params.append((key, str(value)))

        return self

    def params(self, params: Mapping[str, Any] | None) -> "URLBuilder":
        """
        Add multiple query parameters.

        Args:
            params: Dictionary of parameters

        Returns:
            Self for chaining
        """
        if params:
            for key, value in params.items():
                self.param(key, value)
        return self

    def fragment(self, fragment: str) -> "URLBuilder":
        """
        Set URL fragment.

        Args:
            fragment: Fragment string (without #)

        Returns:
            Self for chaining
        """
        self._fragment = fragment
        return self

    def build(self) -> str:
        """
        Build the final URL.

        Returns:
            Complete URL string
        """
        # Parse base URL
        parsed = urlparse(self.base_url)

        # Build path
        base_path = parsed.path.rstrip("/")
        if self._paths:
            path = "/".join([base_path] + self._paths)
        else:
            path = base_path

        # Build query string
        existing_params = parse_qsl(parsed.query)
        all_params = existing_params + self._params
        query = urlencode(all_params)

        # Build fragment
        fragment = self._fragment or parsed.fragment

        # Reconstruct URL
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                path,
                parsed.params,
                query,
                fragment,
            )
        )


def build_url(
    base_url: str,
    *path_segments: str | int,
    params: Mapping[str, Any] | None = None,
    fragment: str = "",
) -> str:
    """
    Build a URL with path and query parameters.

    Args:
        base_url: Base URL
        *path_segments: Additional path segments
        params: Query parameters
        fragment: URL fragment

    Returns:
        Complete URL string

    Example:
        >>> build_url("https://api.example.com", "users", 123, params={"active": True})
        'https://api.example.com/users/123?active=true'
    """
    builder = URLBuilder(base_url)

    if path_segments:
        builder.path(*path_segments)

    if params:
        builder.params(params)

    if fragment:
        builder.fragment(fragment)

    return builder.build()


def join_url(*parts: str) -> str:
    """
    Join URL parts safely.

    Args:
        *parts: URL parts to join

    Returns:
        Joined URL

    Example:
        >>> join_url("https://example.com/", "/api/", "/v1/", "users")
        'https://example.com/api/v1/users'
    """
    if not parts:
        return ""

    result = parts[0].rstrip("/")
    for part in parts[1:]:
        part = part.strip("/")
        if part:
            result = f"{result}/{part}"

    return result


# =============================================================================
# Query String Operations
# =============================================================================


def parse_query_string(
    query: str,
    keep_blank_values: bool = True,
) -> dict[str, list[str]]:
    """
    Parse query string into dictionary.

    Args:
        query: Query string (with or without leading ?)
        keep_blank_values: Whether to keep empty values

    Returns:
        Dictionary mapping keys to lists of values

    Example:
        >>> parse_query_string("a=1&b=2&a=3")
        {'a': ['1', '3'], 'b': ['2']}
    """
    if query.startswith("?"):
        query = query[1:]

    return parse_qs(query, keep_blank_values=keep_blank_values)


def parse_query_string_flat(
    query: str,
    keep_blank_values: bool = True,
) -> dict[str, str]:
    """
    Parse query string into flat dictionary (last value wins).

    Args:
        query: Query string
        keep_blank_values: Whether to keep empty values

    Returns:
        Dictionary mapping keys to single values

    Example:
        >>> parse_query_string_flat("a=1&b=2&a=3")
        {'a': '3', 'b': '2'}
    """
    if query.startswith("?"):
        query = query[1:]

    return dict(parse_qsl(query, keep_blank_values=keep_blank_values))


def build_query_string(
    params: Mapping[str, Any],
    *,
    doseq: bool = True,
    safe: str = "",
) -> str:
    """
    Build query string from dictionary.

    Args:
        params: Parameters dictionary
        doseq: Whether to encode sequences as multiple params
        safe: Characters to not encode

    Returns:
        Query string (without leading ?)

    Example:
        >>> build_query_string({"a": 1, "b": [2, 3]})
        'a=1&b=2&b=3'
    """
    # Convert values to strings, handling None and bool
    encoded_params: list[tuple[str, str]] = []

    for key, value in params.items():
        if value is None:
            continue

        if isinstance(value, bool):
            encoded_params.append((key, str(value).lower()))
        elif isinstance(value, (list, tuple)) and doseq:
            for v in value:
                encoded_params.append((key, str(v)))
        else:
            encoded_params.append((key, str(value)))

    return urlencode(encoded_params, safe=safe)


def add_query_params(url: str, params: Mapping[str, Any]) -> str:
    """
    Add query parameters to an existing URL.

    Args:
        url: Original URL
        params: Parameters to add

    Returns:
        URL with added parameters

    Example:
        >>> add_query_params("https://example.com?a=1", {"b": 2})
        'https://example.com?a=1&b=2'
    """
    return URLBuilder(url).params(params).build()


def remove_query_params(url: str, *keys: str) -> str:
    """
    Remove specific query parameters from URL.

    Args:
        url: Original URL
        *keys: Parameter keys to remove

    Returns:
        URL without specified parameters

    Example:
        >>> remove_query_params("https://example.com?a=1&b=2&c=3", "b")
        'https://example.com?a=1&c=3'
    """
    parsed = urlparse(url)
    params = parse_qsl(parsed.query)
    keys_to_remove = set(keys)

    filtered_params = [(k, v) for k, v in params if k not in keys_to_remove]

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(filtered_params),
            parsed.fragment,
        )
    )


def get_query_param(url: str, key: str, default: str | None = None) -> str | None:
    """
    Get a single query parameter value from URL.

    Args:
        url: URL to parse
        key: Parameter key
        default: Default if not found

    Returns:
        Parameter value or default

    Example:
        >>> get_query_param("https://example.com?a=1&b=2", "a")
        '1'
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    values = params.get(key, [])
    return values[0] if values else default


def get_all_query_params(url: str, key: str) -> list[str]:
    """
    Get all values for a query parameter.

    Args:
        url: URL to parse
        key: Parameter key

    Returns:
        List of values (empty if not found)

    Example:
        >>> get_all_query_params("https://example.com?a=1&a=2", "a")
        ['1', '2']
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return params.get(key, [])


# =============================================================================
# URL Parsing
# =============================================================================


@dataclass
class ParsedURL:
    """Structured URL components."""

    scheme: str
    host: str
    port: int | None
    path: str
    query: str
    fragment: str
    username: str | None
    password: str | None

    @property
    def netloc(self) -> str:
        """Get network location (host:port)."""
        if self.port:
            return f"{self.host}:{self.port}"
        return self.host

    @property
    def origin(self) -> str:
        """Get origin (scheme://host:port)."""
        return f"{self.scheme}://{self.netloc}"

    @property
    def is_secure(self) -> bool:
        """Check if URL uses secure protocol."""
        return self.scheme in ("https", "wss", "ftps")

    @property
    def query_params(self) -> dict[str, list[str]]:
        """Parse query string into dict."""
        return parse_qs(self.query)

    def to_url(self) -> str:
        """Reconstruct URL string."""
        auth = ""
        if self.username:
            if self.password:
                auth = f"{self.username}:{self.password}@"
            else:
                auth = f"{self.username}@"

        netloc = f"{auth}{self.netloc}"

        return urlunparse(
            (
                self.scheme,
                netloc,
                self.path,
                "",
                self.query,
                self.fragment,
            )
        )


def parse_url(url: str) -> ParsedURL:
    """
    Parse URL into structured components.

    Args:
        url: URL string to parse

    Returns:
        ParsedURL with all components

    Example:
        >>> parsed = parse_url("https://user:pass@example.com:8080/path?q=1#frag")
        >>> parsed.host
        'example.com'
        >>> parsed.port
        8080
    """
    parsed = urlparse(url)

    # Extract port from netloc
    host = parsed.hostname or ""
    port = parsed.port

    return ParsedURL(
        scheme=parsed.scheme,
        host=host,
        port=port,
        path=parsed.path,
        query=parsed.query,
        fragment=parsed.fragment,
        username=parsed.username,
        password=parsed.password,
    )


def get_domain(url: str, include_subdomain: bool = True) -> str:
    """
    Extract domain from URL.

    Args:
        url: URL to parse
        include_subdomain: Whether to include subdomains

    Returns:
        Domain string

    Example:
        >>> get_domain("https://www.example.com/path")
        'www.example.com'
        >>> get_domain("https://www.example.com/path", include_subdomain=False)
        'example.com'
    """
    parsed = urlparse(url)
    host = parsed.hostname or ""

    if include_subdomain:
        return host

    # Simple extraction - may not work for all TLDs
    parts = host.split(".")
    if len(parts) > 2:
        return ".".join(parts[-2:])
    return host


def get_base_url(url: str) -> str:
    """
    Get base URL (scheme + host + port).

    Args:
        url: Full URL

    Returns:
        Base URL without path, query, or fragment

    Example:
        >>> get_base_url("https://example.com:8080/path?query=1")
        'https://example.com:8080'
    """
    parsed = urlparse(url)
    netloc = (
        parsed.netloc or f"{parsed.hostname}:{parsed.port}"
        if parsed.port
        else parsed.hostname or ""
    )
    return f"{parsed.scheme}://{netloc}"


def get_path(url: str) -> str:
    """
    Extract path from URL.

    Args:
        url: URL to parse

    Returns:
        Path component

    Example:
        >>> get_path("https://example.com/api/users?id=1")
        '/api/users'
    """
    return urlparse(url).path


def get_path_segments(url: str) -> list[str]:
    """
    Get path as list of segments.

    Args:
        url: URL to parse

    Returns:
        List of path segments

    Example:
        >>> get_path_segments("https://example.com/api/users/123")
        ['api', 'users', '123']
    """
    path = urlparse(url).path
    return [seg for seg in path.split("/") if seg]


# =============================================================================
# URL Validation
# =============================================================================


# URL validation regex
URL_PATTERN = re.compile(
    r"^"
    r"(?:(?:https?|ftp)://)"  # Scheme
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+"  # Domain
    r"(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # TLD
    r"localhost|"  # localhost
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # IP
    r"(?::\d+)?"  # Port
    r"(?:/?|[/?]\S+)"  # Path
    r"$",
    re.IGNORECASE,
)


def is_valid_url(url: str) -> bool:
    """
    Check if string is a valid URL.

    Args:
        url: String to validate

    Returns:
        True if valid URL

    Example:
        >>> is_valid_url("https://example.com")
        True
        >>> is_valid_url("not a url")
        False
    """
    if not url:
        return False
    return URL_PATTERN.match(url) is not None


def is_absolute_url(url: str) -> bool:
    """
    Check if URL is absolute (has scheme).

    Args:
        url: URL to check

    Returns:
        True if absolute URL

    Example:
        >>> is_absolute_url("https://example.com/path")
        True
        >>> is_absolute_url("/path/to/resource")
        False
    """
    return bool(urlparse(url).scheme)


def is_relative_url(url: str) -> bool:
    """
    Check if URL is relative (no scheme).

    Args:
        url: URL to check

    Returns:
        True if relative URL

    Example:
        >>> is_relative_url("/path/to/resource")
        True
        >>> is_relative_url("https://example.com")
        False
    """
    return not bool(urlparse(url).scheme)


def is_same_origin(url1: str, url2: str) -> bool:
    """
    Check if two URLs have the same origin.

    Args:
        url1: First URL
        url2: Second URL

    Returns:
        True if same origin (scheme + host + port)

    Example:
        >>> is_same_origin("https://example.com/a", "https://example.com/b")
        True
        >>> is_same_origin("https://example.com", "http://example.com")
        False
    """
    parsed1 = urlparse(url1)
    parsed2 = urlparse(url2)

    return parsed1.scheme == parsed2.scheme and parsed1.netloc == parsed2.netloc


# =============================================================================
# URL Encoding
# =============================================================================


def url_encode(text: str, safe: str = "") -> str:
    """
    URL encode a string.

    Args:
        text: String to encode
        safe: Characters to not encode

    Returns:
        URL-encoded string

    Example:
        >>> url_encode("hello world")
        'hello%20world'
    """
    return quote(text, safe=safe)


def url_decode(text: str) -> str:
    """
    URL decode a string.

    Args:
        text: URL-encoded string

    Returns:
        Decoded string

    Example:
        >>> url_decode("hello%20world")
        'hello world'
    """
    return unquote(text)


def url_encode_plus(text: str, safe: str = "") -> str:
    """
    URL encode for form data (spaces become +).

    Args:
        text: String to encode
        safe: Characters to not encode

    Returns:
        URL-encoded string with + for spaces

    Example:
        >>> url_encode_plus("hello world")
        'hello+world'
    """
    return quote_plus(text, safe=safe)


def url_decode_plus(text: str) -> str:
    """
    URL decode form data (+ becomes space).

    Args:
        text: URL-encoded string

    Returns:
        Decoded string

    Example:
        >>> url_decode_plus("hello+world")
        'hello world'
    """
    return unquote_plus(text)


# =============================================================================
# URL Manipulation
# =============================================================================


def normalize_url(url: str) -> str:
    """
    Normalize URL (lowercase scheme and host, remove default ports).

    Args:
        url: URL to normalize

    Returns:
        Normalized URL

    Example:
        >>> normalize_url("HTTPS://EXAMPLE.COM:443/Path")
        'https://example.com/Path'
    """
    parsed = urlparse(url)

    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port

    # Remove default ports
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None

    netloc = host
    if port:
        netloc = f"{host}:{port}"

    if parsed.username:
        auth = parsed.username
        if parsed.password:
            auth = f"{auth}:{parsed.password}"
        netloc = f"{auth}@{netloc}"

    return urlunparse(
        (
            scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def make_absolute(url: str, base_url: str) -> str:
    """
    Convert relative URL to absolute.

    Args:
        url: URL that might be relative
        base_url: Base URL for resolution

    Returns:
        Absolute URL

    Example:
        >>> make_absolute("/path/to/page", "https://example.com/other")
        'https://example.com/path/to/page'
    """
    return urljoin(base_url, url)


def strip_query_and_fragment(url: str) -> str:
    """
    Remove query string and fragment from URL.

    Args:
        url: URL to strip

    Returns:
        URL without query and fragment

    Example:
        >>> strip_query_and_fragment("https://example.com/path?q=1#section")
        'https://example.com/path'
    """
    parsed = urlparse(url)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            "",
            "",
            "",
        )
    )


def replace_path(url: str, new_path: str) -> str:
    """
    Replace the path component of a URL.

    Args:
        url: Original URL
        new_path: New path to use

    Returns:
        URL with replaced path

    Example:
        >>> replace_path("https://example.com/old/path?q=1", "/new/path")
        'https://example.com/new/path?q=1'
    """
    parsed = urlparse(url)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            new_path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def replace_host(url: str, new_host: str) -> str:
    """
    Replace the host in a URL.

    Args:
        url: Original URL
        new_host: New host to use

    Returns:
        URL with replaced host

    Example:
        >>> replace_host("https://old.example.com/path", "new.example.com")
        'https://new.example.com/path'
    """
    parsed = urlparse(url)

    # Preserve port if present
    port = parsed.port
    netloc = new_host
    if port:
        netloc = f"{new_host}:{port}"

    # Preserve auth if present
    if parsed.username:
        auth = parsed.username
        if parsed.password:
            auth = f"{auth}:{parsed.password}"
        netloc = f"{auth}@{netloc}"

    return urlunparse(
        (
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def append_path(url: str, *segments: str) -> str:
    """
    Append path segments to URL.

    Args:
        url: Base URL
        *segments: Path segments to append

    Returns:
        URL with appended path

    Example:
        >>> append_path("https://example.com/api", "users", "123")
        'https://example.com/api/users/123'
    """
    return URLBuilder(url).path(*segments).build()


# =============================================================================
# Utility Functions
# =============================================================================


def extract_urls(text: str) -> list[str]:
    """
    Extract all URLs from text.

    Args:
        text: Text to search

    Returns:
        List of found URLs

    Example:
        >>> extract_urls("Visit https://example.com or http://test.com")
        ['https://example.com', 'http://test.com']
    """
    url_pattern = re.compile(
        r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*",
        re.IGNORECASE,
    )
    return url_pattern.findall(text)


def is_internal_url(url: str, base_url: str) -> bool:
    """
    Check if URL is internal (same domain as base).

    Args:
        url: URL to check
        base_url: Base URL for comparison

    Returns:
        True if URL is internal

    Example:
        >>> is_internal_url("/path", "https://example.com")
        True
        >>> is_internal_url("https://other.com", "https://example.com")
        False
    """
    # Relative URLs are always internal
    if is_relative_url(url):
        return True

    return is_same_origin(url, base_url)


def slugify_path(path: str) -> str:
    """
    Convert path to URL-safe slug.

    Args:
        path: Path to slugify

    Returns:
        URL-safe path

    Example:
        >>> slugify_path("Hello World/Test Page")
        'hello-world/test-page'
    """
    # Split by path separator
    segments = path.split("/")

    # Slugify each segment
    slugified = []
    for segment in segments:
        if not segment:
            continue
        # Convert to lowercase, replace non-alphanumeric with hyphens
        slug = re.sub(r"[^\w\s-]", "", segment.lower())
        slug = re.sub(r"[-\s]+", "-", slug).strip("-")
        if slug:
            slugified.append(slug)

    return "/".join(slugified)
