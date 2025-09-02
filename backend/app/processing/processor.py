"""
Main document processor that orchestrates parsing, preprocessing, and status tracking.
"""
import logging
import traceback
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from .parsers import DocumentParserFactory
from .preprocessor import preprocess_document_content, PreprocessingConfig
from ..models import Document, DocumentChunk
from ..database import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ProcessingStatus(Enum):
    """Document processing status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    PARSING = "parsing"
    PREPROCESSING = "preprocessing"
    CHUNKING = "chunking"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingError(Exception):
    """Custom exception for document processing errors."""
    
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        super().__init__(message)
        self.error_code = error_code or "PROCESSING_ERROR"
        self.details = details or {}


class DocumentProcessor:
    """Main document processor class."""
    
    def __init__(self, db_session: Session = None):
        self.parser_factory = DocumentParserFactory()
        self.db_session = db_session
        
        # Default preprocessing configuration
        self.preprocessing_config = PreprocessingConfig(
            remove_extra_whitespace=True,
            normalize_unicode=True,
            remove_special_chars=False,
            min_line_length=3,
            preserve_structure=True,
            remove_urls=False,
            remove_emails=False,
            lowercase=False
        )
    
    def process_document(
        self, 
        document_id: str, 
        file_content: bytes, 
        filename: str, 
        mime_type: str
    ) -> Dict[str, Any]:
        """
        Process a document through the complete pipeline.
        
        Args:
            document_id: Database document ID
            file_content: Raw file content
            filename: Original filename
            mime_type: MIME type of the file
            
        Returns:
            Processing result with extracted content and metadata
        """
        processing_result = {
            "document_id": document_id,
            "filename": filename,
            "mime_type": mime_type,
            "status": ProcessingStatus.PENDING.value,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "error": None,
            "content": None,
            "metadata": None,
            "chunks": [],
            "processing_stats": {}
        }
        
        try:
            # Update status to processing
            self._update_document_status(document_id, ProcessingStatus.PROCESSING.value)
            processing_result["status"] = ProcessingStatus.PROCESSING.value
            
            # Step 1: Parse document
            logger.info(f"Starting document parsing for {filename}")
            self._update_document_status(document_id, ProcessingStatus.PARSING.value)
            
            parsing_result = self._parse_document(file_content, filename, mime_type)
            processing_result["parsing_result"] = parsing_result
            
            # Step 2: Preprocess content
            logger.info(f"Starting content preprocessing for {filename}")
            self._update_document_status(document_id, ProcessingStatus.PREPROCESSING.value)
            
            preprocessing_result = self._preprocess_content(
                parsing_result["content"], 
                parsing_result["metadata"]
            )
            processing_result["preprocessing_result"] = preprocessing_result
            
            # Step 3: Create document chunks (basic chunking for now)
            logger.info(f"Starting content chunking for {filename}")
            self._update_document_status(document_id, ProcessingStatus.CHUNKING.value)
            
            chunks = self._create_basic_chunks(
                preprocessing_result["processed_content"],
                preprocessing_result["structure_metadata"]
            )
            processing_result["chunks"] = chunks
            
            # Step 4: Store results
            self._store_processing_results(document_id, preprocessing_result, chunks)
            
            # Update final status with metadata
            final_metadata = {
                "processing_stats": processing_result.get("processing_stats", {}),
                "completed_at": datetime.utcnow().isoformat()
            }
            self._update_document_status(
                document_id, 
                ProcessingStatus.COMPLETED.value, 
                metadata=final_metadata
            )
            processing_result["status"] = ProcessingStatus.COMPLETED.value
            processing_result["completed_at"] = datetime.utcnow().isoformat()
            
            # Compile final results
            processing_result.update({
                "content": preprocessing_result["processed_content"],
                "metadata": {
                    **parsing_result["metadata"],
                    **preprocessing_result["structure_metadata"],
                    "preprocessing_stats": preprocessing_result["preprocessing_stats"]
                },
                "processing_stats": {
                    "original_length": len(parsing_result["content"]),
                    "processed_length": len(preprocessing_result["processed_content"]),
                    "chunk_count": len(chunks),
                    "parsing_successful": True,
                    "preprocessing_successful": True
                }
            })
            
            logger.info(f"Document processing completed successfully for {filename}")
            return processing_result
            
        except Exception as e:
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()
            }
            
            logger.error(f"Document processing failed for {filename}: {error_details}")
            
            # Update status to failed
            self._update_document_status(
                document_id, 
                ProcessingStatus.FAILED.value, 
                error=error_details["error_message"]
            )
            
            processing_result.update({
                "status": ProcessingStatus.FAILED.value,
                "completed_at": datetime.utcnow().isoformat(),
                "error": error_details
            })
            
            return processing_result
    
    def _parse_document(self, file_content: bytes, filename: str, mime_type: str) -> Dict[str, Any]:
        """Parse document using appropriate parser."""
        try:
            result = self.parser_factory.parse_document(file_content, filename, mime_type)
            logger.info(f"Document parsing successful for {filename}")
            return result
        except Exception as e:
            raise ProcessingError(
                f"Failed to parse document: {str(e)}",
                error_code="PARSING_FAILED",
                details={"filename": filename, "mime_type": mime_type}
            )
    
    def _preprocess_content(self, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Preprocess document content."""
        try:
            result = preprocess_document_content(content, metadata, self.preprocessing_config)
            logger.info(f"Content preprocessing successful")
            return result
        except Exception as e:
            raise ProcessingError(
                f"Failed to preprocess content: {str(e)}",
                error_code="PREPROCESSING_FAILED"
            )
    
    def _create_basic_chunks(
        self, 
        content: str, 
        structure_metadata: Dict[str, Any],
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> List[Dict[str, Any]]:
        """Create basic text chunks from processed content."""
        # Import here to avoid circular imports
        from .chunking import create_semantic_chunks, ChunkingConfig, ChunkingStrategy
        
        try:
            # Use the new semantic chunking if available
            config = ChunkingConfig(
                strategy=ChunkingStrategy.HYBRID,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                min_chunk_size=100,
                max_chunk_size=chunk_size * 2,
                preserve_sentences=True,
                preserve_paragraphs=True,
                respect_structure=True
            )
            
            chunks = create_semantic_chunks(content, structure_metadata, config)
            
            if chunks:
                logger.info(f"Created {len(chunks)} semantic chunks from content")
                return chunks
            else:
                logger.warning("Semantic chunking returned no chunks, falling back to basic chunking")
        
        except Exception as e:
            logger.warning(f"Semantic chunking failed, falling back to basic chunking: {e}")
        
        # Fallback to basic chunking
        chunks = []
        
        # Simple chunking by character count with overlap
        content_length = len(content)
        start = 0
        chunk_index = 0
        
        while start < content_length:
            end = min(start + chunk_size, content_length)
            
            # Try to break at sentence boundaries
            if end < content_length:
                # Look for sentence endings within the last 100 characters
                search_start = max(end - 100, start)
                sentence_end = -1
                
                for i in range(end - 1, search_start - 1, -1):
                    if content[i] in '.!?':
                        # Check if this is likely a sentence end (not abbreviation)
                        if i + 1 < len(content) and content[i + 1] in ' \n':
                            sentence_end = i + 1
                            break
                
                if sentence_end > start:
                    end = sentence_end
            
            chunk_content = content[start:end].strip()
            
            if chunk_content:  # Only add non-empty chunks
                chunk_metadata = {
                    "chunk_index": chunk_index,
                    "start_position": start,
                    "end_position": end,
                    "character_count": len(chunk_content),
                    "word_count": len(chunk_content.split()),
                    "has_structure_markers": self._check_structure_markers(
                        chunk_content, structure_metadata
                    )
                }
                
                chunks.append({
                    "content": chunk_content,
                    "metadata": chunk_metadata
                })
                
                chunk_index += 1
            
            # Move start position with overlap
            start = max(end - chunk_overlap, start + 1)
            
            # Prevent infinite loop
            if start >= end:
                break
        
        logger.info(f"Created {len(chunks)} basic chunks from content")
        return chunks
    
    def _check_structure_markers(self, chunk_content: str, structure_metadata: Dict[str, Any]) -> Dict[str, bool]:
        """Check if chunk contains structure markers."""
        return {
            "has_headings": any(marker["title"] in chunk_content 
                              for marker in structure_metadata.get("structure_markers", {}).get("headings", [])),
            "has_lists": any("- " in chunk_content or "* " in chunk_content or 
                           any(f"{i}." in chunk_content for i in range(1, 10))),
            "has_tables": "|" in chunk_content,
            "has_code": "```" in chunk_content or "    " in chunk_content,
            "has_quotes": ">" in chunk_content
        }
    
    def _store_processing_results(
        self, 
        document_id: str, 
        preprocessing_result: Dict[str, Any], 
        chunks: List[Dict[str, Any]]
    ):
        """Store processing results in database."""
        if not self.db_session:
            logger.warning("No database session available, skipping storage")
            return
        
        try:
            # Store document chunks
            for chunk_data in chunks:
                chunk = DocumentChunk(
                    document_id=document_id,
                    chunk_index=chunk_data["metadata"]["chunk_index"],
                    content=chunk_data["content"],
                    metadata_json=chunk_data["metadata"]
                )
                self.db_session.add(chunk)
            
            self.db_session.commit()
            logger.info(f"Stored {len(chunks)} chunks for document {document_id}")
            
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to store processing results: {e}")
            raise ProcessingError(
                f"Failed to store processing results: {str(e)}",
                error_code="STORAGE_FAILED"
            )
    
    def _update_document_status(self, document_id: str, status: str, metadata: Dict[str, Any] = None, error: str = None):
        """Update document processing status in database."""
        if not self.db_session:
            logger.warning("No database session available, skipping status update")
            return
        
        try:
            document = self.db_session.query(Document).filter(Document.id == document_id).first()
            if document:
                document.status = status
                document.updated_at = datetime.utcnow()
                
                if metadata:
                    document.processing_metadata = metadata
                
                if error:
                    document.processing_error = error
                elif status == ProcessingStatus.COMPLETED.value:
                    # Clear any previous error on successful completion
                    document.processing_error = None
                
                self.db_session.commit()
                logger.debug(f"Updated document {document_id} status to {status}")
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to update document status: {e}")


def process_document_async(
    document_id: str,
    file_content: bytes,
    filename: str,
    mime_type: str,
    db_session: Session = None
) -> Dict[str, Any]:
    """
    Async wrapper for document processing.
    This function can be called by Celery tasks or other async processors.
    """
    processor = DocumentProcessor(db_session)
    return processor.process_document(document_id, file_content, filename, mime_type)


def get_supported_formats() -> Dict[str, List[str]]:
    """Get list of supported document formats."""
    return {
        "pdf": ["application/pdf", ".pdf"],
        "word": [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
            ".docx", ".doc"
        ],
        "text": ["text/plain", "text/txt", ".txt", ".text"],
        "markdown": ["text/markdown", "text/x-markdown", ".md", ".markdown"]
    }