"""Tests for string utilities."""

from __future__ import annotations

import pytest

from app.utils.strings import (
    coalesce,
    dedent,
    extract_emails,
    extract_numbers,
    extract_urls,
    generate_random_string,
    generate_token,
    humanize,
    indent,
    is_blank,
    is_not_blank,
    levenshtein_distance,
    mask_string,
    normalize_whitespace,
    ordinalize,
    parameterize,
    pluralize,
    safe_str,
    similarity_ratio,
    singularize,
    slugify,
    strip_html,
    to_title_case,
    truncate,
    truncate_words,
    wrap_text,
)


class TestSlugify:
    """Tests for slugify function."""

    def test_basic_slugify(self):
        """Test basic slugification."""
        assert slugify("Hello World") == "hello-world"

    def test_removes_special_chars(self):
        """Test removing special characters."""
        assert slugify("Hello! World?") == "hello-world"

    def test_custom_separator(self):
        """Test custom separator."""
        assert slugify("Hello World", separator="_") == "hello_world"

    def test_preserve_case(self):
        """Test preserving case."""
        assert slugify("Hello World", lowercase=False) == "Hello-World"

    def test_max_length(self):
        """Test max length."""
        result = slugify("Hello World Example", max_length=10)
        assert len(result) <= 10
        assert result == "hello-worl"

    def test_max_length_no_trailing_separator(self):
        """Test max length doesn't leave trailing separator."""
        result = slugify("Hello World", max_length=6)
        assert not result.endswith("-")

    def test_unicode_characters(self):
        """Test unicode handling."""
        assert slugify("Café au Lait") == "cafe-au-lait"

    def test_allow_unicode(self):
        """Test allowing unicode."""
        result = slugify("Café au Lait", allow_unicode=True)
        assert "café" in result

    def test_multiple_spaces(self):
        """Test multiple spaces."""
        assert slugify("Hello    World") == "hello-world"

    def test_leading_trailing_spaces(self):
        """Test leading/trailing spaces."""
        assert slugify("  Hello World  ") == "hello-world"


class TestTruncate:
    """Tests for truncate function."""

    def test_no_truncation_needed(self):
        """Test when no truncation needed."""
        assert truncate("Hello", 10) == "Hello"

    def test_basic_truncation(self):
        """Test basic truncation."""
        assert truncate("Hello World", 8) == "Hello..."

    def test_custom_suffix(self):
        """Test custom suffix."""
        assert truncate("Hello World", 8, suffix="…") == "Hello W…"

    def test_word_boundary(self):
        """Test truncation at word boundary."""
        result = truncate("Hello World Example", 12, word_boundary=True)
        assert result == "Hello..."

    def test_exact_length(self):
        """Test truncation to exact length."""
        assert truncate("Hello", 5) == "Hello"

    def test_very_short_length(self):
        """Test with very short length."""
        assert truncate("Hello World", 3) == "..."


class TestTruncateWords:
    """Tests for truncate_words function."""

    def test_no_truncation_needed(self):
        """Test when no truncation needed."""
        assert truncate_words("Hello World", 5) == "Hello World"

    def test_basic_truncation(self):
        """Test basic word truncation."""
        assert truncate_words("The quick brown fox jumps", 3) == "The quick brown..."

    def test_custom_suffix(self):
        """Test custom suffix."""
        result = truncate_words("One two three four", 2, suffix="…")
        assert result == "One two…"

    def test_single_word(self):
        """Test single word limit."""
        assert truncate_words("One two three", 1) == "One..."


class TestStripHtml:
    """Tests for strip_html function."""

    def test_basic_strip(self):
        """Test basic HTML stripping."""
        assert strip_html("<p>Hello</p>") == "Hello"

    def test_nested_tags(self):
        """Test nested tags."""
        assert strip_html("<div><p>Hello <b>World</b></p></div>") == "Hello World"

    def test_html_entities(self):
        """Test HTML entity decoding."""
        assert strip_html("&lt;Hello&gt; &amp; World") == "<Hello> & World"

    def test_keep_links(self):
        """Test keeping link URLs."""
        html = '<a href="https://example.com">Click here</a>'
        result = strip_html(html, keep_links=True)
        assert "https://example.com" in result
        assert "Click here" in result


class TestNormalizeWhitespace:
    """Tests for normalize_whitespace function."""

    def test_multiple_spaces(self):
        """Test collapsing multiple spaces."""
        assert normalize_whitespace("Hello    World") == "Hello World"

    def test_trim(self):
        """Test trimming."""
        assert normalize_whitespace("  Hello  ") == "Hello"

    def test_newlines_and_tabs(self):
        """Test handling newlines and tabs."""
        assert normalize_whitespace("Hello\n\tWorld") == "Hello World"


class TestToTitleCase:
    """Tests for to_title_case function."""

    def test_basic_title_case(self):
        """Test basic title case."""
        assert to_title_case("hello world") == "Hello World"

    def test_small_words(self):
        """Test small words remain lowercase."""
        assert to_title_case("the lord of the rings") == "The Lord of the Rings"

    def test_first_word_capitalized(self):
        """Test first word is always capitalized."""
        assert to_title_case("a tale of two cities") == "A Tale of Two Cities"


class TestPluralize:
    """Tests for pluralize function."""

    def test_singular_count(self):
        """Test singular count returns singular."""
        assert pluralize("item", 1) == "item"

    def test_regular_plural(self):
        """Test regular plural."""
        assert pluralize("item", 2) == "items"

    def test_ends_with_s(self):
        """Test words ending with s."""
        assert pluralize("bus", 2) == "buses"

    def test_ends_with_sh(self):
        """Test words ending with sh."""
        assert pluralize("brush", 2) == "brushes"

    def test_ends_with_ch(self):
        """Test words ending with ch."""
        assert pluralize("watch", 2) == "watches"

    def test_ends_with_x(self):
        """Test words ending with x."""
        assert pluralize("box", 2) == "boxes"

    def test_ends_with_y(self):
        """Test words ending with consonant + y."""
        assert pluralize("city", 2) == "cities"

    def test_ends_with_vowel_y(self):
        """Test words ending with vowel + y."""
        assert pluralize("day", 2) == "days"

    def test_irregular(self):
        """Test irregular plurals."""
        assert pluralize("child", 2) == "children"
        assert pluralize("person", 2) == "people"

    def test_preserves_capitalization(self):
        """Test preserves first letter capitalization."""
        assert pluralize("Child", 2) == "Children"


class TestSingularize:
    """Tests for singularize function."""

    def test_already_singular(self):
        """Test already singular word."""
        assert singularize("item") == "item"

    def test_regular_plural(self):
        """Test regular plural."""
        assert singularize("items") == "item"

    def test_ends_with_ies(self):
        """Test words ending with ies."""
        assert singularize("cities") == "city"

    def test_ends_with_es(self):
        """Test words ending with es."""
        assert singularize("boxes") == "box"
        assert singularize("buses") == "bus"

    def test_irregular(self):
        """Test irregular plurals."""
        assert singularize("children") == "child"
        assert singularize("people") == "person"


class TestOrdinalize:
    """Tests for ordinalize function."""

    def test_first(self):
        """Test 1st."""
        assert ordinalize(1) == "1st"

    def test_second(self):
        """Test 2nd."""
        assert ordinalize(2) == "2nd"

    def test_third(self):
        """Test 3rd."""
        assert ordinalize(3) == "3rd"

    def test_fourth(self):
        """Test 4th."""
        assert ordinalize(4) == "4th"

    def test_eleventh(self):
        """Test 11th (special case)."""
        assert ordinalize(11) == "11th"

    def test_twelfth(self):
        """Test 12th (special case)."""
        assert ordinalize(12) == "12th"

    def test_thirteenth(self):
        """Test 13th (special case)."""
        assert ordinalize(13) == "13th"

    def test_twenty_first(self):
        """Test 21st."""
        assert ordinalize(21) == "21st"

    def test_hundred_eleventh(self):
        """Test 111th."""
        assert ordinalize(111) == "111th"


class TestHumanize:
    """Tests for humanize function."""

    def test_snake_case(self):
        """Test snake_case."""
        assert humanize("user_name") == "User name"

    def test_camel_case(self):
        """Test camelCase."""
        assert humanize("userName") == "User name"

    def test_multiple_underscores(self):
        """Test multiple underscores."""
        assert humanize("first_middle_last") == "First middle last"


class TestParameterize:
    """Tests for parameterize function."""

    def test_basic(self):
        """Test basic parameterization."""
        assert parameterize("Hello World!") == "hello-world"

    def test_custom_separator(self):
        """Test custom separator."""
        assert parameterize("Hello World", separator="_") == "hello_world"


class TestGenerateRandomString:
    """Tests for generate_random_string function."""

    def test_default_length(self):
        """Test default length."""
        result = generate_random_string()
        assert len(result) == 16

    def test_custom_length(self):
        """Test custom length."""
        result = generate_random_string(32)
        assert len(result) == 32

    def test_unique(self):
        """Test uniqueness."""
        results = {generate_random_string() for _ in range(100)}
        assert len(results) == 100

    def test_only_digits(self):
        """Test digits only."""
        result = generate_random_string(
            20,
            include_uppercase=False,
            include_lowercase=False,
            include_digits=True,
        )
        assert result.isdigit()

    def test_custom_charset(self):
        """Test custom charset."""
        result = generate_random_string(10, charset="abc")
        assert all(c in "abc" for c in result)


class TestGenerateToken:
    """Tests for generate_token function."""

    def test_default_length(self):
        """Test token generation."""
        token = generate_token()
        assert len(token) >= 32

    def test_with_prefix(self):
        """Test token with prefix."""
        token = generate_token(prefix="api_")
        assert token.startswith("api_")

    def test_url_safe(self):
        """Test URL safety."""
        token = generate_token()
        # URL-safe base64 characters
        assert all(c.isalnum() or c in "-_" for c in token)


class TestMaskString:
    """Tests for mask_string function."""

    def test_mask_end_visible(self):
        """Test masking with end visible."""
        assert mask_string("1234567890", visible_end=4) == "******7890"

    def test_mask_both_ends(self):
        """Test masking with both ends visible."""
        assert mask_string("secret", visible_start=1, visible_end=1) == "s****t"

    def test_short_string(self):
        """Test short string handling."""
        result = mask_string("hi", visible_start=1, visible_end=1)
        assert "*" in result

    def test_custom_mask_char(self):
        """Test custom mask character."""
        result = mask_string("secret", visible_end=2, mask_char="X")
        assert "X" in result


class TestExtractNumbers:
    """Tests for extract_numbers function."""

    def test_extract_integers(self):
        """Test extracting integers."""
        assert extract_numbers("I have 3 apples and 42 oranges") == ["3", "42"]

    def test_extract_decimals(self):
        """Test extracting decimals."""
        assert extract_numbers("Price: $19.99") == ["19.99"]

    def test_no_numbers(self):
        """Test with no numbers."""
        assert extract_numbers("No numbers here") == []


class TestExtractEmails:
    """Tests for extract_emails function."""

    def test_single_email(self):
        """Test extracting single email."""
        assert extract_emails("Contact: user@example.com") == ["user@example.com"]

    def test_multiple_emails(self):
        """Test extracting multiple emails."""
        text = "Contact user@a.com or admin@b.org"
        result = extract_emails(text)
        assert "user@a.com" in result
        assert "admin@b.org" in result

    def test_no_emails(self):
        """Test with no emails."""
        assert extract_emails("No email here") == []


class TestExtractUrls:
    """Tests for extract_urls function."""

    def test_https_url(self):
        """Test extracting https URL."""
        assert extract_urls("Visit https://example.com") == ["https://example.com"]

    def test_http_url(self):
        """Test extracting http URL."""
        assert extract_urls("Visit http://example.com") == ["http://example.com"]

    def test_url_with_path(self):
        """Test URL with path."""
        result = extract_urls("Go to https://example.com/page")
        assert "https://example.com/page" in result

    def test_no_urls(self):
        """Test with no URLs."""
        assert extract_urls("No URLs here") == []


class TestIsBlank:
    """Tests for is_blank function."""

    def test_none(self):
        """Test None is blank."""
        assert is_blank(None) is True

    def test_empty(self):
        """Test empty string is blank."""
        assert is_blank("") is True

    def test_whitespace(self):
        """Test whitespace is blank."""
        assert is_blank("   ") is True

    def test_not_blank(self):
        """Test non-blank string."""
        assert is_blank("hello") is False


class TestIsNotBlank:
    """Tests for is_not_blank function."""

    def test_not_blank(self):
        """Test non-blank string."""
        assert is_not_blank("hello") is True

    def test_blank(self):
        """Test blank string."""
        assert is_not_blank("") is False


class TestCoalesce:
    """Tests for coalesce function."""

    def test_first_non_blank(self):
        """Test returns first non-blank."""
        assert coalesce(None, "", "hello") == "hello"

    def test_all_blank(self):
        """Test returns default when all blank."""
        assert coalesce(None, "", "   ", default="default") == "default"

    def test_first_is_valid(self):
        """Test when first is valid."""
        assert coalesce("first", "second") == "first"


class TestSafeStr:
    """Tests for safe_str function."""

    def test_none(self):
        """Test None returns default."""
        assert safe_str(None) == ""
        assert safe_str(None, "default") == "default"

    def test_string(self):
        """Test string passthrough."""
        assert safe_str("hello") == "hello"

    def test_number(self):
        """Test number conversion."""
        assert safe_str(42) == "42"


class TestIndent:
    """Tests for indent function."""

    def test_basic_indent(self):
        """Test basic indentation."""
        result = indent("line1\nline2", 2)
        assert result == "  line1\n  line2"

    def test_skip_first_line(self):
        """Test skipping first line."""
        result = indent("line1\nline2", 2, first_line=False)
        assert result == "line1\n  line2"


class TestDedent:
    """Tests for dedent function."""

    def test_basic_dedent(self):
        """Test basic dedentation."""
        text = "    line1\n    line2"
        result = dedent(text)
        assert result == "line1\nline2"


class TestWrapText:
    """Tests for wrap_text function."""

    def test_basic_wrap(self):
        """Test basic wrapping."""
        text = "This is a long line that should be wrapped"
        result = wrap_text(text, width=20)
        lines = result.split("\n")
        assert all(len(line) <= 20 for line in lines)


class TestLevenshteinDistance:
    """Tests for levenshtein_distance function."""

    def test_identical_strings(self):
        """Test identical strings."""
        assert levenshtein_distance("hello", "hello") == 0

    def test_single_edit(self):
        """Test single character difference."""
        assert levenshtein_distance("hello", "hallo") == 1

    def test_multiple_edits(self):
        """Test multiple edits."""
        assert levenshtein_distance("kitten", "sitting") == 3

    def test_empty_string(self):
        """Test with empty string."""
        assert levenshtein_distance("hello", "") == 5
        assert levenshtein_distance("", "hello") == 5

    def test_completely_different(self):
        """Test completely different strings."""
        assert levenshtein_distance("abc", "xyz") == 3


class TestSimilarityRatio:
    """Tests for similarity_ratio function."""

    def test_identical_strings(self):
        """Test identical strings."""
        assert similarity_ratio("hello", "hello") == 1.0

    def test_similar_strings(self):
        """Test similar strings."""
        ratio = similarity_ratio("hello", "hallo")
        assert 0.7 < ratio < 0.9

    def test_different_strings(self):
        """Test very different strings."""
        ratio = similarity_ratio("abc", "xyz")
        assert ratio == 0.0

    def test_empty_strings(self):
        """Test both empty."""
        assert similarity_ratio("", "") == 1.0
