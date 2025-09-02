"""
Document management service layer.
"""
import logging
import io
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from fastapi import UploadFile, HTTPException

from ..models import Document, User
from ..storage import storage
from .schemas import DocumentCreate, DocumentUpdate, DocumentResponse, DocumentListResponse
from .utils import FileValidator, generate_unique_filename, get_file_info

logger = logging.getLogger(__name__)


class DocumentService:
    """Service class for document management operations."""
    
    def __init__(self):
        self.file_validator = FileValidator()
    
    async def upload_document(
        self, 
        db: Session, 
        file: UploadFile, 
        user_id: UUID
    ) -> DocumentResponse:
        """
        Upload and store a document.
        
        Args:
            db: Database session
            file: Uploaded file
            user_id: ID of the user uploading the document
            
        Returns:
            DocumentResponse object
            
        Raises:
            HTTPException: If validation fails or upload fails
        """
        # Validate file
        is_valid, error_message = await self.file_validator.validate_upload(file)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_message)
        
        # Read file content
        try:
            file_content = await file.read()
            await file.seek(0)
        except Exception as e:
            logger.error(f"Failed to read uploaded file: {e}")
            raise HTTPException(status_code=400, detail="Failed to read uploaded file")
        
        # Get file information
        file_info = get_file_info(file_content, file.filename)
        
        # Generate unique filename for storage
        storage_filename = generate_unique_filename(file.filename)
        
        # Create document record in database
        document = Document(
            user_id=user_id,
            filename=storage_filename,
            original_name=file_info['sanitized_name'],
            file_size=file_info['size'],
            mime_type=file_info['mime_type'],
            file_path=f"documents/{user_id}/{storage_filename}",
            status="processing"
        )
        
        try:
            # Save to database first
            db.add(document)
            db.commit()
            db.refresh(document)
            
            # Upload to storage
            file_stream = io.BytesIO(file_content)
            success = await storage.upload_file(
                file_data=file_stream,
                object_name=document.file_path,
                content_type=file_info['mime_type'],
                metadata={
                    'original_name': file.filename,
                    'user_id': str(user_id),
                    'document_id': str(document.id),
                    'file_hash': file_info['hash']
                }
            )
            
            if not success:
                # Rollback database changes if storage upload fails
                db.delete(document)
                db.commit()
                raise HTTPException(status_code=500, detail="Failed to upload file to storage")
            
            # Update status to completed (will be changed to processing by document processor later)
            document.status = "uploaded"
            db.commit()
            db.refresh(document)
            
            logger.info(f"Successfully uploaded document {document.id} for user {user_id}")
            return DocumentResponse.model_validate(document)
            
        except Exception as e:
            # Cleanup on failure
            try:
                if document.id:
                    db.delete(document)
                    db.commit()
                    # Try to delete from storage if it was uploaded
                    await storage.delete_file(document.file_path)
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup after upload failure: {cleanup_error}")
            
            logger.error(f"Failed to upload document: {e}")
            raise HTTPException(status_code=500, detail="Failed to upload document")
    
    def get_documents(
        self, 
        db: Session, 
        user_id: UUID, 
        page: int = 1, 
        page_size: int = 20,
        status_filter: Optional[str] = None
    ) -> DocumentListResponse:
        """
        Get paginated list of user's documents.
        
        Args:
            db: Database session
            user_id: ID of the user
            page: Page number (1-based)
            page_size: Number of documents per page
            status_filter: Optional status filter
            
        Returns:
            DocumentListResponse object
        """
        # Build query
        query = db.query(Document).filter(Document.user_id == user_id)
        
        if status_filter:
            query = query.filter(Document.status == status_filter)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        documents = (
            query
            .order_by(desc(Document.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        
        # Calculate total pages
        total_pages = (total + page_size - 1) // page_size
        
        return DocumentListResponse(
            documents=[DocumentResponse.model_validate(doc) for doc in documents],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    
    def get_document(self, db: Session, document_id: UUID, user_id: UUID) -> Optional[DocumentResponse]:
        """
        Get a specific document by ID.
        
        Args:
            db: Database session
            document_id: ID of the document
            user_id: ID of the user (for authorization)
            
        Returns:
            DocumentResponse object or None if not found
        """
        document = db.query(Document).filter(
            and_(
                Document.id == document_id,
                Document.user_id == user_id
            )
        ).first()
        
        if document:
            return DocumentResponse.model_validate(document)
        return None
    
    async def delete_document(self, db: Session, document_id: UUID, user_id: UUID) -> bool:
        """
        Delete a document and its associated files.
        
        Args:
            db: Database session
            document_id: ID of the document to delete
            user_id: ID of the user (for authorization)
            
        Returns:
            True if deletion successful, False otherwise
        """
        # Find the document
        document = db.query(Document).filter(
            and_(
                Document.id == document_id,
                Document.user_id == user_id
            )
        ).first()
        
        if not document:
            return False
        
        try:
            # Delete from storage first
            storage_deleted = await storage.delete_file(document.file_path)
            if not storage_deleted:
                logger.warning(f"Failed to delete file from storage: {document.file_path}")
            
            # Delete from database (this will cascade to document_chunks)
            db.delete(document)
            db.commit()
            
            logger.info(f"Successfully deleted document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            db.rollback()
            return False
    
    def search_documents(
        self, 
        db: Session, 
        user_id: UUID, 
        query: str, 
        page: int = 1, 
        page_size: int = 20
    ) -> DocumentListResponse:
        """
        Search documents by filename or content.
        
        Args:
            db: Database session
            user_id: ID of the user
            query: Search query string
            page: Page number (1-based)
            page_size: Number of documents per page
            
        Returns:
            DocumentListResponse object
        """
        # Build search query
        search_filter = or_(
            Document.original_name.ilike(f"%{query}%"),
            Document.filename.ilike(f"%{query}%")
        )
        
        base_query = db.query(Document).filter(
            and_(
                Document.user_id == user_id,
                search_filter
            )
        )
        
        # Get total count
        total = base_query.count()
        
        # Apply pagination and ordering
        documents = (
            base_query
            .order_by(desc(Document.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        
        # Calculate total pages
        total_pages = (total + page_size - 1) // page_size
        
        return DocumentListResponse(
            documents=[DocumentResponse.model_validate(doc) for doc in documents],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    
    def get_document_stats(self, db: Session, user_id: UUID) -> dict:
        """
        Get document statistics for a user.
        
        Args:
            db: Database session
            user_id: ID of the user
            
        Returns:
            Dictionary with statistics
        """
        # Get basic counts
        total_documents = db.query(Document).filter(Document.user_id == user_id).count()
        
        # Get total size
        total_size_result = db.query(func.sum(Document.file_size)).filter(
            Document.user_id == user_id
        ).scalar()
        total_size = total_size_result or 0
        
        # Get status counts
        status_counts = db.query(
            Document.status,
            func.count(Document.id)
        ).filter(
            Document.user_id == user_id
        ).group_by(Document.status).all()
        
        status_dict = {status: count for status, count in status_counts}
        
        # Get recent uploads (last 5)
        recent_documents = (
            db.query(Document)
            .filter(Document.user_id == user_id)
            .order_by(desc(Document.created_at))
            .limit(5)
            .all()
        )
        
        return {
            'total_documents': total_documents,
            'total_size': total_size,
            'processing_count': status_dict.get('processing', 0),
            'completed_count': status_dict.get('completed', 0),
            'failed_count': status_dict.get('failed', 0),
            'uploaded_count': status_dict.get('uploaded', 0),
            'recent_uploads': [DocumentResponse.model_validate(doc) for doc in recent_documents]
        }
    
    async def get_document_content(self, db: Session, document_id: UUID, user_id: UUID) -> Optional[bytes]:
        """
        Get the raw content of a document.
        
        Args:
            db: Database session
            document_id: ID of the document
            user_id: ID of the user (for authorization)
            
        Returns:
            Document content as bytes or None if not found
        """
        # Find the document
        document = db.query(Document).filter(
            and_(
                Document.id == document_id,
                Document.user_id == user_id
            )
        ).first()
        
        if not document:
            return None
        
        # Download from storage
        content = await storage.download_file(document.file_path)
        return content
    
    async def update_document_status(
        self, 
        db: Session, 
        document_id: UUID, 
        status: str,
        user_id: Optional[UUID] = None
    ) -> bool:
        """
        Update document processing status.
        
        Args:
            db: Database session
            document_id: ID of the document
            status: New status value
            user_id: Optional user ID for authorization
            
        Returns:
            True if update successful, False otherwise
        """
        query = db.query(Document).filter(Document.id == document_id)
        
        if user_id:
            query = query.filter(Document.user_id == user_id)
        
        document = query.first()
        if not document:
            return False
        
        try:
            document.status = status
            db.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update document status: {e}")
            db.rollback()
            return False


# Global service instance
document_service = DocumentService()