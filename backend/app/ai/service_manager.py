"""
AI Service Manager for handling multiple AI services with failover and health monitoring.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime, timedelta

from .interfaces import (
    BaseAIService, AIServiceType, AIServiceStatus,
    EmbeddingRequest, EmbeddingResponse,
    ChatRequest, ChatResponse, ChatMessage,
    HealthCheckResponse
)
from .openai_service import OpenAIService, OpenAIEmbeddingService, OpenAIChatService
from .ollama_service import OllamaService, OllamaEmbeddingService, OllamaChatService

logger = logging.getLogger(__name__)


class AIServiceManager:
    """Manages multiple AI services with health monitoring and failover."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.services: Dict[AIServiceType, BaseAIService] = {}
        self.embedding_services: Dict[AIServiceType, Any] = {}
        self.chat_services: Dict[AIServiceType, Any] = {}
        
        # Service priority for failover (higher priority first)
        self.service_priority = [
            AIServiceType.OPENAI,
            AIServiceType.OLLAMA,
        ]
        
        # Health check settings
        self.health_check_interval = config.get("health_check_interval", 300)  # 5 minutes
        self.health_check_timeout = config.get("health_check_timeout", 30)
        self.max_retry_attempts = config.get("max_retry_attempts", 3)
        self.retry_delay = config.get("retry_delay", 1)
        
        # Circuit breaker settings
        self.circuit_breaker_threshold = config.get("circuit_breaker_threshold", 5)
        self.circuit_breaker_timeout = config.get("circuit_breaker_timeout", 60)
        self.failure_counts: Dict[AIServiceType, int] = {}
        self.circuit_breaker_reset_time: Dict[AIServiceType, datetime] = {}
        
        self._health_check_task: Optional[asyncio.Task] = None
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize all configured AI services."""
        # Initialize OpenAI service if configured
        if self.config.get("openai", {}).get("api_key"):
            try:
                openai_config = self.config["openai"]
                openai_service = OpenAIService(openai_config)
                self.services[AIServiceType.OPENAI] = openai_service
                self.embedding_services[AIServiceType.OPENAI] = OpenAIEmbeddingService(openai_service)
                self.chat_services[AIServiceType.OPENAI] = OpenAIChatService(openai_service)
                self.failure_counts[AIServiceType.OPENAI] = 0
                logger.info("OpenAI service initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI service: {e}")
        
        # Initialize Ollama service if configured
        if self.config.get("ollama", {}).get("base_url"):
            try:
                ollama_config = self.config["ollama"]
                ollama_service = OllamaService(ollama_config)
                self.services[AIServiceType.OLLAMA] = ollama_service
                self.embedding_services[AIServiceType.OLLAMA] = OllamaEmbeddingService(ollama_service)
                self.chat_services[AIServiceType.OLLAMA] = OllamaChatService(ollama_service)
                self.failure_counts[AIServiceType.OLLAMA] = 0
                logger.info("Ollama service initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Ollama service: {e}")
    
    async def start_health_monitoring(self):
        """Start background health monitoring task."""
        if self._health_check_task is None or self._health_check_task.done():
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info("Health monitoring started")
    
    async def stop_health_monitoring(self):
        """Stop background health monitoring task."""
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            logger.info("Health monitoring stopped")
    
    async def _health_check_loop(self):
        """Background health check loop."""
        while True:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(self.health_check_interval)
    
    async def _perform_health_checks(self):
        """Perform health checks on all services."""
        for service_type, service in self.services.items():
            try:
                health_response = await asyncio.wait_for(
                    service.health_check(),
                    timeout=self.health_check_timeout
                )
                
                if health_response.status == AIServiceStatus.HEALTHY:
                    self.failure_counts[service_type] = 0
                    if service_type in self.circuit_breaker_reset_time:
                        del self.circuit_breaker_reset_time[service_type]
                else:
                    self._handle_service_failure(service_type)
                
                logger.debug(f"{service_type} health check: {health_response.status}")
                
            except asyncio.TimeoutError:
                logger.warning(f"{service_type} health check timeout")
                self._handle_service_failure(service_type)
            except Exception as e:
                logger.error(f"{service_type} health check failed: {e}")
                self._handle_service_failure(service_type)
    
    def _handle_service_failure(self, service_type: AIServiceType):
        """Handle service failure and update circuit breaker state."""
        self.failure_counts[service_type] += 1
        
        if self.failure_counts[service_type] >= self.circuit_breaker_threshold:
            self.circuit_breaker_reset_time[service_type] = (
                datetime.now() + timedelta(seconds=self.circuit_breaker_timeout)
            )
            logger.warning(f"Circuit breaker opened for {service_type}")
    
    def _is_service_available(self, service_type: AIServiceType) -> bool:
        """Check if service is available (not in circuit breaker state)."""
        if service_type not in self.circuit_breaker_reset_time:
            return True
        
        if datetime.now() > self.circuit_breaker_reset_time[service_type]:
            del self.circuit_breaker_reset_time[service_type]
            self.failure_counts[service_type] = 0
            logger.info(f"Circuit breaker reset for {service_type}")
            return True
        
        return False
    
    def _get_available_services(self, service_type_filter: Optional[List[AIServiceType]] = None) -> List[AIServiceType]:
        """Get list of available services in priority order."""
        available_services = []
        
        for service_type in self.service_priority:
            if service_type_filter and service_type not in service_type_filter:
                continue
            
            if (service_type in self.services and 
                self._is_service_available(service_type) and
                self.services[service_type].is_healthy):
                available_services.append(service_type)
        
        return available_services
    
    async def _execute_with_retry(self, func, *args, **kwargs):
        """Execute function with retry logic and failover."""
        last_exception = None
        
        for attempt in range(self.max_retry_attempts):
            available_services = self._get_available_services()
            
            if not available_services:
                raise Exception("No available AI services")
            
            for service_type in available_services:
                try:
                    return await func(service_type, *args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"Service {service_type} failed (attempt {attempt + 1}): {e}")
                    self._handle_service_failure(service_type)
            
            if attempt < self.max_retry_attempts - 1:
                await asyncio.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
        
        raise last_exception or Exception("All AI services failed")
    
    # Embedding methods
    async def generate_embedding(self, text: str, model: Optional[str] = None) -> List[float]:
        """Generate text embedding with failover."""
        async def _embed(service_type: AIServiceType, text: str, model: Optional[str]):
            embedding_service = self.embedding_services[service_type]
            return await embedding_service.embed_text(text, model)
        
        return await self._execute_with_retry(_embed, text, model)
    
    async def generate_embeddings(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """Generate multiple text embeddings with failover."""
        async def _embed_multiple(service_type: AIServiceType, texts: List[str], model: Optional[str]):
            embedding_service = self.embedding_services[service_type]
            return await embedding_service.embed_texts(texts, model)
        
        return await self._execute_with_retry(_embed_multiple, texts, model)
    
    # Chat methods
    async def generate_chat_response(
        self, 
        messages: List[ChatMessage], 
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate chat response with failover."""
        async def _chat(service_type: AIServiceType, messages: List[ChatMessage], model: Optional[str], **kwargs):
            chat_service = self.chat_services[service_type]
            return await chat_service.generate_response(messages, model, **kwargs)
        
        return await self._execute_with_retry(_chat, messages, model, **kwargs)
    
    async def generate_chat_response_stream(
        self, 
        messages: List[ChatMessage], 
        model: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate streaming chat response with failover."""
        available_services = self._get_available_services()
        
        if not available_services:
            raise Exception("No available AI services")
        
        last_exception = None
        
        for service_type in available_services:
            try:
                chat_service = self.chat_services[service_type]
                async for chunk in chat_service.generate_response_stream(messages, model, **kwargs):
                    yield chunk
                return
            except Exception as e:
                last_exception = e
                logger.warning(f"Streaming service {service_type} failed: {e}")
                self._handle_service_failure(service_type)
        
        raise last_exception or Exception("All AI services failed for streaming")
    
    # Service management methods
    async def get_service_status(self) -> Dict[str, HealthCheckResponse]:
        """Get status of all services."""
        status = {}
        
        for service_type, service in self.services.items():
            try:
                health_response = await asyncio.wait_for(
                    service.health_check(),
                    timeout=self.health_check_timeout
                )
                status[service_type.value] = health_response
            except Exception as e:
                status[service_type.value] = HealthCheckResponse(
                    status=AIServiceStatus.UNHEALTHY,
                    service_type=service_type,
                    error=str(e)
                )
        
        return status
    
    async def list_all_models(self) -> Dict[str, List[Dict[str, Any]]]:
        """List models from all available services."""
        models = {}
        
        for service_type, service in self.services.items():
            if self._is_service_available(service_type):
                try:
                    service_models = await service.list_models()
                    models[service_type.value] = service_models
                except Exception as e:
                    logger.error(f"Failed to list models for {service_type}: {e}")
                    models[service_type.value] = []
        
        return models
    
    def get_preferred_service(self) -> Optional[AIServiceType]:
        """Get the preferred (highest priority available) service."""
        available_services = self._get_available_services()
        return available_services[0] if available_services else None