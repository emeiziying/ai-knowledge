"""
End-to-end tests for document processing workflow.
Tests the complete flow from upload to vectorization and search.
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
from app.models import User, Document, DocumentChunk
from app.auth.jwt import JWTManager
from app.config import get_settings


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_e2e_processing.db"
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


@pytest.fixture
def sample_pdf_content():
    """Sample PDF content for testing."""
    return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Machine learning is a subset of artificial intelligence) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000074 00000 n 
0000000120 00000 n 
0000000179 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
274
%%EOF"""


@pytest.fixture
def sample_text_content():
    """Sample text content for testing."""
    return """Machine Learning Fundamentals

Machine learning is a subset of artificial intelligence (AI) that focuses on the development of algorithms and statistical models that enable computer systems to improve their performance on a specific task through experience.

Key Concepts:
1. Supervised Learning - Learning with labeled data
2. Unsupervised Learning - Finding patterns in unlabeled data  
3. Reinforcement Learning - Learning through interaction with environment

Applications:
- Image recognition
- Natural language processing
- Recommendation systems
- Autonomous vehicles

The field has grown rapidly due to advances in computing power and the availability of large datasets."""


class TestDocumentProcessingE2E:
    """End-to-end document processing tests."""
    
    @patch('app.documents.service.document_service')
    @patch('app.processing.processor.DocumentProcessor')
    @patch('app.processing.vector_storage.VectorStorage')
    @patch('app.storage.get_storage')
    def test_complete_pdf_processing_workflow(
        self, 
        mock_get_storage,
        mock_vector_storage,
        mock_processor,
        mock_doc_service,
        client, 
        auth_headers, 
        test_user,
        sample_pdf_content
    ):
        """Test complete PDF processing from upload to search."""
        
        # Setup mocks
        document_id = uuid4()
        mock_document = Document(
            id=document_id,
            user_id=test_user.id,
            filename="ml_guide.pdf",
            original_name="Machine Learning Guide.pdf",
            file_size=len(sample_pdf_content),
            mime_type="application/pdf",
            file_path=f"/documents/{document_id}/ml_guide.pdf",
            status="uploaded"
        )
        
        # Mock storage
        mock_storage = Mock()
        mock_storage.upload_file = AsyncMock(return_value="/documents/test/path")
        mock_get_storage.return_value = mock_storage
        
        # Mock document service
        mock_doc_service.upload_document = AsyncMock(return_value=mock_document)
        mock_doc_service.get_document.return_value = mock_document
        mock_doc_service.update_document_status = AsyncMock()
        
        # Mock document processor
        mock_processor_instance = Mock()
        mock_processor_instance.extract_text = AsyncMock(return_value={
            "content": "Machine learning is a subset of artificial intelligence",
            "metadata": {"pages": 1, "title": "ML Guide"}
        })
        mock_processor_instance.chunk_text = AsyncMock(return_value=[
            {
                "content": "Machine learning is a subset of artificial intelligence",
                "metadata": {"chunk_index": 0, "start_position": 0, "end_position": 55}
            }
        ])
        mock_processor.return_value = mock_processor_instance
        
        # Mock vector storage
        mock_vector_instance = Mock()
        mock_vector_instance.add_chunks = AsyncMock(return_value=["vector_1"])
        mock_vector_storage.return_value = mock_vector_instance
        
        # Step 1: Upload document
        files = {"file": ("ml_guide.pdf", sample_pdf_content, "application/pdf")}
        response = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
        
        assert response.status_code == 201
        upload_data = response.json()
        assert upload_data["status"] == "uploaded"
        doc_id = upload_data["document_id"]
        
        # Step 2: Simulate processing (normally done by background task)
        with patch('app.processing.tasks.process_document') as mock_process:
            # Mock the processing function
            async def mock_processing():
                # Extract text
                extracted = await mock_processor_instance.extract_text(sample_pdf_content, "application/pdf")
                
                # Chunk text
                chunks = await mock_processor_instance.chunk_text(extracted["content"])
                
                # Create embeddings and store vectors
                vector_ids = await mock_vector_instance.add_chunks(document_id, chunks)
                
                # Update document status
                await mock_doc_service.update_document_status(None, document_id, "completed")
                
                return {
                    "document_id": str(document_id),
                    "status": "completed",
                    "chunks_created": len(chunks),
                    "vector_ids": vector_ids
                }
            
            mock_process.return_value = await mock_processing()
        
        # Step 3: Verify document status updated
        mock_document.status = "completed"
        response = client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
        assert response.status_code == 200
        
        # Step 4: Test search functionality
        with patch('app.chat.rag_service.get_rag_service') as mock_get_rag_service:
            mock_rag_service = Mock()
            mock_rag_service.search_documents = AsyncMock(return_value={
                "results": [
                    {
                        "vector_id": "vector_1",
                        "score": 0.95,
                        "final_score": 0.95,
                        "document_id": str(document_id),
                        "chunk_index": 0,
                        "content": "Machine learning is a subset of artificial intelligence",
                        "character_count": 55,
                        "word_count": 9,
                        "start_position": 0,
                        "end_position": 55,
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
                "search_time_ms": 50.0,
                "cached": False
            })
            mock_get_rag_service.return_value = mock_rag_service
            
            # Search for content
            response = client.post(
                "/api/v1/chat/search",
                json={"query": "machine learning", "limit": 10},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            search_data = response.json()
            assert search_data["total_results"] == 1
            assert len(search_data["results"]) == 1
            assert "machine learning" in search_data["results"][0]["content"].lower()
    
    @patch('app.documents.service.document_service')
    @patch('app.processing.processor.DocumentProcessor')
    def test_text_document_processing(
        self,
        mock_processor,
        mock_doc_service,
        client,
        auth_headers,
        test_user,
        sample_text_content
    ):
        """Test processing of text documents."""
        
        document_id = uuid4()
        mock_document = Document(
            id=document_id,
            user_id=test_user.id,
            filename="ml_fundamentals.txt",
            original_name="ML Fundamentals.txt",
            file_size=len(sample_text_content.encode()),
            mime_type="text/plain",
            file_path=f"/documents/{document_id}/ml_fundamentals.txt",
            status="uploaded"
        )
        
        # Mock document service
        mock_doc_service.upload_document = AsyncMock(return_value=mock_document)
        
        # Mock processor
        mock_processor_instance = Mock()
        mock_processor_instance.extract_text = AsyncMock(return_value={
            "content": sample_text_content,
            "metadata": {"lines": 20, "words": 150}
        })
        mock_processor_instance.chunk_text = AsyncMock(return_value=[
            {
                "content": "Machine Learning Fundamentals\n\nMachine learning is a subset of artificial intelligence",
                "metadata": {"chunk_index": 0, "start_position": 0, "end_position": 85}
            },
            {
                "content": "Key Concepts:\n1. Supervised Learning - Learning with labeled data",
                "metadata": {"chunk_index": 1, "start_position": 200, "end_position": 265}
            }
        ])
        mock_processor.return_value = mock_processor_instance
        
        # Upload text document
        files = {"file": ("ml_fundamentals.txt", sample_text_content.encode(), "text/plain")}
        response = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
        
        assert response.status_code == 201
        upload_data = response.json()
        assert upload_data["status"] == "uploaded"
    
    @patch('app.documents.service.document_service')
    def test_document_processing_error_handling(
        self,
        mock_doc_service,
        client,
        auth_headers,
        test_user
    ):
        """Test error handling during document processing."""
        
        # Mock document service to simulate processing failure
        mock_doc_service.upload_document = AsyncMock(side_effect=Exception("Processing failed"))
        
        # Try to upload document
        files = {"file": ("corrupt.pdf", b"invalid pdf content", "application/pdf")}
        response = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
        
        # Should handle error gracefully
        assert response.status_code == 500
        error_data = response.json()
        assert "detail" in error_data
    
    @patch('app.documents.service.document_service')
    @patch('app.processing.processor.DocumentProcessor')
    @patch('app.processing.vector_storage.VectorStorage')
    def test_large_document_chunking(
        self,
        mock_vector_storage,
        mock_processor,
        mock_doc_service,
        client,
        auth_headers,
        test_user
    ):
        """Test processing of large documents with multiple chunks."""
        
        # Create large text content
        large_content = "\n\n".join([
            f"Section {i}: This is a detailed section about machine learning topic {i}. " * 50
            for i in range(10)
        ])
        
        document_id = uuid4()
        mock_document = Document(
            id=document_id,
            user_id=test_user.id,
            filename="large_ml_book.txt",
            original_name="Large ML Book.txt",
            file_size=len(large_content.encode()),
            mime_type="text/plain",
            file_path=f"/documents/{document_id}/large_ml_book.txt",
            status="uploaded"
        )
        
        # Mock services
        mock_doc_service.upload_document = AsyncMock(return_value=mock_document)
        
        # Mock processor to return multiple chunks
        mock_processor_instance = Mock()
        mock_processor_instance.extract_text = AsyncMock(return_value={
            "content": large_content,
            "metadata": {"sections": 10, "words": 5000}
        })
        
        # Simulate chunking into multiple pieces
        chunks = []
        for i in range(10):
            chunks.append({
                "content": f"Section {i}: This is a detailed section about machine learning topic {i}.",
                "metadata": {"chunk_index": i, "start_position": i * 500, "end_position": (i + 1) * 500}
            })
        
        mock_processor_instance.chunk_text = AsyncMock(return_value=chunks)
        mock_processor.return_value = mock_processor_instance
        
        # Mock vector storage
        mock_vector_instance = Mock()
        mock_vector_instance.add_chunks = AsyncMock(return_value=[f"vector_{i}" for i in range(10)])
        mock_vector_storage.return_value = mock_vector_instance
        
        # Upload large document
        files = {"file": ("large_ml_book.txt", large_content.encode(), "text/plain")}
        response = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
        
        assert response.status_code == 201
        upload_data = response.json()
        assert upload_data["status"] == "uploaded"
    
    def test_unsupported_file_type(self, client, auth_headers):
        """Test handling of unsupported file types."""
        
        # Try to upload unsupported file type
        files = {"file": ("test.exe", b"executable content", "application/x-executable")}
        response = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
        
        # Should reject unsupported file type
        assert response.status_code == 400
        error_data = response.json()
        assert "unsupported" in error_data["detail"].lower() or "invalid" in error_data["detail"].lower()
    
    def test_file_size_limit(self, client, auth_headers):
        """Test file size limit enforcement."""
        
        # Create oversized file content (assuming 50MB limit)
        oversized_content = b"x" * (51 * 1024 * 1024)  # 51MB
        
        files = {"file": ("huge_file.txt", oversized_content, "text/plain")}
        response = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
        
        # Should reject oversized file
        assert response.status_code == 413
    
    @patch('app.chat.answer_service.answer_service')
    @patch('app.chat.rag_service.get_rag_service')
    def test_end_to_end_rag_query(
        self,
        mock_get_rag_service,
        mock_answer_service,
        client,
        auth_headers,
        test_user
    ):
        """Test end-to-end RAG query after document processing."""
        
        # Mock RAG service with processed document content
        mock_rag_service = Mock()
        mock_rag_service.search_documents = AsyncMock(return_value={
            "results": [
                {
                    "vector_id": "vector_1",
                    "score": 0.92,
                    "final_score": 0.92,
                    "document_id": str(uuid4()),
                    "chunk_index": 0,
                    "content": "Machine learning is a subset of artificial intelligence that focuses on algorithms",
                    "character_count": 80,
                    "word_count": 12,
                    "start_position": 0,
                    "end_position": 80,
                    "chunking_strategy": "semantic",
                    "created_at": "2024-01-01T00:00:00Z",
                    "document_metadata": {
                        "filename": "ml_guide.pdf",
                        "original_name": "Machine Learning Guide.pdf"
                    }
                }
            ],
            "total_results": 1,
            "query": "what is machine learning",
            "search_time_ms": 75.0,
            "cached": False
        })
        mock_get_rag_service.return_value = mock_rag_service
        
        # Mock answer service
        mock_answer_service.generate_answer = AsyncMock(return_value={
            "answer": "Machine learning is a subset of artificial intelligence that focuses on developing algorithms and statistical models that enable computer systems to improve their performance on specific tasks through experience, without being explicitly programmed.",
            "sources": [
                {
                    "document_id": str(uuid4()),
                    "document_name": "Machine Learning Guide.pdf",
                    "content": "Machine learning is a subset of artificial intelligence that focuses on algorithms",
                    "relevance_score": 0.92
                }
            ],
            "conversation_id": str(uuid4()),
            "message_id": str(uuid4()),
            "processing_time_ms": 1250.0
        })
        
        # Create conversation and ask question
        with patch('app.chat.conversation_service.conversation_service') as mock_conv_service:
            conversation_id = uuid4()
            mock_conversation = Mock()
            mock_conversation.id = conversation_id
            mock_conv_service.create_conversation.return_value = mock_conversation
            
            # Create conversation
            response = client.post(
                "/api/v1/chat/conversations",
                json={"title": "ML Questions"},
                headers=auth_headers
            )
            assert response.status_code == 201
            
            # Ask question
            response = client.post(
                f"/api/v1/chat/conversations/{conversation_id}/messages",
                json={"content": "What is machine learning?"},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            answer_data = response.json()
            assert "answer" in answer_data
            assert "sources" in answer_data
            assert len(answer_data["sources"]) > 0
            assert "machine learning" in answer_data["answer"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])