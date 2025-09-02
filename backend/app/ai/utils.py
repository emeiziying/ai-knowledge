"""
Utility functions for AI service integration.
"""
import logging
from typing import List, Optional, Dict, Any
from fastapi import Request

from .interfaces import ChatMessage
from .service_manager import AIServiceManager
from .factory import AIServiceFactory
from ..config import get_settings

logger = logging.getLogger(__name__)


def get_ai_service_manager_from_app(request: Request) -> Optional[AIServiceManager]:
    """Get AI service manager from FastAPI app state."""
    return getattr(request.app.state, 'ai_service_manager', None)


async def get_or_create_ai_service_manager() -> AIServiceManager:
    """Get or create AI service manager instance."""
    settings = get_settings()
    return AIServiceFactory.create_service_manager(settings)


async def embed_text_with_fallback(text: str, model: Optional[str] = None) -> List[float]:
    """
    Embed text with automatic fallback to available services.
    
    Args:
        text: Text to embed
        model: Optional model name
        
    Returns:
        List of embedding values
        
    Raises:
        Exception: If no AI services are available
    """
    try:
        manager = await get_or_create_ai_service_manager()
        return await manager.generate_embedding(text, model)
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        raise


async def generate_chat_response_with_fallback(
    messages: List[ChatMessage], 
    model: Optional[str] = None,
    **kwargs
) -> str:
    """
    Generate chat response with automatic fallback to available services.
    
    Args:
        messages: List of chat messages
        model: Optional model name
        **kwargs: Additional parameters (temperature, max_tokens, etc.)
        
    Returns:
        Generated response text
        
    Raises:
        Exception: If no AI services are available
    """
    try:
        manager = await get_or_create_ai_service_manager()
        return await manager.generate_chat_response(messages, model, **kwargs)
    except Exception as e:
        logger.error(f"Failed to generate chat response: {e}")
        raise


async def check_ai_services_health() -> Dict[str, Any]:
    """
    Check health of all AI services.
    
    Returns:
        Dictionary with service health status
    """
    try:
        manager = await get_or_create_ai_service_manager()
        return await manager.get_service_status()
    except Exception as e:
        logger.error(f"Failed to check AI services health: {e}")
        return {}


def create_system_message(content: str) -> ChatMessage:
    """Create a system message for chat."""
    return ChatMessage(role="system", content=content)


def create_user_message(content: str) -> ChatMessage:
    """Create a user message for chat."""
    return ChatMessage(role="user", content=content)


def create_assistant_message(content: str) -> ChatMessage:
    """Create an assistant message for chat."""
    return ChatMessage(role="assistant", content=content)


def build_rag_prompt(
    user_question: str,
    context_documents: List[str],
    system_prompt: Optional[str] = None
) -> List[ChatMessage]:
    """
    Build a RAG (Retrieval Augmented Generation) prompt from user question and context.
    
    Args:
        user_question: The user's question
        context_documents: List of relevant document excerpts
        system_prompt: Optional custom system prompt
        
    Returns:
        List of ChatMessage objects for the conversation
    """
    if system_prompt is None:
        system_prompt = """You are a helpful AI assistant that answers questions based on the provided context documents. 
Use only the information from the context to answer questions. If the context doesn't contain enough information 
to answer the question, say so clearly. Always cite which document or section your answer comes from."""
    
    # Build context section
    context_text = "\n\n".join([
        f"Document {i+1}:\n{doc}" 
        for i, doc in enumerate(context_documents)
    ])
    
    # Create the full prompt
    full_prompt = f"""Context Documents:
{context_text}

Question: {user_question}

Please answer the question based on the context documents provided above."""
    
    return [
        create_system_message(system_prompt),
        create_user_message(full_prompt)
    ]


async def generate_rag_response(
    user_question: str,
    context_documents: List[str],
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    **kwargs
) -> str:
    """
    Generate a RAG response using the AI service.
    
    Args:
        user_question: The user's question
        context_documents: List of relevant document excerpts
        model: Optional model name
        system_prompt: Optional custom system prompt
        **kwargs: Additional parameters for the AI service
        
    Returns:
        Generated response text
    """
    messages = build_rag_prompt(user_question, context_documents, system_prompt)
    return await generate_chat_response_with_fallback(messages, model, **kwargs)


class AIServiceHealthChecker:
    """Utility class for monitoring AI service health."""
    
    def __init__(self, check_interval: int = 300):
        self.check_interval = check_interval
        self.last_status = {}
    
    async def get_current_status(self) -> Dict[str, Any]:
        """Get current health status of all AI services."""
        self.last_status = await check_ai_services_health()
        return self.last_status
    
    def is_any_service_healthy(self) -> bool:
        """Check if any AI service is currently healthy."""
        return any(
            status.get('status') == 'healthy' 
            for status in self.last_status.values()
        )
    
    def get_healthy_services(self) -> List[str]:
        """Get list of currently healthy service names."""
        return [
            service_name 
            for service_name, status in self.last_status.items()
            if status.get('status') == 'healthy'
        ]
    
    def get_unhealthy_services(self) -> List[str]:
        """Get list of currently unhealthy service names."""
        return [
            service_name 
            for service_name, status in self.last_status.items()
            if status.get('status') != 'healthy'
        ]