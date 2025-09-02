"""
Document management module.
"""

def get_router():
    """Lazy import of router to avoid circular dependencies."""
    from .router import router
    return router

def get_document_service():
    """Lazy import of document service."""
    from .service import document_service
    return document_service

# Export schemas directly as they don't have dependencies
from .schemas import (
    DocumentResponse,
    DocumentListResponse,
    DocumentSearchRequest,
    DocumentSearchResponse,
    FileUploadResponse,
    DocumentStatsResponse
)

__all__ = [
    "get_router",
    "get_document_service", 
    "DocumentResponse",
    "DocumentListResponse", 
    "DocumentSearchRequest",
    "DocumentSearchResponse",
    "FileUploadResponse",
    "DocumentStatsResponse"
]