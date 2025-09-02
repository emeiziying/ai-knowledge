"""
AI Service Factory for creating and configuring AI services.
"""
import logging
from typing import Dict, Any, Optional

from ..config import Settings
from .service_manager import AIServiceManager

logger = logging.getLogger(__name__)


class AIServiceFactory:
    """Factory for creating AI service instances."""
    
    @staticmethod
    def create_service_manager(settings: Settings) -> AIServiceManager:
        """Create AI service manager with configuration from settings."""
        config = AIServiceFactory._build_config(settings)
        return AIServiceManager(config)
    
    @staticmethod
    def _build_config(settings: Settings) -> Dict[str, Any]:
        """Build AI service configuration from application settings."""
        config = {
            "health_check_interval": 300,  # 5 minutes
            "health_check_timeout": 30,
            "max_retry_attempts": 3,
            "retry_delay": 1,
            "circuit_breaker_threshold": 5,
            "circuit_breaker_timeout": 60,
        }
        
        # OpenAI configuration
        if settings.openai_api_key:
            config["openai"] = {
                "api_key": settings.openai_api_key,
                "base_url": getattr(settings, "openai_base_url", None),
                "organization": getattr(settings, "openai_organization", None),
                "default_chat_model": getattr(settings, "openai_chat_model", "gpt-3.5-turbo"),
                "default_embedding_model": getattr(settings, "openai_embedding_model", "text-embedding-ada-002"),
            }
            logger.info("OpenAI service configured")
        
        # Ollama configuration
        if settings.ollama_base_url:
            config["ollama"] = {
                "base_url": settings.ollama_base_url,
                "default_chat_model": getattr(settings, "ollama_chat_model", "llama2"),
                "default_embedding_model": getattr(settings, "ollama_embedding_model", "nomic-embed-text"),
                "timeout": getattr(settings, "ollama_timeout", 60),
            }
            logger.info("Ollama service configured")
        
        return config
    
    @staticmethod
    def create_embedding_service(settings: Settings):
        """Create a standalone embedding service."""
        service_manager = AIServiceFactory.create_service_manager(settings)
        return EmbeddingServiceWrapper(service_manager)
    
    @staticmethod
    def create_chat_service(settings: Settings):
        """Create a standalone chat service."""
        service_manager = AIServiceFactory.create_service_manager(settings)
        return ChatServiceWrapper(service_manager)


class EmbeddingServiceWrapper:
    """Wrapper for embedding functionality from service manager."""
    
    def __init__(self, service_manager: AIServiceManager):
        self.service_manager = service_manager
    
    async def embed_text(self, text: str, model: Optional[str] = None) -> list[float]:
        """Embed single text."""
        return await self.service_manager.generate_embedding(text, model)
    
    async def embed_texts(self, texts: list[str], model: Optional[str] = None) -> list[list[float]]:
        """Embed multiple texts."""
        return await self.service_manager.generate_embeddings(texts, model)


class ChatServiceWrapper:
    """Wrapper for chat functionality from service manager."""
    
    def __init__(self, service_manager: AIServiceManager):
        self.service_manager = service_manager
    
    async def generate_response(self, messages, model: Optional[str] = None, **kwargs) -> str:
        """Generate chat response."""
        return await self.service_manager.generate_chat_response(messages, model, **kwargs)
    
    async def generate_response_stream(self, messages, model: Optional[str] = None, **kwargs):
        """Generate streaming chat response."""
        async for chunk in self.service_manager.generate_chat_response_stream(messages, model, **kwargs):
            yield chunk