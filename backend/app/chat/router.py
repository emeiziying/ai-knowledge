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
from .conversation_service import get_conversation_service
from .schemas import (
    ConversationCreate, ConversationUpdate, ConversationResponse,
    ConversationListResponse, MessageCreate, MessageResponse,
    MessageListResponse, ConversationContextResponse
)

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


# Conversation Management Endpoints

@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    request: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new conversation for the current user.
    
    This endpoint creates a new conversation session that can be used
    to maintain context across multiple messages.
    """
    try:
        conversation_service = get_conversation_service()
        
        result = await conversation_service.create_conversation(
            db=db,
            user_id=str(current_user.id),
            title=request.title
        )
        
        return ConversationResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to create conversation for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create conversation: {str(e)}"
        )


@router.get("/conversations", response_model=ConversationListResponse)
async def get_conversations(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of conversations to return"),
    offset: int = Query(default=0, ge=0, description="Number of conversations to skip"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get conversations for the current user with pagination.
    
    Returns a list of conversations ordered by most recently updated.
    """
    try:
        conversation_service = get_conversation_service()
        
        result = await conversation_service.get_conversations(
            db=db,
            user_id=str(current_user.id),
            limit=limit,
            offset=offset
        )
        
        return ConversationListResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to get conversations for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get conversations: {str(e)}"
        )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific conversation by ID.
    
    Returns conversation details including message count.
    """
    try:
        conversation_service = get_conversation_service()
        
        result = await conversation_service.get_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=str(current_user.id)
        )
        
        return ConversationResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to get conversation {conversation_id} for user {current_user.id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get conversation: {str(e)}"
        )


@router.put("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    request: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a conversation's details.
    
    Currently supports updating the conversation title.
    """
    try:
        conversation_service = get_conversation_service()
        
        result = await conversation_service.update_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=str(current_user.id),
            title=request.title
        )
        
        return ConversationResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to update conversation {conversation_id} for user {current_user.id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update conversation: {str(e)}"
        )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a conversation and all its messages.
    
    This action is irreversible and will permanently delete
    the conversation and all associated messages.
    """
    try:
        conversation_service = get_conversation_service()
        
        result = await conversation_service.delete_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=str(current_user.id)
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to delete conversation {conversation_id} for user {current_user.id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete conversation: {str(e)}"
        )


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def add_message(
    conversation_id: str,
    request: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a message to a conversation.
    
    This endpoint allows adding both user messages and assistant responses
    to maintain conversation history.
    """
    try:
        conversation_service = get_conversation_service()
        
        result = await conversation_service.add_message(
            db=db,
            conversation_id=conversation_id,
            user_id=str(current_user.id),
            role=request.role,
            content=request.content,
            metadata=request.metadata
        )
        
        return MessageResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to add message to conversation {conversation_id} for user {current_user.id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add message: {str(e)}"
        )


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
async def get_messages(
    conversation_id: str,
    limit: int = Query(default=100, ge=1, le=500, description="Maximum number of messages to return"),
    offset: int = Query(default=0, ge=0, description="Number of messages to skip"),
    include_metadata: bool = Query(default=True, description="Whether to include message metadata"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get messages from a conversation with pagination.
    
    Returns messages in chronological order (oldest first).
    """
    try:
        conversation_service = get_conversation_service()
        
        result = await conversation_service.get_messages(
            db=db,
            conversation_id=conversation_id,
            user_id=str(current_user.id),
            limit=limit,
            offset=offset,
            include_metadata=include_metadata
        )
        
        return MessageListResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to get messages for conversation {conversation_id} for user {current_user.id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get messages: {str(e)}"
        )


@router.get("/conversations/{conversation_id}/context", response_model=ConversationContextResponse)
async def get_conversation_context(
    conversation_id: str,
    max_messages: int = Query(default=10, ge=1, le=50, description="Maximum number of recent messages to include"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recent conversation context for multi-turn dialogue.
    
    Returns the most recent messages from the conversation to provide
    context for generating responses.
    """
    try:
        conversation_service = get_conversation_service()
        
        context = await conversation_service.get_conversation_context(
            db=db,
            conversation_id=conversation_id,
            user_id=str(current_user.id),
            max_messages=max_messages
        )
        
        return ConversationContextResponse(
            context=context,
            conversation_id=conversation_id,
            max_messages=max_messages
        )
        
    except Exception as e:
        logger.error(f"Failed to get context for conversation {conversation_id} for user {current_user.id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get conversation context: {str(e)}"
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