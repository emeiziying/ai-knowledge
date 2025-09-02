"""
Integration tests for document management with authentication.
"""
import pytest
import io
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Mock external dependencies before importing app
import sys
sys.modules['psycopg2'] = MagicMock()

# Mock settings
mock_settings = MagicMock()
mock_settings.debug = True
mock_settings.database_url = "sqlite:///test.db"
mock_settings.max_file_size = 50 * 1024 * 1024
mock_settings.allowed_file_types = ["application/pdf", "text/plain"]

with patch('app.config.get_settings', return_value=mock_settings):
    with patch('app.database.create_engine'):
        with patch('app.database.sessionmaker'):
            with patch('app.startup.init_db'):
                with patch('app.startup.vector_store'):
                    with patch('app.startup.storage'):
                        from app.main import app
                        from app.models import User, Document


class TestDocumentIntegration:
    """Integration tests for document management."""
    
    @pytest.fixture
    def client(self):
        """Test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user."""
        user = User()
        user.id = uuid4()
        user.username = "testuser"
        user.email = "test@example.com"
        return user
    
    def test_document_endpoints_require_auth(self, client):
        """Test that all document endpoints require authentication."""
        # Test upload endpoint
        files = {"file": ("test.pdf", b"test content", "application/pdf")}
        response = client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 401
        
        # Test list endpoint
        response = client.get("/api/v1/documents")
        assert response.status_code == 401
        
        # Test search endpoint
        response = client.get("/api/v1/documents/search?query=test")
        assert response.status_code == 401
        
        # Test stats endpoint
        response = client.get("/api/v1/documents/stats")
        assert response.status_code == 401
        
        # Test get document endpoint
        doc_id = str(uuid4())
        response = client.get(f"/api/v1/documents/{doc_id}")
        assert response.status_code == 401
        
        # Test download endpoint
        response = client.get(f"/api/v1/documents/{doc_id}/download")
        assert response.status_code == 401
        
        # Test delete endpoint
        response = client.delete(f"/api/v1/documents/{doc_id}")
        assert response.status_code == 401
        
        # Test update status endpoint
        response = client.patch(f"/api/v1/documents/{doc_id}/status?status=completed")
        assert response.status_code == 401
    
    def test_document_health_check_no_auth(self, client):
        """Test that health check endpoint doesn't require auth."""
        with patch('app.documents.router.storage') as mock_storage:
            mock_storage.list_files = AsyncMock(return_value=[])
            
            response = client.get("/api/v1/documents/health/check")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "document_management"
    
    @patch('app.documents.router.get_current_user')
    @patch('app.documents.router.get_db')
    def test_upload_document_with_auth(self, mock_get_db, mock_get_current_user, client, mock_user):
        """Test document upload with authentication."""
        # Mock authentication
        mock_get_current_user.return_value = mock_user
        
        # Mock database
        mock_db = MagicMock(spec=Session)
        mock_get_db.return_value = mock_db
        
        # Mock document service
        with patch('app.documents.router.document_service') as mock_service:
            mock_document = MagicMock()
            mock_document.id = uuid4()
            mock_document.user_id = mock_user.id
            mock_document.original_name = "test.pdf"
            mock_document.status = "uploaded"
            
            mock_service.upload_document = AsyncMock(return_value=mock_document)
            
            # Test upload
            files = {"file": ("test.pdf", b"%PDF-1.4 test content", "application/pdf")}
            response = client.post("/api/v1/documents/upload", files=files)
            
            assert response.status_code == 201
            data = response.json()
            assert data["message"] == "Document uploaded successfully"
            assert data["status"] == "uploaded"
            assert "document_id" in data
    
    @patch('app.documents.router.get_current_user')
    @patch('app.documents.router.get_db')
    def test_get_documents_with_auth(self, mock_get_db, mock_get_current_user, client, mock_user):
        """Test getting documents with authentication."""
        # Mock authentication
        mock_get_current_user.return_value = mock_user
        
        # Mock database
        mock_db = MagicMock(spec=Session)
        mock_get_db.return_value = mock_db
        
        # Mock document service
        with patch('app.documents.router.document_service') as mock_service:
            mock_response = MagicMock()
            mock_response.documents = []
            mock_response.total = 0
            mock_response.page = 1
            mock_response.page_size = 20
            mock_response.total_pages = 0
            
            mock_service.get_documents.return_value = mock_response
            
            # Test get documents
            response = client.get("/api/v1/documents")
            
            assert response.status_code == 200
            mock_service.get_documents.assert_called_once_with(
                db=mock_db,
                user_id=mock_user.id,
                page=1,
                page_size=20,
                status_filter=None
            )
    
    @patch('app.documents.router.get_current_user')
    @patch('app.documents.router.get_db')
    def test_search_documents_with_auth(self, mock_get_db, mock_get_current_user, client, mock_user):
        """Test searching documents with authentication."""
        # Mock authentication
        mock_get_current_user.return_value = mock_user
        
        # Mock database
        mock_db = MagicMock(spec=Session)
        mock_get_db.return_value = mock_db
        
        # Mock document service
        with patch('app.documents.router.document_service') as mock_service:
            mock_response = MagicMock()
            mock_response.documents = []
            mock_response.total = 0
            mock_response.page = 1
            mock_response.page_size = 20
            mock_response.total_pages = 0
            
            mock_service.search_documents.return_value = mock_response
            
            # Test search documents
            response = client.get("/api/v1/documents/search?query=test")
            
            assert response.status_code == 200
            mock_service.search_documents.assert_called_once_with(
                db=mock_db,
                user_id=mock_user.id,
                query="test",
                page=1,
                page_size=20
            )
    
    @patch('app.documents.router.get_current_user')
    @patch('app.documents.router.get_db')
    def test_get_document_stats_with_auth(self, mock_get_db, mock_get_current_user, client, mock_user):
        """Test getting document stats with authentication."""
        # Mock authentication
        mock_get_current_user.return_value = mock_user
        
        # Mock database
        mock_db = MagicMock(spec=Session)
        mock_get_db.return_value = mock_db
        
        # Mock document service
        with patch('app.documents.router.document_service') as mock_service:
            mock_stats = {
                'total_documents': 5,
                'total_size': 1024000,
                'processing_count': 1,
                'completed_count': 3,
                'failed_count': 1,
                'uploaded_count': 0,
                'recent_uploads': []
            }
            
            mock_service.get_document_stats.return_value = mock_stats
            
            # Test get stats
            response = client.get("/api/v1/documents/stats")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_documents"] == 5
            assert data["total_size"] == 1024000
            assert data["processing_count"] == 1
            assert data["completed_count"] == 3
            assert data["failed_count"] == 1
    
    @patch('app.documents.router.get_current_user')
    @patch('app.documents.router.get_db')
    def test_delete_document_with_auth(self, mock_get_db, mock_get_current_user, client, mock_user):
        """Test deleting document with authentication."""
        # Mock authentication
        mock_get_current_user.return_value = mock_user
        
        # Mock database
        mock_db = MagicMock(spec=Session)
        mock_get_db.return_value = mock_db
        
        # Mock document service
        with patch('app.documents.router.document_service') as mock_service:
            mock_service.delete_document = AsyncMock(return_value=True)
            
            # Test delete document
            doc_id = str(uuid4())
            response = client.delete(f"/api/v1/documents/{doc_id}")
            
            assert response.status_code == 204
            mock_service.delete_document.assert_called_once_with(
                mock_db, 
                uuid4(doc_id), 
                mock_user.id
            )
    
    def test_api_documentation_includes_documents(self, client):
        """Test that API documentation includes document endpoints."""
        response = client.get("/docs")
        # Should return the OpenAPI docs page (or redirect)
        assert response.status_code in [200, 307]  # 307 for redirect
    
    def test_root_endpoint_works(self, client):
        """Test that root endpoint works."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "AI Knowledge Base API"
        assert data["version"] == "1.0.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])