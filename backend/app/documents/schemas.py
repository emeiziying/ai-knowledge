"""
Pydantic schemas for document management.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, validator


class DocumentBase(BaseModel):
    """Base document schema."""
    original_name: str = Field(..., description="Original filename")
    

class DocumentCreate(DocumentBase):
    """Schema for creating a document."""
    pass


class DocumentUpdate(BaseModel):
    """Schema for updating a document."""
    original_name: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(processing|completed|failed)$")


class DocumentResponse(DocumentBase):
    """Schema for document response."""
    id: UUID
    user_id: UUID
    filename: str = Field(..., description="Stored filename")
    file_size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type of the file")
    status: str = Field(..., description="Processing status")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Schema for document list response."""
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class DocumentSearchRequest(BaseModel):
    """Schema for document search request."""
    query: str = Field(..., min_length=1, max_length=500)
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class DocumentSearchResponse(BaseModel):
    """Schema for document search response."""
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    query: str


class FileUploadResponse(BaseModel):
    """Schema for file upload response."""
    document_id: UUID
    message: str
    status: str


class DocumentStatsResponse(BaseModel):
    """Schema for document statistics."""
    total_documents: int
    total_size: int
    processing_count: int
    completed_count: int
    failed_count: int
    uploaded_count: int
    recent_uploads: List[DocumentResponse]