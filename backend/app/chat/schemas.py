"""
Pydantic schemas for chat and RAG functionality.
"""
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum


class SearchSortBy(str, Enum):
    """Search result sorting options."""
    RELEVANCE = "relevance"
    DATE = "date"
    DOCUMENT_NAME = "document_name"


class SearchFilterType(str, Enum):
    """Search filter types."""
    DOCUMENT_TYPE = "document_type"
    DATE_RANGE = "date_range"
    FILE_SIZE = "file_size"


class SearchFilter(BaseModel):
    """Search filter model."""
    type: SearchFilterType
    value: Union[str, List[str], Dict[str, Any]]


class AdvancedSearchRequest(BaseModel):
    """Advanced search request with filters and sorting."""
    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    score_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    sort_by: SearchSortBy = SearchSortBy.RELEVANCE
    filters: Optional[List[SearchFilter]] = None
    document_ids: Optional[List[str]] = None
    include_metadata: bool = Field(default=True)
    use_cache: bool = Field(default=True)


class DocumentChunkResult(BaseModel):
    """Document chunk search result."""
    id: str
    document_id: str
    chunk_index: int
    content: str
    score: float
    final_score: Optional[float] = None
    
    # Chunk metadata
    character_count: int
    word_count: int
    start_position: int
    end_position: int
    chunking_strategy: str
    
    # Optional structure information
    structure_markers: Optional[bool] = None
    section_info: Optional[Dict[str, Any]] = None
    
    # Ranking information
    ranking_factors: Optional[Dict[str, Any]] = None
    
    # Timestamps
    created_at: datetime


class DocumentMetadata(BaseModel):
    """Document metadata for search results."""
    id: str
    filename: str
    original_name: str
    file_size: int
    mime_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    processing_metadata: Optional[Dict[str, Any]] = None


class EnrichedSearchResult(BaseModel):
    """Enriched search result with document metadata."""
    chunk: DocumentChunkResult
    document: DocumentMetadata
    highlight: Optional[str] = None  # Highlighted content snippet


class SearchStats(BaseModel):
    """Search statistics and metadata."""
    total_results: int
    search_time_ms: float
    cached: bool
    query_vector_time_ms: Optional[float] = None
    vector_search_time_ms: Optional[float] = None
    ranking_time_ms: Optional[float] = None
    
    # Search quality metrics
    avg_score: Optional[float] = None
    max_score: Optional[float] = None
    min_score: Optional[float] = None


class AdvancedSearchResponse(BaseModel):
    """Advanced search response."""
    results: List[EnrichedSearchResult]
    stats: SearchStats
    query: str
    filters_applied: Optional[List[SearchFilter]] = None
    suggestions: Optional[List[str]] = None


class QueryAnalysis(BaseModel):
    """Query analysis result."""
    original_query: str
    processed_query: str
    query_type: str  # "factual", "conceptual", "procedural", etc.
    key_terms: List[str]
    intent: Optional[str] = None
    confidence: Optional[float] = None


class SearchContext(BaseModel):
    """Search context for maintaining session state."""
    session_id: str
    user_id: str
    previous_queries: List[str] = Field(default_factory=list)
    search_history: List[Dict[str, Any]] = Field(default_factory=list)
    preferences: Optional[Dict[str, Any]] = None


class CacheStats(BaseModel):
    """Cache statistics."""
    total_entries: int
    hit_rate: float
    miss_rate: float
    avg_response_time_ms: float
    cache_size_mb: Optional[float] = None


class ServiceHealth(BaseModel):
    """Service health status."""
    service_name: str
    status: str  # "healthy", "degraded", "unhealthy"
    last_check: datetime
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None


class RAGServiceStatus(BaseModel):
    """RAG service overall status."""
    overall_status: str
    services: List[ServiceHealth]
    cache_stats: Optional[CacheStats] = None
    vector_store_stats: Optional[Dict[str, Any]] = None


class SearchExplanation(BaseModel):
    """Explanation of search results."""
    query_interpretation: str
    search_strategy: str
    ranking_explanation: str
    suggestions_for_improvement: Optional[List[str]] = None


class DetailedSearchResponse(BaseModel):
    """Detailed search response with explanations."""
    results: List[EnrichedSearchResult]
    stats: SearchStats
    query_analysis: QueryAnalysis
    explanation: SearchExplanation
    related_queries: Optional[List[str]] = None


# Validation helpers
class SearchRequestValidator:
    """Validator for search requests."""
    
    @staticmethod
    def validate_query(query: str) -> str:
        """Validate and clean query string."""
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        # Remove excessive whitespace
        cleaned_query = " ".join(query.strip().split())
        
        # Check length
        if len(cleaned_query) > 1000:
            raise ValueError("Query too long (max 1000 characters)")
        
        return cleaned_query
    
    @staticmethod
    def validate_document_ids(document_ids: Optional[List[str]]) -> Optional[List[str]]:
        """Validate document IDs."""
        if not document_ids:
            return None
        
        # Remove empty strings and duplicates
        valid_ids = list(set(doc_id.strip() for doc_id in document_ids if doc_id.strip()))
        
        if len(valid_ids) > 100:  # Reasonable limit
            raise ValueError("Too many document IDs (max 100)")
        
        return valid_ids if valid_ids else None


# Response formatters
class ResponseFormatter:
    """Formatter for search responses."""
    
    @staticmethod
    def format_search_result(
        raw_result: Dict[str, Any],
        include_debug_info: bool = False
    ) -> DocumentChunkResult:
        """Format raw search result into structured response."""
        try:
            result = DocumentChunkResult(
                id=raw_result["vector_id"],
                document_id=raw_result["document_id"],
                chunk_index=raw_result["chunk_index"],
                content=raw_result["content"],
                score=raw_result["score"],
                final_score=raw_result.get("final_score"),
                character_count=raw_result["character_count"],
                word_count=raw_result["word_count"],
                start_position=raw_result["start_position"],
                end_position=raw_result["end_position"],
                chunking_strategy=raw_result["chunking_strategy"],
                structure_markers=raw_result.get("structure_markers"),
                section_info=raw_result.get("section_info"),
                created_at=datetime.fromisoformat(raw_result["created_at"].replace("Z", "+00:00"))
            )
            
            if include_debug_info:
                result.ranking_factors = raw_result.get("ranking_factors")
            
            return result
            
        except Exception as e:
            raise ValueError(f"Failed to format search result: {e}")
    
    @staticmethod
    def create_highlight(content: str, query: str, max_length: int = 200) -> str:
        """Create highlighted content snippet."""
        if not content or not query:
            return content[:max_length] if content else ""
        
        query_words = query.lower().split()
        content_lower = content.lower()
        
        # Find the best position to start the highlight
        best_pos = 0
        max_matches = 0
        
        for i in range(len(content) - max_length + 1):
            snippet = content_lower[i:i + max_length]
            matches = sum(1 for word in query_words if word in snippet)
            
            if matches > max_matches:
                max_matches = matches
                best_pos = i
        
        # Extract and highlight the snippet
        snippet = content[best_pos:best_pos + max_length]
        
        # Simple highlighting (in a real implementation, you might use more sophisticated highlighting)
        for word in query_words:
            if len(word) > 2:  # Only highlight meaningful words
                snippet = snippet.replace(
                    word, 
                    f"**{word}**", 
                    1  # Only replace first occurrence
                )
        
        return snippet + ("..." if len(content) > best_pos + max_length else "")


# Error models
class SearchError(BaseModel):
    """Search error response."""
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None


class ValidationError(BaseModel):
    """Validation error response."""
    field: str
    message: str
    invalid_value: Optional[Any] = None