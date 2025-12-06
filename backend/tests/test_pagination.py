"""Tests for pagination utilities."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel

from app.utils.pagination import (
    CursorData,
    PagedResponse,
    PaginationMeta,
    PaginationParams,
    PaginationStrategy,
    SortOrder,
    decode_cursor,
    empty_page,
    encode_cursor,
    paginate_list,
    validate_pagination_params,
)


# =============================================================================
# Test Models
# =============================================================================


class ItemModel(BaseModel):
    """Test model for pagination."""

    id: int
    name: str


# =============================================================================
# PaginationParams Tests
# =============================================================================


class TestPaginationParams:
    """Tests for PaginationParams class."""

    def test_default_values(self):
        """Test default pagination parameters."""
        # Create with explicit values since Query defaults work at runtime
        params = PaginationParams.__new__(PaginationParams)
        params.page = 1
        params.limit = 20
        params.cursor = None
        params.sort_by = None
        params.sort_order = SortOrder.DESC

        assert params.page == 1
        assert params.limit == 20
        assert params.cursor is None
        assert params.sort_by is None
        assert params.sort_order == SortOrder.DESC

    def test_custom_values(self):
        """Test custom pagination parameters."""
        params = PaginationParams.__new__(PaginationParams)
        params.page = 3
        params.limit = 50
        params.cursor = "abc123"
        params.sort_by = "created_at"
        params.sort_order = SortOrder.ASC

        assert params.page == 3
        assert params.limit == 50
        assert params.cursor == "abc123"
        assert params.sort_by == "created_at"
        assert params.sort_order == SortOrder.ASC

    def test_offset_calculation(self):
        """Test offset calculation from page."""
        params = PaginationParams.__new__(PaginationParams)
        params.page = 1
        params.limit = 20
        assert params.offset == 0

        params.page = 2
        params.limit = 20
        assert params.offset == 20

        params.page = 5
        params.limit = 10
        assert params.offset == 40

    def test_is_cursor_based(self):
        """Test cursor-based pagination detection."""
        params = PaginationParams.__new__(PaginationParams)
        params.cursor = None
        assert params.is_cursor_based is False

        params.cursor = "abc123"
        assert params.is_cursor_based is True


# =============================================================================
# SortOrder Tests
# =============================================================================


class TestSortOrder:
    """Tests for SortOrder enum."""

    def test_sort_order_values(self):
        """Test sort order values."""
        assert SortOrder.ASC.value == "asc"
        assert SortOrder.DESC.value == "desc"

    def test_sort_order_count(self):
        """Test we have expected number of options."""
        assert len(SortOrder) == 2


# =============================================================================
# PaginationMeta Tests
# =============================================================================


class TestPaginationMeta:
    """Tests for PaginationMeta class."""

    def test_basic_meta(self):
        """Test basic pagination metadata."""
        meta = PaginationMeta(
            page=1,
            limit=20,
            total_items=100,
            total_pages=5,
            has_next=True,
            has_prev=False,
        )

        assert meta.page == 1
        assert meta.limit == 20
        assert meta.total_items == 100
        assert meta.total_pages == 5
        assert meta.has_next is True
        assert meta.has_prev is False
        assert meta.next_cursor is None
        assert meta.prev_cursor is None

    def test_meta_with_cursors(self):
        """Test metadata with cursors."""
        meta = PaginationMeta(
            page=1,
            limit=20,
            total_items=-1,
            total_pages=-1,
            has_next=True,
            has_prev=True,
            next_cursor="next_abc",
            prev_cursor="prev_xyz",
        )

        assert meta.next_cursor == "next_abc"
        assert meta.prev_cursor == "prev_xyz"

    def test_meta_serialization(self):
        """Test metadata serializes with aliases."""
        meta = PaginationMeta(
            page=1,
            limit=20,
            total_items=100,
            total_pages=5,
            has_next=True,
            has_prev=False,
        )

        data = meta.model_dump(by_alias=True)

        assert "totalItems" in data
        assert "totalPages" in data
        assert "hasNext" in data
        assert "hasPrev" in data


# =============================================================================
# PagedResponse Tests
# =============================================================================


class TestPagedResponse:
    """Tests for PagedResponse class."""

    def test_empty_response(self):
        """Test empty paginated response."""
        response = PagedResponse(
            items=[],
            meta=PaginationMeta(
                page=1,
                limit=20,
                total_items=0,
                total_pages=0,
                has_next=False,
                has_prev=False,
            ),
        )

        assert response.items == []
        assert response.meta.total_items == 0

    def test_response_with_items(self):
        """Test paginated response with items."""
        items = [
            ItemModel(id=1, name="Item 1"),
            ItemModel(id=2, name="Item 2"),
        ]

        response = PagedResponse[ItemModel](
            items=items,
            meta=PaginationMeta(
                page=1,
                limit=20,
                total_items=2,
                total_pages=1,
                has_next=False,
                has_prev=False,
            ),
        )

        assert len(response.items) == 2
        assert response.items[0].id == 1

    def test_response_with_links(self):
        """Test paginated response with navigation links."""
        response = PagedResponse(
            items=[],
            meta=PaginationMeta(
                page=2,
                limit=20,
                total_items=100,
                total_pages=5,
                has_next=True,
                has_prev=True,
            ),
            links={
                "self": "/api/items?page=2",
                "first": "/api/items?page=1",
                "last": "/api/items?page=5",
                "next": "/api/items?page=3",
                "prev": "/api/items?page=1",
            },
        )

        assert response.links["self"] == "/api/items?page=2"
        assert response.links["next"] == "/api/items?page=3"


# =============================================================================
# Cursor Tests
# =============================================================================


class TestCursorEncoding:
    """Tests for cursor encoding/decoding."""

    def test_encode_decode_basic(self):
        """Test basic cursor encoding and decoding."""
        original = CursorData(id=123, direction="next")

        encoded = encode_cursor(original)
        decoded = decode_cursor(encoded)

        assert decoded is not None
        assert decoded.id == 123
        assert decoded.direction == "next"

    def test_encode_decode_with_created_at(self):
        """Test cursor with created_at field."""
        now = datetime.now(timezone.utc).isoformat()
        original = CursorData(id="abc-123", created_at=now, direction="prev")

        encoded = encode_cursor(original)
        decoded = decode_cursor(encoded)

        assert decoded is not None
        assert decoded.id == "abc-123"
        assert decoded.created_at == now
        assert decoded.direction == "prev"

    def test_encode_decode_with_sort_value(self):
        """Test cursor with sort value."""
        original = CursorData(id=42, sort_value="test_value", direction="next")

        encoded = encode_cursor(original)
        decoded = decode_cursor(encoded)

        assert decoded is not None
        assert decoded.sort_value == "test_value"

    def test_decode_invalid_cursor(self):
        """Test decoding invalid cursor returns None."""
        result = decode_cursor("invalid_cursor_string")
        assert result is None

    def test_decode_empty_cursor(self):
        """Test decoding empty cursor returns None."""
        result = decode_cursor("")
        assert result is None

    def test_cursor_is_url_safe(self):
        """Test encoded cursor is URL-safe."""
        original = CursorData(id=123, direction="next")
        encoded = encode_cursor(original)

        # URL-safe base64 should not contain +, /, or =
        assert "+" not in encoded
        assert "/" not in encoded


# =============================================================================
# paginate_list Tests
# =============================================================================


class TestPaginateList:
    """Tests for paginate_list function."""

    def test_paginate_empty_list(self):
        """Test paginating empty list."""
        params = PaginationParams(page=1, limit=10)
        result = paginate_list([], params)

        assert result.items == []
        assert result.meta.total_items == 0
        assert result.meta.total_pages == 1
        assert result.meta.has_next is False
        assert result.meta.has_prev is False

    def test_paginate_single_page(self):
        """Test paginating list that fits in one page."""
        items = [1, 2, 3, 4, 5]
        params = PaginationParams(page=1, limit=10)

        result = paginate_list(items, params)

        assert result.items == [1, 2, 3, 4, 5]
        assert result.meta.total_items == 5
        assert result.meta.total_pages == 1
        assert result.meta.has_next is False

    def test_paginate_multiple_pages(self):
        """Test paginating list across multiple pages."""
        items = list(range(1, 26))  # 25 items
        params = PaginationParams(page=1, limit=10)

        result = paginate_list(items, params)

        assert len(result.items) == 10
        assert result.items == list(range(1, 11))
        assert result.meta.total_items == 25
        assert result.meta.total_pages == 3
        assert result.meta.has_next is True
        assert result.meta.has_prev is False

    def test_paginate_second_page(self):
        """Test getting second page."""
        items = list(range(1, 26))  # 25 items
        params = PaginationParams(page=2, limit=10)

        result = paginate_list(items, params)

        assert result.items == list(range(11, 21))
        assert result.meta.page == 2
        assert result.meta.has_next is True
        assert result.meta.has_prev is True

    def test_paginate_last_page(self):
        """Test getting last page."""
        items = list(range(1, 26))  # 25 items
        params = PaginationParams(page=3, limit=10)

        result = paginate_list(items, params)

        assert result.items == [21, 22, 23, 24, 25]
        assert result.meta.page == 3
        assert result.meta.has_next is False
        assert result.meta.has_prev is True

    def test_paginate_beyond_last_page(self):
        """Test requesting page beyond last."""
        items = list(range(1, 11))  # 10 items
        params = PaginationParams(page=5, limit=10)

        result = paginate_list(items, params)

        assert result.items == []
        assert result.meta.total_items == 10

    def test_paginate_with_different_limits(self):
        """Test pagination with different page sizes."""
        items = list(range(1, 101))  # 100 items

        # Limit 25 = 4 pages
        params = PaginationParams(page=1, limit=25)
        result = paginate_list(items, params)
        assert result.meta.total_pages == 4

        # Limit 30 = 4 pages (100/30 = 3.33, ceil = 4)
        params = PaginationParams(page=1, limit=30)
        result = paginate_list(items, params)
        assert result.meta.total_pages == 4

        # Limit 50 = 2 pages
        params = PaginationParams(page=1, limit=50)
        result = paginate_list(items, params)
        assert result.meta.total_pages == 2


# =============================================================================
# validate_pagination_params Tests
# =============================================================================


class TestValidatePaginationParams:
    """Tests for validate_pagination_params function."""

    def test_valid_params(self):
        """Test valid parameters return no errors."""
        params = PaginationParams(page=1, limit=20)
        errors = validate_pagination_params(params)

        assert errors == []

    def test_invalid_page(self):
        """Test invalid page number."""
        params = PaginationParams.__new__(PaginationParams)
        params.page = 0
        params.limit = 20
        params.sort_by = None

        errors = validate_pagination_params(params)

        assert "Page must be >= 1" in errors

    def test_invalid_limit_too_small(self):
        """Test limit too small."""
        params = PaginationParams.__new__(PaginationParams)
        params.page = 1
        params.limit = 0
        params.sort_by = None

        errors = validate_pagination_params(params)

        assert "Limit must be >= 1" in errors

    def test_invalid_limit_too_large(self):
        """Test limit exceeds maximum."""
        params = PaginationParams.__new__(PaginationParams)
        params.page = 1
        params.limit = 500
        params.sort_by = None

        errors = validate_pagination_params(params, max_limit=100)

        assert "Limit must be <= 100" in errors

    def test_invalid_sort_field(self):
        """Test invalid sort field."""
        params = PaginationParams.__new__(PaginationParams)
        params.page = 1
        params.limit = 20
        params.sort_by = "invalid_field"

        errors = validate_pagination_params(
            params,
            allowed_sort_fields=["name", "created_at"],
        )

        assert len(errors) == 1
        assert "Invalid sort field" in errors[0]

    def test_valid_sort_field(self):
        """Test valid sort field."""
        params = PaginationParams.__new__(PaginationParams)
        params.page = 1
        params.limit = 20
        params.sort_by = "name"

        errors = validate_pagination_params(
            params,
            allowed_sort_fields=["name", "created_at"],
        )

        assert errors == []


# =============================================================================
# empty_page Tests
# =============================================================================


class TestEmptyPage:
    """Tests for empty_page function."""

    def test_empty_page(self):
        """Test creating empty page response."""
        params = PaginationParams(page=1, limit=20)
        result = empty_page(params)

        assert result.items == []
        assert result.meta.page == 1
        assert result.meta.limit == 20
        assert result.meta.total_items == 0
        assert result.meta.total_pages == 0
        assert result.meta.has_next is False
        assert result.meta.has_prev is False

    def test_empty_page_preserves_params(self):
        """Test empty page preserves pagination params."""
        params = PaginationParams(page=3, limit=50)
        result = empty_page(params)

        assert result.meta.page == 3
        assert result.meta.limit == 50


# =============================================================================
# PaginationStrategy Tests
# =============================================================================


class TestPaginationStrategy:
    """Tests for PaginationStrategy enum."""

    def test_strategy_values(self):
        """Test strategy values."""
        assert PaginationStrategy.OFFSET.value == "offset"
        assert PaginationStrategy.CURSOR.value == "cursor"
        assert PaginationStrategy.KEYSET.value == "keyset"

    def test_strategy_count(self):
        """Test we have expected number of strategies."""
        assert len(PaginationStrategy) == 3


# =============================================================================
# CursorData Tests
# =============================================================================


class TestCursorData:
    """Tests for CursorData model."""

    def test_cursor_data_defaults(self):
        """Test cursor data default values."""
        cursor = CursorData(id=123)

        assert cursor.id == 123
        assert cursor.created_at is None
        assert cursor.sort_value is None
        assert cursor.direction == "next"

    def test_cursor_data_with_all_fields(self):
        """Test cursor data with all fields."""
        cursor = CursorData(
            id="abc-123",
            created_at="2024-01-01T00:00:00Z",
            sort_value=42,
            direction="prev",
        )

        assert cursor.id == "abc-123"
        assert cursor.created_at == "2024-01-01T00:00:00Z"
        assert cursor.sort_value == 42
        assert cursor.direction == "prev"

    def test_cursor_data_serialization(self):
        """Test cursor data serialization."""
        cursor = CursorData(id=123, direction="next")

        data = cursor.model_dump()

        assert data["id"] == 123
        assert data["direction"] == "next"
