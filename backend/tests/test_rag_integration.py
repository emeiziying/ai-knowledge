"""
Integration tests for RAG API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db, Base
from app.models import User, Document
from app.auth.jwt import JWTManager
from app.config import get_settings


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_rag.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def client():
    """Create test client."""
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user():
    """Create test user."""
    db = TestingSessionLocal()
    try:
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


@pytest.fixture
def test_document(test_user):
    """Create test document."""
    db = TestingSessionLocal()
    try:
        document = Document(
            user_id=test_user.id,
            filename="test_doc.pdf",
            original_name="test_document.pdf",
            file_size=1024,
            mime_type="application/pdf",
            file_path="/test/path",
            status="completed"
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document
    finally:
        db.close()


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers."""
    settings = get_settings()
    jwt_manager = JWTManager(settings.SECRET_KEY, settings.ALGORITHM, settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = jwt_manager.create_access_token(data={"sub": str(test_user.id), "username": test_user.username})
    return {"Authorization": f"Bearer {token}"}


class TestRAGAPIEndpoints:
    """Test RAG API endpoints."""
    
    @patch('app.chat.rag_service.get_rag_service')
    def test_search_documents_post(self, mock_get_rag_service, client, auth_headers, test_document):
        """Test POST /api/v1/chat/search endpoint."""
        # Mock RAG service
        mock_rag_service = Mock()
        mock_rag_service.search_documents = AsyncMock(return_value={
            "results": [
                {
                    "vector_id": "test_vector_1",
                    "score": 0.9,
                    "final_score": 0.95,
                    "document_id": str(test_document.id),
                    "chunk_index": 0,
                    "content": "This is test content about machine learning",
                    "character_count": 45,
                    "word_count": 8,
                    "start_position": 0,
                    "end_position": 45,
                    "chunking_strategy": "semantic",
                    "created_at": "2024-01-01T00:00:00Z",
                    "document_metadata": {
                        "filename": "test_doc.pdf",
                        "original_name": "test_document.pdf"
                    }
                }
            ],
            "total_results": 1,
            "query": "machine learning",
            "search_time_ms": 150.5,
            "cached": False
        })
        mock_get_rag_service.return_value = mock_rag_service
        
        # Test request
        response = client.post(
            "/api/v1/chat/search",
            json={
                "query": "machine learning",
                "limit": 10,
                "score_threshold": 0.7
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "results" in data
        assert "total_results" in data
        assert "query" in data
        assert "search_time_ms" in data
        assert data["query"] == "machine learning"
        assert data["total_results"] == 1
        assert len(data["results"]) == 1
        
        result = data["results"][0]
        assert result["content"] == "This is test content about machine learning"
        assert result["score"] == 0.9
    
    @patch('app.chat.rag_service.get_rag_service')
    def test_search_documents_get(self, mock_get_rag_service, client, auth_headers, test_document):
        """Test GET /api/v1/chat/search endpoint."""
        # Mock RAG service
        mock_rag_service = Mock()
        mock_rag_service.search_documents = AsyncMock(return_value={
            "results": [],
            "total_results": 0,
            "query": "test query",
            "search_time_ms": 50.0,
            "cached": True
        })
        mock_get_rag_service.return_value = mock_rag_service
        
        # Test request
        response = client.get(
            "/api/v1/chat/search?q=test query&limit=5&score_threshold=0.8",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["query"] == "test query"
        assert data["total_results"] == 0
        assert data["cached"] is True
    
    @patch('app.chat.rag_service.get_rag_service')
    def test_search_suggestions(self, mock_get_rag_service, client, auth_headers):
        """Test search suggestions endpoint."""
        # Mock RAG service
        mock_rag_service = Mock()
        mock_rag_service.get_search_suggestions = AsyncMock(return_value=[
            "machine learning",
            "machine learning algorithms",
            "machine learning models"
        ])
        mock_get_rag_service.return_value = mock_rag_service
        
        # Test POST request
        response = client.post(
            "/api/v1/chat/suggestions",
            json={
                "partial_query": "machine",
                "limit": 5
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "suggestions" in data
        assert "partial_query" in data
        assert data["partial_query"] == "machine"
        assert len(data["suggestions"]) == 3
        assert "machine learning" in data["suggestions"]
    
    @patch('app.chat.rag_service.get_rag_service')
    def test_search_suggestions_get(self, mock_get_rag_service, client, auth_headers):
        """Test GET search suggestions endpoint."""
        # Mock RAG service
        mock_rag_service = Mock()
        mock_rag_service.get_search_suggestions = AsyncMock(return_value=["learning"])
        mock_get_rag_service.return_value = mock_rag_service
        
        # Test GET request
        response = client.get(
            "/api/v1/chat/suggestions?q=learn&limit=3",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["partial_query"] == "learn"
        assert data["suggestions"] == ["learning"]
    
    @patch('app.chat.rag_service.get_rag_service')
    def test_clear_search_cache(self, mock_get_rag_service, client, auth_headers):
        """Test clear search cache endpoint."""
        # Mock RAG service
        mock_rag_service = Mock()
        mock_rag_service.search_cache = Mock()
        mock_rag_service.search_cache.invalidate_user_cache = AsyncMock()
        mock_get_rag_service.return_value = mock_rag_service
        
        # Test request
        response = client.delete(
            "/api/v1/chat/cache",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "cleared" in data["message"].lower()
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        with patch('app.chat.rag_service.get_rag_service') as mock_get_rag_service:
            mock_rag_service = Mock()
            mock_rag_service.search_cache = Mock()
            mock_rag_service.search_cache.redis_client = Mock()  # Redis available
            mock_get_rag_service.return_value = mock_rag_service
            
            response = client.get("/api/v1/chat/health")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "status" in data
            assert data["status"] == "healthy"
            assert "cache_available" in data
            assert data["cache_available"] is True
    
    def test_health_check_no_service(self, client):
        """Test health check when RAG service is not available."""
        with patch('app.chat.rag_service.get_rag_service', return_value=None):
            response = client.get("/api/v1/chat/health")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "unhealthy"
            assert "not initialized" in data["message"]
    
    def test_search_without_auth(self, client):
        """Test search endpoint without authentication."""
        response = client.post(
            "/api/v1/chat/search",
            json={"query": "test"}
        )
        
        assert response.status_code == 401
    
    def test_search_invalid_request(self, client, auth_headers):
        """Test search with invalid request data."""
        response = client.post(
            "/api/v1/chat/search",
            json={
                "query": "",  # Empty query
                "limit": 10
            },
            headers=auth_headers
        )
        
        assert response.status_code == 422  # Validation error
    
    @patch('app.chat.rag_service.get_rag_service')
    def test_search_service_error(self, mock_get_rag_service, client, auth_headers):
        """Test search when service raises an error."""
        # Mock RAG service to raise an exception
        mock_rag_service = Mock()
        mock_rag_service.search_documents = AsyncMock(side_effect=Exception("Service error"))
        mock_get_rag_service.return_value = mock_rag_service
        
        response = client.post(
            "/api/v1/chat/search",
            json={"query": "test query"},
            headers=auth_headers
        )
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Search failed" in data["detail"]


if __name__ == "__main__":
    pytest.main([__file__])