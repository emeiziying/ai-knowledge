"""
API router for document processing endpoints.
"""
import logging
from typing import Dict, Any, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth.dependencies import get_current_user
from ..models import User
from .integration import processing_integration
from .parsers import DocumentParserFactory
from . import get_supported_formats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/processing", tags=["processing"])


@router.get("/formats")
async def get_supported_document_formats() -> Dict[str, Any]:
    """
    Get list of supported document formats.
    
    Returns:
        Dictionary of supported formats with MIME types and extensions
    """
    try:
        formats = get_supported_formats()
        return {
            "supported_formats": formats,
            "total_formats": len(formats)
        }
    except Exception as e:
        logger.error(f"Failed to get supported formats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve supported formats")


@router.post("/parse")
async def parse_document_content(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Parse document content without storing it.
    Useful for testing or preview purposes.
    
    Args:
        file: Document file to parse
        current_user: Current authenticated user
        
    Returns:
        Parsed document content and metadata
    """
    try:
        # Read file content
        file_content = await file.read()
        
        # Get parser
        factory = DocumentParserFactory()
        parser = factory.get_parser(file.content_type, file.filename)
        
        if not parser:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file format: {file.content_type}"
            )
        
        # Parse document
        result = parser.parse(file_content, file.filename)
        
        # Add processing info
        result["processing_info"] = {
            "parser_type": type(parser).__name__,
            "file_size": len(file_content),
            "filename": file.filename,
            "mime_type": file.content_type
        }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to parse document {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse document: {str(e)}")


@router.post("/documents/{document_id}/process")
async def process_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Process an uploaded document.
    
    Args:
        document_id: ID of the document to process
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Processing result
    """
    try:
        result = await processing_integration.process_uploaded_document(
            db, document_id, current_user.id
        )
        return result
        
    except Exception as e:
        logger.error(f"Failed to process document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")


@router.post("/documents/{document_id}/reprocess")
async def reprocess_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Reprocess an existing document.
    
    Args:
        document_id: ID of the document to reprocess
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Processing result
    """
    try:
        result = await processing_integration.reprocess_document(
            db, document_id, current_user.id
        )
        return result
        
    except Exception as e:
        logger.error(f"Failed to reprocess document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reprocess document: {str(e)}")


@router.get("/documents/{document_id}/status")
async def get_processing_status(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get processing status for a document.
    
    Args:
        document_id: ID of the document
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Processing status information
    """
    try:
        status = processing_integration.get_processing_status(
            db, document_id, current_user.id
        )
        
        if "error" in status:
            raise HTTPException(status_code=404, detail=status["error"])
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get processing status for {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get processing status: {str(e)}")


@router.get("/documents/{document_id}/chunks")
async def get_document_chunks(
    document_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of chunks per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get processed chunks for a document.
    
    Args:
        document_id: ID of the document
        page: Page number (1-based)
        page_size: Number of chunks per page
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Document chunks with pagination info
    """
    try:
        chunks = processing_integration.get_document_chunks(
            db, document_id, current_user.id, page, page_size
        )
        
        if "error" in chunks:
            raise HTTPException(status_code=404, detail=chunks["error"])
        
        return chunks
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document chunks for {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get document chunks: {str(e)}")


@router.get("/health")
async def processing_health_check() -> Dict[str, Any]:
    """
    Health check for processing service.
    
    Returns:
        Health status information
    """
    try:
        # Test parser factory
        factory = DocumentParserFactory()
        parser_count = len(factory.parsers)
        
        # Test supported formats
        formats = get_supported_formats()
        
        return {
            "status": "healthy",
            "parsers_available": parser_count,
            "supported_formats": len(formats),
            "service": "document_processing"
        }
        
    except Exception as e:
        logger.error(f"Processing health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "service": "document_processing"
        }