"""Security headers middleware for enhanced API protection.

This middleware adds security headers to all responses to protect against
common web vulnerabilities like XSS, clickjacking, and content sniffing.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses.
    
    Security headers included:
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: Legacy XSS protection (deprecated but still useful for older browsers)
    - Referrer-Policy: Controls referrer information leakage
    - Cache-Control: Prevents caching of sensitive data
    - Strict-Transport-Security: Enforces HTTPS (production only)
    - Content-Security-Policy: Restricts resource loading
    - Permissions-Policy: Restricts browser features
    """
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Add security headers to the response."""
        response = await call_next(request)
        settings = get_settings()
        
        # Prevent MIME type sniffing attacks
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Prevent clickjacking - API shouldn't be embedded in iframes
        response.headers["X-Frame-Options"] = "DENY"
        
        # Legacy XSS protection for older browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Prevent caching of API responses containing sensitive data
        # Individual endpoints can override this if caching is desired
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        
        # HSTS - enforce HTTPS in production
        if settings.is_production:
            # 1 year max-age, include subdomains, allow preload list inclusion
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        
        # Content Security Policy - restrictive for API
        # APIs generally don't serve HTML, but if they do (like docs), this helps
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' cdn.redoc.ly",  # Allow ReDoc
            "style-src 'self' 'unsafe-inline' fonts.googleapis.com",
            "font-src 'self' fonts.gstatic.com",
            "img-src 'self' data: https:",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "base-uri 'self'",
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        
        # Permissions Policy - disable unnecessary browser features
        permissions = [
            "accelerometer=()",
            "autoplay=()",
            "camera=()",
            "cross-origin-isolated=()",
            "display-capture=()",
            "encrypted-media=()",
            "fullscreen=()",
            "geolocation=()",
            "gyroscope=()",
            "keyboard-map=()",
            "magnetometer=()",
            "microphone=()",
            "midi=()",
            "payment=()",
            "picture-in-picture=()",
            "publickey-credentials-get=()",
            "screen-wake-lock=()",
            "sync-xhr=()",
            "usb=()",
            "xr-spatial-tracking=()",
        ]
        response.headers["Permissions-Policy"] = ", ".join(permissions)
        
        return response
