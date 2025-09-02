"""
Tests for document management functionality.
"""
import pytest
import io
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import AsyncMock, patch, MagicMock

from app.main import app
from app.models import User, Document
from app.documents.service import document_service
from app.documents.utils import FileValidator, validate_file_type, validate_file_size


class TestFileValidation:
    """Test file validation utilities."""
    
    def test_validate_file_type_pdf(self):
        """Test PDF file type validation."""
        mock_file = MagicMock()
        mock_file.content_type = "application/pdf"
        mock_file.filename = "test.pdf"
        
        assert validate_file_type(mock_file) is True
    
    def test_validate_file_type_docx(self):
        """Test DOCX file type validation."""
        mock_file = MagicMock()
        mock_file.content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        mock_file.filename = "test.docx"
        
        assert validate_file_type(mock_file) is True
    
    def test_validate_file_type_invalid(self):
        """Test invalid file type validation."""
        mock_file = MagicMock()
        mock_file.content_type = "application/exe"
        mock_file.filename = "test.exe"
        
        assert validate_file_type(mock_file) is False
    
    def test_validate_file_size_valid(self):
        """Test valid file size."""
        mock_file = MagicMock()
        mock_file.size = 1024 * 1024  # 1MB
        
        assert validate_file_size(mock_file) is True
    
    def test_validate_file_size_too_large(self):
        """Test file size too large."""
        mock_file = MagicMock()
        mock_file.size = 100 * 1024 * 1024  # 100MB (exceeds 50MB limit)
        
        assert validate_file_size(mock_file) is False
    
    @pytest.mark.asyncio
    async def test_file_validator_valid_file(self):
        """Test FileValidator with valid file."""
        validator = FileValidator()
        
        mock_file = MagicMock()
        mock_file.filename = "test.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.read = AsyncMock(return_value=b"%PDF-1.4 test content")
        mock_file.seek = AsyncMock()
        
        is_valid, error = await validator.validate_upload(mock_file)
        
        assert is_valid is True
        assert error is None
    
    @pytest.mark.asyncio
    async def test_file_validator_no_file(self):
        """Test FileValidator with no file."""
        validator = FileValidator()
        
        is_valid, error = await validator.validate_upload(None)
        
        assert is_valid is False
        assert "No file provided" in error
    
    @pytest.mark.asyncio
    async def test_file_validator_empty_file(self):
        """Test FileValidator with empty file."""
        validator = FileValidator()
        
        mock_file = MagicMock()
        mock_file.filename = "test.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.read = AsyncMock(return_value=b"")
        mock_file.seek = AsyncMock()
        
        is_valid, error = await validator.validate_upload(mock_file)
        
        assert is_valid is False
        assert "File is empty" in error


class TestDocumentService:
    """Test document service functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return MagicMock(spec=Session)
    
    @pytest.fixture
    def mock_user(self):
        """Mock user."""
        user = User()
        user.id = uuid4()
        user.username = "testuser"
        user.email = "test@example.com"
        return user
    
    @pytest.fixture
    def mock_document(self, mock_user):
        """Mock document."""
        doc = Document()
        doc.id = uuid4()
        doc.user_id = mock_user.id
        doc.filename = "test-file.pdf"
        doc.original_name = "test.pdf"
        doc.file_size = 1024
        doc.mime_type = "application/pdf"
        doc.file_path = f"documents/{mock_user.id}/test-file.pdf"
        doc.status = "uploaded"
        return doc
    
    @pytest.mark.asyncio
    async def test_upload_document_success(self, mock_db, mock_user):
        """Test successful document upload."""
        # Mock file
        mock_file = MagicMock()
        mock_file.filename = "test.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.read = AsyncMock(return_value=b"%PDF-1.4 test content")
        mock_file.seek = AsyncMock()
        
        # Mock storage
        with patch('app.documents.service.storage') as mock_storage:
            mock_storage.upload_file = AsyncMock(return_value=True)
            
            # Mock database operations
            mock_db.add = MagicMock()
            mock_db.commit = MagicMock()
            mock_db.refresh = MagicMock()
            
            # Create a mock document that gets returned
            mock_document = Document()
            mock_document.id = uuid4()
            mock_document.user_id = mock_user.id
            mock_document.filename = "test-file.pdf"
            mock_document.original_name = "test.pdf"
            mock_document.file_size = 20
            mock_document.mime_type = "application/pdf"
            mock_document.file_path = f"documents/{mock_user.id}/test-file.pdf"
            mock_document.status = "uploaded"
            
            mock_db.refresh.side_effect = lambda doc: setattr(doc, 'id', mock_document.id)
            
            # Test upload
            result = await document_service.upload_document(mock_db, mock_file, mock_user.id)
            
            # Verify calls
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called()
            mock_storage.upload_file.assert_called_once()
            
            # Verify result
            assert result.user_id == mock_user.id
            assert result.original_name == "test.pdf"
            assert result.status == "uploaded"
    
    def test_get_documents(self, mock_db, mock_user, mock_document):
        """Test getting user documents."""
        # Mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_document]
        
        mock_db.query.return_value = mock_query
        
        # Test get documents
        result = document_service.get_documents(mock_db, mock_user.id, page=1, page_size=20)
        
        # Verify result
        assert result.total == 1
        assert result.page == 1
        assert result.page_size == 20
        assert len(result.documents) == 1
        assert result.documents[0].id == mock_document.id
    
    def test_get_document(self, mock_db, mock_user, mock_document):
        """Test getting a specific document."""
        # Mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_document
        
        mock_db.query.return_value = mock_query
        
        # Test get document
        result = document_service.get_document(mock_db, mock_document.id, mock_user.id)
        
        # Verify result
        assert result is not None
        assert result.id == mock_document.id
        assert result.user_id == mock_user.id
    
    def test_get_document_not_found(self, mock_db, mock_user):
        """Test getting a non-existent document."""
        # Mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        mock_db.query.return_value = mock_query
        
        # Test get document
        result = document_service.get_document(mock_db, uuid4(), mock_user.id)
        
        # Verify result
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_document_success(self, mock_db, mock_user, mock_document):
        """Test successful document deletion."""
        # Mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_document
        
        mock_db.query.return_value = mock_query
        mock_db.delete = MagicMock()
        mock_db.commit = MagicMock()
        
        # Mock storage
        with patch('app.documents.service.storage') as mock_storage:
            mock_storage.delete_file = AsyncMock(return_value=True)
            
            # Test delete
            result = await document_service.delete_document(mock_db, mock_document.id, mock_user.id)
            
            # Verify calls
            mock_storage.delete_file.assert_called_once_with(mock_document.file_path)
            mock_db.delete.assert_called_once_with(mock_document)
            mock_db.commit.assert_called_once()
            
            # Verify result
            assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_document_not_found(self, mock_db, mock_user):
        """Test deleting a non-existent document."""
        # Mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        mock_db.query.return_value = mock_query
        
        # Test delete
        result = await document_service.delete_document(mock_db, uuid4(), mock_user.id)
        
        # Verify result
        assert result is False
    
    def test_search_documents(self, mock_db, mock_user, mock_document):
        """Test document search functionality."""
        # Mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_document]
        
        mock_db.query.return_value = mock_query
        
        # Test search
        result = document_service.search_documents(mock_db, mock_user.id, "test", page=1, page_size=20)
        
        # Verify result
        assert result.total == 1
        assert len(result.documents) == 1
        assert result.documents[0].id == mock_document.id


class TestDocumentAPI:
    """Test document API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Mock authentication headers."""
        return {"Authorization": "Bearer test-token"}
    
    def test_upload_document_no_auth(self, client):
        """Test upload without authentication."""
        files = {"file": ("test.pdf", b"test content", "application/pdf")}
        response = client.post("/api/v1/documents/upload", files=files)
        
        assert response.status_code == 401
    
    def test_get_documents_no_auth(self, client):
        """Test get documents without authentication."""
        response = client.get("/api/v1/documents")
        
        assert response.status_code == 401
    
    def test_get_document_no_auth(self, client):
        """Test get specific document without authentication."""
        doc_id = str(uuid4())
        response = client.get(f"/api/v1/documents/{doc_id}")
        
        assert response.status_code == 401
    
    def test_delete_document_no_auth(self, client):
        """Test delete document without authentication."""
        doc_id = str(uuid4())
        response = client.delete(f"/api/v1/documents/{doc_id}")
        
        assert response.status_code == 401
    
    def test_search_documents_no_auth(self, client):
        """Test search documents without authentication."""
        response = client.get("/api/v1/documents/search?query=test")
        
        assert response.status_code == 401
    
    def test_document_stats_no_auth(self, client):
        """Test document stats without authentication."""
        response = client.get("/api/v1/documents/stats")
        
        assert response.status_code == 401
    
    def test_health_check(self, client):
        """Test document service health check."""
        with patch('app.documents.router.storage') as mock_storage:
            mock_storage.list_files = AsyncMock(return_value=[])
            
            response = client.get("/api/v1/documents/health/check")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "document_management"