"""
AI services module for managing multiple AI service providers.
"""
from .interfaces import (
    AIServiceType,
    AIServiceStatus,
    ChatMessage,
    EmbeddingRequest,
    EmbeddingResponse,
    ChatRequest,
    ChatResponse,
    HealthCheckResponse
)
from .service_manager import AIServiceManager
from .factory import AIServiceFactory, EmbeddingServiceWrapper, ChatServiceWrapper
from .openai_service import OpenAIService
from .ollama_service import OllamaService

__all__ = [
    "AIServiceType",
    "AIServiceStatus", 
    "ChatMessage",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "ChatRequest",
    "ChatResponse",
    "HealthCheckResponse",
    "AIServiceManager",
    "AIServiceFactory",
    "EmbeddingServiceWrapper",
    "ChatServiceWrapper",
    "OpenAIService",
    "OllamaService",
]