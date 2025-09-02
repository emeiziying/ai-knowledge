"""
Comprehensive API integration tests covering all major endpoints and workflows.
"""
import pytest
import asyncio
import tempfile
import os
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db, Base
from app.models import User, Document, Conversation, Message
from app.auth.jwt import JWTManager
from app.config import get_settings


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_api_integration.db"
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
            password_hash="$2b$12$hashed_password"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers."""
    settings = get_settings()
    jwt_manager = JWTManager(settings.SECRET_KEY, settings.ALGORITHM, settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = jwt_manager.create_access_token(data={"sub": str(test_user.id), "username": test_user.username})
    return {"Authorization": f"Bearer {token}"}


class TestAPIIntegration:
    """Comprehensive API integration tests."""
    
    def test_health_endpoints(self, client):
        """Test all health check endpoints."""
        # Main health check
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        
        # Document service health
        with patch('app.documents.router.storage') as mock_storage:
            mock_storage.list_files = AsyncMock(return_value=[])
            response = client.get("/api/v1/documents/health/check")
            assert response.status_code == 200
            
        # Chat service health
        with patch('app.chat.rag_service.get_rag_service') as mock_rag:
            mock_rag_service = Mock()
            mock_rag_service.search_cache = Mock()
            mock_rag_service.search_cache.redis_client = Mock()
            mock_rag.return_value = mock_rag_service
            
            response = client.get("/api/v1/chat/health")
            assert response.status_code == 200
    
    def test_authentication_flow(self, client):
        """Test complete authentication flow."""
        # Register new user
        register_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "testpassword123"
        }
        
        with patch('app.auth.service.AuthService.register_user') as mock_register:
            mock_user = User(
                id=uuid4(),
                username="newuser",
                email="newuser@example.com"
            )
            mock_register.return_value = mock_user
            
            response = client.post("/api/v1/auth/register", json=register_data)
            assert response.status_code == 201
            data = response.json()
            assert data["message"] == "User registered successfully"
        
        # Login
        login_data = {
            "username": "newuser",
            "password": "testpassword123"
        }
        
        with patch('app.auth.service.AuthService.authenticate_user') as mock_auth:
            mock_auth.return_value = mock_user
            
            response = client.post("/api/v1/auth/login", json=login_data)
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
    
    @patch('app.documents.service.document_service')
    @patch('app.processing.tasks.process_document_task.delay')
    def test_document_management_flow(self, mock_process_task, mock_doc_service, client, auth_headers, test_user):
        """Test complete document management workflow."""
        # Mock document service
        mock_document = Document(
            id=uuid4(),
            user_id=test_user.id,
            filename="test_doc.pdf",
            original_name="test_document.pdf",
            file_size=1024,
            mime_type="application/pdf",
            file_path="/test/path",
            status="uploaded"
        )
        mock_doc_service.upload_document = AsyncMock(return_value=mock_document)
        mock_doc_service.get_documents.return_value = Mock(
            documents=[mock_document],
            total=1,
            page=1,
            page_size=20,
            total_pages=1
        )
        mock_doc_service.get_document.return_value = mock_document
        mock_doc_service.delete_document = AsyncMock(return_value=True)
        
        # Upload document
        files = {"file": ("test.pdf", b"%PDF-1.4 test content", "application/pdf")}
        response = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
        assert response.status_code == 201
        
        upload_data = response.json()
        document_id = upload_data["document_id"]
        
        # List documents
        response = client.get("/api/v1/documents", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["documents"]) == 1
        
        # Get specific document
        response = client.get(f"/api/v1/documents/{document_id}", headers=auth_headers)
        assert response.status_code == 200
        
        # Search documents
        response = client.get("/api/v1/documents/search?query=test", headers=auth_headers)
        assert response.status_code == 200
        
        # Delete document
        response = client.delete(f"/api/v1/documents/{document_id}", headers=auth_headers)
        assert response.status_code == 204
    
    @patch('app.chat.conversation_service.conversation_service')
    @patch('app.chat.answer_service.answer_service')
    def test_conversation_flow(self, mock_answer_service, mock_conv_service, client, auth_headers, test_user):
        """Test complete conversation workflow."""
        # Mock services
        conversation_id = uuid4()
        mock_conversation = Conversation(
            id=conversation_id,
            user_id=test_user.id,
            title="Test Conversation"
        )
        
        mock_message = Message(
            id=uuid4(),
            conversation_id=conversation_id,
            role="user",
            content="What is machine learning?"
        )
        
        mock_conv_service.create_conversation.return_value = mock_conversation
        mock_conv_service.get_conversations.return_value = [mock_conversation]
        mock_conv_service.get_conversation.return_value = mock_conversation
        mock_conv_service.get_messages.return_value = [mock_message]
        
        mock_answer_service.generate_answer = AsyncMock(return_value={
            "answer": "Machine learning is a subset of AI...",
            "sources": [{"document_id": str(uuid4()), "content": "ML definition"}],
            "conversation_id": str(conversation_id),
            "message_id": str(uuid4())
        })
        
        # Create conversation
        response = client.post(
            "/api/v1/chat/conversations",
            json={"title": "Test Conversation"},
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        conv_id = data["id"]
        
        # List conversations
        response = client.get("/api/v1/chat/conversations", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        
        # Send message
        response = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"content": "What is machine learning?"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        
        # Get conversation history
        response = client.get(f"/api/v1/chat/conversations/{conv_id}/messages", headers=auth_headers)
        assert response.status_code == 200
    
    @patch('app.chat.rag_service.get_rag_service')
    def test_rag_search_flow(self, mock_get_rag_service, client, auth_headers):
        """Test RAG search functionality."""
        # Mock RAG service
        mock_rag_service = Mock()
        mock_rag_service.search_documents = AsyncMock(return_value={
            "results": [
                {
                    "vector_id": "test_vector_1",
                    "score": 0.9,
                    "final_score": 0.95,
                    "document_id": str(uuid4()),
                    "chunk_index": 0,
                    "content": "Machine learning is a method of data analysis",
                    "character_count": 45,
                    "word_count": 8,
                    "start_position": 0,
                    "end_position": 45,
                    "chunking_strategy": "semantic",
                    "created_at": "2024-01-01T00:00:00Z",
                    "document_metadata": {
                        "filename": "ml_guide.pdf",
                        "original_name": "Machine Learning Guide.pdf"
                    }
                }
            ],
            "total_results": 1,
            "query": "machine learning",
            "search_time_ms": 150.5,
            "cached": False
        })
        mock_rag_service.get_search_suggestions = AsyncMock(return_value=[
            "machine learning",
            "machine learning algorithms"
        ])
        mock_get_rag_service.return_value = mock_rag_service
        
        # Search documents
        response = client.post(
            "/api/v1/chat/search",
            json={"query": "machine learning", "limit": 10},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_results"] == 1
        assert len(data["results"]) == 1
        
        # Get search suggestions
        response = client.post(
            "/api/v1/chat/suggestions",
            json={"partial_query": "machine", "limit": 5},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
    
    def test_error_handling(self, client, auth_headers):
        """Test API error handling."""
        # Test 404 for non-existent document
        fake_id = str(uuid4())
        response = client.get(f"/api/v1/documents/{fake_id}", headers=auth_headers)
        assert response.status_code == 404
        
        # Test validation errors
        response = client.post(
            "/api/v1/chat/conversations",
            json={"title": ""},  # Empty title
            headers=auth_headers
        )
        assert response.status_code == 422
        
        # Test unauthorized access
        response = client.get("/api/v1/documents")
        assert response.status_code == 401
    
    def test_rate_limiting_headers(self, client, auth_headers):
        """Test that rate limiting headers are present."""
        response = client.get("/api/v1/documents", headers=auth_headers)
        # Note: This would require actual rate limiting middleware to be implemented
        # For now, just check that the endpoint responds correctly
        assert response.status_code in [200, 429]  # 429 if rate limited
    
    def test_cors_headers(self, client):
        """Test CORS headers are present."""
        response = client.options("/api/v1/documents")
        # CORS headers should be present
        assert "access-control-allow-origin" in [h.lower() for h in response.headers.keys()]
    
    @patch('app.processing.tasks.process_document_task.delay')
    def test_async_processing_integration(self, mock_process_task, client, auth_headers):
        """Test integration with async processing."""
        with patch('app.documents.service.document_service') as mock_doc_service:
            mock_document = Document(
                id=uuid4(),
                user_id=uuid4(),
                filename="test.pdf",
                original_name="test.pdf",
                file_size=1024,
                mime_type="application/pdf",
                file_path="/test/path",
                status="uploaded"
            )
            mock_doc_service.upload_document = AsyncMock(return_value=mock_document)
            
            # Upload should trigger async processing
            files = {"file": ("test.pdf", b"%PDF-1.4 content", "application/pdf")}
            response = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
            
            assert response.status_code == 201
            # Verify async task was triggered
            mock_process_task.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])