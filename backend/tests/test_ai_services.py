"""
Tests for AI services integration.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from app.ai.interfaces import (
    AIServiceType, AIServiceStatus, ChatMessage,
    EmbeddingRequest, EmbeddingResponse,
    ChatRequest, ChatResponse,
    HealthCheckResponse
)
from app.ai.service_manager import AIServiceManager
from app.ai.factory import AIServiceFactory
from app.config import Settings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Settings()
    settings.openai_api_key = "test-api-key"
    settings.ollama_base_url = "http://localhost:11434"
    return settings


@pytest.fixture
def ai_config():
    """Create AI service configuration for testing."""
    return {
        "openai": {
            "api_key": "test-api-key",
            "default_chat_model": "gpt-3.5-turbo",
            "default_embedding_model": "text-embedding-ada-002"
        },
        "ollama": {
            "base_url": "http://localhost:11434",
            "default_chat_model": "llama2",
            "default_embedding_model": "nomic-embed-text"
        },
        "health_check_interval": 300,
        "max_retry_attempts": 3,
        "circuit_breaker_threshold": 5
    }


class TestAIServiceManager:
    """Test AI Service Manager functionality."""
    
    def test_service_manager_initialization(self, ai_config):
        """Test service manager initialization."""
        with patch('app.ai.service_manager.OpenAIService') as mock_openai, \
             patch('app.ai.service_manager.OllamaService') as mock_ollama:
            
            manager = AIServiceManager(ai_config)
            
            # Check that services were initialized
            assert AIServiceType.OPENAI in manager.services
            assert AIServiceType.OLLAMA in manager.services
            assert len(manager.services) == 2
    
    @pytest.mark.asyncio
    async def test_embedding_generation_with_failover(self, ai_config):
        """Test embedding generation with service failover."""
        with patch('app.ai.service_manager.OpenAIService') as mock_openai_class, \
             patch('app.ai.service_manager.OllamaService') as mock_ollama_class:
            
            # Setup mock services
            mock_openai = AsyncMock()
            mock_ollama = AsyncMock()
            mock_openai_class.return_value = mock_openai
            mock_ollama_class.return_value = mock_ollama
            
            # Mock embedding services
            mock_openai_embedding = AsyncMock()
            mock_ollama_embedding = AsyncMock()
            
            # First service fails, second succeeds
            mock_openai_embedding.embed_text.side_effect = Exception("OpenAI failed")
            mock_ollama_embedding.embed_text.return_value = [0.1, 0.2, 0.3]
            
            manager = AIServiceManager(ai_config)
            manager.embedding_services[AIServiceType.OPENAI] = mock_openai_embedding
            manager.embedding_services[AIServiceType.OLLAMA] = mock_ollama_embedding
            
            # Test failover
            result = await manager.generate_embedding("test text")
            
            assert result == [0.1, 0.2, 0.3]
            mock_openai_embedding.embed_text.assert_called_once()
            mock_ollama_embedding.embed_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_chat_response_generation(self, ai_config):
        """Test chat response generation."""
        with patch('app.ai.service_manager.OpenAIService') as mock_openai_class:
            
            # Setup mock service
            mock_openai = AsyncMock()
            mock_openai_class.return_value = mock_openai
            
            # Mock chat service
            mock_chat_service = AsyncMock()
            mock_chat_service.generate_response.return_value = "Test response"
            
            manager = AIServiceManager(ai_config)
            manager.chat_services[AIServiceType.OPENAI] = mock_chat_service
            
            messages = [ChatMessage(role="user", content="Hello")]
            result = await manager.generate_chat_response(messages)
            
            assert result == "Test response"
            mock_chat_service.generate_response.assert_called_once_with(
                messages, None
            )
    
    @pytest.mark.asyncio
    async def test_service_health_check(self, ai_config):
        """Test service health checking."""
        with patch('app.ai.service_manager.OpenAIService') as mock_openai_class:
            
            # Setup mock service
            mock_openai = AsyncMock()
            mock_openai_class.return_value = mock_openai
            
            # Mock health check response
            health_response = HealthCheckResponse(
                status=AIServiceStatus.HEALTHY,
                service_type=AIServiceType.OPENAI,
                response_time_ms=100.0
            )
            mock_openai.health_check.return_value = health_response
            
            manager = AIServiceManager(ai_config)
            
            status = await manager.get_service_status()
            
            assert AIServiceType.OPENAI.value in status
            assert status[AIServiceType.OPENAI.value].status == AIServiceStatus.HEALTHY
    
    def test_circuit_breaker_functionality(self, ai_config):
        """Test circuit breaker pattern."""
        manager = AIServiceManager(ai_config)
        
        # Simulate multiple failures
        for _ in range(6):  # Exceed threshold of 5
            manager._handle_service_failure(AIServiceType.OPENAI)
        
        # Service should be unavailable due to circuit breaker
        assert not manager._is_service_available(AIServiceType.OPENAI)
        assert AIServiceType.OPENAI in manager.circuit_breaker_reset_time


class TestAIServiceFactory:
    """Test AI Service Factory functionality."""
    
    def test_create_service_manager(self, mock_settings):
        """Test service manager creation from settings."""
        with patch('app.ai.factory.AIServiceManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            
            result = AIServiceFactory.create_service_manager(mock_settings)
            
            assert result == mock_manager
            mock_manager_class.assert_called_once()
    
    def test_build_config_from_settings(self, mock_settings):
        """Test configuration building from settings."""
        config = AIServiceFactory._build_config(mock_settings)
        
        assert "openai" in config
        assert "ollama" in config
        assert config["openai"]["api_key"] == "test-api-key"
        assert config["ollama"]["base_url"] == "http://localhost:11434"
    
    def test_create_embedding_service(self, mock_settings):
        """Test embedding service wrapper creation."""
        with patch('app.ai.factory.AIServiceFactory.create_service_manager') as mock_create:
            mock_manager = MagicMock()
            mock_create.return_value = mock_manager
            
            service = AIServiceFactory.create_embedding_service(mock_settings)
            
            assert service.service_manager == mock_manager
    
    def test_create_chat_service(self, mock_settings):
        """Test chat service wrapper creation."""
        with patch('app.ai.factory.AIServiceFactory.create_service_manager') as mock_create:
            mock_manager = MagicMock()
            mock_create.return_value = mock_manager
            
            service = AIServiceFactory.create_chat_service(mock_settings)
            
            assert service.service_manager == mock_manager


class TestServiceWrappers:
    """Test service wrapper classes."""
    
    @pytest.mark.asyncio
    async def test_embedding_service_wrapper(self):
        """Test embedding service wrapper functionality."""
        from app.ai.factory import EmbeddingServiceWrapper
        
        mock_manager = AsyncMock()
        mock_manager.generate_embedding.return_value = [0.1, 0.2, 0.3]
        mock_manager.generate_embeddings.return_value = [[0.1, 0.2], [0.3, 0.4]]
        
        wrapper = EmbeddingServiceWrapper(mock_manager)
        
        # Test single embedding
        result = await wrapper.embed_text("test")
        assert result == [0.1, 0.2, 0.3]
        
        # Test multiple embeddings
        results = await wrapper.embed_texts(["test1", "test2"])
        assert results == [[0.1, 0.2], [0.3, 0.4]]
    
    @pytest.mark.asyncio
    async def test_chat_service_wrapper(self):
        """Test chat service wrapper functionality."""
        from app.ai.factory import ChatServiceWrapper
        
        mock_manager = AsyncMock()
        mock_manager.generate_chat_response.return_value = "Test response"
        
        # Mock async generator for streaming
        async def mock_stream(*args, **kwargs):
            yield "chunk1"
            yield "chunk2"
        
        mock_manager.generate_chat_response_stream = mock_stream
        
        wrapper = ChatServiceWrapper(mock_manager)
        
        # Test regular response
        messages = [ChatMessage(role="user", content="Hello")]
        result = await wrapper.generate_response(messages)
        assert result == "Test response"
        
        # Test streaming response
        chunks = []
        async for chunk in wrapper.generate_response_stream(messages):
            chunks.append(chunk)
        assert chunks == ["chunk1", "chunk2"]


@pytest.mark.asyncio
async def test_ai_service_integration():
    """Integration test for AI services."""
    # This test would require actual AI service endpoints
    # For now, we'll test the configuration and initialization
    
    config = {
        "openai": {
            "api_key": "test-key",
            "default_chat_model": "gpt-3.5-turbo"
        },
        "health_check_interval": 60,
        "max_retry_attempts": 2
    }
    
    with patch('app.ai.service_manager.OpenAIService') as mock_service:
        mock_instance = AsyncMock()
        mock_service.return_value = mock_instance
        
        manager = AIServiceManager(config)
        
        # Verify service was initialized
        assert AIServiceType.OPENAI in manager.services
        assert manager.max_retry_attempts == 2
        assert manager.health_check_interval == 60