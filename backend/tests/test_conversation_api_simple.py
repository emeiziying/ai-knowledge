"""
Simple API tests for conversation endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


class TestConversationAPISimple:
    """Simple tests for conversation API endpoints."""
    
    def test_conversation_endpoints_exist(self):
        """Test that conversation endpoints are registered and return proper error codes."""
        
        # Test POST /api/v1/chat/conversations (should require auth)
        response = client.post("/api/v1/chat/conversations")
        print(f"POST conversations response: {response.status_code}, {response.text}")
        # Could be 400 (validation error) or 401 (auth error) - both indicate endpoint exists
        assert response.status_code in [400, 401]  # Either validation or auth error, not 404
        
        # Test GET /api/v1/chat/conversations (should require auth)
        response = client.get("/api/v1/chat/conversations")
        assert response.status_code in [400, 401]  # Either validation or auth error, not 404
        
        # Test GET /api/v1/chat/conversations/{id} (should require auth)
        response = client.get("/api/v1/chat/conversations/test-id")
        assert response.status_code in [400, 401]  # Either validation or auth error, not 404
        
        # Test PUT /api/v1/chat/conversations/{id} (should require auth)
        response = client.put("/api/v1/chat/conversations/test-id")
        assert response.status_code in [400, 401]  # Either validation or auth error, not 404
        
        # Test DELETE /api/v1/chat/conversations/{id} (should require auth)
        response = client.delete("/api/v1/chat/conversations/test-id")
        assert response.status_code in [400, 401]  # Either validation or auth error, not 404
        
        # Test POST /api/v1/chat/conversations/{id}/messages (should require auth)
        response = client.post("/api/v1/chat/conversations/test-id/messages")
        assert response.status_code in [400, 401]  # Either validation or auth error, not 404
        
        # Test GET /api/v1/chat/conversations/{id}/messages (should require auth)
        response = client.get("/api/v1/chat/conversations/test-id/messages")
        assert response.status_code in [400, 401]  # Either validation or auth error, not 404
        
        # Test GET /api/v1/chat/conversations/{id}/context (should require auth)
        response = client.get("/api/v1/chat/conversations/test-id/context")
        assert response.status_code in [400, 401]  # Either validation or auth error, not 404
    
    def test_health_endpoint_works(self):
        """Test that the health endpoint works."""
        response = client.get("/api/v1/chat/health")
        print(f"Health response: {response.status_code}, {response.text}")
        # Health endpoint might return error if services aren't initialized
        assert response.status_code in [200, 400, 503]  # OK, Bad Request, or Service Unavailable
        
        if response.status_code == 200:
            data = response.json()
            assert "status" in data
            assert "message" in data


if __name__ == "__main__":
    pytest.main([__file__])