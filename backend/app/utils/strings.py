"""
String utilities for text manipulation and formatting.

Provides helpers for common string operations, slugification,
truncation, and text processing.
"""

from __future__ import annotations

import html
import re
import secrets
import string
import unicodedata
from typing import Any

__all__ = [
    "slugify",
    "truncate",
    "truncate_words",
    "strip_html",
    "normalize_whitespace",
    "to_title_case",
    "pluralize",
    "singularize",
    "ordinalize",
    "humanize",
    "parameterize",
    "generate_random_string",
    "generate_token",
    "mask_string",
    "extract_numbers",
    "extract_emails",
    "extract_urls",
    "is_blank",
    "is_not_blank",
    "coalesce",
    "safe_str",
    "indent",
    "dedent",
    "wrap_text",
    "levenshtein_distance",
    "similarity_ratio",
]


def slugify(
    text: str,
    *,
    separator: str = "-",
    lowercase: bool = True,
    max_length: int | None = None,
    allow_unicode: bool = False,
) -> str:
    """
    Convert text to URL-friendly slug.
    
    Args:
        text: Text to convert
        separator: Character to use between words
        lowercase: Convert to lowercase
        max_length: Maximum length of slug
        allow_unicode: Allow unicode characters
        
    Returns:
        URL-safe slug
        
    Examples:
        >>> slugify("Hello World!")
        'hello-world'
        >>> slugify("Café au Lait", allow_unicode=True)
        'café-au-lait'
    """
    # Normalize unicode
    if not allow_unicode:
        text = unicodedata.normalize("NFKD", text)
        text = text.encode("ascii", "ignore").decode("ascii")
    else:
        text = unicodedata.normalize("NFKC", text)
    
    # Lowercase
    if lowercase:
        text = text.lower()
    
    # Replace spaces and invalid chars with separator
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", separator, text)
    text = text.strip(separator)
    
    # Truncate if needed
    if max_length and len(text) > max_length:
        text = text[:max_length].rstrip(separator)
    
    return text


def truncate(
    text: str,
    length: int,
    *,
    suffix: str = "...",
    word_boundary: bool = False,
) -> str:
    """
    Truncate text to specified length.
    
    Args:
        text: Text to truncate
        length: Maximum length (including suffix)
        suffix: Suffix to append when truncated
        word_boundary: Truncate at word boundary
        
    Returns:
        Truncated text
        
    Examples:
        >>> truncate("Hello World", 8)
        'Hello...'
        >>> truncate("Hello World", 8, word_boundary=True)
        'Hello...'
    """
    if len(text) <= length:
        return text
    
    # Calculate truncation point
    trunc_length = length - len(suffix)
    if trunc_length <= 0:
        return suffix[:length]
    
    truncated = text[:trunc_length]
    
    # Find word boundary
    if word_boundary:
        last_space = truncated.rfind(" ")
        if last_space > 0:
            truncated = truncated[:last_space]
    
    return truncated.rstrip() + suffix


def truncate_words(
    text: str,
    word_count: int,
    *,
    suffix: str = "...",
) -> str:
    """
    Truncate text to specified number of words.
    
    Args:
        text: Text to truncate
        word_count: Maximum number of words
        suffix: Suffix to append when truncated
        
    Returns:
        Truncated text
        
    Examples:
        >>> truncate_words("The quick brown fox jumps", 3)
        'The quick brown...'
    """
    words = text.split()
    if len(words) <= word_count:
        return text
    
    return " ".join(words[:word_count]) + suffix


def strip_html(text: str, *, keep_links: bool = False) -> str:
    """
    Remove HTML tags from text.
    
    Args:
        text: Text containing HTML
        keep_links: If True, keep link URLs as text
        
    Returns:
        Text with HTML removed
        
    Examples:
        >>> strip_html("<p>Hello <b>World</b></p>")
        'Hello World'
    """
    if keep_links:
        # Replace links with their href
        text = re.sub(
            r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>([^<]*)</a>',
            r'\2 (\1)',
            text,
            flags=re.IGNORECASE,
        )
    
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    
    # Decode HTML entities
    text = html.unescape(text)
    
    return normalize_whitespace(text)


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text (collapse multiple spaces, trim).
    
    Args:
        text: Text to normalize
        
    Returns:
        Normalized text
        
    Examples:
        >>> normalize_whitespace("  Hello   World  ")
        'Hello World'
    """
    return " ".join(text.split())


def to_title_case(text: str) -> str:
    """
    Convert text to title case (capitalize first letter of each word).
    
    Handles articles and prepositions correctly.
    
    Args:
        text: Text to convert
        
    Returns:
        Title-cased text
        
    Examples:
        >>> to_title_case("the quick brown fox")
        'The Quick Brown Fox'
        >>> to_title_case("a tale of two cities")
        'A Tale of Two Cities'
    """
    # Words that should remain lowercase (unless first word)
    small_words = {
        "a", "an", "the", "and", "but", "or", "for", "nor", "on",
        "at", "to", "from", "by", "of", "in", "with", "as",
    }
    
    words = text.lower().split()
    result = []
    
    for i, word in enumerate(words):
        if i == 0 or word not in small_words:
            result.append(word.capitalize())
        else:
            result.append(word)
    
    return " ".join(result)


def pluralize(word: str, count: int = 2) -> str:
    """
    Get plural form of a word based on count.
    
    Basic pluralization rules. For complex cases, consider
    using a library like inflect.
    
    Args:
        word: Word to pluralize
        count: Number to determine plural form
        
    Returns:
        Singular or plural form
        
    Examples:
        >>> pluralize("item", 1)
        'item'
        >>> pluralize("item", 2)
        'items'
        >>> pluralize("box", 2)
        'boxes'
    """
    if count == 1:
        return word
    
    # Common irregular plurals
    irregulars = {
        "child": "children",
        "person": "people",
        "man": "men",
        "woman": "women",
        "foot": "feet",
        "tooth": "teeth",
        "goose": "geese",
        "mouse": "mice",
    }
    
    lower = word.lower()
    if lower in irregulars:
        plural = irregulars[lower]
        return plural.capitalize() if word[0].isupper() else plural
    
    # Rules for pluralization
    if lower.endswith(("s", "ss", "sh", "ch", "x", "z")):
        return word + "es"
    elif lower.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    elif lower.endswith("fe"):
        return word[:-2] + "ves"
    elif lower.endswith("f"):
        return word[:-1] + "ves"
    else:
        return word + "s"


def singularize(word: str) -> str:
    """
    Get singular form of a word.
    
    Basic singularization. For complex cases, consider
    using a library like inflect.
    
    Args:
        word: Word to singularize
        
    Returns:
        Singular form
        
    Examples:
        >>> singularize("items")
        'item'
        >>> singularize("boxes")
        'box'
    """
    # Common irregular plurals (reversed)
    irregulars = {
        "children": "child",
        "people": "person",
        "men": "man",
        "women": "woman",
        "feet": "foot",
        "teeth": "tooth",
        "geese": "goose",
        "mice": "mouse",
    }
    
    lower = word.lower()
    if lower in irregulars:
        singular = irregulars[lower]
        return singular.capitalize() if word[0].isupper() else singular
    
    # Rules for singularization
    if lower.endswith("ies") and len(word) > 3:
        return word[:-3] + "y"
    elif lower.endswith("ves"):
        return word[:-3] + "f"
    elif lower.endswith("xes") or lower.endswith("zes"):
        return word[:-2]
    elif lower.endswith("sses") or lower.endswith("shes") or lower.endswith("ches"):
        return word[:-2]
    elif lower.endswith("ses"):
        return word[:-2]
    elif lower.endswith("s") and not lower.endswith("ss"):
        return word[:-1]
    
    return word


def ordinalize(number: int) -> str:
    """
    Convert number to ordinal string (1st, 2nd, 3rd, etc.).
    
    Args:
        number: Number to convert
        
    Returns:
        Ordinal string
        
    Examples:
        >>> ordinalize(1)
        '1st'
        >>> ordinalize(2)
        '2nd'
        >>> ordinalize(11)
        '11th'
    """
    if 11 <= abs(number) % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(abs(number) % 10, "th")
    
    return f"{number}{suffix}"


def humanize(text: str) -> str:
    """
    Convert identifier to human-readable string.
    
    Args:
        text: Snake_case or camelCase identifier
        
    Returns:
        Human-readable string
        
    Examples:
        >>> humanize("user_name")
        'User name'
        >>> humanize("userName")
        'User name'
    """
    # Convert camelCase to spaces
    text = re.sub(r"([A-Z])", r" \1", text)
    # Convert underscores to spaces
    text = text.replace("_", " ")
    # Normalize whitespace and capitalize
    text = normalize_whitespace(text)
    return text.capitalize()


def parameterize(text: str, separator: str = "-") -> str:
    """
    Convert text to URL parameter format.
    
    Similar to slugify but specifically for URL parameters.
    
    Args:
        text: Text to convert
        separator: Character to use between words
        
    Returns:
        Parameterized string
        
    Examples:
        >>> parameterize("Hello World!")
        'hello-world'
    """
    return slugify(text, separator=separator)


def generate_random_string(
    length: int = 16,
    *,
    charset: str | None = None,
    include_uppercase: bool = True,
    include_lowercase: bool = True,
    include_digits: bool = True,
    include_special: bool = False,
) -> str:
    """
    Generate a cryptographically secure random string.
    
    Args:
        length: Length of string to generate
        charset: Custom character set (overrides other options)
        include_uppercase: Include uppercase letters
        include_lowercase: Include lowercase letters
        include_digits: Include digits
        include_special: Include special characters
        
    Returns:
        Random string
        
    Examples:
        >>> len(generate_random_string(32))
        32
    """
    if charset is None:
        charset = ""
        if include_uppercase:
            charset += string.ascii_uppercase
        if include_lowercase:
            charset += string.ascii_lowercase
        if include_digits:
            charset += string.digits
        if include_special:
            charset += "!@#$%^&*"
        
        if not charset:
            charset = string.ascii_letters + string.digits
    
    return "".join(secrets.choice(charset) for _ in range(length))


def generate_token(
    length: int = 32,
    *,
    prefix: str | None = None,
) -> str:
    """
    Generate a URL-safe token.
    
    Args:
        length: Length of token (not including prefix)
        prefix: Optional prefix for the token
        
    Returns:
        URL-safe token
        
    Examples:
        >>> token = generate_token(prefix="api_")
        >>> token.startswith("api_")
        True
    """
    token = secrets.token_urlsafe(length)
    if prefix:
        return prefix + token
    return token


def mask_string(
    text: str,
    *,
    visible_start: int = 0,
    visible_end: int = 4,
    mask_char: str = "*",
    min_masked: int = 4,
) -> str:
    """
    Mask a string, showing only start and end characters.
    
    Args:
        text: String to mask
        visible_start: Number of characters visible at start
        visible_end: Number of characters visible at end
        mask_char: Character to use for masking
        min_masked: Minimum number of masked characters
        
    Returns:
        Masked string
        
    Examples:
        >>> mask_string("1234567890", visible_end=4)
        '******7890'
        >>> mask_string("secret", visible_start=1, visible_end=1)
        's****t'
    """
    if len(text) <= visible_start + visible_end + min_masked:
        # String too short, mask all except ends
        mask_length = max(len(text) - visible_start - visible_end, min_masked)
        if mask_length >= len(text):
            return mask_char * len(text)
    
    mask_length = len(text) - visible_start - visible_end
    mask_length = max(mask_length, min_masked)
    
    start = text[:visible_start] if visible_start > 0 else ""
    end = text[-visible_end:] if visible_end > 0 else ""
    
    return start + (mask_char * mask_length) + end


def extract_numbers(text: str) -> list[str]:
    """
    Extract all numbers from text.
    
    Args:
        text: Text to search
        
    Returns:
        List of number strings
        
    Examples:
        >>> extract_numbers("I have 3 apples and 42 oranges")
        ['3', '42']
        >>> extract_numbers("Price: $19.99")
        ['19.99']
    """
    return re.findall(r"\d+(?:\.\d+)?", text)


def extract_emails(text: str) -> list[str]:
    """
    Extract email addresses from text.
    
    Args:
        text: Text to search
        
    Returns:
        List of email addresses
        
    Examples:
        >>> extract_emails("Contact us at info@example.com")
        ['info@example.com']
    """
    pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    return re.findall(pattern, text)


def extract_urls(text: str) -> list[str]:
    """
    Extract URLs from text.
    
    Args:
        text: Text to search
        
    Returns:
        List of URLs
        
    Examples:
        >>> extract_urls("Visit https://example.com for more")
        ['https://example.com']
    """
    pattern = r"https?://[^\s<>\"']+"
    return re.findall(pattern, text)


def is_blank(text: str | None) -> bool:
    """
    Check if string is None, empty, or contains only whitespace.
    
    Args:
        text: String to check
        
    Returns:
        True if blank
        
    Examples:
        >>> is_blank("")
        True
        >>> is_blank("   ")
        True
        >>> is_blank(None)
        True
        >>> is_blank("hello")
        False
    """
    return text is None or text.strip() == ""


def is_not_blank(text: str | None) -> bool:
    """
    Check if string is not blank.
    
    Args:
        text: String to check
        
    Returns:
        True if not blank
    """
    return not is_blank(text)


def coalesce(*values: str | None, default: str = "") -> str:
    """
    Return the first non-blank value, or default.
    
    Args:
        *values: Values to check
        default: Default value if all are blank
        
    Returns:
        First non-blank value or default
        
    Examples:
        >>> coalesce(None, "", "hello", "world")
        'hello'
    """
    for value in values:
        if is_not_blank(value):
            return value  # type: ignore
    return default


def safe_str(value: Any, default: str = "") -> str:
    """
    Safely convert any value to string.
    
    Args:
        value: Value to convert
        default: Default if value is None
        
    Returns:
        String representation
        
    Examples:
        >>> safe_str(None)
        ''
        >>> safe_str(42)
        '42'
    """
    if value is None:
        return default
    return str(value)


def indent(text: str, spaces: int = 4, *, first_line: bool = True) -> str:
    """
    Indent text by adding spaces to each line.
    
    Args:
        text: Text to indent
        spaces: Number of spaces to add
        first_line: Whether to indent the first line
        
    Returns:
        Indented text
        
    Examples:
        >>> print(indent("line1\\nline2", 2))
          line1
          line2
    """
    prefix = " " * spaces
    lines = text.split("\n")
    
    if first_line:
        return "\n".join(prefix + line for line in lines)
    else:
        return lines[0] + "\n" + "\n".join(prefix + line for line in lines[1:])


def dedent(text: str) -> str:
    """
    Remove common leading whitespace from all lines.
    
    Args:
        text: Text to dedent
        
    Returns:
        Dedented text
        
    Examples:
        >>> print(dedent("    line1\\n    line2"))
        line1
        line2
    """
    import textwrap
    return textwrap.dedent(text)


def wrap_text(
    text: str,
    width: int = 80,
    *,
    break_long_words: bool = True,
    break_on_hyphens: bool = True,
) -> str:
    """
    Wrap text to specified width.
    
    Args:
        text: Text to wrap
        width: Maximum line width
        break_long_words: Break words longer than width
        break_on_hyphens: Break on hyphens
        
    Returns:
        Wrapped text
    """
    import textwrap
    return textwrap.fill(
        text,
        width=width,
        break_long_words=break_long_words,
        break_on_hyphens=break_on_hyphens,
    )


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate the Levenshtein distance between two strings.
    
    The Levenshtein distance is the minimum number of single-character
    edits (insertions, deletions, substitutions) needed to transform
    one string into another.
    
    Args:
        s1: First string
        s2: Second string
        
    Returns:
        Edit distance between strings
        
    Examples:
        >>> levenshtein_distance("kitten", "sitting")
        3
        >>> levenshtein_distance("hello", "hello")
        0
    """
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = list(range(len(s2) + 1))
    
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Calculate costs
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def similarity_ratio(s1: str, s2: str) -> float:
    """
    Calculate similarity ratio between two strings (0.0 to 1.0).
    
    Based on Levenshtein distance. Returns 1.0 for identical strings,
    0.0 for completely different strings.
    
    Args:
        s1: First string
        s2: Second string
        
    Returns:
        Similarity ratio (0.0 to 1.0)
        
    Examples:
        >>> similarity_ratio("hello", "hello")
        1.0
        >>> similarity_ratio("hello", "hallo")
        0.8
    """
    if not s1 and not s2:
        return 1.0
    
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    
    distance = levenshtein_distance(s1, s2)
    return 1.0 - (distance / max_len)
