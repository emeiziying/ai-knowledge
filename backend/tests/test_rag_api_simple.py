"""
Simple API tests for RAG endpoints without database setup.
"""
import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch

# Set testing environment to avoid host validation issues
os.environ["ENVIRONMENT"] = "testing"

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestRAGAPISimple:
    """Simple RAG API tests."""
    
    def test_health_check_endpoint_exists(self, client):
        """Test that health check endpoint exists."""
        response = client.get("/api/v1/chat/health")
        # Should return 200 even if service is not available
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
    
    def test_search_endpoint_requires_auth(self, client):
        """Test that search endpoint requires authentication."""
        response = client.post(
            "/api/v1/chat/search",
            json={"query": "test"}
        )
        assert response.status_code == 403
    
    def test_search_get_endpoint_requires_auth(self, client):
        """Test that GET search endpoint requires authentication."""
        response = client.get("/api/v1/chat/search?q=test")
        assert response.status_code == 403
    
    def test_suggestions_endpoint_requires_auth(self, client):
        """Test that suggestions endpoint requires authentication."""
        response = client.post(
            "/api/v1/chat/suggestions",
            json={"partial_query": "test"}
        )
        assert response.status_code == 403
    
    def test_cache_clear_endpoint_requires_auth(self, client):
        """Test that cache clear endpoint requires authentication."""
        response = client.delete("/api/v1/chat/cache")
        assert response.status_code == 403
    
    def test_search_validation_error(self, client):
        """Test search endpoint validation."""
        # Mock authentication to bypass auth requirement
        with patch('app.auth.dependencies.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.id = "test_user_id"
            mock_auth.return_value = mock_user
            
            # Test with invalid query (empty string)
            response = client.post(
                "/api/v1/chat/search",
                json={"query": ""}  # Empty query should fail validation
            )
            assert response.status_code == 422
    
    def test_suggestions_validation_error(self, client):
        """Test suggestions endpoint validation."""
        with patch('app.auth.dependencies.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.id = "test_user_id"
            mock_auth.return_value = mock_user
            
            # Test with invalid partial query (empty string)
            response = client.post(
                "/api/v1/chat/suggestions",
                json={"partial_query": ""}  # Empty query should fail validation
            )
            assert response.status_code == 422
    
    @patch('app.chat.rag_service.get_rag_service')
    def test_search_service_unavailable(self, mock_get_rag_service, client):
        """Test search when RAG service is unavailable."""
        mock_get_rag_service.return_value = None
        
        with patch('app.auth.dependencies.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.id = "test_user_id"
            mock_auth.return_value = mock_user
            
            response = client.post(
                "/api/v1/chat/search",
                json={"query": "test query"}
            )
            assert response.status_code == 503
            data = response.json()
            assert "RAG service not available" in data["detail"]
    
    @patch('app.chat.rag_service.get_rag_service')
    def test_search_success_mock(self, mock_get_rag_service, client):
        """Test successful search with mocked service."""
        # Mock RAG service
        mock_rag_service = Mock()
        mock_rag_service.search_documents = AsyncMock(return_value={
            "results": [
                {
                    "vector_id": "test_vector_1",
                    "score": 0.9,
                    "final_score": 0.95,
                    "document_id": "test_doc_id",
                    "chunk_index": 0,
                    "content": "This is test content",
                    "character_count": 20,
                    "word_count": 4,
                    "start_position": 0,
                    "end_position": 20,
                    "chunking_strategy": "semantic",
                    "created_at": "2024-01-01T00:00:00Z"
                }
            ],
            "total_results": 1,
            "query": "test query",
            "search_time_ms": 150.5,
            "cached": False
        })
        mock_get_rag_service.return_value = mock_rag_service
        
        with patch('app.auth.dependencies.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.id = "test_user_id"
            mock_auth.return_value = mock_user
            
            response = client.post(
                "/api/v1/chat/search",
                json={"query": "test query", "limit": 10}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert "results" in data
            assert "total_results" in data
            assert data["query"] == "test query"
            assert data["total_results"] == 1
            assert len(data["results"]) == 1
            
            result = data["results"][0]
            assert result["content"] == "This is test content"
            assert result["score"] == 0.9
    
    @patch('app.chat.rag_service.get_rag_service')
    def test_suggestions_success_mock(self, mock_get_rag_service, client):
        """Test successful suggestions with mocked service."""
        # Mock RAG service
        mock_rag_service = Mock()
        mock_rag_service.get_search_suggestions = AsyncMock(return_value=[
            "machine learning",
            "machine learning algorithms"
        ])
        mock_get_rag_service.return_value = mock_rag_service
        
        with patch('app.auth.dependencies.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.id = "test_user_id"
            mock_auth.return_value = mock_user
            
            response = client.post(
                "/api/v1/chat/suggestions",
                json={"partial_query": "machine", "limit": 5}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert "suggestions" in data
            assert "partial_query" in data
            assert data["partial_query"] == "machine"
            assert len(data["suggestions"]) == 2
            assert "machine learning" in data["suggestions"]
    
    @patch('app.chat.rag_service.get_rag_service')
    def test_cache_clear_success_mock(self, mock_get_rag_service, client):
        """Test successful cache clear with mocked service."""
        # Mock RAG service
        mock_rag_service = Mock()
        mock_rag_service.search_cache = Mock()
        mock_rag_service.search_cache.invalidate_user_cache = AsyncMock()
        mock_get_rag_service.return_value = mock_rag_service
        
        with patch('app.auth.dependencies.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.id = "test_user_id"
            mock_auth.return_value = mock_user
            
            response = client.delete("/api/v1/chat/cache")
            
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "cleared" in data["message"].lower()
    
    def test_get_search_with_parameters(self, client):
        """Test GET search endpoint with query parameters."""
        with patch('app.auth.dependencies.get_current_user') as mock_auth:
            with patch('app.chat.rag_service.get_rag_service') as mock_get_rag_service:
                mock_user = Mock()
                mock_user.id = "test_user_id"
                mock_auth.return_value = mock_user
                
                mock_rag_service = Mock()
                mock_rag_service.search_documents = AsyncMock(return_value={
                    "results": [],
                    "total_results": 0,
                    "query": "test query",
                    "search_time_ms": 50.0,
                    "cached": True
                })
                mock_get_rag_service.return_value = mock_rag_service
                
                response = client.get(
                    "/api/v1/chat/search?q=test query&limit=5&score_threshold=0.8&use_cache=true"
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["query"] == "test query"
                assert data["cached"] is True
    
    def test_get_suggestions_with_parameters(self, client):
        """Test GET suggestions endpoint with query parameters."""
        with patch('app.auth.dependencies.get_current_user') as mock_auth:
            with patch('app.chat.rag_service.get_rag_service') as mock_get_rag_service:
                mock_user = Mock()
                mock_user.id = "test_user_id"
                mock_auth.return_value = mock_user
                
                mock_rag_service = Mock()
                mock_rag_service.get_search_suggestions = AsyncMock(return_value=["learning"])
                mock_get_rag_service.return_value = mock_rag_service
                
                response = client.get("/api/v1/chat/suggestions?q=learn&limit=3")
                
                assert response.status_code == 200
                data = response.json()
                assert data["partial_query"] == "learn"
                assert data["suggestions"] == ["learning"]


if __name__ == "__main__":
    pytest.main([__file__])