"""
Tests for document vectorization functionality.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from typing import List, Dict, Any

from app.processing.chunking import (
    SemanticChunker, 
    ChunkingConfig, 
    ChunkingStrategy,
    create_semantic_chunks
)
from app.processing.embeddings import (
    SentenceTransformersEmbedding,
    EmbeddingConfig,
    EmbeddingProvider,
    DocumentVectorizer,
    EmbeddingManager
)
from app.processing.vector_storage import VectorStorageService
from app.processing.tasks import DocumentVectorizationTask


class TestSemanticChunker:
    """Test semantic chunking functionality."""
    
    def test_chunking_config_defaults(self):
        """Test default chunking configuration."""
        config = ChunkingConfig()
        assert config.strategy == ChunkingStrategy.HYBRID
        assert config.chunk_size == 1000
        assert config.chunk_overlap == 200
        assert config.preserve_sentences is True
        assert config.preserve_paragraphs is True
    
    def test_fixed_size_chunking(self):
        """Test fixed size chunking strategy."""
        config = ChunkingConfig(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=100,
            chunk_overlap=20
        )
        chunker = SemanticChunker(config)
        
        content = "This is a test document. " * 20  # ~500 characters
        chunks = chunker.chunk_document(content)
        
        assert len(chunks) > 0
        assert all(len(chunk["content"]) <= 120 for chunk in chunks)  # Allow some overlap
        assert all("chunk_index" in chunk["metadata"] for chunk in chunks)
    
    def test_semantic_chunking_with_paragraphs(self):
        """Test semantic chunking with paragraph structure."""
        config = ChunkingConfig(
            strategy=ChunkingStrategy.SEMANTIC,
            chunk_size=200,
            max_chunk_size=400
        )
        chunker = SemanticChunker(config)
        
        content = """This is the first paragraph. It contains some important information.

This is the second paragraph. It has different content and should be preserved.

This is the third paragraph. It continues the document structure."""
        
        chunks = chunker.chunk_document(content)
        
        assert len(chunks) > 0
        # Check that paragraph structure is somewhat preserved
        assert any("\n\n" in chunk["content"] for chunk in chunks)
    
    def test_structure_aware_chunking(self):
        """Test structure-aware chunking with headings."""
        config = ChunkingConfig(strategy=ChunkingStrategy.STRUCTURE_AWARE)
        chunker = SemanticChunker(config)
        
        content = """# Introduction
This is the introduction section.

## Background
This section provides background information.

### Details
More detailed information here.

# Conclusion
This is the conclusion."""
        
        structure_metadata = {
            "has_headings": True,
            "structure_markers": {
                "headings": [
                    {"line": 0, "level": 1, "title": "Introduction", "position": 0},
                    {"line": 2, "level": 2, "title": "Background", "position": 50},
                    {"line": 4, "level": 3, "title": "Details", "position": 100},
                    {"line": 6, "level": 1, "title": "Conclusion", "position": 150}
                ]
            }
        }
        
        chunks = chunker.chunk_document(content, structure_metadata)
        
        assert len(chunks) > 0
        # Check that some chunks contain headings
        assert any("#" in chunk["content"] for chunk in chunks)
    
    def test_empty_content_handling(self):
        """Test handling of empty content."""
        chunker = SemanticChunker()
        
        chunks = chunker.chunk_document("")
        assert chunks == []
        
        chunks = chunker.chunk_document("   \n\n   ")
        assert chunks == []
    
    def test_create_semantic_chunks_function(self):
        """Test the convenience function for creating semantic chunks."""
        content = "This is a test document with multiple sentences. Each sentence should be preserved properly."
        
        chunks = create_semantic_chunks(content)
        
        assert len(chunks) > 0
        assert all("content" in chunk for chunk in chunks)
        assert all("metadata" in chunk for chunk in chunks)


class TestEmbeddingService:
    """Test embedding service functionality."""
    
    @pytest.mark.asyncio
    async def test_sentence_transformers_embedding_config(self):
        """Test SentenceTransformers embedding configuration."""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.SENTENCE_TRANSFORMERS,
            model_name="all-MiniLM-L6-v2",
            batch_size=16
        )
        
        assert config.provider == EmbeddingProvider.SENTENCE_TRANSFORMERS
        assert config.model_name == "all-MiniLM-L6-v2"
        assert config.batch_size == 16
    
    @pytest.mark.asyncio
    async def test_embedding_service_initialization(self):
        """Test embedding service initialization."""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.SENTENCE_TRANSFORMERS,
            model_name="all-MiniLM-L6-v2"
        )
        
        service = SentenceTransformersEmbedding(config)
        
        # Mock the model loading to avoid downloading
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model.encode.return_value = [[0.1, 0.2, 0.3]]
            mock_st.return_value = mock_model
            
            success = await service.initialize()
            assert success is True
            assert service.model is not None
    
    @pytest.mark.asyncio
    async def test_document_vectorizer(self):
        """Test document vectorizer functionality."""
        # Mock embedding service
        mock_service = Mock()
        mock_service.encode_texts = AsyncMock(return_value=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
        mock_service.config = Mock()
        mock_service.config.model_name = "test-model"
        
        vectorizer = DocumentVectorizer(mock_service)
        
        chunks = [
            {
                "content": "First chunk content",
                "metadata": {"chunk_index": 0}
            },
            {
                "content": "Second chunk content", 
                "metadata": {"chunk_index": 1}
            }
        ]
        
        vectorized_chunks = await vectorizer.vectorize_chunks(chunks)
        
        assert len(vectorized_chunks) == 2
        assert all("vector" in chunk for chunk in vectorized_chunks)
        assert vectorized_chunks[0]["vector"] == [0.1, 0.2, 0.3]
        assert vectorized_chunks[1]["vector"] == [0.4, 0.5, 0.6]
    
    @pytest.mark.asyncio
    async def test_embedding_manager(self):
        """Test embedding manager functionality."""
        manager = EmbeddingManager()
        
        # Mock successful service initialization
        with patch('app.processing.embeddings.EmbeddingServiceFactory.create_service') as mock_factory:
            mock_service = Mock()
            mock_service.initialize = AsyncMock(return_value=True)
            mock_factory.return_value = mock_service
            
            config = EmbeddingConfig()
            success = await manager.add_service("test", config)
            
            assert success is True
            assert "test" in manager.services
            assert manager.default_service == "test"


class TestVectorStorage:
    """Test vector storage functionality."""
    
    @pytest.mark.asyncio
    async def test_vector_storage_service_initialization(self):
        """Test vector storage service initialization."""
        service = VectorStorageService()
        
        # Mock vector store
        service.vector_store = Mock()
        service.vector_store.add_vectors = AsyncMock(return_value=True)
        
        assert service.vector_store is not None
    
    @pytest.mark.asyncio
    async def test_store_document_vectors(self):
        """Test storing document vectors."""
        service = VectorStorageService()
        
        # Mock dependencies
        service.vector_store = Mock()
        service.vector_store.add_vectors = AsyncMock(return_value=True)
        
        mock_db = Mock()
        mock_db.add = Mock()
        mock_db.commit = Mock()
        
        vectorized_chunks = [
            {
                "content": "Test content",
                "vector": [0.1, 0.2, 0.3],
                "metadata": {
                    "chunk_index": 0,
                    "character_count": 12,
                    "word_count": 2,
                    "start_position": 0,
                    "end_position": 12,
                    "chunking_strategy": "hybrid"
                }
            }
        ]
        
        result = await service.store_document_vectors(
            mock_db, "test-doc-id", vectorized_chunks
        )
        
        assert result["success"] is True
        assert result["vectors_stored"] == 1
        assert result["document_id"] == "test-doc-id"
    
    @pytest.mark.asyncio
    async def test_search_similar_chunks(self):
        """Test searching for similar chunks."""
        service = VectorStorageService()
        
        # Mock vector store search
        service.vector_store = Mock()
        service.vector_store.search_similar = AsyncMock(return_value=[
            {
                "id": "vector-1",
                "score": 0.95,
                "payload": {
                    "document_id": "doc-1",
                    "chunk_index": 0,
                    "content": "Similar content",
                    "character_count": 15,
                    "word_count": 2,
                    "start_position": 0,
                    "end_position": 15,
                    "chunking_strategy": "hybrid",
                    "created_at": "2024-01-01T00:00:00Z"
                }
            }
        ])
        
        query_vector = [0.1, 0.2, 0.3]
        results = await service.search_similar_chunks(query_vector)
        
        assert len(results) == 1
        assert results[0]["vector_id"] == "vector-1"
        assert results[0]["score"] == 0.95
        assert results[0]["content"] == "Similar content"


class TestDocumentVectorizationTask:
    """Test document vectorization task functionality."""
    
    @pytest.mark.asyncio
    async def test_task_initialization(self):
        """Test task processor initialization."""
        task = DocumentVectorizationTask()
        
        # Mock dependencies
        with patch('app.processing.tasks.initialize_default_embedding_service') as mock_embed:
            with patch('app.processing.tasks.initialize_vector_storage') as mock_vector:
                with patch('app.processing.tasks.get_default_vectorizer') as mock_vectorizer:
                    mock_embed.return_value = True
                    mock_vector.return_value = True
                    mock_vectorizer.return_value = Mock()
                    
                    success = await task.initialize()
                    assert success is True
                    assert task.initialized is True
    
    @pytest.mark.asyncio
    async def test_process_document_vectorization_success(self):
        """Test successful document vectorization process."""
        task = DocumentVectorizationTask()
        task.initialized = True
        
        # Mock all dependencies
        task.processor = Mock()
        task.vectorizer = Mock()
        task.vectorizer.vectorize_chunks = AsyncMock(return_value=[
            {
                "content": "Test content",
                "vector": [0.1, 0.2, 0.3],
                "metadata": {"chunk_index": 0}
            }
        ])
        
        with patch('app.processing.tasks.get_db') as mock_get_db:
            with patch('app.processing.tasks.storage') as mock_storage:
                with patch('app.processing.tasks.vector_storage_service') as mock_vector_service:
                    # Mock database
                    mock_db = Mock()
                    mock_document = Mock()
                    mock_document.id = "test-doc-id"
                    mock_document.original_name = "test.pdf"
                    mock_document.mime_type = "application/pdf"
                    mock_document.file_path = "test/path"
                    mock_db.query.return_value.filter.return_value.first.return_value = mock_document
                    mock_get_db.return_value = iter([mock_db])
                    
                    # Mock storage
                    mock_storage.download_file = AsyncMock(return_value=b"test content")
                    
                    # Mock processor
                    task.processor.process_document.return_value = {
                        "status": "completed",
                        "content": "Test document content",
                        "metadata": {"test": "metadata"},
                        "processing_stats": {"chunks": 1}
                    }
                    
                    # Mock vector storage
                    mock_vector_service.store_document_vectors = AsyncMock(return_value={
                        "success": True,
                        "vectors_stored": 1,
                        "vector_ids": ["vec-1"]
                    })
                    
                    # Mock chunking
                    with patch('app.processing.tasks.create_semantic_chunks') as mock_chunks:
                        mock_chunks.return_value = [
                            {
                                "content": "Test content",
                                "metadata": {"chunk_index": 0}
                            }
                        ]
                        
                        result = await task.process_document_vectorization("test-doc-id")
                        
                        assert result["status"] == "completed"
                        assert "vectorization" in result["steps_completed"]
                        assert "vector_storage" in result["steps_completed"]


class TestIntegration:
    """Integration tests for the complete vectorization pipeline."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_vectorization_pipeline(self):
        """Test the complete vectorization pipeline from chunking to storage."""
        # Test content
        content = """# Introduction
This is a test document for the vectorization pipeline.

## Section 1
This section contains important information about the system.

## Section 2  
This section provides additional details and examples."""
        
        # Step 1: Chunking
        chunks = create_semantic_chunks(content)
        assert len(chunks) > 0
        
        # Step 2: Mock vectorization
        mock_service = Mock()
        mock_service.encode_texts = AsyncMock(return_value=[
            [0.1, 0.2, 0.3] for _ in chunks
        ])
        mock_service.config = Mock()
        mock_service.config.model_name = "test-model"
        
        vectorizer = DocumentVectorizer(mock_service)
        vectorized_chunks = await vectorizer.vectorize_chunks(chunks)
        
        assert len(vectorized_chunks) == len(chunks)
        assert all("vector" in chunk for chunk in vectorized_chunks)
        
        # Step 3: Mock storage
        storage_service = VectorStorageService()
        storage_service.vector_store = Mock()
        storage_service.vector_store.add_vectors = AsyncMock(return_value=True)
        
        mock_db = Mock()
        mock_db.add = Mock()
        mock_db.commit = Mock()
        
        result = await storage_service.store_document_vectors(
            mock_db, "test-doc-id", vectorized_chunks
        )
        
        assert result["success"] is True
        assert result["vectors_stored"] == len(vectorized_chunks)


if __name__ == "__main__":
    pytest.main([__file__])