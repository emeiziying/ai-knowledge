"""
Document management API router.
"""
import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth.dependencies import get_current_user
from ..models import User
from .service import document_service
from .schemas import (
    DocumentResponse, 
    DocumentListResponse, 
    DocumentSearchRequest,
    DocumentSearchResponse,
    FileUploadResponse,
    DocumentStatsResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a new document.
    
    - **file**: Document file to upload (PDF, DOCX, DOC, TXT, MD)
    - Maximum file size: 50MB
    - Supported formats: PDF, Word documents, plain text, Markdown
    """
    try:
        document = await document_service.upload_document(db, file, current_user.id)
        
        return FileUploadResponse(
            document_id=document.id,
            message="Document uploaded successfully",
            status="uploaded"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during document upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during upload"
        )


@router.get("", response_model=DocumentListResponse)
def get_documents(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of documents per page"),
    status_filter: Optional[str] = Query(None, pattern="^(processing|completed|failed|uploaded)$", description="Filter by status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get paginated list of user's documents.
    
    - **page**: Page number (starting from 1)
    - **page_size**: Number of documents per page (1-100)
    - **status_filter**: Optional filter by document status
    """
    try:
        return document_service.get_documents(
            db=db,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            status_filter=status_filter
        )
    except Exception as e:
        logger.error(f"Error retrieving documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents"
        )


@router.get("/search", response_model=DocumentListResponse)
def search_documents(
    query: str = Query(..., min_length=1, max_length=500, description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of documents per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search documents by filename or content.
    
    - **query**: Search query string
    - **page**: Page number (starting from 1)
    - **page_size**: Number of documents per page (1-100)
    """
    try:
        return document_service.search_documents(
            db=db,
            user_id=current_user.id,
            query=query,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search documents"
        )


@router.get("/stats", response_model=DocumentStatsResponse)
def get_document_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get document statistics for the current user.
    
    Returns counts by status, total size, and recent uploads.
    """
    try:
        stats = document_service.get_document_stats(db, current_user.id)
        return DocumentStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Error retrieving document stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document statistics"
        )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get details of a specific document.
    
    - **document_id**: UUID of the document
    """
    document = document_service.get_document(db, document_id, current_user.id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return document


@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download the original document file.
    
    - **document_id**: UUID of the document
    """
    # Get document info
    document = document_service.get_document(db, document_id, current_user.id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Get file content
    try:
        content = await document_service.get_document_content(db, document_id, current_user.id)
        
        if content is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document file not found in storage"
            )
        
        # Create streaming response
        def generate():
            yield content
        
        return StreamingResponse(
            generate(),
            media_type=document.mime_type,
            headers={
                "Content-Disposition": f"attachment; filename=\"{document.original_name}\"",
                "Content-Length": str(len(content))
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download document"
        )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a document and its associated files.
    
    - **document_id**: UUID of the document to delete
    """
    success = await document_service.delete_document(db, document_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )


@router.patch("/{document_id}/status")
async def update_document_status(
    document_id: UUID,
    status: str = Query(..., pattern="^(processing|completed|failed|uploaded)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update document processing status.
    
    - **document_id**: UUID of the document
    - **status**: New status (processing, completed, failed, uploaded)
    """
    success = await document_service.update_document_status(
        db, document_id, status, current_user.id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return {"message": "Document status updated successfully"}


# Health check endpoint for document service
@router.get("/health/check")
async def document_service_health():
    """
    Health check endpoint for document service.
    """
    try:
        # Test storage connection
        from ..storage import storage
        
        # Simple connectivity test
        files = await storage.list_files(prefix="health-check-")
        
        return {
            "status": "healthy",
            "service": "document_management",
            "storage_connected": True,
            "timestamp": "2024-01-01T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"Document service health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document service is unhealthy"
        )