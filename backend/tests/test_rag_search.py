"""
Tests for RAG query and semantic search functionality.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import List, Dict, Any

from app.chat.rag_service import (
    QueryVectorizer, SearchResultRanker, SearchCache, RAGQueryService
)
from app.chat.search_service import QueryAnalyzer, AdvancedSearchService
from app.chat.schemas import SearchFilter, SearchFilterType, SearchSortBy


class TestQueryVectorizer:
    """Test query vectorization functionality."""
    
    @pytest.fixture
    def mock_ai_service_manager(self):
        """Mock AI service manager."""
        manager = Mock()
        manager.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
        return manager
    
    @pytest.fixture
    def query_vectorizer(self, mock_ai_service_manager):
        """Create query vectorizer instance."""
        return QueryVectorizer(mock_ai_service_manager)
    
    @pytest.mark.asyncio
    async def test_vectorize_query_success(self, query_vectorizer):
        """Test successful query vectorization."""
        await query_vectorizer.initialize()
        
        query = "What is machine learning?"
        result = await query_vectorizer.vectorize_query(query)
        
        assert isinstance(result, list)
        assert len(result) == 3
        assert result == [0.1, 0.2, 0.3]
    
    @pytest.mark.asyncio
    async def test_vectorize_query_preprocessing(self, query_vectorizer):
        """Test query preprocessing."""
        await query_vectorizer.initialize()
        
        # Test with extra whitespace
        query = "  What   is    machine learning?  "
        result = await query_vectorizer.vectorize_query(query)
        
        # Should still work and call the service with cleaned query
        assert isinstance(result, list)
        query_vectorizer.ai_service_manager.generate_embedding.assert_called_once()
        
        # Check that the query was cleaned
        called_args = query_vectorizer.ai_service_manager.generate_embedding.call_args[0]
        assert called_args[0] == "What is machine learning?"
    
    @pytest.mark.asyncio
    async def test_vectorize_query_long_text(self, query_vectorizer):
        """Test query vectorization with long text."""
        await query_vectorizer.initialize()
        
        # Create a very long query
        long_query = "What is machine learning? " * 100  # Very long query
        result = await query_vectorizer.vectorize_query(long_query)
        
        assert isinstance(result, list)
        
        # Check that the query was truncated
        called_args = query_vectorizer.ai_service_manager.generate_embedding.call_args[0]
        assert len(called_args[0]) <= 1000


class TestSearchResultRanker:
    """Test search result ranking and filtering."""
    
    @pytest.fixture
    def ranker(self):
        """Create search result ranker instance."""
        return SearchResultRanker()
    
    @pytest.fixture
    def sample_results(self):
        """Sample search results for testing."""
        return [
            {
                "vector_id": "1",
                "score": 0.9,
                "content": "Machine learning is a subset of artificial intelligence",
                "document_id": "doc1",
                "created_at": "2024-01-01T00:00:00Z"
            },
            {
                "vector_id": "2", 
                "score": 0.8,
                "content": "Deep learning uses neural networks",
                "document_id": "doc2",
                "created_at": "2024-01-02T00:00:00Z"
            },
            {
                "vector_id": "3",
                "score": 0.7,
                "content": "Machine learning algorithms learn from data",
                "document_id": "doc1",
                "created_at": "2024-01-03T00:00:00Z"
            }
        ]
    
    def test_rank_and_filter_basic(self, ranker, sample_results):
        """Test basic ranking and filtering."""
        query = "machine learning"
        result = ranker.rank_and_filter_results(sample_results, query)
        
        assert len(result) <= len(sample_results)
        assert all("final_score" in r for r in result)
        assert all("ranking_factors" in r for r in result)
        
        # Results should be sorted by final score
        scores = [r["final_score"] for r in result]
        assert scores == sorted(scores, reverse=True)
    
    def test_filter_by_score_threshold(self, ranker, sample_results):
        """Test filtering by minimum score threshold."""
        ranker.min_score_threshold = 0.85
        
        query = "machine learning"
        result = ranker.rank_and_filter_results(sample_results, query)
        
        # Only results with score >= 0.85 should remain
        assert all(r["score"] >= 0.85 for r in result)
        assert len(result) == 1  # Only the first result should pass
    
    def test_remove_duplicates(self, ranker):
        """Test duplicate removal."""
        # Create results with very similar content
        duplicate_results = [
            {
                "vector_id": "1",
                "score": 0.9,
                "content": "Machine learning is great",
                "document_id": "doc1"
            },
            {
                "vector_id": "2",
                "score": 0.8,
                "content": "Machine learning is great and useful",  # Very similar
                "document_id": "doc2"
            }
        ]
        
        ranker.diversity_threshold = 0.5  # Lower threshold for testing
        
        query = "machine learning"
        result = ranker.rank_and_filter_results(duplicate_results, query)
        
        # Should keep only the higher-scored result
        assert len(result) == 1
        assert result[0]["vector_id"] == "1"  # Higher score
    
    def test_keyword_bonus(self, ranker, sample_results):
        """Test keyword matching bonus."""
        query = "machine learning algorithms"
        result = ranker.rank_and_filter_results(sample_results, query)
        
        # Result with "algorithms" should get a bonus
        algorithms_result = next(r for r in result if "algorithms" in r["content"])
        
        # Check that keyword bonus was applied
        assert algorithms_result["ranking_factors"]["keyword_bonus"] > 0
        
        # All results should have "machine" and "learning" so they all get some bonus
        # But the algorithms result should have the highest bonus
        max_bonus = max(r["ranking_factors"]["keyword_bonus"] for r in result)
        assert algorithms_result["ranking_factors"]["keyword_bonus"] == max_bonus


class TestSearchCache:
    """Test search result caching."""
    
    @pytest.fixture
    def cache(self):
        """Create search cache instance."""
        return SearchCache()
    
    @pytest.mark.asyncio
    async def test_cache_key_generation(self, cache):
        """Test cache key generation."""
        query = "test query"
        user_id = "user123"
        filters = {"limit": 10}
        
        key1 = cache._generate_cache_key(query, user_id, filters)
        key2 = cache._generate_cache_key(query, user_id, filters)
        
        # Same parameters should generate same key
        assert key1 == key2
        
        # Different parameters should generate different keys
        key3 = cache._generate_cache_key("different query", user_id, filters)
        assert key1 != key3
    
    @pytest.mark.asyncio
    async def test_cache_without_redis(self, cache):
        """Test cache operations when Redis is not available."""
        # Don't initialize Redis connection
        cache.redis_client = None
        
        # Should not raise errors
        result = await cache.get_cached_results("test", "user123")
        assert result is None
        
        await cache.cache_results("test", [], "user123")
        # Should complete without error


class TestQueryAnalyzer:
    """Test query analysis functionality."""
    
    @pytest.fixture
    def analyzer(self):
        """Create query analyzer instance."""
        return QueryAnalyzer()
    
    def test_analyze_factual_query(self, analyzer):
        """Test analysis of factual queries."""
        query = "What is machine learning?"
        result = analyzer.analyze_query(query)
        
        assert result.original_query == query
        assert result.query_type == "factual"
        assert "machine" in result.key_terms
        assert "learning" in result.key_terms
        assert result.confidence > 0.5
    
    def test_analyze_procedural_query(self, analyzer):
        """Test analysis of procedural queries."""
        query = "How to implement machine learning?"
        result = analyzer.analyze_query(query)
        
        assert result.query_type == "procedural"
        assert result.intent == "learn_process"
        assert "implement" in result.key_terms
    
    def test_analyze_conceptual_query(self, analyzer):
        """Test analysis of conceptual queries."""
        query = "Why does machine learning work?"
        result = analyzer.analyze_query(query)
        
        assert result.query_type == "conceptual"
        assert "machine" in result.key_terms
        assert "learning" in result.key_terms
    
    def test_extract_key_terms(self, analyzer):
        """Test key term extraction."""
        query = "What is the difference between supervised and unsupervised learning?"
        result = analyzer.analyze_query(query)
        
        # Should extract meaningful terms and exclude stop words
        assert "difference" in result.key_terms
        assert "supervised" in result.key_terms
        assert "unsupervised" in result.key_terms
        assert "learning" in result.key_terms
        
        # Should not include stop words
        assert "the" not in result.key_terms
        assert "between" not in result.key_terms
        assert "and" not in result.key_terms


class TestRAGQueryService:
    """Test main RAG query service."""
    
    @pytest.fixture
    def mock_ai_service_manager(self):
        """Mock AI service manager."""
        manager = Mock()
        manager.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
        return manager
    
    @pytest.fixture
    def mock_vector_storage(self):
        """Mock vector storage service."""
        storage = Mock()
        storage.search_similar_chunks = AsyncMock(return_value=[
            {
                "vector_id": "1",
                "score": 0.9,
                "document_id": "doc1",
                "chunk_index": 0,
                "content": "Machine learning content",
                "character_count": 100,
                "word_count": 20,
                "start_position": 0,
                "end_position": 100,
                "chunking_strategy": "semantic",
                "created_at": "2024-01-01T00:00:00Z"
            }
        ])
        return storage
    
    @pytest.fixture
    def rag_service(self, mock_ai_service_manager):
        """Create RAG service instance."""
        service = RAGQueryService(mock_ai_service_manager)
        return service
    
    @pytest.mark.asyncio
    async def test_initialize_service(self, rag_service):
        """Test RAG service initialization."""
        with patch.object(rag_service.query_vectorizer, 'initialize', new_callable=AsyncMock):
            with patch.object(rag_service.search_cache, 'initialize', new_callable=AsyncMock):
                await rag_service.initialize()
                
                rag_service.query_vectorizer.initialize.assert_called_once()
                rag_service.search_cache.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_documents_no_documents(self, rag_service):
        """Test search when user has no documents."""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        await rag_service.initialize()
        
        result = await rag_service.search_documents(
            db=mock_db,
            query="test query",
            user_id="user123"
        )
        
        assert result["total_results"] == 0
        assert result["results"] == []
        assert "No accessible documents found" in result["message"]
    
    @pytest.mark.asyncio
    async def test_search_suggestions(self, rag_service):
        """Test search suggestions generation."""
        mock_db = Mock()
        
        # Mock documents with titles
        mock_doc1 = Mock()
        mock_doc1.original_name = "machine_learning_guide.pdf"
        mock_doc2 = Mock()
        mock_doc2.original_name = "deep_learning_tutorial.pdf"
        
        mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = [
            mock_doc1, mock_doc2
        ]
        
        await rag_service.initialize()
        
        suggestions = await rag_service.get_search_suggestions(
            db=mock_db,
            partial_query="machine",
            user_id="user123"
        )
        
        assert isinstance(suggestions, list)
        # Should find "machine_learning_guide" from the document name
        # (implementation may vary based on exact logic)


@pytest.mark.asyncio
async def test_integration_search_flow():
    """Integration test for the complete search flow."""
    # This would test the entire flow from query to results
    # In a real test, you'd set up test data and verify the complete pipeline
    
    # Mock all dependencies
    mock_ai_manager = Mock()
    mock_ai_manager.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
    
    rag_service = RAGQueryService(mock_ai_manager)
    
    # Mock the vector storage
    with patch.object(rag_service, 'vector_storage') as mock_vector_storage:
        mock_vector_storage.search_similar_chunks = AsyncMock(return_value=[])
        
        await rag_service.initialize()
        
        # Mock database
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = await rag_service.search_documents(
            db=mock_db,
            query="test query",
            user_id="user123"
        )
        
        assert "results" in result
        assert "total_results" in result
        assert "search_time_ms" in result


if __name__ == "__main__":
    pytest.main([__file__])