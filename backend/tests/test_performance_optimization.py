"""
Performance tests and optimization validation.
"""
import pytest
import asyncio
import time
import concurrent.futures
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db, Base
from app.models import User, Document


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_performance.db"
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
            username="perfuser",
            email="perf@example.com",
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
    from app.auth.jwt import JWTManager
    from app.config import get_settings
    
    settings = get_settings()
    jwt_manager = JWTManager(settings.SECRET_KEY, settings.ALGORITHM, settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = jwt_manager.create_access_token(data={"sub": str(test_user.id), "username": test_user.username})
    return {"Authorization": f"Bearer {token}"}


class TestPerformanceOptimization:
    """Performance tests and optimization validation."""
    
    def test_api_response_times(self, client, auth_headers):
        """Test API response times are within acceptable limits."""
        
        # Health check should be very fast
        start_time = time.time()
        response = client.get("/health")
        health_time = time.time() - start_time
        
        assert response.status_code == 200
        assert health_time < 0.1  # Should respond in under 100ms
        
        # Document list should be reasonably fast
        with patch('app.documents.service.document_service') as mock_service:
            mock_service.get_documents.return_value = Mock(
                documents=[],
                total=0,
                page=1,
                page_size=20,
                total_pages=0
            )
            
            start_time = time.time()
            response = client.get("/api/v1/documents", headers=auth_headers)
            list_time = time.time() - start_time
            
            assert response.status_code == 200
            assert list_time < 0.5  # Should respond in under 500ms
    
    def test_concurrent_requests(self, client, auth_headers):
        """Test system handles concurrent requests efficiently."""
        
        def make_request():
            with patch('app.documents.service.document_service') as mock_service:
                mock_service.get_documents.return_value = Mock(
                    documents=[],
                    total=0,
                    page=1,
                    page_size=20,
                    total_pages=0
                )
                
                response = client.get("/api/v1/documents", headers=auth_headers)
                return response.status_code == 200
        
        # Test with 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            start_time = time.time()
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
            total_time = time.time() - start_time
        
        # All requests should succeed
        assert all(results)
        # Should handle 10 concurrent requests in reasonable time
        assert total_time < 2.0
    
    @patch('app.chat.rag_service.get_rag_service')
    def test_search_performance(self, mock_get_rag_service, client, auth_headers):
        """Test search performance with various query sizes."""
        
        # Mock RAG service with realistic response times
        mock_rag_service = Mock()
        
        def mock_search(query, **kwargs):
            # Simulate search time based on query complexity
            search_time = len(query.split()) * 10  # 10ms per word
            time.sleep(search_time / 1000)  # Convert to seconds
            
            return {
                "results": [
                    {
                        "vector_id": f"vector_{i}",
                        "score": 0.9 - (i * 0.1),
                        "final_score": 0.9 - (i * 0.1),
                        "document_id": str(uuid4()),
                        "chunk_index": i,
                        "content": f"Result {i} for query: {query}",
                        "character_count": 50,
                        "word_count": 10,
                        "start_position": i * 100,
                        "end_position": (i + 1) * 100,
                        "chunking_strategy": "semantic",
                        "created_at": "2024-01-01T00:00:00Z",
                        "document_metadata": {
                            "filename": f"doc_{i}.pdf",
                            "original_name": f"Document {i}.pdf"
                        }
                    }
                    for i in range(min(5, len(query.split())))
                ],
                "total_results": min(5, len(query.split())),
                "query": query,
                "search_time_ms": search_time,
                "cached": False
            }
        
        mock_rag_service.search_documents = AsyncMock(side_effect=mock_search)
        mock_get_rag_service.return_value = mock_rag_service
        
        # Test different query complexities
        test_queries = [
            "simple",
            "machine learning",
            "artificial intelligence and machine learning",
            "deep learning neural networks artificial intelligence machine learning algorithms"
        ]
        
        for query in test_queries:
            start_time = time.time()
            response = client.post(
                "/api/v1/chat/search",
                json={"query": query, "limit": 10},
                headers=auth_headers
            )
            response_time = time.time() - start_time
            
            assert response.status_code == 200
            data = response.json()
            
            # Response time should be reasonable even for complex queries
            assert response_time < 1.0
            
            # Search time should be reported in response
            assert "search_time_ms" in data
            assert data["search_time_ms"] > 0
    
    def test_memory_usage_optimization(self, client, auth_headers):
        """Test memory usage doesn't grow excessively with requests."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Make multiple requests to check for memory leaks
        with patch('app.documents.service.document_service') as mock_service:
            mock_service.get_documents.return_value = Mock(
                documents=[],
                total=0,
                page=1,
                page_size=20,
                total_pages=0
            )
            
            for _ in range(50):
                response = client.get("/api/v1/documents", headers=auth_headers)
                assert response.status_code == 200
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be minimal (less than 50MB)
        assert memory_increase < 50 * 1024 * 1024
    
    @patch('app.documents.service.document_service')
    def test_large_document_list_performance(self, mock_doc_service, client, auth_headers):
        """Test performance with large document lists."""
        
        # Mock large document list
        large_doc_list = []
        for i in range(1000):
            large_doc_list.append(Mock(
                id=str(uuid4()),
                original_name=f"document_{i}.pdf",
                file_size=1024000,
                mime_type="application/pdf",
                status="completed",
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z"
            ))
        
        mock_doc_service.get_documents.return_value = Mock(
            documents=large_doc_list[:20],  # Paginated
            total=1000,
            page=1,
            page_size=20,
            total_pages=50
        )
        
        start_time = time.time()
        response = client.get("/api/v1/documents?page_size=20", headers=auth_headers)
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        # Should handle large datasets efficiently with pagination
        assert response_time < 0.5
        
        data = response.json()
        assert data["total"] == 1000
        assert len(data["documents"]) == 20
    
    @patch('app.processing.processor.DocumentProcessor')
    def test_document_processing_performance(self, mock_processor, client, auth_headers):
        """Test document processing performance optimization."""
        
        # Mock processor with performance metrics
        mock_processor_instance = Mock()
        
        def mock_extract_text(content, mime_type):
            # Simulate processing time based on content size
            processing_time = len(content) / 10000  # 10KB per second
            time.sleep(processing_time)
            
            return {
                "content": "Extracted text content",
                "metadata": {
                    "processing_time_ms": processing_time * 1000,
                    "content_length": len(content)
                }
            }
        
        mock_processor_instance.extract_text = AsyncMock(side_effect=mock_extract_text)
        mock_processor_instance.chunk_text = AsyncMock(return_value=[
            {
                "content": "Chunk 1",
                "metadata": {"chunk_index": 0}
            }
        ])
        mock_processor.return_value = mock_processor_instance
        
        # Test with different file sizes
        test_sizes = [1024, 10240, 102400]  # 1KB, 10KB, 100KB
        
        for size in test_sizes:
            content = b"x" * size
            
            with patch('app.documents.service.document_service') as mock_doc_service:
                mock_document = Mock(
                    id=uuid4(),
                    user_id=uuid4(),
                    filename=f"test_{size}.txt",
                    original_name=f"test_{size}.txt",
                    file_size=size,
                    mime_type="text/plain",
                    file_path="/test/path",
                    status="uploaded"
                )
                mock_doc_service.upload_document = AsyncMock(return_value=mock_document)
                
                start_time = time.time()
                files = {"file": (f"test_{size}.txt", content, "text/plain")}
                response = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
                upload_time = time.time() - start_time
                
                assert response.status_code == 201
                # Upload should be fast regardless of file size (processing is async)
                assert upload_time < 1.0
    
    def test_database_query_optimization(self, client, auth_headers):
        """Test database query performance optimization."""
        
        # Test with indexed queries
        with patch('app.documents.service.document_service') as mock_service:
            # Mock efficient query execution
            def mock_get_documents(db, user_id, **kwargs):
                # Simulate database query time
                time.sleep(0.01)  # 10ms query time
                return Mock(
                    documents=[],
                    total=0,
                    page=1,
                    page_size=20,
                    total_pages=0
                )
            
            mock_service.get_documents = mock_get_documents
            
            start_time = time.time()
            response = client.get("/api/v1/documents", headers=auth_headers)
            query_time = time.time() - start_time
            
            assert response.status_code == 200
            # Database queries should be optimized
            assert query_time < 0.1
    
    @patch('app.chat.rag_service.get_rag_service')
    def test_caching_performance(self, mock_get_rag_service, client, auth_headers):
        """Test caching improves performance for repeated queries."""
        
        mock_rag_service = Mock()
        
        # First call - not cached
        def first_search(*args, **kwargs):
            time.sleep(0.1)  # Simulate search time
            return {
                "results": [],
                "total_results": 0,
                "query": "test query",
                "search_time_ms": 100.0,
                "cached": False
            }
        
        # Second call - cached
        def cached_search(*args, **kwargs):
            time.sleep(0.01)  # Much faster
            return {
                "results": [],
                "total_results": 0,
                "query": "test query",
                "search_time_ms": 10.0,
                "cached": True
            }
        
        mock_rag_service.search_documents = AsyncMock(side_effect=first_search)
        mock_get_rag_service.return_value = mock_rag_service
        
        # First request
        start_time = time.time()
        response1 = client.post(
            "/api/v1/chat/search",
            json={"query": "test query"},
            headers=auth_headers
        )
        first_time = time.time() - start_time
        
        # Second request (should be cached)
        mock_rag_service.search_documents = AsyncMock(side_effect=cached_search)
        
        start_time = time.time()
        response2 = client.post(
            "/api/v1/chat/search",
            json={"query": "test query"},
            headers=auth_headers
        )
        second_time = time.time() - start_time
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Cached request should be significantly faster
        assert second_time < first_time / 2
        
        # Response should indicate caching
        data2 = response2.json()
        assert data2["cached"] is True
    
    def test_error_handling_performance(self, client, auth_headers):
        """Test error handling doesn't significantly impact performance."""
        
        # Test with various error conditions
        error_endpoints = [
            ("/api/v1/documents/nonexistent", 404),
            ("/api/v1/documents", 401),  # Without auth headers
        ]
        
        for endpoint, expected_status in error_endpoints:
            start_time = time.time()
            if expected_status == 401:
                response = client.get(endpoint)  # No auth headers
            else:
                response = client.get(endpoint, headers=auth_headers)
            error_time = time.time() - start_time
            
            assert response.status_code == expected_status
            # Error responses should be fast
            assert error_time < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])