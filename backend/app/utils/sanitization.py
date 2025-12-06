"""Input sanitization utilities for secure data handling.

Provides functions to sanitize user input and prevent injection attacks,
XSS, and other security vulnerabilities.
"""

from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional


def sanitize_html(text: str) -> str:
    """Escape HTML entities to prevent XSS attacks.
    
    Args:
        text: Raw text input
        
    Returns:
        Text with HTML entities escaped
    """
    return html.escape(text)


def strip_html_tags(text: str) -> str:
    """Remove all HTML tags from text.
    
    Args:
        text: Text that may contain HTML
        
    Returns:
        Text with all HTML tags removed
    """
    return re.sub(r'<[^>]+>', '', text)


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """Sanitize a filename to prevent path traversal attacks.
    
    Args:
        filename: Original filename
        max_length: Maximum allowed length
        
    Returns:
        Sanitized filename safe for filesystem operations
    """
    # Remove path separators and dangerous characters
    sanitized = re.sub(r'[/\\:*?"<>|]', '_', filename)
    
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    
    # Remove any remaining path traversal attempts
    sanitized = sanitized.replace('..', '_')
    
    # Limit length
    if len(sanitized) > max_length:
        # Keep extension if present
        name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
        if ext:
            max_name_len = max_length - len(ext) - 1
            sanitized = f"{name[:max_name_len]}.{ext}"
        else:
            sanitized = sanitized[:max_length]
    
    # Ensure we have a valid filename
    if not sanitized or sanitized in ('.', '..'):
        sanitized = 'unnamed'
    
    return sanitized


def sanitize_email(email: str) -> str:
    """Normalize and sanitize email address.
    
    Args:
        email: Raw email input
        
    Returns:
        Lowercase, stripped email address
    """
    return email.lower().strip()


def sanitize_display_name(name: str, max_length: int = 120) -> str:
    """Sanitize display name for safe storage and display.
    
    Args:
        name: Raw display name
        max_length: Maximum allowed length
        
    Returns:
        Sanitized display name
    """
    # Strip whitespace and normalize internal spaces
    sanitized = ' '.join(name.split())
    
    # Remove control characters
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip()
    
    return sanitized


def sanitize_search_query(query: str, max_length: int = 200) -> str:
    """Sanitize search query for safe database operations.
    
    Args:
        query: Raw search query
        max_length: Maximum allowed length
        
    Returns:
        Sanitized search query
    """
    # Strip and normalize whitespace
    sanitized = ' '.join(query.split())
    
    # Remove SQL injection attempts (basic)
    sanitized = re.sub(r'[;\'"\\]', '', sanitized)
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip()
    
    return sanitized


def sanitize_url(url: str) -> Optional[str]:
    """Validate and sanitize URL.
    
    Args:
        url: Raw URL input
        
    Returns:
        Sanitized URL or None if invalid
    """
    url = url.strip()
    
    # Only allow http and https schemes
    if not url.startswith(('http://', 'https://')):
        return None
    
    # Remove dangerous characters
    url = re.sub(r'[<>"\'\\]', '', url)
    
    # Basic URL validation
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )
    
    if not url_pattern.match(url):
        return None
    
    return url


def sanitize_dict(data: Dict[str, Any], html_fields: List[str] = None) -> Dict[str, Any]:
    """Recursively sanitize dictionary values.
    
    Args:
        data: Dictionary to sanitize
        html_fields: Field names that should have HTML escaped
        
    Returns:
        Sanitized dictionary
    """
    html_fields = html_fields or []
    result = {}
    
    for key, value in data.items():
        if isinstance(value, str):
            if key in html_fields:
                result[key] = sanitize_html(value)
            else:
                # Basic sanitization for strings
                result[key] = value.strip()
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, html_fields)
        elif isinstance(value, list):
            result[key] = [
                sanitize_dict(item, html_fields) if isinstance(item, dict)
                else sanitize_html(item) if isinstance(item, str) and key in html_fields
                else item.strip() if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            result[key] = value
    
    return result


def is_safe_redirect_url(url: str, allowed_hosts: List[str]) -> bool:
    """Check if URL is safe for redirect (prevents open redirect attacks).
    
    Args:
        url: URL to check
        allowed_hosts: List of allowed hostnames
        
    Returns:
        True if URL is safe for redirect
    """
    # Allow relative URLs
    if url.startswith('/') and not url.startswith('//'):
        return True
    
    # Check against allowed hosts
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        
        # Must be http or https
        if parsed.scheme not in ('http', 'https'):
            return False
        
        # Must be in allowed hosts
        return parsed.netloc in allowed_hosts
    except Exception:
        return False
