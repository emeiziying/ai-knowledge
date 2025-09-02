"""Main FastAPI application with comprehensive middleware setup."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

# Import middleware
from .middleware.cors import add_cors_middleware
from .middleware.logging import LoggingMiddleware, setup_logging
from .middleware.error_handler import (
    APIError,
    api_error_handler,
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler
)
from .middleware.security import add_security_middleware, add_security_headers

# Import routers
from .routers.health import router as health_router
from .auth import get_router
from .documents import get_router as get_documents_router
from .processing.router import router as processing_router
from .ai.router import router as ai_router
from .chat.router import router as chat_router

# Import startup functions
from .startup import lifespan
from .config import get_settings

settings = get_settings()

# Setup logging first
setup_logging()
logger = logging.getLogger(__name__)


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    # Create FastAPI app
    app = FastAPI(
        title="AI Knowledge Base API",
        description="Backend API for AI Knowledge Base application with RAG capabilities",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan
    )
    
    # Add middleware (order matters!)
    add_security_middleware(app)
    add_cors_middleware(app)
    add_security_headers(app)
    app.add_middleware(LoggingMiddleware)
    
    # Add exception handlers
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    # Include routers
    app.include_router(health_router)
    auth_router = get_router()
    app.include_router(auth_router, prefix="/api/v1")
    documents_router = get_documents_router()
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(processing_router)
    app.include_router(ai_router, prefix="/api/v1")
    app.include_router(chat_router)
    
    # Root endpoint
    @app.get("/", tags=["root"])
    async def root():
        """Root endpoint with basic API information."""
        return {
            "message": "AI Knowledge Base API",
            "version": "1.0.0",
            "docs_url": "/docs" if settings.debug else None,
            "health_check": "/api/v1/health"
        }
    
    logger.info("FastAPI application created and configured")
    return app


# Create the application instance
app = create_application()