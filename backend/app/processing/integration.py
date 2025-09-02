"""
Integration service that connects document management with processing pipeline.
"""
import logging
from typing import Dict, Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from .processor import DocumentProcessor, ProcessingStatus
from ..documents.service import document_service
from ..storage import storage

logger = logging.getLogger(__name__)


class DocumentProcessingIntegration:
    """Service to integrate document processing with the existing document management system."""
    
    def __init__(self):
        self.processor = DocumentProcessor()
    
    async def process_uploaded_document(
        self, 
        db: Session, 
        document_id: UUID, 
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Process a document that has been uploaded to the system.
        
        Args:
            db: Database session
            document_id: ID of the document to process
            user_id: Optional user ID for authorization
            
        Returns:
            Processing result dictionary
        """
        try:
            # Get document from database
            document = await self._get_document_for_processing(db, document_id, user_id)
            if not document:
                raise ValueError(f"Document {document_id} not found or not accessible")
            
            # Download file content from storage
            file_content = await storage.download_file(document.file_path)
            if not file_content:
                raise ValueError(f"Could not download file content for document {document_id}")
            
            # Update processor with database session
            self.processor.db_session = db
            
            # Process the document
            result = self.processor.process_document(
                document_id=str(document_id),
                file_content=file_content,
                filename=document.original_name,
                mime_type=document.mime_type
            )
            
            logger.info(f"Document processing completed for {document_id}: {result['status']}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process document {document_id}: {e}")
            
            # Update document status to failed
            await document_service.update_document_status(
                db, document_id, ProcessingStatus.FAILED.value, user_id
            )
            
            return {
                "document_id": str(document_id),
                "status": ProcessingStatus.FAILED.value,
                "error": {
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
            }
    
    async def _get_document_for_processing(
        self, 
        db: Session, 
        document_id: UUID, 
        user_id: Optional[UUID] = None
    ):
        """Get document record for processing."""
        if user_id:
            return document_service.get_document(db, document_id, user_id)
        else:
            # For system-level processing, get document without user restriction
            from ..models import Document
            return db.query(Document).filter(Document.id == document_id).first()
    
    async def reprocess_document(
        self, 
        db: Session, 
        document_id: UUID, 
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Reprocess an existing document (e.g., after processing failure or configuration change).
        
        Args:
            db: Database session
            document_id: ID of the document to reprocess
            user_id: Optional user ID for authorization
            
        Returns:
            Processing result dictionary
        """
        try:
            # Clear existing chunks before reprocessing
            await self._clear_document_chunks(db, document_id)
            
            # Reset document status
            await document_service.update_document_status(
                db, document_id, ProcessingStatus.PENDING.value, user_id
            )
            
            # Process the document
            return await self.process_uploaded_document(db, document_id, user_id)
            
        except Exception as e:
            logger.error(f"Failed to reprocess document {document_id}: {e}")
            return {
                "document_id": str(document_id),
                "status": ProcessingStatus.FAILED.value,
                "error": {
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
            }
    
    async def _clear_document_chunks(self, db: Session, document_id: UUID):
        """Clear existing document chunks before reprocessing."""
        try:
            from ..models import DocumentChunk
            
            # Delete existing chunks
            chunks_deleted = db.query(DocumentChunk).filter(
                DocumentChunk.document_id == document_id
            ).delete()
            
            db.commit()
            logger.info(f"Cleared {chunks_deleted} existing chunks for document {document_id}")
            
        except Exception as e:
            logger.error(f"Failed to clear document chunks: {e}")
            db.rollback()
            raise
    
    def get_processing_status(self, db: Session, document_id: UUID, user_id: Optional[UUID] = None) -> Dict[str, Any]:
        """
        Get current processing status for a document.
        
        Args:
            db: Database session
            document_id: ID of the document
            user_id: Optional user ID for authorization
            
        Returns:
            Status information dictionary
        """
        try:
            document = self._get_document_for_processing(db, document_id, user_id)
            if not document:
                return {"error": "Document not found"}
            
            # Get chunk count
            from ..models import DocumentChunk
            chunk_count = db.query(DocumentChunk).filter(
                DocumentChunk.document_id == document_id
            ).count()
            
            return {
                "document_id": str(document_id),
                "status": document.status,
                "filename": document.original_name,
                "file_size": document.file_size,
                "mime_type": document.mime_type,
                "chunk_count": chunk_count,
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get processing status for {document_id}: {e}")
            return {"error": str(e)}
    
    def get_document_chunks(
        self, 
        db: Session, 
        document_id: UUID, 
        user_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Get processed chunks for a document.
        
        Args:
            db: Database session
            document_id: ID of the document
            user_id: Optional user ID for authorization
            page: Page number (1-based)
            page_size: Number of chunks per page
            
        Returns:
            Chunks data with pagination info
        """
        try:
            # Verify document access
            document = self._get_document_for_processing(db, document_id, user_id)
            if not document:
                return {"error": "Document not found"}
            
            from ..models import DocumentChunk
            
            # Get total count
            total = db.query(DocumentChunk).filter(
                DocumentChunk.document_id == document_id
            ).count()
            
            # Get chunks with pagination
            chunks = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index)
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            
            # Calculate total pages
            total_pages = (total + page_size - 1) // page_size
            
            return {
                "document_id": str(document_id),
                "chunks": [
                    {
                        "id": str(chunk.id),
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "metadata": chunk.metadata_json,
                        "vector_id": chunk.vector_id,
                        "created_at": chunk.created_at.isoformat()
                    }
                    for chunk in chunks
                ],
                "pagination": {
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get document chunks for {document_id}: {e}")
            return {"error": str(e)}


# Global integration service instance
processing_integration = DocumentProcessingIntegration()