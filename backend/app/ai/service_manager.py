"""
AI Service Manager for handling multiple AI services with failover and health monitoring.
"""
import asyncio
import logging
import random
from typing import Dict, List, Optional, Any, AsyncGenerator, Callable
from datetime import datetime, timedelta
from enum import Enum

from .interfaces import (
    BaseAIService, AIServiceType, AIServiceStatus,
    EmbeddingRequest, EmbeddingResponse,
    ChatRequest, ChatResponse, ChatMessage,
    HealthCheckResponse
)
from .openai_service import OpenAIService, OpenAIEmbeddingService, OpenAIChatService
from .ollama_service import OllamaService, OllamaEmbeddingService, OllamaChatService
from ..middleware.error_handler import AIServiceError, CircuitBreakerError, ServiceDegradationError

logger = logging.getLogger(__name__)


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Enhanced circuit breaker implementation."""
    
    def __init__(
        self,
        service_type: AIServiceType,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 3,
        timeout: int = 30
    ):
        self.service_type = service_type
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.timeout = timeout
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
        
    def can_execute(self) -> bool:
        """Check if request can be executed."""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                logger.info(f"Circuit breaker for {self.service_type} moved to HALF_OPEN")
                return True
            return False
        
        # HALF_OPEN state
        return True
    
    def record_success(self):
        """Record successful execution."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._reset()
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0
    
    def record_failure(self):
        """Record failed execution."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self._trip()
        elif (self.state == CircuitBreakerState.CLOSED and 
              self.failure_count >= self.failure_threshold):
            self._trip()
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        if not self.last_failure_time:
            return True
        
        return (datetime.now() - self.last_failure_time).total_seconds() >= self.recovery_timeout
    
    def _trip(self):
        """Trip the circuit breaker to OPEN state."""
        self.state = CircuitBreakerState.OPEN
        logger.warning(f"Circuit breaker for {self.service_type} tripped to OPEN")
    
    def _reset(self):
        """Reset the circuit breaker to CLOSED state."""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info(f"Circuit breaker for {self.service_type} reset to CLOSED")
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "next_retry_time": (
                (self.last_failure_time + timedelta(seconds=self.recovery_timeout)).isoformat()
                if self.last_failure_time and self.state == CircuitBreakerState.OPEN
                else None
            )
        }


class RetryConfig:
    """Configuration for retry logic."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt."""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # Add jitter to prevent thundering herd
            delay *= (0.5 + random.random() * 0.5)
        
        return delay


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
        
        # Enhanced retry configuration
        self.retry_config = RetryConfig(
            max_attempts=config.get("max_retry_attempts", 3),
            base_delay=config.get("retry_base_delay", 1.0),
            max_delay=config.get("retry_max_delay", 60.0),
            exponential_base=config.get("retry_exponential_base", 2.0),
            jitter=config.get("retry_jitter", True)
        )
        
        # Circuit breakers for each service
        self.circuit_breakers: Dict[AIServiceType, CircuitBreaker] = {}
        
        # Service degradation settings
        self.enable_degradation = config.get("enable_service_degradation", True)
        self.degradation_fallback_order = config.get("degradation_fallback_order", [
            AIServiceType.OLLAMA,  # Prefer local models for degradation
            AIServiceType.OPENAI
        ])
        
        # Performance tracking
        self.service_performance: Dict[AIServiceType, Dict[str, Any]] = {}
        
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
                
                # Initialize circuit breaker
                self.circuit_breakers[AIServiceType.OPENAI] = CircuitBreaker(
                    service_type=AIServiceType.OPENAI,
                    failure_threshold=self.config.get("circuit_breaker_threshold", 5),
                    recovery_timeout=self.config.get("circuit_breaker_timeout", 60)
                )
                
                # Initialize performance tracking
                self.service_performance[AIServiceType.OPENAI] = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "average_response_time": 0.0,
                    "last_success_time": None,
                    "last_failure_time": None
                }
                
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
                
                # Initialize circuit breaker
                self.circuit_breakers[AIServiceType.OLLAMA] = CircuitBreaker(
                    service_type=AIServiceType.OLLAMA,
                    failure_threshold=self.config.get("circuit_breaker_threshold", 5),
                    recovery_timeout=self.config.get("circuit_breaker_timeout", 60)
                )
                
                # Initialize performance tracking
                self.service_performance[AIServiceType.OLLAMA] = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "average_response_time": 0.0,
                    "last_success_time": None,
                    "last_failure_time": None
                }
                
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
    
    def _handle_service_failure(self, service_type: AIServiceType, error: Exception = None):
        """Handle service failure and update circuit breaker state."""
        if service_type in self.circuit_breakers:
            self.circuit_breakers[service_type].record_failure()
        
        # Update performance metrics
        if service_type in self.service_performance:
            self.service_performance[service_type]["failed_requests"] += 1
            self.service_performance[service_type]["last_failure_time"] = datetime.now()
        
        logger.warning(f"Service failure recorded for {service_type}: {error}")
    
    def _handle_service_success(self, service_type: AIServiceType, response_time: float = None):
        """Handle service success and update metrics."""
        if service_type in self.circuit_breakers:
            self.circuit_breakers[service_type].record_success()
        
        # Update performance metrics
        if service_type in self.service_performance:
            perf = self.service_performance[service_type]
            perf["successful_requests"] += 1
            perf["last_success_time"] = datetime.now()
            
            if response_time is not None:
                # Update average response time
                total_requests = perf["total_requests"]
                current_avg = perf["average_response_time"]
                perf["average_response_time"] = (
                    (current_avg * total_requests + response_time) / (total_requests + 1)
                )
    
    def _is_service_available(self, service_type: AIServiceType) -> bool:
        """Check if service is available (not in circuit breaker state)."""
        if service_type not in self.circuit_breakers:
            return True
        
        return self.circuit_breakers[service_type].can_execute()
    
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
    
    async def _execute_with_retry(self, func: Callable, *args, **kwargs):
        """Execute function with enhanced retry logic and failover."""
        last_exception = None
        attempted_services = set()
        
        for attempt in range(self.retry_config.max_attempts):
            available_services = self._get_available_services()
            
            if not available_services:
                if self.enable_degradation:
                    return await self._execute_with_degradation(func, attempted_services, *args, **kwargs)
                else:
                    raise AIServiceError(
                        message="No available AI services",
                        service_type="all",
                        error_code="ALL_SERVICES_UNAVAILABLE"
                    )
            
            for service_type in available_services:
                if service_type in attempted_services:
                    continue
                
                try:
                    start_time = datetime.now()
                    
                    # Update performance metrics
                    if service_type in self.service_performance:
                        self.service_performance[service_type]["total_requests"] += 1
                    
                    result = await func(service_type, *args, **kwargs)
                    
                    # Record success
                    response_time = (datetime.now() - start_time).total_seconds() * 1000
                    self._handle_service_success(service_type, response_time)
                    
                    return result
                    
                except Exception as e:
                    last_exception = e
                    attempted_services.add(service_type)
                    
                    logger.warning(f"Service {service_type} failed (attempt {attempt + 1}): {e}")
                    self._handle_service_failure(service_type, e)
                    
                    # Check if this is a circuit breaker error
                    if service_type in self.circuit_breakers:
                        cb_status = self.circuit_breakers[service_type].get_status()
                        if cb_status["state"] == CircuitBreakerState.OPEN.value:
                            raise CircuitBreakerError(
                                service_type=service_type.value,
                                retry_after=60
                            )
            
            # Wait before next attempt if we have more attempts
            if attempt < self.retry_config.max_attempts - 1:
                delay = self.retry_config.get_delay(attempt)
                logger.info(f"Retrying in {delay:.2f} seconds (attempt {attempt + 1})")
                await asyncio.sleep(delay)
        
        # If we get here, all retries failed
        if self.enable_degradation:
            return await self._execute_with_degradation(func, attempted_services, *args, **kwargs)
        
        raise last_exception or AIServiceError(
            message="All AI services failed after retries",
            service_type="all",
            error_code="ALL_RETRIES_EXHAUSTED"
        )
    
    async def _execute_with_degradation(self, func: Callable, attempted_services: set, *args, **kwargs):
        """Execute with service degradation fallback."""
        logger.warning("Attempting service degradation")
        
        # Try fallback services in degradation order
        for service_type in self.degradation_fallback_order:
            if service_type in attempted_services or service_type not in self.services:
                continue
            
            try:
                logger.info(f"Attempting degraded service: {service_type}")
                result = await func(service_type, *args, **kwargs)
                
                # Wrap result to indicate degradation
                if isinstance(result, str):
                    degradation_notice = "\n\n[注意：此回答由备用服务生成，可能质量有所不同]"
                    result = result + degradation_notice
                
                raise ServiceDegradationError(
                    message="Response generated using fallback service",
                    fallback_used=service_type.value,
                    original_error="Primary services unavailable"
                )
                
            except ServiceDegradationError:
                # Re-raise degradation errors
                raise
            except Exception as e:
                logger.warning(f"Degradation service {service_type} also failed: {e}")
                continue
        
        # All degradation attempts failed
        raise AIServiceError(
            message="All AI services including degradation fallbacks failed",
            service_type="all",
            error_code="DEGRADATION_FAILED"
        )
    
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
    async def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all services."""
        status = {}
        
        for service_type, service in self.services.items():
            try:
                health_response = await asyncio.wait_for(
                    service.health_check(),
                    timeout=self.health_check_timeout
                )
                
                # Get circuit breaker status
                cb_status = {}
                if service_type in self.circuit_breakers:
                    cb_status = self.circuit_breakers[service_type].get_status()
                
                # Get performance metrics
                perf_metrics = self.service_performance.get(service_type, {})
                
                status[service_type.value] = {
                    "health": health_response.dict(),
                    "circuit_breaker": cb_status,
                    "performance": {
                        **perf_metrics,
                        "last_success_time": (
                            perf_metrics.get("last_success_time").isoformat()
                            if perf_metrics.get("last_success_time") else None
                        ),
                        "last_failure_time": (
                            perf_metrics.get("last_failure_time").isoformat()
                            if perf_metrics.get("last_failure_time") else None
                        ),
                        "success_rate": (
                            perf_metrics.get("successful_requests", 0) / 
                            max(perf_metrics.get("total_requests", 1), 1) * 100
                        )
                    },
                    "is_available": self._is_service_available(service_type)
                }
                
            except Exception as e:
                status[service_type.value] = {
                    "health": {
                        "status": AIServiceStatus.UNHEALTHY.value,
                        "service_type": service_type.value,
                        "error": str(e)
                    },
                    "circuit_breaker": (
                        self.circuit_breakers[service_type].get_status()
                        if service_type in self.circuit_breakers else {}
                    ),
                    "performance": self.service_performance.get(service_type, {}),
                    "is_available": False
                }
        
        return {
            "services": status,
            "summary": {
                "total_services": len(self.services),
                "available_services": len(self._get_available_services()),
                "degradation_enabled": self.enable_degradation,
                "preferred_service": (
                    self.get_preferred_service().value
                    if self.get_preferred_service() else None
                )
            }
        }
    
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
    
    def reset_circuit_breaker(self, service_type: AIServiceType) -> bool:
        """Manually reset circuit breaker for a service."""
        if service_type in self.circuit_breakers:
            self.circuit_breakers[service_type]._reset()
            logger.info(f"Circuit breaker manually reset for {service_type}")
            return True
        return False
    
    def reset_all_circuit_breakers(self):
        """Reset all circuit breakers."""
        for service_type in self.circuit_breakers:
            self.reset_circuit_breaker(service_type)
        logger.info("All circuit breakers reset")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed performance metrics for all services."""
        metrics = {}
        
        for service_type, perf in self.service_performance.items():
            metrics[service_type.value] = {
                **perf,
                "last_success_time": (
                    perf.get("last_success_time").isoformat()
                    if perf.get("last_success_time") else None
                ),
                "last_failure_time": (
                    perf.get("last_failure_time").isoformat()
                    if perf.get("last_failure_time") else None
                ),
                "success_rate": (
                    perf.get("successful_requests", 0) / 
                    max(perf.get("total_requests", 1), 1) * 100
                ),
                "failure_rate": (
                    perf.get("failed_requests", 0) / 
                    max(perf.get("total_requests", 1), 1) * 100
                )
            }
        
        return metrics
    
    def reset_performance_metrics(self, service_type: Optional[AIServiceType] = None):
        """Reset performance metrics for a service or all services."""
        if service_type:
            if service_type in self.service_performance:
                self.service_performance[service_type] = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "average_response_time": 0.0,
                    "last_success_time": None,
                    "last_failure_time": None
                }
                logger.info(f"Performance metrics reset for {service_type}")
        else:
            for service_type in self.service_performance:
                self.reset_performance_metrics(service_type)
            logger.info("All performance metrics reset")
    
    async def test_service_connectivity(self, service_type: AIServiceType) -> Dict[str, Any]:
        """Test connectivity to a specific service."""
        if service_type not in self.services:
            return {
                "service_type": service_type.value,
                "available": False,
                "error": "Service not configured"
            }
        
        try:
            start_time = datetime.now()
            health_response = await asyncio.wait_for(
                self.services[service_type].health_check(),
                timeout=self.health_check_timeout
            )
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                "service_type": service_type.value,
                "available": health_response.status == AIServiceStatus.HEALTHY,
                "response_time_ms": response_time,
                "health_response": health_response.dict()
            }
            
        except Exception as e:
            return {
                "service_type": service_type.value,
                "available": False,
                "error": str(e),
                "response_time_ms": None
            }
    
    def configure_service_priority(self, priority_order: List[AIServiceType]):
        """Update service priority order for failover."""
        # Validate that all services in priority order are configured
        valid_services = [s for s in priority_order if s in self.services]
        
        if valid_services:
            self.service_priority = valid_services
            logger.info(f"Service priority updated: {[s.value for s in valid_services]}")
        else:
            logger.warning("No valid services in priority order, keeping current configuration")
    
    def enable_service_degradation(self, enabled: bool):
        """Enable or disable service degradation."""
        self.enable_degradation = enabled
        logger.info(f"Service degradation {'enabled' if enabled else 'disabled'}")
    
    def update_retry_config(self, **kwargs):
        """Update retry configuration."""
        for key, value in kwargs.items():
            if hasattr(self.retry_config, key):
                setattr(self.retry_config, key, value)
                logger.info(f"Retry config updated: {key} = {value}")
    
    async def graceful_shutdown(self):
        """Gracefully shutdown the service manager."""
        logger.info("Starting graceful shutdown of AI Service Manager")
        
        # Stop health monitoring
        await self.stop_health_monitoring()
        
        # Close all service connections
        for service_type, service in self.services.items():
            try:
                if hasattr(service, 'close'):
                    await service.close()
                logger.info(f"Service {service_type} closed")
            except Exception as e:
                logger.error(f"Error closing service {service_type}: {e}")
        
        logger.info("AI Service Manager shutdown complete")