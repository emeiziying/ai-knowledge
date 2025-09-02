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
from .answer_service import get_answer_service
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


class AnswerRequest(BaseModel):
    """RAG answer generation request model."""
    question: str = Field(..., min_length=1, max_length=2000, description="User question")
    conversation_id: Optional[str] = Field(default=None, description="Optional conversation ID for context")
    search_params: Optional[Dict[str, Any]] = Field(default=None, description="Optional search parameters")
    model: Optional[str] = Field(default=None, description="Optional AI model to use")
    stream: bool = Field(default=False, description="Whether to stream the response")


class AnswerSource(BaseModel):
    """Answer source information model."""
    document_id: str
    document_name: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    created_at: Optional[str] = None
    chunks_referenced: List[Dict[str, Any]] = Field(default_factory=list)


class QualityValidation(BaseModel):
    """Answer quality validation model."""
    is_valid: bool
    quality_score: float
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


class AnswerResponse(BaseModel):
    """RAG answer generation response model."""
    answer: str
    sources: List[AnswerSource]
    quality_validation: QualityValidation
    question: str
    search_metadata: Dict[str, Any]
    processing_time_ms: float
    model_used: Optional[str] = None
    has_context: bool
    context_used: bool
    context_chunks: int


class AnswerImprovementRequest(BaseModel):
    """Answer improvement request model."""
    original_answer: str = Field(..., min_length=1, description="Original answer to improve")
    question: str = Field(..., min_length=1, description="Original question")
    feedback: str = Field(..., min_length=1, description="User feedback on the answer")
    model: Optional[str] = Field(default=None, description="Optional AI model to use")


class AnswerImprovementResponse(BaseModel):
    """Answer improvement response model."""
    improved_answer: str
    sources: List[AnswerSource]
    quality_validation: QualityValidation
    improvement_applied: bool


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


@router.post("/answer", response_model=AnswerResponse)
async def generate_answer(
    request: AnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate RAG-based answer for user question.
    
    This endpoint combines semantic search with AI generation to provide
    intelligent answers based on the user's knowledge base.
    """
    try:
        answer_service = get_answer_service()
        if not answer_service:
            raise HTTPException(
                status_code=503,
                detail="Answer service not available"
            )
        
        # Generate answer
        result = await answer_service.generate_answer(
            db=db,
            question=request.question,
            user_id=str(current_user.id),
            conversation_id=request.conversation_id,
            search_params=request.search_params,
            model=request.model
        )
        
        return AnswerResponse(**result)
        
    except Exception as e:
        logger.error(f"Answer generation failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Answer generation failed: {str(e)}"
        )


@router.post("/answer/stream")
async def generate_answer_stream(
    request: AnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate streaming RAG-based answer for real-time responses.
    
    This endpoint provides streaming responses for better user experience
    with longer answer generation times.
    """
    try:
        answer_service = get_answer_service()
        if not answer_service:
            raise HTTPException(
                status_code=503,
                detail="Answer service not available"
            )
        
        from fastapi.responses import StreamingResponse
        
        async def generate_stream():
            try:
                async for chunk in answer_service.generate_streaming_answer(
                    db=db,
                    question=request.question,
                    user_id=str(current_user.id),
                    conversation_id=request.conversation_id,
                    search_params=request.search_params,
                    model=request.model
                ):
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Streaming answer generation failed: {e}")
                yield f"data: 抱歉，生成回答时出现错误：{str(e)}\n\n"
                yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )
        
    except Exception as e:
        logger.error(f"Streaming answer generation failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Streaming answer generation failed: {str(e)}"
        )


@router.post("/answer/improve", response_model=AnswerImprovementResponse)
async def improve_answer(
    request: AnswerImprovementRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Improve an existing answer based on user feedback.
    
    This endpoint allows users to provide feedback on generated answers
    and receive improved versions.
    """
    try:
        answer_service = get_answer_service()
        if not answer_service:
            raise HTTPException(
                status_code=503,
                detail="Answer service not available"
            )
        
        # First, perform search to get context for improvement
        rag_service = get_rag_service()
        if not rag_service:
            raise HTTPException(
                status_code=503,
                detail="RAG service not available"
            )
        
        search_results = await rag_service.search_documents(
            db=db,
            query=request.question,
            user_id=str(current_user.id),
            limit=5,
            score_threshold=0.7
        )
        
        # Improve answer
        result = await answer_service.improve_answer(
            original_answer=request.original_answer,
            question=request.question,
            feedback=request.feedback,
            search_results=search_results["results"],
            model=request.model
        )
        
        return AnswerImprovementResponse(**result)
        
    except Exception as e:
        logger.error(f"Answer improvement failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Answer improvement failed: {str(e)}"
        )


@router.post("/qa", response_model=MessageResponse)
async def ask_question(
    request: AnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ask a question and automatically save to conversation.
    
    This endpoint combines answer generation with conversation management,
    automatically creating or updating a conversation with the Q&A pair.
    """
    try:
        answer_service = get_answer_service()
        conversation_service = get_conversation_service()
        
        if not answer_service:
            raise HTTPException(
                status_code=503,
                detail="Answer service not available"
            )
        
        # Create conversation if not provided
        conversation_id = request.conversation_id
        if not conversation_id:
            conv_result = await conversation_service.create_conversation(
                db=db,
                user_id=str(current_user.id),
                title=request.question[:50] + "..." if len(request.question) > 50 else request.question
            )
            conversation_id = conv_result["id"]
        
        # Add user message
        user_message = await conversation_service.add_message(
            db=db,
            conversation_id=conversation_id,
            user_id=str(current_user.id),
            role="user",
            content=request.question
        )
        
        # Generate answer
        answer_result = await answer_service.generate_answer(
            db=db,
            question=request.question,
            user_id=str(current_user.id),
            conversation_id=conversation_id,
            search_params=request.search_params,
            model=request.model
        )
        
        # Add assistant message with metadata
        assistant_metadata = {
            "sources": answer_result["sources"],
            "quality_validation": answer_result["quality_validation"],
            "search_metadata": answer_result["search_metadata"],
            "processing_time_ms": answer_result["processing_time_ms"],
            "model_used": answer_result["model_used"],
            "has_context": answer_result["has_context"]
        }
        
        assistant_message = await conversation_service.add_message(
            db=db,
            conversation_id=conversation_id,
            user_id=str(current_user.id),
            role="assistant",
            content=answer_result["answer"],
            metadata=assistant_metadata
        )
        
        return MessageResponse(**assistant_message)
        
    except Exception as e:
        logger.error(f"Q&A failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Q&A failed: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint for the chat/RAG service.
    """
    try:
        rag_service = get_rag_service()
        answer_service = get_answer_service()
        
        health_status = {
            "status": "healthy",
            "message": "Chat services operational",
            "services": {}
        }
        
        # Check RAG service
        if not rag_service:
            health_status["services"]["rag"] = "unavailable"
            health_status["status"] = "degraded"
        else:
            health_status["services"]["rag"] = "available"
            health_status["cache_available"] = rag_service.search_cache.redis_client is not None
        
        # Check answer service
        if not answer_service:
            health_status["services"]["answer"] = "unavailable"
            health_status["status"] = "degraded"
        else:
            health_status["services"]["answer"] = "available"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"Health check failed: {str(e)}"
        }