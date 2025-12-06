"""Pagination utilities for API endpoints.

Provides standardized pagination with multiple strategies:
- Offset-based pagination (traditional page/limit)
- Cursor-based pagination (for large datasets)
- Keyset pagination (efficient for sorted data)

Usage:
    from app.utils.pagination import (
        PaginationParams,
        paginate_query,
        PagedResponse,
    )

    # In FastAPI endpoint
    @router.get("/songs")
    async def list_songs(
        pagination: PaginationParams = Depends(),
        db: AsyncSession = Depends(get_db),
    ) -> PagedResponse[SongResponse]:
        return await paginate_query(
            db,
            select(Song).order_by(Song.created_at.desc()),
            pagination,
            response_model=SongResponse,
        )
"""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, Sequence, TypeVar
from urllib.parse import urlencode

from fastapi import Query, Request
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")
ModelT = TypeVar("ModelT", bound=BaseModel)


class SortOrder(str, Enum):
    """Sort order for pagination."""

    ASC = "asc"
    DESC = "desc"


class PaginationStrategy(str, Enum):
    """Pagination strategies."""

    OFFSET = "offset"  # Traditional page/limit
    CURSOR = "cursor"  # For infinite scroll / large datasets
    KEYSET = "keyset"  # Efficient for sorted data


@dataclass
class PaginationParams:
    """Pagination parameters from query string.

    Use as a FastAPI dependency:
        @router.get("/items")
        async def list_items(pagination: PaginationParams = Depends()):
            ...
    """

    page: int = 1
    limit: int = 20
    cursor: str | None = None
    sort_by: str | None = None
    sort_order: SortOrder = SortOrder.DESC

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(20, ge=1, le=100, description="Items per page"),
        cursor: str | None = Query(
            None, description="Cursor for cursor-based pagination"
        ),
        sort_by: str | None = Query(None, description="Field to sort by"),
        sort_order: SortOrder = Query(SortOrder.DESC, description="Sort order"),
    ):
        self.page = page
        self.limit = limit
        self.cursor = cursor
        self.sort_by = sort_by
        self.sort_order = sort_order

    @property
    def offset(self) -> int:
        """Calculate offset from page number."""
        return (self.page - 1) * self.limit

    @property
    def is_cursor_based(self) -> bool:
        """Check if using cursor-based pagination."""
        return self.cursor is not None


class PaginationMeta(BaseModel):
    """Metadata about pagination results."""

    model_config = ConfigDict(populate_by_name=True)

    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")
    total_items: int = Field(
        ..., alias="totalItems", description="Total number of items"
    )
    total_pages: int = Field(
        ..., alias="totalPages", description="Total number of pages"
    )
    has_next: bool = Field(
        ..., alias="hasNext", description="Whether there's a next page"
    )
    has_prev: bool = Field(
        ..., alias="hasPrev", description="Whether there's a previous page"
    )
    next_cursor: str | None = Field(
        None, alias="nextCursor", description="Cursor for next page"
    )
    prev_cursor: str | None = Field(
        None, alias="prevCursor", description="Cursor for previous page"
    )


class PagedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[T] = Field(..., description="List of items")
    meta: PaginationMeta = Field(..., description="Pagination metadata")
    links: dict[str, str | None] = Field(
        default_factory=dict,
        description="Navigation links (self, first, last, next, prev)",
    )


class CursorData(BaseModel):
    """Data encoded in a pagination cursor."""

    id: str | int
    created_at: str | None = None
    sort_value: Any = None
    direction: str = "next"  # "next" or "prev"


# =============================================================================
# Cursor encoding/decoding
# =============================================================================


def encode_cursor(data: CursorData) -> str:
    """Encode cursor data to a base64 string.

    Args:
        data: Cursor data to encode

    Returns:
        Base64-encoded cursor string
    """
    json_str = data.model_dump_json()
    return base64.urlsafe_b64encode(json_str.encode()).decode()


def decode_cursor(cursor: str) -> CursorData | None:
    """Decode a cursor string to cursor data.

    Args:
        cursor: Base64-encoded cursor string

    Returns:
        Decoded cursor data or None if invalid
    """
    try:
        json_str = base64.urlsafe_b64decode(cursor.encode()).decode()
        return CursorData.model_validate_json(json_str)
    except Exception:
        return None


# =============================================================================
# Query pagination helpers
# =============================================================================


async def count_query(
    db: AsyncSession,
    query: Select,
) -> int:
    """Count total items for a query.

    Args:
        db: Database session
        query: SQLAlchemy select query

    Returns:
        Total count of items
    """
    # Create count query
    count_q = select(func.count()).select_from(query.subquery())
    result = await db.execute(count_q)
    return result.scalar() or 0


async def paginate_query(
    db: AsyncSession,
    query: Select,
    params: PaginationParams,
    response_model: type[ModelT] | None = None,
    request: Request | None = None,
) -> PagedResponse[ModelT]:
    """Paginate a SQLAlchemy query with offset-based pagination.

    Args:
        db: Database session
        query: SQLAlchemy select query
        params: Pagination parameters
        response_model: Pydantic model to serialize results
        request: FastAPI request for generating links

    Returns:
        Paginated response with items and metadata
    """
    # Get total count
    total_items = await count_query(db, query)
    total_pages = max(1, math.ceil(total_items / params.limit))

    # Apply pagination
    paginated_query = query.offset(params.offset).limit(params.limit)
    result = await db.execute(paginated_query)
    rows = result.scalars().all()

    # Convert to response model if provided
    if response_model:
        items = [
            response_model.model_validate(row, from_attributes=True) for row in rows
        ]
    else:
        items = list(rows)

    # Build metadata
    meta = PaginationMeta(
        page=params.page,
        limit=params.limit,
        total_items=total_items,
        total_pages=total_pages,
        has_next=params.page < total_pages,
        has_prev=params.page > 1,
    )

    # Build links
    links = _build_pagination_links(request, params, total_pages)

    return PagedResponse(items=items, meta=meta, links=links)


async def paginate_query_cursor(
    db: AsyncSession,
    query: Select,
    params: PaginationParams,
    id_column: Any,
    sort_column: Any | None = None,
    response_model: type[ModelT] | None = None,
) -> PagedResponse[ModelT]:
    """Paginate a query using cursor-based pagination.

    More efficient for large datasets and infinite scroll.

    Args:
        db: Database session
        query: Base SQLAlchemy select query
        params: Pagination parameters
        id_column: Column to use as cursor ID
        sort_column: Column being sorted (for keyset pagination)
        response_model: Pydantic model to serialize results

    Returns:
        Paginated response with cursor-based navigation
    """
    # Decode cursor if provided
    cursor_data = None
    if params.cursor:
        cursor_data = decode_cursor(params.cursor)

    # Apply cursor filter
    if cursor_data:
        if cursor_data.direction == "next":
            if params.sort_order == SortOrder.DESC:
                query = query.where(id_column < cursor_data.id)
            else:
                query = query.where(id_column > cursor_data.id)
        else:  # prev
            if params.sort_order == SortOrder.DESC:
                query = query.where(id_column > cursor_data.id)
            else:
                query = query.where(id_column < cursor_data.id)

    # Fetch one extra to determine if there's a next page
    paginated_query = query.limit(params.limit + 1)
    result = await db.execute(paginated_query)
    rows = list(result.scalars().all())

    # Check if there's more
    has_next = len(rows) > params.limit
    if has_next:
        rows = rows[: params.limit]

    # Convert to response model
    if response_model:
        items = [
            response_model.model_validate(row, from_attributes=True) for row in rows
        ]
    else:
        items = list(rows)

    # Build cursors
    next_cursor = None
    prev_cursor = None

    if items:
        last_item = rows[-1]
        first_item = rows[0]

        if has_next:
            next_cursor = encode_cursor(
                CursorData(
                    id=getattr(last_item, "id"),
                    direction="next",
                )
            )

        if cursor_data:
            prev_cursor = encode_cursor(
                CursorData(
                    id=getattr(first_item, "id"),
                    direction="prev",
                )
            )

    # For cursor-based, we don't know total without expensive count
    meta = PaginationMeta(
        page=1,  # Not meaningful for cursor-based
        limit=params.limit,
        total_items=-1,  # Unknown
        total_pages=-1,  # Unknown
        has_next=has_next,
        has_prev=cursor_data is not None,
        next_cursor=next_cursor,
        prev_cursor=prev_cursor,
    )

    return PagedResponse(items=items, meta=meta, links={})


def _build_pagination_links(
    request: Request | None,
    params: PaginationParams,
    total_pages: int,
) -> dict[str, str | None]:
    """Build pagination navigation links.

    Args:
        request: FastAPI request
        params: Pagination parameters
        total_pages: Total number of pages

    Returns:
        Dictionary of navigation links
    """
    if not request:
        return {}

    base_url = str(request.url).split("?")[0]

    def build_url(page: int) -> str:
        query_params = {
            "page": page,
            "limit": params.limit,
        }
        if params.sort_by:
            query_params["sort_by"] = params.sort_by
            query_params["sort_order"] = params.sort_order.value
        return f"{base_url}?{urlencode(query_params)}"

    links = {
        "self": build_url(params.page),
        "first": build_url(1),
        "last": build_url(total_pages) if total_pages > 0 else None,
        "next": build_url(params.page + 1) if params.page < total_pages else None,
        "prev": build_url(params.page - 1) if params.page > 1 else None,
    }

    return links


# =============================================================================
# In-memory pagination helpers
# =============================================================================


def paginate_list(
    items: Sequence[T],
    params: PaginationParams,
) -> PagedResponse[T]:
    """Paginate an in-memory list.

    Args:
        items: List of items to paginate
        params: Pagination parameters

    Returns:
        Paginated response
    """
    total_items = len(items)
    total_pages = max(1, math.ceil(total_items / params.limit))

    # Slice items
    start = params.offset
    end = start + params.limit
    page_items = list(items[start:end])

    meta = PaginationMeta(
        page=params.page,
        limit=params.limit,
        total_items=total_items,
        total_pages=total_pages,
        has_next=params.page < total_pages,
        has_prev=params.page > 1,
    )

    return PagedResponse(items=page_items, meta=meta, links={})


# =============================================================================
# Pagination validation
# =============================================================================


def validate_pagination_params(
    params: PaginationParams,
    allowed_sort_fields: list[str] | None = None,
    max_limit: int = 100,
) -> list[str]:
    """Validate pagination parameters.

    Args:
        params: Pagination parameters
        allowed_sort_fields: List of allowed sort field names
        max_limit: Maximum allowed limit

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if params.page < 1:
        errors.append("Page must be >= 1")

    if params.limit < 1:
        errors.append("Limit must be >= 1")
    elif params.limit > max_limit:
        errors.append(f"Limit must be <= {max_limit}")

    if params.sort_by and allowed_sort_fields:
        if params.sort_by not in allowed_sort_fields:
            errors.append(
                f"Invalid sort field. Allowed: {', '.join(allowed_sort_fields)}"
            )

    return errors


# =============================================================================
# Response helpers
# =============================================================================


def empty_page(params: PaginationParams) -> PagedResponse:
    """Create an empty paginated response.

    Args:
        params: Pagination parameters

    Returns:
        Empty paginated response
    """
    return PagedResponse(
        items=[],
        meta=PaginationMeta(
            page=params.page,
            limit=params.limit,
            total_items=0,
            total_pages=0,
            has_next=False,
            has_prev=False,
        ),
        links={},
    )
