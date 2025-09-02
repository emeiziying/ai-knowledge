"""
RAG (Retrieval-Augmented Generation) service for semantic search and query processing.
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import hashlib
import json
import redis.asyncio as redis
from sqlalchemy.orm import Session

from ..ai.service_manager import AIServiceManager
from ..processing.vector_storage import vector_storage_service
from ..processing.embeddings import embedding_manager
from ..models import Document, DocumentChunk, User
from ..config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class QueryVectorizer:
    """Query vectorization service."""
    
    def __init__(self, ai_service_manager: AIServiceManager):
        self.ai_service_manager = ai_service_manager
        self.embedding_service = None
    
    async def initialize(self):
        """Initialize the vectorizer."""
        try:
            # Try to get embedding service from manager
            self.embedding_service = embedding_manager.get_service()
            if not self.embedding_service:
                logger.warning("No embedding service available from manager")
            
            logger.info("Query vectorizer initialized")
        except Exception as e:
            logger.error(f"Failed to initialize query vectorizer: {e}")
            raise
    
    async def vectorize_query(self, query: str) -> List[float]:
        """
        Vectorize user query for semantic search.
        
        Args:
            query: User query text
            
        Returns:
            Query vector
        """
        try:
            # Preprocess query
            processed_query = self._preprocess_query(query)
            
            # Try embedding service first
            if self.embedding_service:
                try:
                    return await self.embedding_service.encode_single_text(processed_query)
                except Exception as e:
                    logger.warning(f"Embedding service failed, trying AI service manager: {e}")
            
            # Fallback to AI service manager
            return await self.ai_service_manager.generate_embedding(processed_query)
            
        except Exception as e:
            logger.error(f"Failed to vectorize query: {e}")
            raise
    
    def _preprocess_query(self, query: str) -> str:
        """Preprocess query text."""
        # Remove extra whitespace
        query = " ".join(query.split())
        
        # Truncate if too long
        if len(query) > 1000:
            query = query[:1000]
        
        return query


class SearchResultRanker:
    """Ranking and filtering service for search results."""
    
    def __init__(self):
        self.min_score_threshold = 0.7
        self.max_results = 20
        self.diversity_threshold = 0.9  # Similarity threshold for deduplication
    
    def rank_and_filter_results(
        self,
        search_results: List[Dict[str, Any]],
        query: str,
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Rank and filter search results.
        
        Args:
            search_results: Raw search results from vector store
            query: Original user query
            user_preferences: User-specific preferences
            
        Returns:
            Ranked and filtered results
        """
        if not search_results:
            return []
        
        try:
            # Filter by minimum score
            filtered_results = [
                result for result in search_results 
                if result.get("score", 0) >= self.min_score_threshold
            ]
            
            # Remove duplicates based on content similarity
            deduplicated_results = self._remove_duplicates(filtered_results)
            
            # Apply additional ranking factors
            ranked_results = self._apply_ranking_factors(deduplicated_results, query)
            
            # Apply user preferences if available
            if user_preferences:
                ranked_results = self._apply_user_preferences(ranked_results, user_preferences)
            
            # Limit results
            return ranked_results[:self.max_results]
            
        except Exception as e:
            logger.error(f"Failed to rank and filter results: {e}")
            return search_results[:self.max_results]  # Return original results as fallback
    
    def _remove_duplicates(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate or very similar results."""
        if len(results) <= 1:
            return results
        
        deduplicated = []
        
        for result in results:
            is_duplicate = False
            result_content = result.get("content", "").lower()
            
            for existing in deduplicated:
                existing_content = existing.get("content", "").lower()
                
                # Simple similarity check based on content overlap
                similarity = self._calculate_text_similarity(result_content, existing_content)
                
                if similarity > self.diversity_threshold:
                    is_duplicate = True
                    # Keep the one with higher score
                    if result.get("score", 0) > existing.get("score", 0):
                        deduplicated.remove(existing)
                        deduplicated.append(result)
                    break
            
            if not is_duplicate:
                deduplicated.append(result)
        
        return deduplicated
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity based on word overlap."""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _apply_ranking_factors(
        self, 
        results: List[Dict[str, Any]], 
        query: str
    ) -> List[Dict[str, Any]]:
        """Apply additional ranking factors."""
        query_words = set(query.lower().split())
        
        for result in results:
            # Base score from vector similarity
            base_score = result.get("score", 0)
            
            # Keyword match bonus
            content_words = set(result.get("content", "").lower().split())
            keyword_overlap = len(query_words.intersection(content_words))
            keyword_bonus = min(keyword_overlap * 0.1, 0.3)  # Max 30% bonus
            
            # Content length factor (prefer medium-length chunks)
            content_length = len(result.get("content", ""))
            if 100 <= content_length <= 1000:
                length_bonus = 0.05
            elif content_length < 100:
                length_bonus = -0.1
            else:
                length_bonus = 0.0
            
            # Document recency factor (if available)
            recency_bonus = 0.0
            if "created_at" in result:
                try:
                    created_at = datetime.fromisoformat(result["created_at"].replace("Z", "+00:00"))
                    days_old = (datetime.now() - created_at.replace(tzinfo=None)).days
                    if days_old < 30:
                        recency_bonus = 0.05
                except:
                    pass
            
            # Calculate final score
            final_score = base_score + keyword_bonus + length_bonus + recency_bonus
            result["final_score"] = min(final_score, 1.0)  # Cap at 1.0
            result["ranking_factors"] = {
                "base_score": base_score,
                "keyword_bonus": keyword_bonus,
                "length_bonus": length_bonus,
                "recency_bonus": recency_bonus
            }
        
        # Sort by final score
        return sorted(results, key=lambda x: x.get("final_score", 0), reverse=True)
    
    def _apply_user_preferences(
        self, 
        results: List[Dict[str, Any]], 
        preferences: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply user-specific preferences to ranking."""
        # This can be extended based on user preferences
        # For now, just return the results as-is
        return results


class SearchCache:
    """Cache service for search results."""
    
    def __init__(self):
        self.redis_client = None
        self.cache_ttl = 3600  # 1 hour
        self.cache_prefix = "rag_search:"
    
    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self.redis_client.ping()
            logger.info("Search cache initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize search cache: {e}")
            self.redis_client = None
    
    async def get_cached_results(
        self, 
        query: str, 
        user_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached search results."""
        if not self.redis_client:
            return None
        
        try:
            cache_key = self._generate_cache_key(query, user_id, filters)
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached results: {e}")
            return None
    
    async def cache_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        user_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ):
        """Cache search results."""
        if not self.redis_client:
            return
        
        try:
            cache_key = self._generate_cache_key(query, user_id, filters)
            cached_data = json.dumps(results, default=str)
            
            await self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                cached_data
            )
            
        except Exception as e:
            logger.error(f"Failed to cache results: {e}")
    
    def _generate_cache_key(
        self, 
        query: str, 
        user_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate cache key for query."""
        # Create a hash of the query and parameters
        key_data = {
            "query": query.lower().strip(),
            "user_id": user_id,
            "filters": filters or {}
        }
        
        key_string = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        
        return f"{self.cache_prefix}{key_hash}"
    
    async def invalidate_user_cache(self, user_id: str):
        """Invalidate all cached results for a user."""
        if not self.redis_client:
            return
        
        try:
            # Find all keys for this user (this is a simplified approach)
            pattern = f"{self.cache_prefix}*"
            keys = await self.redis_client.keys(pattern)
            
            # This is not efficient for large caches, but works for now
            # In production, consider using a more sophisticated cache invalidation strategy
            if keys:
                await self.redis_client.delete(*keys)
                
        except Exception as e:
            logger.error(f"Failed to invalidate user cache: {e}")
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()


class RAGQueryService:
    """Main RAG query service that orchestrates semantic search."""
    
    def __init__(self, ai_service_manager: AIServiceManager):
        self.ai_service_manager = ai_service_manager
        self.query_vectorizer = QueryVectorizer(ai_service_manager)
        self.result_ranker = SearchResultRanker()
        self.search_cache = SearchCache()
        self.vector_storage = vector_storage_service
    
    async def initialize(self):
        """Initialize the RAG query service."""
        try:
            await self.query_vectorizer.initialize()
            await self.search_cache.initialize()
            logger.info("RAG query service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize RAG query service: {e}")
            raise
    
    async def search_documents(
        self,
        db: Session,
        query: str,
        user_id: str,
        limit: int = 10,
        score_threshold: float = 0.7,
        document_ids: Optional[List[str]] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Perform semantic search on documents.
        
        Args:
            db: Database session
            query: User query
            user_id: User ID for access control
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            document_ids: Optional list of document IDs to search within
            use_cache: Whether to use caching
            
        Returns:
            Search results with metadata
        """
        try:
            search_start_time = datetime.now()
            
            # Check cache first
            cached_results = None
            if use_cache:
                cache_filters = {
                    "limit": limit,
                    "score_threshold": score_threshold,
                    "document_ids": document_ids
                }
                cached_results = await self.search_cache.get_cached_results(
                    query, user_id, cache_filters
                )
                
                if cached_results:
                    return {
                        "results": cached_results,
                        "total_results": len(cached_results),
                        "query": query,
                        "search_time_ms": 0,  # Cached result
                        "cached": True
                    }
            
            # Vectorize query
            query_vector = await self.query_vectorizer.vectorize_query(query)
            
            # Get user's accessible documents if document_ids not specified
            accessible_doc_ids = document_ids
            if not accessible_doc_ids:
                user_documents = db.query(Document).filter(
                    Document.user_id == user_id,
                    Document.status == "completed"
                ).all()
                accessible_doc_ids = [str(doc.id) for doc in user_documents]
            
            if not accessible_doc_ids:
                return {
                    "results": [],
                    "total_results": 0,
                    "query": query,
                    "search_time_ms": 0,
                    "cached": False,
                    "message": "No accessible documents found"
                }
            
            # Perform vector search
            search_results = await self.vector_storage.search_similar_chunks(
                query_vector=query_vector,
                limit=limit * 2,  # Get more results for better ranking
                score_threshold=score_threshold,
                document_ids=accessible_doc_ids,
                user_id=user_id
            )
            
            # Rank and filter results
            ranked_results = self.result_ranker.rank_and_filter_results(
                search_results, query
            )
            
            # Limit final results
            final_results = ranked_results[:limit]
            
            # Enrich results with document metadata
            enriched_results = await self._enrich_results_with_metadata(db, final_results)
            
            # Calculate search time
            search_time_ms = (datetime.now() - search_start_time).total_seconds() * 1000
            
            # Cache results
            if use_cache and enriched_results:
                cache_filters = {
                    "limit": limit,
                    "score_threshold": score_threshold,
                    "document_ids": document_ids
                }
                await self.search_cache.cache_results(
                    query, enriched_results, user_id, cache_filters
                )
            
            return {
                "results": enriched_results,
                "total_results": len(enriched_results),
                "query": query,
                "search_time_ms": round(search_time_ms, 2),
                "cached": False
            }
            
        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            raise
    
    async def _enrich_results_with_metadata(
        self, 
        db: Session, 
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Enrich search results with document metadata."""
        if not results:
            return []
        
        try:
            # Get unique document IDs
            document_ids = list(set(result.get("document_id") for result in results))
            
            # Fetch document metadata
            documents = db.query(Document).filter(
                Document.id.in_(document_ids)
            ).all()
            
            doc_metadata = {
                str(doc.id): {
                    "filename": doc.filename,
                    "original_name": doc.original_name,
                    "file_size": doc.file_size,
                    "mime_type": doc.mime_type,
                    "created_at": doc.created_at.isoformat(),
                    "updated_at": doc.updated_at.isoformat()
                }
                for doc in documents
            }
            
            # Enrich results
            enriched_results = []
            for result in results:
                enriched_result = result.copy()
                doc_id = result.get("document_id")
                
                if doc_id in doc_metadata:
                    enriched_result["document_metadata"] = doc_metadata[doc_id]
                
                enriched_results.append(enriched_result)
            
            return enriched_results
            
        except Exception as e:
            logger.error(f"Failed to enrich results with metadata: {e}")
            return results  # Return original results as fallback
    
    async def get_search_suggestions(
        self,
        db: Session,
        partial_query: str,
        user_id: str,
        limit: int = 5
    ) -> List[str]:
        """
        Get search suggestions based on partial query.
        
        Args:
            db: Database session
            partial_query: Partial user query
            user_id: User ID
            limit: Maximum number of suggestions
            
        Returns:
            List of suggested queries
        """
        try:
            # This is a simplified implementation
            # In a production system, you might want to:
            # 1. Use a dedicated search suggestion service
            # 2. Analyze user's previous queries
            # 3. Extract common phrases from documents
            
            if len(partial_query) < 3:
                return []
            
            # Get user's documents
            user_documents = db.query(Document).filter(
                Document.user_id == user_id,
                Document.status == "completed"
            ).limit(10).all()
            
            suggestions = []
            
            # Extract potential suggestions from document titles
            for doc in user_documents:
                title_words = doc.original_name.lower().split()
                for word in title_words:
                    if (word.startswith(partial_query.lower()) and 
                        len(word) > len(partial_query) and
                        word not in suggestions):
                        suggestions.append(word)
            
            return suggestions[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get search suggestions: {e}")
            return []
    
    async def close(self):
        """Close the RAG query service."""
        try:
            await self.search_cache.close()
            logger.info("RAG query service closed")
        except Exception as e:
            logger.error(f"Error closing RAG query service: {e}")


# Global RAG query service instance
rag_query_service = None


async def initialize_rag_service(ai_service_manager: AIServiceManager) -> RAGQueryService:
    """Initialize the global RAG query service."""
    global rag_query_service
    
    try:
        rag_query_service = RAGQueryService(ai_service_manager)
        await rag_query_service.initialize()
        logger.info("Global RAG query service initialized")
        return rag_query_service
    except Exception as e:
        logger.error(f"Failed to initialize global RAG query service: {e}")
        raise


def get_rag_service() -> Optional[RAGQueryService]:
    """Get the global RAG query service instance."""
    return rag_query_service