"""
Chat and RAG query API endpoints.
"""
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ..database import get_db
from ..auth.dependencies import get_current_user
from ..models import User
from .rag_service import get_rag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


# Request/Response Models
class SearchRequest(BaseModel):
    """Search request model."""
    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of results")
    score_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum similarity score")
    document_ids: Optional[List[str]] = Field(default=None, description="Optional list of document IDs to search within")
    use_cache: bool = Field(default=True, description="Whether to use caching")


class SearchResult(BaseModel):
    """Individual search result model."""
    vector_id: str
    score: float
    final_score: Optional[float] = None
    document_id: str
    chunk_index: int
    content: str
    character_count: int
    word_count: int
    start_position: int
    end_position: int
    chunking_strategy: str
    created_at: str
    structure_markers: Optional[bool] = None
    section_info: Optional[Dict[str, Any]] = None
    document_metadata: Optional[Dict[str, Any]] = None
    ranking_factors: Optional[Dict[str, Any]] = None


class SearchResponse(BaseModel):
    """Search response model."""
    results: List[SearchResult]
    total_results: int
    query: str
    search_time_ms: float
    cached: bool
    message: Optional[str] = None


class SuggestionsRequest(BaseModel):
    """Search suggestions request model."""
    partial_query: str = Field(..., min_length=1, max_length=100, description="Partial search query")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum number of suggestions")


class SuggestionsResponse(BaseModel):
    """Search suggestions response model."""
    suggestions: List[str]
    partial_query: str


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Perform semantic search on user's documents.
    
    This endpoint allows users to search through their uploaded documents using
    natural language queries. The search uses vector similarity to find the most
    relevant document chunks.
    """
    try:
        rag_service = get_rag_service()
        if not rag_service:
            raise HTTPException(
                status_code=503,
                detail="RAG service not available"
            )
        
        # Perform search
        search_results = await rag_service.search_documents(
            db=db,
            query=request.query,
            user_id=str(current_user.id),
            limit=request.limit,
            score_threshold=request.score_threshold,
            document_ids=request.document_ids,
            use_cache=request.use_cache
        )
        
        return SearchResponse(**search_results)
        
    except Exception as e:
        logger.error(f"Search failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/search", response_model=SearchResponse)
async def search_documents_get(
    q: str = Query(..., description="Search query"),
    limit: int = Query(default=10, ge=1, le=50, description="Maximum number of results"),
    score_threshold: float = Query(default=0.7, ge=0.0, le=1.0, description="Minimum similarity score"),
    document_ids: Optional[str] = Query(default=None, description="Comma-separated list of document IDs"),
    use_cache: bool = Query(default=True, description="Whether to use caching"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Perform semantic search on user's documents (GET version).
    
    This is a GET version of the search endpoint for easier integration
    with web applications and direct URL access.
    """
    try:
        # Parse document IDs if provided
        parsed_document_ids = None
        if document_ids:
            parsed_document_ids = [doc_id.strip() for doc_id in document_ids.split(",") if doc_id.strip()]
        
        # Create request object
        request = SearchRequest(
            query=q,
            limit=limit,
            score_threshold=score_threshold,
            document_ids=parsed_document_ids,
            use_cache=use_cache
        )
        
        # Use the same logic as POST endpoint
        return await search_documents(request, current_user, db)
        
    except Exception as e:
        logger.error(f"GET search failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.post("/suggestions", response_model=SuggestionsResponse)
async def get_search_suggestions(
    request: SuggestionsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get search suggestions based on partial query.
    
    This endpoint provides autocomplete suggestions to help users
    formulate better search queries.
    """
    try:
        rag_service = get_rag_service()
        if not rag_service:
            raise HTTPException(
                status_code=503,
                detail="RAG service not available"
            )
        
        suggestions = await rag_service.get_search_suggestions(
            db=db,
            partial_query=request.partial_query,
            user_id=str(current_user.id),
            limit=request.limit
        )
        
        return SuggestionsResponse(
            suggestions=suggestions,
            partial_query=request.partial_query
        )
        
    except Exception as e:
        logger.error(f"Suggestions failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get suggestions: {str(e)}"
        )


@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_search_suggestions_get(
    q: str = Query(..., description="Partial search query"),
    limit: int = Query(default=5, ge=1, le=20, description="Maximum number of suggestions"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get search suggestions based on partial query (GET version).
    """
    try:
        request = SuggestionsRequest(
            partial_query=q,
            limit=limit
        )
        
        return await get_search_suggestions(request, current_user, db)
        
    except Exception as e:
        logger.error(f"GET suggestions failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get suggestions: {str(e)}"
        )


@router.delete("/cache")
async def clear_search_cache(
    current_user: User = Depends(get_current_user)
):
    """
    Clear search cache for the current user.
    
    This endpoint allows users to clear their search cache,
    which can be useful when they want fresh results.
    """
    try:
        rag_service = get_rag_service()
        if not rag_service:
            raise HTTPException(
                status_code=503,
                detail="RAG service not available"
            )
        
        await rag_service.search_cache.invalidate_user_cache(str(current_user.id))
        
        return {"message": "Search cache cleared successfully"}
        
    except Exception as e:
        logger.error(f"Cache clear failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear cache: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint for the chat/RAG service.
    """
    try:
        rag_service = get_rag_service()
        
        if not rag_service:
            return {
                "status": "unhealthy",
                "message": "RAG service not initialized"
            }
        
        # Basic health check - could be extended with more detailed checks
        return {
            "status": "healthy",
            "message": "RAG service is operational",
            "cache_available": rag_service.search_cache.redis_client is not None
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"Health check failed: {str(e)}"
        }