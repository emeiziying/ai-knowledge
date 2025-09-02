"""
Tests for enhanced error handling and monitoring functionality.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from fastapi import Request, HTTPException
from fastapi.testclient import TestClient

from app.middleware.error_handler import (
    APIError, AIServiceError, CircuitBreakerError, ServiceDegradationError,
    DocumentProcessingError, RateLimitError, ErrorMetrics, ErrorNotificationService,
    ErrorMonitoringService, create_error_response, api_error_handler,
    enhanced_api_error_handler, get_error_metrics, get_error_monitoring_service
)
from app.ai.service_manager import CircuitBreaker, CircuitBreakerState, RetryConfig
from app.ai.interfaces import AIServiceType


class TestErrorClasses:
    """Test custom error classes."""
    
    def test_api_error_creation(self):
        """Test APIError creation with various parameters."""
        error = APIError(
            message="Test error",
            status_code=400,
            error_code="TEST_ERROR",
            details={"key": "value"},
            retry_after=60,
            service_type="test_service"
        )
        
        assert error.message == "Test error"
        assert error.status_code == 400
        assert error.error_code == "TEST_ERROR"
        assert error.details == {"key": "value"}
        assert error.retry_after == 60
        assert error.service_type == "test_service"
    
    def test_ai_service_error(self):
        """Test AIServiceError with default values."""
        error = AIServiceError(
            message="AI service failed",
            service_type="openai"
        )
        
        assert error.message == "AI service failed"
        assert error.service_type == "openai"
        assert error.status_code == 502
        assert error.error_code == "AI_SERVICE_ERROR"
    
    def test_circuit_breaker_error(self):
        """Test CircuitBreakerError with default message."""
        error = CircuitBreakerError(service_type="ollama")
        
        assert "ollama service is temporarily unavailable" in error.message
        assert error.status_code == 503
        assert error.error_code == "CIRCUIT_BREAKER_OPEN"
        assert error.retry_after == 60
    
    def test_service_degradation_error(self):
        """Test ServiceDegradationError."""
        error = ServiceDegradationError(
            message="Using fallback service",
            fallback_used="ollama",
            original_error="OpenAI API failed"
        )
        
        assert error.message == "Using fallback service"
        assert error.status_code == 206
        assert error.error_code == "SERVICE_DEGRADED"
        assert error.details["fallback_used"] == "ollama"
        assert error.details["original_error"] == "OpenAI API failed"
    
    def test_document_processing_error(self):
        """Test DocumentProcessingError."""
        error = DocumentProcessingError(
            message="Failed to parse PDF",
            document_id="doc123",
            processing_stage="parsing"
        )
        
        assert error.message == "Failed to parse PDF"
        assert error.status_code == 422
        assert error.details["document_id"] == "doc123"
        assert error.details["processing_stage"] == "parsing"
    
    def test_rate_limit_error(self):
        """Test RateLimitError."""
        error = RateLimitError(retry_after=120)
        
        assert error.status_code == 429
        assert error.error_code == "RATE_LIMIT_EXCEEDED"
        assert error.retry_after == 120


class TestErrorMetrics:
    """Test error metrics collection."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = ErrorMetrics()
    
    def test_record_error_basic(self):
        """Test basic error recording."""
        self.metrics.record_error("TEST_ERROR", "test_service", 500)
        
        metrics_data = self.metrics.get_metrics()
        assert metrics_data["error_counts"]["TEST_ERROR"] == 1
        assert metrics_data["service_errors"]["test_service"]["TEST_ERROR"] == 1
        assert metrics_data["status_code_counts"][500] == 1
        assert metrics_data["total_errors"] == 1
    
    def test_record_multiple_errors(self):
        """Test recording multiple errors."""
        self.metrics.record_error("ERROR_A", "service1", 400)
        self.metrics.record_error("ERROR_B", "service1", 500)
        self.metrics.record_error("ERROR_A", "service2", 400)
        
        metrics_data = self.metrics.get_metrics()
        assert metrics_data["error_counts"]["ERROR_A"] == 2
        assert metrics_data["error_counts"]["ERROR_B"] == 1
        assert metrics_data["service_errors"]["service1"]["ERROR_A"] == 1
        assert metrics_data["service_errors"]["service1"]["ERROR_B"] == 1
        assert metrics_data["service_errors"]["service2"]["ERROR_A"] == 1
        assert metrics_data["total_errors"] == 3
    
    def test_hourly_error_tracking(self):
        """Test hourly error tracking."""
        # Record errors
        self.metrics.record_error("TEST_ERROR", "test_service", 500)
        
        metrics_data = self.metrics.get_metrics()
        current_hour = datetime.utcnow().strftime("%Y-%m-%d-%H")
        
        assert current_hour in metrics_data["hourly_error_counts"]
        assert metrics_data["hourly_error_counts"][current_hour] == 1
        assert metrics_data["last_hour_errors"] == 1
    
    def test_error_history(self):
        """Test error history tracking."""
        self.metrics.record_error(
            "TEST_ERROR", 
            "test_service", 
            500,
            user_id="user123",
            endpoint="/api/test",
            error_details={"key": "value"}
        )
        
        metrics_data = self.metrics.get_metrics()
        assert len(metrics_data["recent_errors"]) == 1
        
        error_record = metrics_data["recent_errors"][0]
        assert error_record["error_code"] == "TEST_ERROR"
        assert error_record["service_type"] == "test_service"
        assert error_record["user_id"] == "user123"
        assert error_record["endpoint"] == "/api/test"
        assert error_record["details"]["key"] == "value"
    
    def test_service_health_summary(self):
        """Test service health summary generation."""
        # Record some errors for different services
        self.metrics.record_error("ERROR_1", "service1", 500)
        self.metrics.record_error("ERROR_2", "service2", 400)
        
        health_summary = self.metrics.get_service_health_summary()
        
        assert "service1" in health_summary
        assert "service2" in health_summary
        assert health_summary["service1"]["total_errors"] == 1
        assert health_summary["service2"]["total_errors"] == 1
        assert health_summary["service1"]["health_status"] == "warning"
    
    def test_reset_metrics(self):
        """Test metrics reset functionality."""
        self.metrics.record_error("TEST_ERROR", "test_service", 500)
        
        # Verify data exists
        metrics_data = self.metrics.get_metrics()
        assert metrics_data["total_errors"] == 1
        
        # Reset and verify
        self.metrics.reset_metrics()
        metrics_data = self.metrics.get_metrics()
        assert metrics_data["total_errors"] == 0
        assert len(metrics_data["error_counts"]) == 0
        assert len(metrics_data["error_history"]) == 0


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.circuit_breaker = CircuitBreaker(
            service_type=AIServiceType.OPENAI,
            failure_threshold=3,
            recovery_timeout=60,
            success_threshold=2
        )
    
    def test_initial_state(self):
        """Test circuit breaker initial state."""
        assert self.circuit_breaker.state == CircuitBreakerState.CLOSED
        assert self.circuit_breaker.can_execute() is True
        assert self.circuit_breaker.failure_count == 0
    
    def test_failure_recording(self):
        """Test failure recording and state transitions."""
        # Record failures below threshold
        self.circuit_breaker.record_failure()
        self.circuit_breaker.record_failure()
        assert self.circuit_breaker.state == CircuitBreakerState.CLOSED
        
        # Record failure that trips the breaker
        self.circuit_breaker.record_failure()
        assert self.circuit_breaker.state == CircuitBreakerState.OPEN
        assert self.circuit_breaker.can_execute() is False
    
    def test_success_recording(self):
        """Test success recording and reset."""
        # Trip the breaker
        for _ in range(3):
            self.circuit_breaker.record_failure()
        
        assert self.circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Simulate recovery timeout
        self.circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=70)
        assert self.circuit_breaker.can_execute() is True
        assert self.circuit_breaker.state == CircuitBreakerState.HALF_OPEN
        
        # Record successes to reset
        self.circuit_breaker.record_success()
        self.circuit_breaker.record_success()
        assert self.circuit_breaker.state == CircuitBreakerState.CLOSED
    
    def test_half_open_failure(self):
        """Test failure in half-open state."""
        # Trip the breaker and move to half-open
        for _ in range(3):
            self.circuit_breaker.record_failure()
        
        self.circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=70)
        self.circuit_breaker.can_execute()  # Moves to HALF_OPEN
        
        # Failure in half-open should trip back to open
        self.circuit_breaker.record_failure()
        assert self.circuit_breaker.state == CircuitBreakerState.OPEN
    
    def test_get_status(self):
        """Test status reporting."""
        status = self.circuit_breaker.get_status()
        
        assert status["state"] == CircuitBreakerState.CLOSED.value
        assert status["failure_count"] == 0
        assert status["success_count"] == 0
        assert status["last_failure_time"] is None


class TestErrorNotificationService:
    """Test error notification service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.notification_service = ErrorNotificationService({
            "error_rate_threshold": 5,
            "critical_error_threshold": 3,
            "notification_cooldown": 60
        })
    
    @pytest.mark.asyncio
    async def test_notification_threshold_check(self):
        """Test notification threshold checking."""
        # Record errors below threshold
        await self.notification_service.check_and_notify("TEST_ERROR", "test_service", "warning")
        await self.notification_service.check_and_notify("TEST_ERROR", "test_service", "warning")
        
        # Should not trigger notification yet
        assert len(self.notification_service.last_notifications) == 0
        
        # Record error that exceeds threshold
        await self.notification_service.check_and_notify("TEST_ERROR", "test_service", "warning")
        await self.notification_service.check_and_notify("TEST_ERROR", "test_service", "warning")
        
        # Should trigger notification
        assert len(self.notification_service.last_notifications) > 0
    
    @pytest.mark.asyncio
    async def test_notification_cooldown(self):
        """Test notification cooldown mechanism."""
        # Trigger notification
        for _ in range(4):
            await self.notification_service.check_and_notify("TEST_ERROR", "test_service", "warning")
        
        initial_count = len(self.notification_service.last_notifications)
        
        # Try to trigger again immediately (should be blocked by cooldown)
        await self.notification_service.check_and_notify("TEST_ERROR", "test_service", "warning")
        
        assert len(self.notification_service.last_notifications) == initial_count
    
    @pytest.mark.asyncio
    async def test_critical_error_immediate_notification(self):
        """Test that critical errors trigger immediate notifications."""
        await self.notification_service.check_and_notify("CRITICAL_ERROR", "test_service", "critical")
        
        # Should trigger notification immediately
        assert len(self.notification_service.last_notifications) > 0
    
    def test_recommended_actions(self):
        """Test recommended actions for different error types."""
        actions = self.notification_service._get_recommended_actions("CIRCUIT_BREAKER_OPEN", "openai")
        assert any("Check openai service health" in action for action in actions)
        
        actions = self.notification_service._get_recommended_actions("SERVICE_DEGRADED", "ollama")
        assert any("Monitor fallback service performance" in action for action in actions)
        
        actions = self.notification_service._get_recommended_actions("AI_SERVICE_ERROR", None)
        assert any("Check AI service API status" in action for action in actions)


class TestErrorMonitoringService:
    """Test error monitoring service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.monitoring_service = ErrorMonitoringService()
        # Clear any existing metrics
        self.monitoring_service.metrics.reset_metrics()
    
    def test_error_dashboard(self):
        """Test error dashboard data generation."""
        # Record some test errors
        self.monitoring_service.metrics.record_error("ERROR_1", "service1", 500)
        self.monitoring_service.metrics.record_error("ERROR_2", "service2", 400)
        
        dashboard = self.monitoring_service.get_error_dashboard()
        
        assert "overview" in dashboard
        assert "error_breakdown" in dashboard
        assert "service_health" in dashboard
        assert "recent_errors" in dashboard
        assert "trends" in dashboard
        
        assert dashboard["overview"]["total_errors"] == 2
        assert len(dashboard["error_breakdown"]["by_code"]) > 0
    
    def test_service_degradation_status(self):
        """Test service degradation status reporting."""
        # Record errors to simulate degraded services
        for _ in range(10):  # High error count for critical status
            self.monitoring_service.metrics.record_error("ERROR_1", "service1", 500)
        
        for _ in range(3):  # Medium error count for warning status
            self.monitoring_service.metrics.record_error("ERROR_2", "service2", 400)
        
        degradation_status = self.monitoring_service.get_service_degradation_status()
        
        assert degradation_status["overall_status"] in ["critical", "warning", "healthy"]
        assert "critical_services" in degradation_status
        assert "degraded_services" in degradation_status
        assert "healthy_services" in degradation_status
    
    def test_error_pattern_analysis(self):
        """Test error pattern analysis."""
        # Record various errors
        for _ in range(25):  # High frequency error
            self.monitoring_service.metrics.record_error("HIGH_FREQ_ERROR", "service1", 500)
        
        for _ in range(3):  # Low frequency error
            self.monitoring_service.metrics.record_error("LOW_FREQ_ERROR", "service2", 400)
        
        analysis = self.monitoring_service.analyze_error_patterns()
        
        assert "error_patterns" in analysis
        assert "service_reliability" in analysis
        assert "recommendations" in analysis
        
        # High frequency error should be analyzed
        assert "HIGH_FREQ_ERROR" in analysis["error_patterns"]
        assert analysis["error_patterns"]["HIGH_FREQ_ERROR"]["severity"] == "high"
        
        # Low frequency error should not be analyzed
        assert "LOW_FREQ_ERROR" not in analysis["error_patterns"]


class TestRetryConfig:
    """Test retry configuration."""
    
    def test_retry_delay_calculation(self):
        """Test retry delay calculation with exponential backoff."""
        config = RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=False  # Disable jitter for predictable testing
        )
        
        # Test delay progression
        assert config.get_delay(0) == 1.0  # Base delay
        assert config.get_delay(1) == 2.0  # 1 * 2^1
        assert config.get_delay(2) == 4.0  # 1 * 2^2
    
    def test_retry_delay_max_limit(self):
        """Test that retry delay respects max limit."""
        config = RetryConfig(
            base_delay=1.0,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=False
        )
        
        # Large attempt number should be capped at max_delay
        assert config.get_delay(10) == 5.0
    
    def test_retry_delay_with_jitter(self):
        """Test retry delay with jitter enabled."""
        config = RetryConfig(
            base_delay=2.0,
            exponential_base=2.0,
            jitter=True
        )
        
        delay = config.get_delay(1)
        # With jitter, delay should be between 50% and 100% of calculated delay
        expected_base = 4.0  # 2 * 2^1
        assert expected_base * 0.5 <= delay <= expected_base


@pytest.mark.asyncio
class TestErrorHandlers:
    """Test error handler functions."""
    
    async def test_create_error_response(self):
        """Test error response creation."""
        response = create_error_response(
            status_code=400,
            message="Test error",
            error_code="TEST_ERROR",
            details={"key": "value"},
            retry_after=60
        )
        
        assert response.status_code == 400
        assert "Retry-After" in response.headers
        assert response.headers["Retry-After"] == "60"
        
        content = response.body.decode()
        assert "Test error" in content
        assert "TEST_ERROR" in content
    
    async def test_api_error_handler(self):
        """Test API error handler."""
        # Create mock request
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.__str__ = Mock(return_value="http://test.com/api/test")
        request.method = "POST"
        request.headers = {"user-agent": "test-agent"}
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.state = Mock()
        request.state.request_id = "test-request-123"
        
        # Create test error
        error = APIError(
            message="Test API error",
            status_code=400,
            error_code="TEST_API_ERROR"
        )
        
        # Call handler
        response = await api_error_handler(request, error)
        
        assert response.status_code == 400
        content = response.body.decode()
        assert "Test API error" in content
        assert "TEST_API_ERROR" in content
    
    async def test_enhanced_api_error_handler_metrics(self):
        """Test that enhanced error handler records metrics."""
        # Create mock request
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "POST"
        request.headers = {"user-agent": "test-agent"}
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.state = Mock()
        request.state.user_id = "user123"
        request.state.request_id = "test-request-123"  # Add request_id
        
        # Create test error
        error = AIServiceError(
            message="AI service failed",
            service_type="openai"
        )
        
        # Clear metrics before test
        get_error_metrics().reset_metrics()
        
        # Call enhanced handler
        response = await enhanced_api_error_handler(request, error)
        
        # Verify metrics were recorded
        metrics = get_error_metrics().get_metrics()
        assert metrics["total_errors"] == 1
        assert "AI_SERVICE_ERROR" in metrics["error_counts"]
        assert "openai" in metrics["service_errors"]
        
        # Verify response
        assert response.status_code == 502


if __name__ == "__main__":
    pytest.main([__file__])