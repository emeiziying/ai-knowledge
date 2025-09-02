"""
Configuration for error handling and monitoring.
"""
from typing import Dict, Any, List
from pydantic import BaseModel, Field


class CircuitBreakerConfig(BaseModel):
    """Circuit breaker configuration."""
    failure_threshold: int = Field(default=5, description="Number of failures before opening circuit")
    recovery_timeout: int = Field(default=60, description="Seconds to wait before attempting recovery")
    success_threshold: int = Field(default=3, description="Number of successes needed to close circuit")
    timeout: int = Field(default=30, description="Request timeout in seconds")


class RetryConfig(BaseModel):
    """Retry configuration."""
    max_attempts: int = Field(default=3, description="Maximum retry attempts")
    base_delay: float = Field(default=1.0, description="Base delay in seconds")
    max_delay: float = Field(default=60.0, description="Maximum delay in seconds")
    exponential_base: float = Field(default=2.0, description="Exponential backoff base")
    jitter: bool = Field(default=True, description="Enable jitter to prevent thundering herd")


class NotificationConfig(BaseModel):
    """Error notification configuration."""
    error_rate_threshold: int = Field(default=10, description="Error rate per minute threshold")
    service_failure_threshold: int = Field(default=5, description="Service failure threshold")
    critical_error_threshold: int = Field(default=3, description="Critical error threshold")
    circuit_breaker_threshold: int = Field(default=3, description="Circuit breaker notification threshold")
    degradation_threshold: int = Field(default=2, description="Service degradation threshold")
    notification_cooldown: int = Field(default=300, description="Notification cooldown in seconds")
    error_window_minutes: int = Field(default=5, description="Error rate calculation window in minutes")


class ServiceDegradationConfig(BaseModel):
    """Service degradation configuration."""
    enabled: bool = Field(default=True, description="Enable service degradation")
    fallback_order: List[str] = Field(
        default=["ollama", "openai"],
        description="Fallback service order for degradation"
    )
    degradation_timeout: int = Field(default=30, description="Timeout for degraded services")
    max_degradation_time: int = Field(default=3600, description="Maximum time to stay in degraded mode")


class MonitoringConfig(BaseModel):
    """Monitoring and metrics configuration."""
    health_check_interval: int = Field(default=300, description="Health check interval in seconds")
    health_check_timeout: int = Field(default=30, description="Health check timeout in seconds")
    metrics_retention_hours: int = Field(default=24, description="Metrics retention period in hours")
    max_error_history: int = Field(default=1000, description="Maximum error history entries")
    enable_detailed_logging: bool = Field(default=True, description="Enable detailed error logging")


class ErrorHandlingConfig(BaseModel):
    """Complete error handling configuration."""
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)
    degradation: ServiceDegradationConfig = Field(default_factory=ServiceDegradationConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    
    # Global error handling settings
    enable_error_tracking: bool = Field(default=True, description="Enable error tracking and metrics")
    enable_notifications: bool = Field(default=True, description="Enable error notifications")
    debug_mode: bool = Field(default=False, description="Enable debug mode for detailed error info")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return self.dict()
    
    @classmethod
    def from_env(cls) -> "ErrorHandlingConfig":
        """Create configuration from environment variables."""
        import os
        
        config_dict = {}
        
        # Circuit breaker settings
        if os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD"):
            config_dict.setdefault("circuit_breaker", {})["failure_threshold"] = int(
                os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD")
            )
        
        if os.getenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT"):
            config_dict.setdefault("circuit_breaker", {})["recovery_timeout"] = int(
                os.getenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT")
            )
        
        # Retry settings
        if os.getenv("RETRY_MAX_ATTEMPTS"):
            config_dict.setdefault("retry", {})["max_attempts"] = int(
                os.getenv("RETRY_MAX_ATTEMPTS")
            )
        
        if os.getenv("RETRY_BASE_DELAY"):
            config_dict.setdefault("retry", {})["base_delay"] = float(
                os.getenv("RETRY_BASE_DELAY")
            )
        
        # Notification settings
        if os.getenv("ERROR_RATE_THRESHOLD"):
            config_dict.setdefault("notification", {})["error_rate_threshold"] = int(
                os.getenv("ERROR_RATE_THRESHOLD")
            )
        
        if os.getenv("NOTIFICATION_COOLDOWN"):
            config_dict.setdefault("notification", {})["notification_cooldown"] = int(
                os.getenv("NOTIFICATION_COOLDOWN")
            )
        
        # Service degradation settings
        if os.getenv("ENABLE_SERVICE_DEGRADATION"):
            config_dict.setdefault("degradation", {})["enabled"] = (
                os.getenv("ENABLE_SERVICE_DEGRADATION").lower() == "true"
            )
        
        if os.getenv("FALLBACK_SERVICE_ORDER"):
            config_dict.setdefault("degradation", {})["fallback_order"] = (
                os.getenv("FALLBACK_SERVICE_ORDER").split(",")
            )
        
        # Monitoring settings
        if os.getenv("HEALTH_CHECK_INTERVAL"):
            config_dict.setdefault("monitoring", {})["health_check_interval"] = int(
                os.getenv("HEALTH_CHECK_INTERVAL")
            )
        
        if os.getenv("ENABLE_DETAILED_LOGGING"):
            config_dict.setdefault("monitoring", {})["enable_detailed_logging"] = (
                os.getenv("ENABLE_DETAILED_LOGGING").lower() == "true"
            )
        
        # Global settings
        if os.getenv("ENABLE_ERROR_TRACKING"):
            config_dict["enable_error_tracking"] = (
                os.getenv("ENABLE_ERROR_TRACKING").lower() == "true"
            )
        
        if os.getenv("ENABLE_ERROR_NOTIFICATIONS"):
            config_dict["enable_notifications"] = (
                os.getenv("ENABLE_ERROR_NOTIFICATIONS").lower() == "true"
            )
        
        if os.getenv("ERROR_DEBUG_MODE"):
            config_dict["debug_mode"] = (
                os.getenv("ERROR_DEBUG_MODE").lower() == "true"
            )
        
        return cls(**config_dict)


# Default configuration instance
default_error_config = ErrorHandlingConfig()


def get_error_handling_config() -> ErrorHandlingConfig:
    """Get error handling configuration from environment or defaults."""
    try:
        return ErrorHandlingConfig.from_env()
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to load error handling config from environment: {e}")
        logger.info("Using default error handling configuration")
        return default_error_config


# Configuration presets for different environments
class ErrorHandlingPresets:
    """Predefined error handling configurations for different environments."""
    
    @staticmethod
    def development() -> ErrorHandlingConfig:
        """Development environment configuration."""
        return ErrorHandlingConfig(
            circuit_breaker=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=30
            ),
            retry=RetryConfig(
                max_attempts=2,
                base_delay=0.5
            ),
            notification=NotificationConfig(
                error_rate_threshold=20,
                notification_cooldown=60
            ),
            degradation=ServiceDegradationConfig(
                enabled=True,
                degradation_timeout=15
            ),
            monitoring=MonitoringConfig(
                health_check_interval=60,
                enable_detailed_logging=True
            ),
            debug_mode=True
        )
    
    @staticmethod
    def production() -> ErrorHandlingConfig:
        """Production environment configuration."""
        return ErrorHandlingConfig(
            circuit_breaker=CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=60
            ),
            retry=RetryConfig(
                max_attempts=3,
                base_delay=1.0
            ),
            notification=NotificationConfig(
                error_rate_threshold=10,
                notification_cooldown=300
            ),
            degradation=ServiceDegradationConfig(
                enabled=True,
                degradation_timeout=30
            ),
            monitoring=MonitoringConfig(
                health_check_interval=300,
                enable_detailed_logging=False
            ),
            debug_mode=False
        )
    
    @staticmethod
    def testing() -> ErrorHandlingConfig:
        """Testing environment configuration."""
        return ErrorHandlingConfig(
            circuit_breaker=CircuitBreakerConfig(
                failure_threshold=2,
                recovery_timeout=10
            ),
            retry=RetryConfig(
                max_attempts=1,
                base_delay=0.1
            ),
            notification=NotificationConfig(
                error_rate_threshold=50,
                notification_cooldown=10
            ),
            degradation=ServiceDegradationConfig(
                enabled=False  # Disable degradation in tests
            ),
            monitoring=MonitoringConfig(
                health_check_interval=30,
                enable_detailed_logging=True
            ),
            debug_mode=True
        )