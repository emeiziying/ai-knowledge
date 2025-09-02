"""Security middleware for headers and basic protection."""

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware
from ..config import get_settings

settings = get_settings()


def add_security_middleware(app: FastAPI) -> None:
    """Add security-related middleware to the FastAPI application."""
    
    # Add session middleware for CSRF protection
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        same_site="lax",
        https_only=False,  # Set to True in production with HTTPS
    )
    
    # Add trusted host middleware (skip in testing environment)
    if settings.environment != "testing":
        allowed_hosts = [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
        ]
        
        # Add production hosts if configured
        if hasattr(settings, 'allowed_hosts') and settings.allowed_hosts:
            allowed_hosts.extend(settings.allowed_hosts)
        
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=allowed_hosts
        )


def add_security_headers(app: FastAPI) -> None:
    """Add security headers to responses."""
    
    @app.middleware("http")
    async def add_security_headers_middleware(request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Content Security Policy (basic)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss:;"
        )
        
        return response