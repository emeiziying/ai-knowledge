"""
Integration tests for RAG Answer API endpoints.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import User
from app.auth.jwt import create_access_token


class TestRAGAnswerAPI:
    """Test RAG Answer API endpoints."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
        
        # Create test user
        self.test_user = User(
            id="test-user-id",
            username="testuser",
            email="test@example.com"
        )
        
        # Create access token
        self.access_token = create_access_token(data={"sub": self.test_user.username})
        self.headers = {"Authorization": f"Bearer {self.access_token}"}
    
    @patch('app.chat.router.get_answer_service')
    @patch('app.auth.dependencies.get_current_user')
    @patch('app.database.get_db')
    def test_generate_answer_endpoint(self, mock_get_db, mock_get_user, mock_get_answer_service):
        """Test the /answer endpoint."""
        # Mock dependencies
        mock_get_user.return_value = self.test_user
        mock_get_db.return_value = Mock(spec=Session)
        
        # Mock answer service
        mock_answer_service = Mock()
        mock_answer_service.generate_answer = AsyncMock(return_value={
            "answer": "This is a test answer based on [test.pdf].",
            "sources": [
                {
                    "document_id": "doc1",
                    "document_name": "test.pdf",
                    "file_size": 1024,
                    "mime_type": "application/pdf",
                    "created_at": "2024-01-01T00:00:00Z",
                    "chunks_referenced": [
                        {
                            "chunk_index": 0,
                            "content_preview": "Test content...",
                            "score": 0.85
                        }
                    ]
                }
            ],
            "quality_validation": {
                "is_valid": True,
                "quality_score": 0.9,
                "issues": [],
                "suggestions": []
            },
            "question": "What is the test about?",
            "search_metadata": {
                "total_results": 1,
                "search_time_ms": 50.0,
                "cached": False
            },
            "processing_time_ms": 150.0,
            "model_used": "gpt-3.5-turbo",
            "has_context": True,
            "context_used": True,
            "context_chunks": 1
        })
        mock_get_answer_service.return_value = mock_answer_service
        
        # Test request
        request_data = {
            "question": "What is the test about?",
            "conversation_id": None,
            "search_params": None,
            "model": None,
            "stream": False
        }
        
        response = self.client.post(
            "/api/v1/chat/answer",
            json=request_data,
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "answer" in data
        assert "sources" in data
        assert "quality_validation" in data
        assert data["answer"] == "This is a test answer based on [test.pdf]."
        assert len(data["sources"]) == 1
        assert data["sources"][0]["document_name"] == "test.pdf"
        assert data["has_context"] is True
    
    @patch('app.chat.router.get_answer_service')
    @patch('app.auth.dependencies.get_current_user')
    @patch('app.database.get_db')
    def test_generate_answer_no_service(self, mock_get_db, mock_get_user, mock_get_answer_service):
        """Test answer endpoint when service is not available."""
        # Mock dependencies
        mock_get_user.return_value = self.test_user
        mock_get_db.return_value = Mock(spec=Session)
        mock_get_answer_service.return_value = None
        
        request_data = {
            "question": "What is the test about?"
        }
        
        response = self.client.post(
            "/api/v1/chat/answer",
            json=request_data,
            headers=self.headers
        )
        
        assert response.status_code == 503
        assert "Answer service not available" in response.json()["detail"]
    
    @patch('app.chat.router.get_answer_service')
    @patch('app.chat.router.get_rag_service')
    @patch('app.auth.dependencies.get_current_user')
    @patch('app.database.get_db')
    def test_improve_answer_endpoint(self, mock_get_db, mock_get_user, mock_get_rag_service, mock_get_answer_service):
        """Test the /answer/improve endpoint."""
        # Mock dependencies
        mock_get_user.return_value = self.test_user
        mock_get_db.return_value = Mock(spec=Session)
        
        # Mock RAG service
        mock_rag_service = Mock()
        mock_rag_service.search_documents = AsyncMock(return_value={
            "results": [
                {
                    "content": "Test content for improvement",
                    "document_metadata": {"original_name": "test.pdf"},
                    "document_id": "doc1",
                    "score": 0.85
                }
            ]
        })
        mock_get_rag_service.return_value = mock_rag_service
        
        # Mock answer service
        mock_answer_service = Mock()
        mock_answer_service.improve_answer = AsyncMock(return_value={
            "improved_answer": "This is an improved answer with more details [test.pdf].",
            "sources": [
                {
                    "document_id": "doc1",
                    "document_name": "test.pdf",
                    "file_size": 1024,
                    "mime_type": "application/pdf",
                    "created_at": "2024-01-01T00:00:00Z",
                    "chunks_referenced": []
                }
            ],
            "quality_validation": {
                "is_valid": True,
                "quality_score": 0.95,
                "issues": [],
                "suggestions": []
            },
            "improvement_applied": True
        })
        mock_get_answer_service.return_value = mock_answer_service
        
        # Test request
        request_data = {
            "original_answer": "This is the original answer.",
            "question": "What is the test about?",
            "feedback": "Please provide more details.",
            "model": None
        }
        
        response = self.client.post(
            "/api/v1/chat/answer/improve",
            json=request_data,
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "improved_answer" in data
        assert "sources" in data
        assert "quality_validation" in data
        assert data["improvement_applied"] is True
        assert "improved answer" in data["improved_answer"].lower()
    
    @patch('app.chat.router.get_answer_service')
    @patch('app.chat.router.get_conversation_service')
    @patch('app.auth.dependencies.get_current_user')
    @patch('app.database.get_db')
    def test_qa_endpoint(self, mock_get_db, mock_get_user, mock_get_conversation_service, mock_get_answer_service):
        """Test the /qa endpoint that combines Q&A with conversation management."""
        # Mock dependencies
        mock_get_user.return_value = self.test_user
        mock_get_db.return_value = Mock(spec=Session)
        
        # Mock conversation service
        mock_conversation_service = Mock()
        mock_conversation_service.create_conversation = AsyncMock(return_value={
            "id": "conv123",
            "user_id": "test-user-id",
            "title": "Test conversation",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "message_count": 0
        })
        mock_conversation_service.add_message = AsyncMock(return_value={
            "id": "msg123",
            "conversation_id": "conv123",
            "role": "assistant",
            "content": "This is the assistant's answer.",
            "metadata": {},
            "created_at": "2024-01-01T00:00:00Z"
        })
        mock_get_conversation_service.return_value = mock_conversation_service
        
        # Mock answer service
        mock_answer_service = Mock()
        mock_answer_service.generate_answer = AsyncMock(return_value={
            "answer": "This is the generated answer.",
            "sources": [],
            "quality_validation": {
                "is_valid": True,
                "quality_score": 0.8,
                "issues": [],
                "suggestions": []
            },
            "search_metadata": {
                "total_results": 0,
                "search_time_ms": 30.0,
                "cached": False
            },
            "processing_time_ms": 100.0,
            "model_used": "gpt-3.5-turbo",
            "has_context": False
        })
        mock_get_answer_service.return_value = mock_answer_service
        
        # Test request
        request_data = {
            "question": "What is the test about?",
            "conversation_id": None
        }
        
        response = self.client.post(
            "/api/v1/chat/qa",
            json=request_data,
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert "conversation_id" in data
        assert "role" in data
        assert "content" in data
        assert data["role"] == "assistant"
        
        # Verify services were called
        mock_conversation_service.create_conversation.assert_called_once()
        mock_conversation_service.add_message.assert_called()
        mock_answer_service.generate_answer.assert_called_once()
    
    def test_answer_request_validation(self):
        """Test request validation for answer endpoints."""
        # Test empty question
        response = self.client.post(
            "/api/v1/chat/answer",
            json={"question": ""},
            headers=self.headers
        )
        assert response.status_code == 422
        
        # Test missing question
        response = self.client.post(
            "/api/v1/chat/answer",
            json={},
            headers=self.headers
        )
        assert response.status_code == 422
        
        # Test question too long
        long_question = "x" * 2001
        response = self.client.post(
            "/api/v1/chat/answer",
            json={"question": long_question},
            headers=self.headers
        )
        assert response.status_code == 422
    
    def test_unauthorized_access(self):
        """Test unauthorized access to answer endpoints."""
        request_data = {
            "question": "What is the test about?"
        }
        
        # Test without authorization header
        response = self.client.post(
            "/api/v1/chat/answer",
            json=request_data
        )
        assert response.status_code == 401
        
        # Test with invalid token
        invalid_headers = {"Authorization": "Bearer invalid_token"}
        response = self.client.post(
            "/api/v1/chat/answer",
            json=request_data,
            headers=invalid_headers
        )
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__])