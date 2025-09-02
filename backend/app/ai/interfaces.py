"""
AI service abstract interfaces and base classes.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
from pydantic import BaseModel
from enum import Enum


class AIServiceType(str, Enum):
    """AI service types."""
    OPENAI = "openai"
    OLLAMA = "ollama"
    LOCAL = "local"


class AIServiceStatus(str, Enum):
    """AI service status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class EmbeddingRequest(BaseModel):
    """Request model for text embedding."""
    text: str
    model: Optional[str] = None


class EmbeddingResponse(BaseModel):
    """Response model for text embedding."""
    embedding: List[float]
    model: str
    usage: Optional[Dict[str, Any]] = None


class ChatMessage(BaseModel):
    """Chat message model."""
    role: str  # "system", "user", "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request model for chat completion."""
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False


class ChatResponse(BaseModel):
    """Response model for chat completion."""
    content: str
    model: str
    usage: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None


class HealthCheckResponse(BaseModel):
    """Health check response model."""
    status: AIServiceStatus
    service_type: AIServiceType
    model_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    response_time_ms: Optional[float] = None


class BaseAIService(ABC):
    """Abstract base class for AI services."""
    
    def __init__(self, service_type: AIServiceType, config: Dict[str, Any]):
        self.service_type = service_type
        self.config = config
        self._is_healthy = True
        self._last_health_check = None
    
    @abstractmethod
    async def generate_embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate text embedding."""
        pass
    
    @abstractmethod
    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Generate chat completion."""
        pass
    
    @abstractmethod
    async def chat_completion_stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """Generate streaming chat completion."""
        pass
    
    @abstractmethod
    async def health_check(self) -> HealthCheckResponse:
        """Check service health."""
        pass
    
    @abstractmethod
    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models."""
        pass
    
    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self._is_healthy
    
    def set_health_status(self, is_healthy: bool):
        """Set health status."""
        self._is_healthy = is_healthy


class EmbeddingService(ABC):
    """Abstract embedding service interface."""
    
    @abstractmethod
    async def embed_text(self, text: str, model: Optional[str] = None) -> List[float]:
        """Embed single text."""
        pass
    
    @abstractmethod
    async def embed_texts(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """Embed multiple texts."""
        pass


class ChatService(ABC):
    """Abstract chat service interface."""
    
    @abstractmethod
    async def generate_response(
        self, 
        messages: List[ChatMessage], 
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate chat response."""
        pass
    
    @abstractmethod
    async def generate_response_stream(
        self, 
        messages: List[ChatMessage], 
        model: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate streaming chat response."""
        pass