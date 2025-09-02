"""Add processing fields and improve document status tracking

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add processing-related fields and constraints."""
    
    # Add processing metadata column to documents table if it doesn't exist
    try:
        op.add_column('documents', sa.Column('processing_metadata', postgresql.JSON, nullable=True))
    except Exception:
        # Column might already exist
        pass
    
    # Add processing error column to documents table if it doesn't exist
    try:
        op.add_column('documents', sa.Column('processing_error', sa.Text, nullable=True))
    except Exception:
        # Column might already exist
        pass
    
    # Update status column to support new processing statuses
    # First, update any existing 'processing' status to 'uploaded'
    op.execute("UPDATE documents SET status = 'uploaded' WHERE status = 'processing'")
    
    # Add check constraint for valid status values
    op.execute("""
        ALTER TABLE documents 
        DROP CONSTRAINT IF EXISTS documents_status_check
    """)
    
    op.execute("""
        ALTER TABLE documents 
        ADD CONSTRAINT documents_status_check 
        CHECK (status IN ('uploaded', 'pending', 'processing', 'parsing', 'preprocessing', 'chunking', 'completed', 'failed'))
    """)
    
    # Add index on status for better query performance
    try:
        op.create_index('idx_documents_status', 'documents', ['status'])
    except Exception:
        # Index might already exist
        pass
    
    # Add index on document_chunks for better performance
    try:
        op.create_index('idx_document_chunks_document_id', 'document_chunks', ['document_id'])
    except Exception:
        # Index might already exist
        pass
    
    try:
        op.create_index('idx_document_chunks_chunk_index', 'document_chunks', ['document_id', 'chunk_index'])
    except Exception:
        # Index might already exist
        pass


def downgrade() -> None:
    """Remove processing-related fields and constraints."""
    
    # Remove indexes
    try:
        op.drop_index('idx_document_chunks_chunk_index')
    except Exception:
        pass
    
    try:
        op.drop_index('idx_document_chunks_document_id')
    except Exception:
        pass
    
    try:
        op.drop_index('idx_documents_status')
    except Exception:
        pass
    
    # Remove check constraint
    op.execute("ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_status_check")
    
    # Remove columns
    try:
        op.drop_column('documents', 'processing_error')
    except Exception:
        pass
    
    try:
        op.drop_column('documents', 'processing_metadata')
    except Exception:
        pass