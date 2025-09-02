"""Error handling middleware and exception handlers."""

import logging
import traceback
import uuid
from datetime import datetime, timedelta
from typing import Union, Dict, Any, Optional, List
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Custom API error class."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: Union[str, dict] = None,
        retry_after: Optional[int] = None,
        service_type: Optional[str] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details
        self.retry_after = retry_after
        self.service_type = service_type
        super().__init__(self.message)


class AIServiceError(APIError):
    """AI service specific error."""
    
    def __init__(
        self,
        message: str,
        service_type: str,
        error_code: str = "AI_SERVICE_ERROR",
        status_code: int = 502,
        details: Union[str, dict] = None,
        retry_after: Optional[int] = None
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            error_code=error_code,
            details=details,
            retry_after=retry_after,
            service_type=service_type
        )


class CircuitBreakerError(APIError):
    """Circuit breaker open error."""
    
    def __init__(
        self,
        service_type: str,
        retry_after: int = 60,
        message: str = None
    ):
        if not message:
            message = f"{service_type} service is temporarily unavailable"
        
        super().__init__(
            message=message,
            status_code=503,
            error_code="CIRCUIT_BREAKER_OPEN",
            details=f"Service will be retried after {retry_after} seconds",
            retry_after=retry_after,
            service_type=service_type
        )


class ServiceDegradationError(APIError):
    """Service degradation error."""
    
    def __init__(
        self,
        message: str,
        fallback_used: str,
        original_error: str = None
    ):
        super().__init__(
            message=message,
            status_code=206,  # Partial Content
            error_code="SERVICE_DEGRADED",
            details={
                "fallback_used": fallback_used,
                "original_error": original_error,
                "note": "Response generated using fallback service"
            }
        )


class DocumentProcessingError(APIError):
    """Document processing specific error."""
    
    def __init__(
        self,
        message: str,
        document_id: str = None,
        processing_stage: str = None,
        error_code: str = "DOCUMENT_PROCESSING_ERROR"
    ):
        super().__init__(
            message=message,
            status_code=422,
            error_code=error_code,
            details={
                "document_id": document_id,
                "processing_stage": processing_stage
            }
        )


class RateLimitError(APIError):
    """Rate limit exceeded error."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 60
    ):
        super().__init__(
            message=message,
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            retry_after=retry_after,
            details=f"Please retry after {retry_after} seconds"
        )


def create_error_response(
    status_code: int,
    message: str,
    error_code: str = None,
    details: Union[str, dict] = None,
    request_id: str = None,
    retry_after: Optional[int] = None,
    service_type: Optional[str] = None,
    trace_id: Optional[str] = None
) -> JSONResponse:
    """Create standardized error response."""
    
    error_data = {
        "error": {
            "message": message,
            "code": error_code or f"HTTP_{status_code}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "trace_id": trace_id or str(uuid.uuid4())
        }
    }
    
    if details:
        error_data["error"]["details"] = details
    
    if request_id:
        error_data["error"]["request_id"] = request_id
    
    if service_type:
        error_data["error"]["service_type"] = service_type
    
    # Add headers for retry information
    headers = {}
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    
    return JSONResponse(
        status_code=status_code,
        content=error_data,
        headers=headers
    )


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle custom API errors."""
    
    request_id = getattr(request.state, "request_id", None)
    trace_id = str(uuid.uuid4())
    
    # Log error with structured data
    error_context = {
        "request_id": request_id,
        "trace_id": trace_id,
        "error_code": exc.error_code,
        "error_message": exc.message,  # Renamed to avoid conflict with logging
        "details": exc.details,
        "service_type": exc.service_type,
        "retry_after": exc.retry_after,
        "url": str(request.url),
        "method": request.method,
        "user_agent": request.headers.get("user-agent"),
        "client_ip": request.client.host if request.client else None
    }
    
    # Log at appropriate level based on error type
    if isinstance(exc, (CircuitBreakerError, ServiceDegradationError)):
        logger.warning(f"Service degradation - {exc.error_code}: {exc.message}", extra=error_context)
    elif isinstance(exc, RateLimitError):
        logger.info(f"Rate limit exceeded: {exc.message}", extra=error_context)
    else:
        logger.error(f"API Error - {exc.error_code}: {exc.message}", extra=error_context)
    
    return create_error_response(
        status_code=exc.status_code,
        message=exc.message,
        error_code=exc.error_code,
        details=exc.details,
        request_id=request_id,
        retry_after=exc.retry_after,
        service_type=exc.service_type,
        trace_id=trace_id
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions."""
    
    request_id = getattr(request.state, "request_id", None)
    
    logger.warning(
        f"HTTP Exception - Request ID: {request_id} | "
        f"Status: {exc.status_code} | "
        f"Detail: {exc.detail}"
    )
    
    return create_error_response(
        status_code=exc.status_code,
        message=exc.detail,
        error_code=f"HTTP_{exc.status_code}",
        request_id=request_id
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors."""
    
    request_id = getattr(request.state, "request_id", None)
    
    # Format validation errors
    errors = []
    for error in exc.errors():
        field_path = " -> ".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field_path,
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(
        f"Validation Error - Request ID: {request_id} | "
        f"Errors: {errors}"
    )
    
    return create_error_response(
        status_code=422,
        message="请求参数验证失败",
        error_code="VALIDATION_ERROR",
        details={"validation_errors": errors},
        request_id=request_id
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    
    request_id = getattr(request.state, "request_id", None)
    trace_id = str(uuid.uuid4())
    
    # Capture full traceback for debugging
    tb_str = traceback.format_exc()
    
    # Log error with comprehensive context
    error_context = {
        "request_id": request_id,
        "trace_id": trace_id,
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "traceback": tb_str,
        "url": str(request.url),
        "method": request.method,
        "headers": dict(request.headers),
        "client_ip": request.client.host if request.client else None
    }
    
    logger.error(
        f"Unexpected Error - {type(exc).__name__}: {str(exc)}",
        extra=error_context,
        exc_info=True
    )
    
    # Don't expose internal error details in production
    details = "请稍后重试或联系系统管理员"
    
    return create_error_response(
        status_code=500,
        message="服务器内部错误",
        error_code="INTERNAL_SERVER_ERROR",
        details=details,
        request_id=request_id,
        trace_id=trace_id
    )


class ErrorMetrics:
    """Enhanced error metrics collection for monitoring."""
    
    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.service_errors: Dict[str, Dict[str, int]] = {}
        self.error_history: List[Dict[str, Any]] = []
        self.status_code_counts: Dict[int, int] = {}
        self.hourly_error_counts: Dict[str, int] = {}  # Hour-based error tracking
        self.last_reset = datetime.utcnow()
        self.max_history_size = 1000  # Keep last 1000 errors
    
    def record_error(
        self,
        error_code: str,
        service_type: Optional[str] = None,
        status_code: int = 500,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None
    ):
        """Record error occurrence for metrics with enhanced tracking."""
        current_time = datetime.utcnow()
        
        # Count by error code
        self.error_counts[error_code] = self.error_counts.get(error_code, 0) + 1
        
        # Count by status code
        self.status_code_counts[status_code] = self.status_code_counts.get(status_code, 0) + 1
        
        # Count by service type if provided
        if service_type:
            if service_type not in self.service_errors:
                self.service_errors[service_type] = {}
            self.service_errors[service_type][error_code] = (
                self.service_errors[service_type].get(error_code, 0) + 1
            )
        
        # Hourly error tracking
        hour_key = current_time.strftime("%Y-%m-%d-%H")
        self.hourly_error_counts[hour_key] = self.hourly_error_counts.get(hour_key, 0) + 1
        
        # Add to error history
        error_record = {
            "timestamp": current_time.isoformat(),
            "error_code": error_code,
            "service_type": service_type,
            "status_code": status_code,
            "user_id": user_id,
            "endpoint": endpoint,
            "details": error_details or {}
        }
        
        self.error_history.append(error_record)
        
        # Maintain history size limit
        if len(self.error_history) > self.max_history_size:
            self.error_history = self.error_history[-self.max_history_size:]
        
        # Clean old hourly counts (keep last 24 hours)
        cutoff_time = current_time - timedelta(hours=24)
        cutoff_hour = cutoff_time.strftime("%Y-%m-%d-%H")
        self.hourly_error_counts = {
            hour: count for hour, count in self.hourly_error_counts.items()
            if hour >= cutoff_hour
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive error metrics."""
        current_time = datetime.utcnow()
        
        # Calculate error rates
        last_hour_errors = sum(
            count for hour, count in self.hourly_error_counts.items()
            if hour >= (current_time - timedelta(hours=1)).strftime("%Y-%m-%d-%H")
        )
        
        last_24h_errors = sum(self.hourly_error_counts.values())
        
        # Get recent error patterns
        recent_errors = [
            error for error in self.error_history
            if datetime.fromisoformat(error["timestamp"]) > current_time - timedelta(hours=1)
        ]
        
        # Calculate top error codes
        top_errors = sorted(
            self.error_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return {
            "error_counts": self.error_counts.copy(),
            "service_errors": self.service_errors.copy(),
            "status_code_counts": self.status_code_counts.copy(),
            "hourly_error_counts": self.hourly_error_counts.copy(),
            "last_reset": self.last_reset.isoformat(),
            "total_errors": sum(self.error_counts.values()),
            "last_hour_errors": last_hour_errors,
            "last_24h_errors": last_24h_errors,
            "error_rate_per_hour": last_hour_errors,
            "recent_errors": recent_errors,
            "top_error_codes": top_errors,
            "error_history_size": len(self.error_history),
            "error_history": self.error_history.copy()
        }
    
    def get_service_health_summary(self) -> Dict[str, Any]:
        """Get service health summary based on error patterns."""
        current_time = datetime.utcnow()
        
        service_health = {}
        for service_type, errors in self.service_errors.items():
            total_service_errors = sum(errors.values())
            
            # Calculate recent error rate for this service
            recent_service_errors = [
                error for error in self.error_history
                if (error.get("service_type") == service_type and
                    datetime.fromisoformat(error["timestamp"]) > current_time - timedelta(hours=1))
            ]
            
            # Determine health status
            if len(recent_service_errors) == 0:
                health_status = "healthy"
            elif len(recent_service_errors) < 5:
                health_status = "warning"
            else:
                health_status = "critical"
            
            service_health[service_type] = {
                "health_status": health_status,
                "total_errors": total_service_errors,
                "recent_errors": len(recent_service_errors),
                "error_types": errors.copy(),
                "last_error_time": max([
                    error["timestamp"] for error in self.error_history
                    if error.get("service_type") == service_type
                ], default=None)
            }
        
        return service_health
    
    def reset_metrics(self):
        """Reset error metrics."""
        self.error_counts.clear()
        self.service_errors.clear()
        self.error_history.clear()
        self.status_code_counts.clear()
        self.hourly_error_counts.clear()
        self.last_reset = datetime.utcnow()


# Global error metrics instance
error_metrics = ErrorMetrics()


def get_error_metrics() -> ErrorMetrics:
    """Get the global error metrics instance."""
    return error_metrics


class ErrorNotificationService:
    """Service for sending error notifications and alerts."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.alert_thresholds = {
            "error_rate_per_minute": self.config.get("error_rate_threshold", 10),
            "service_failure_threshold": self.config.get("service_failure_threshold", 5),
            "critical_error_threshold": self.config.get("critical_error_threshold", 3),
            "circuit_breaker_threshold": self.config.get("circuit_breaker_threshold", 3),
            "degradation_threshold": self.config.get("degradation_threshold", 2)
        }
        self.notification_cooldown = self.config.get("notification_cooldown", 300)  # 5 minutes
        self.last_notifications: Dict[str, datetime] = {}
        self.error_window_minutes = self.config.get("error_window_minutes", 5)
        self.recent_errors: Dict[str, List[datetime]] = {}
    
    async def check_and_notify(
        self,
        error_code: str,
        service_type: Optional[str] = None,
        severity: str = "warning"
    ):
        """Check if notification should be sent and send if needed."""
        try:
            notification_key = f"{error_code}_{service_type or 'general'}"
            current_time = datetime.utcnow()
            
            # Track recent errors for rate calculation
            if notification_key not in self.recent_errors:
                self.recent_errors[notification_key] = []
            
            # Add current error to recent errors
            self.recent_errors[notification_key].append(current_time)
            
            # Clean old errors outside the window
            cutoff_time = current_time - timedelta(minutes=self.error_window_minutes)
            self.recent_errors[notification_key] = [
                error_time for error_time in self.recent_errors[notification_key]
                if error_time > cutoff_time
            ]
            
            # Check cooldown
            if notification_key in self.last_notifications:
                time_since_last = (current_time - self.last_notifications[notification_key]).total_seconds()
                if time_since_last < self.notification_cooldown:
                    return
            
            # Check if thresholds are exceeded
            should_notify = False
            error_rate = len(self.recent_errors[notification_key])
            
            if severity == "critical":
                should_notify = True
            elif error_code == "CIRCUIT_BREAKER_OPEN":
                should_notify = error_rate >= self.alert_thresholds["circuit_breaker_threshold"]
            elif error_code == "SERVICE_DEGRADED":
                should_notify = error_rate >= self.alert_thresholds["degradation_threshold"]
            elif error_rate >= self.alert_thresholds["critical_error_threshold"]:
                should_notify = True
            
            if should_notify:
                metrics = error_metrics.get_metrics()
                await self._send_notification(error_code, service_type, severity, metrics, error_rate)
                self.last_notifications[notification_key] = current_time
        
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")
    
    async def _send_notification(
        self,
        error_code: str,
        service_type: Optional[str],
        severity: str,
        metrics: Dict[str, Any],
        error_rate: int
    ):
        """Send notification (implement based on your notification system)."""
        # This is a placeholder - implement based on your notification requirements
        # Could send to Slack, email, PagerDuty, etc.
        
        notification_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "error_code": error_code,
            "service_type": service_type,
            "severity": severity,
            "error_rate": error_rate,
            "window_minutes": self.error_window_minutes,
            "metrics": metrics,
            "message": f"Error threshold exceeded for {error_code} - {error_rate} errors in {self.error_window_minutes} minutes",
            "recommended_actions": self._get_recommended_actions(error_code, service_type)
        }
        
        # Log with appropriate level based on severity
        if severity == "critical":
            logger.critical(f"CRITICAL ERROR ALERT: {notification_data}")
        else:
            logger.warning(f"Error notification triggered: {notification_data}")
    
    def _get_recommended_actions(self, error_code: str, service_type: Optional[str]) -> List[str]:
        """Get recommended actions for specific error types."""
        actions = []
        
        if error_code == "CIRCUIT_BREAKER_OPEN":
            actions.extend([
                f"Check {service_type} service health",
                "Consider manual circuit breaker reset if service is recovered",
                "Review service logs for root cause",
                "Verify network connectivity to service"
            ])
        elif error_code == "SERVICE_DEGRADED":
            actions.extend([
                "Monitor fallback service performance",
                f"Investigate {service_type} service issues",
                "Consider scaling fallback resources",
                "Review degradation strategy effectiveness"
            ])
        elif error_code == "AI_SERVICE_ERROR":
            actions.extend([
                "Check AI service API status",
                "Verify API keys and authentication",
                "Review rate limits and quotas",
                "Consider switching to backup AI service"
            ])
        elif error_code == "DOCUMENT_PROCESSING_ERROR":
            actions.extend([
                "Check document format and size",
                "Review processing pipeline logs",
                "Verify storage service availability",
                "Consider manual document reprocessing"
            ])
        else:
            actions.extend([
                "Review application logs for details",
                "Check system resource usage",
                "Verify database connectivity",
                "Consider service restart if issues persist"
            ])
        
        return actions


# Global notification service
notification_service = ErrorNotificationService()


class ErrorMonitoringService:
    """Service for monitoring and analyzing error patterns."""
    
    def __init__(self):
        self.metrics = error_metrics
        self.notification_service = notification_service
    
    def get_error_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive error dashboard data."""
        metrics = self.metrics.get_metrics()
        service_health = self.metrics.get_service_health_summary()
        
        return {
            "overview": {
                "total_errors": metrics["total_errors"],
                "last_hour_errors": metrics["last_hour_errors"],
                "last_24h_errors": metrics["last_24h_errors"],
                "error_rate_per_hour": metrics["error_rate_per_hour"],
                "last_reset": metrics["last_reset"]
            },
            "error_breakdown": {
                "by_code": metrics["top_error_codes"],
                "by_status": metrics["status_code_counts"],
                "by_service": metrics["service_errors"]
            },
            "service_health": service_health,
            "recent_errors": metrics["recent_errors"][:20],  # Last 20 errors
            "trends": {
                "hourly_counts": metrics["hourly_error_counts"]
            }
        }
    
    def get_service_degradation_status(self) -> Dict[str, Any]:
        """Get current service degradation status."""
        service_health = self.metrics.get_service_health_summary()
        
        degraded_services = []
        critical_services = []
        
        for service_type, health_info in service_health.items():
            if health_info["health_status"] == "critical":
                critical_services.append({
                    "service": service_type,
                    "recent_errors": health_info["recent_errors"],
                    "last_error": health_info["last_error_time"]
                })
            elif health_info["health_status"] == "warning":
                degraded_services.append({
                    "service": service_type,
                    "recent_errors": health_info["recent_errors"],
                    "last_error": health_info["last_error_time"]
                })
        
        return {
            "overall_status": "critical" if critical_services else ("warning" if degraded_services else "healthy"),
            "critical_services": critical_services,
            "degraded_services": degraded_services,
            "healthy_services": [
                service for service, health in service_health.items()
                if health["health_status"] == "healthy"
            ]
        }
    
    def analyze_error_patterns(self) -> Dict[str, Any]:
        """Analyze error patterns and provide insights."""
        metrics = self.metrics.get_metrics()
        
        # Analyze error frequency patterns
        error_patterns = {}
        for error_code, count in metrics["error_counts"].items():
            if count > 5:  # Only analyze frequent errors
                error_patterns[error_code] = {
                    "frequency": count,
                    "severity": "high" if count > 20 else "medium",
                    "recommendation": self._get_error_recommendation(error_code)
                }
        
        # Analyze service reliability
        service_reliability = {}
        for service_type, errors in metrics["service_errors"].items():
            total_errors = sum(errors.values())
            service_reliability[service_type] = {
                "error_count": total_errors,
                "reliability_score": max(0, 100 - (total_errors * 2)),  # Simple scoring
                "most_common_error": max(errors.items(), key=lambda x: x[1])[0] if errors else None
            }
        
        return {
            "error_patterns": error_patterns,
            "service_reliability": service_reliability,
            "recommendations": self._get_system_recommendations(metrics)
        }
    
    def _get_error_recommendation(self, error_code: str) -> str:
        """Get recommendation for specific error code."""
        recommendations = {
            "AI_SERVICE_ERROR": "Check AI service configuration and API limits",
            "CIRCUIT_BREAKER_OPEN": "Investigate underlying service issues and consider manual reset",
            "SERVICE_DEGRADED": "Monitor fallback performance and fix primary service",
            "DOCUMENT_PROCESSING_ERROR": "Review document formats and processing pipeline",
            "RATE_LIMIT_EXCEEDED": "Implement better rate limiting or increase limits",
            "VALIDATION_ERROR": "Review input validation and user guidance",
            "INTERNAL_SERVER_ERROR": "Check system logs and resource usage"
        }
        return recommendations.get(error_code, "Review logs and investigate root cause")
    
    def _get_system_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """Get system-wide recommendations based on error patterns."""
        recommendations = []
        
        if metrics["error_rate_per_hour"] > 50:
            recommendations.append("High error rate detected - investigate system stability")
        
        if metrics["status_code_counts"].get(500, 0) > 10:
            recommendations.append("Multiple server errors - check application health")
        
        if metrics["status_code_counts"].get(503, 0) > 5:
            recommendations.append("Service unavailable errors - check service dependencies")
        
        if not recommendations:
            recommendations.append("System appears stable - continue monitoring")
        
        return recommendations


# Global monitoring service
error_monitoring_service = ErrorMonitoringService()


def get_error_monitoring_service() -> ErrorMonitoringService:
    """Get the global error monitoring service instance."""
    return error_monitoring_service


async def enhanced_api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Enhanced API error handler with metrics and notifications."""
    
    # Extract additional context
    user_id = getattr(request.state, "user_id", None)
    endpoint = f"{request.method} {request.url.path}"
    
    # Record enhanced metrics
    error_metrics.record_error(
        error_code=exc.error_code,
        service_type=exc.service_type,
        status_code=exc.status_code,
        user_id=user_id,
        endpoint=endpoint,
        error_details={
            "error_message": exc.message,
            "details": exc.details,
            "retry_after": exc.retry_after,
            "user_agent": request.headers.get("user-agent"),
            "client_ip": request.client.host if request.client else None
        }
    )
    
    # Check for notifications
    severity = "critical" if exc.status_code >= 500 else "warning"
    if isinstance(exc, CircuitBreakerError):
        severity = "critical"
    elif isinstance(exc, ServiceDegradationError):
        severity = "warning"
    
    await notification_service.check_and_notify(
        error_code=exc.error_code,
        service_type=exc.service_type,
        severity=severity
    )
    
    # Use the original handler
    return await api_error_handler(request, exc)


async def enhanced_general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Enhanced general exception handler with metrics and notifications."""
    
    # Extract additional context
    user_id = getattr(request.state, "user_id", None)
    endpoint = f"{request.method} {request.url.path}"
    
    # Record enhanced metrics
    error_metrics.record_error(
        error_code="INTERNAL_SERVER_ERROR",
        status_code=500,
        user_id=user_id,
        endpoint=endpoint,
        error_details={
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "user_agent": request.headers.get("user-agent"),
            "client_ip": request.client.host if request.client else None
        }
    )
    
    # Send critical notification
    await notification_service.check_and_notify(
        error_code="INTERNAL_SERVER_ERROR",
        severity="critical"
    )
    
    # Use the original handler
    return await general_exception_handler(request, exc)