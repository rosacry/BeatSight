"""API versioning utilities.

Provides utilities for versioning API endpoints and managing
deprecation of older API versions.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from functools import wraps
from typing import Callable, Optional, TypeVar

from fastapi import Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable)


class APIVersion(str, Enum):
    """Supported API versions."""
    
    V1 = "v1"
    V2 = "v2"  # Future version
    
    @classmethod
    def current(cls) -> "APIVersion":
        """Get the current/latest API version."""
        return cls.V1
    
    @classmethod
    def supported(cls) -> list["APIVersion"]:
        """Get list of supported versions."""
        return [cls.V1]  # Add V2 when ready


# Deprecation information for endpoints
DEPRECATED_ENDPOINTS: dict[str, dict] = {
    # Example:
    # "/api/v1/old-endpoint": {
    #     "deprecated_date": date(2025, 1, 1),
    #     "sunset_date": date(2025, 6, 1),
    #     "replacement": "/api/v2/new-endpoint",
    #     "message": "This endpoint is deprecated. Please use the new endpoint.",
    # },
}


def get_api_version(
    accept_version: Optional[str] = Header(None, alias="Accept-Version"),
    x_api_version: Optional[str] = Header(None, alias="X-API-Version"),
) -> APIVersion:
    """Extract API version from request headers.
    
    Supports both Accept-Version and X-API-Version headers.
    Defaults to current version if not specified.
    """
    version_str = accept_version or x_api_version
    
    if not version_str:
        return APIVersion.current()
    
    try:
        return APIVersion(version_str.lower())
    except ValueError:
        # Unknown version, use current
        logger.warning(
            "unknown_api_version_requested",
            requested_version=version_str,
        )
        return APIVersion.current()


def deprecated(
    sunset_date: date,
    replacement: Optional[str] = None,
    message: Optional[str] = None,
) -> Callable[[F], F]:
    """Mark an endpoint as deprecated.
    
    Adds deprecation headers to the response and logs usage.
    
    Args:
        sunset_date: Date when the endpoint will be removed
        replacement: URL of the replacement endpoint
        message: Custom deprecation message
    
    Example:
        @router.get("/old-endpoint")
        @deprecated(
            sunset_date=date(2025, 6, 1),
            replacement="/api/v2/new-endpoint",
        )
        async def old_endpoint():
            ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get request from kwargs or args
            request = kwargs.get("request")
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            # Log deprecation usage
            logger.warning(
                "deprecated_endpoint_called",
                endpoint=func.__name__,
                sunset_date=sunset_date.isoformat(),
                replacement=replacement,
            )
            
            # Call the original function
            result = await func(*args, **kwargs)
            
            # If result is a Response, add headers
            if isinstance(result, JSONResponse):
                result.headers["Deprecation"] = sunset_date.isoformat()
                if replacement:
                    result.headers["Link"] = f'<{replacement}>; rel="successor-version"'
                if message:
                    result.headers["X-Deprecation-Notice"] = message
                return result
            
            # For dict/model responses, wrap in JSONResponse with headers
            from fastapi.encoders import jsonable_encoder
            response = JSONResponse(content=jsonable_encoder(result))
            response.headers["Deprecation"] = sunset_date.isoformat()
            if replacement:
                response.headers["Link"] = f'<{replacement}>; rel="successor-version"'
            default_message = f"This endpoint is deprecated and will be removed on {sunset_date}."
            response.headers["X-Deprecation-Notice"] = message or default_message
            
            return response
        
        return wrapper  # type: ignore
    
    return decorator


def require_version(min_version: APIVersion) -> Callable[[F], F]:
    """Require a minimum API version for an endpoint.
    
    Args:
        min_version: Minimum required API version
        
    Raises:
        HTTPException: If requested version is below minimum
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get version from kwargs (injected by Depends)
            version = kwargs.get("api_version", APIVersion.current())
            
            if list(APIVersion).index(version) < list(APIVersion).index(min_version):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"This endpoint requires API version {min_version.value} or higher",
                )
            
            return await func(*args, **kwargs)
        
        return wrapper  # type: ignore
    
    return decorator


def add_version_headers(response: JSONResponse, version: APIVersion) -> JSONResponse:
    """Add API version headers to a response.
    
    Args:
        response: The response to modify
        version: The API version used
        
    Returns:
        Response with version headers added
    """
    response.headers["X-API-Version"] = version.value
    response.headers["X-API-Version-Current"] = APIVersion.current().value
    return response
