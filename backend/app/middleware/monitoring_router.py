"""
Error monitoring and system health API endpoints.
"""
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..auth.dependencies import get_current_user
from ..models import User
from .error_handler import get_error_monitoring_service, get_error_metrics
from ..ai.service_manager import AIServiceManager
# from ..startup import get_ai_service_manager

def get_ai_service_manager():
    """Get AI service manager from app state or create a new one."""
    try:
        from ..ai.factory import AIServiceFactory
        from ..config import get_settings
        settings = get_settings()
        return AIServiceFactory.create_service_manager(settings)
    except Exception:
        return None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


class SystemHealthResponse(BaseModel):
    """System health response model."""
    status: str
    timestamp: str
    services: Dict[str, Any]
    error_summary: Dict[str, Any]
    recommendations: list


class ErrorDashboardResponse(BaseModel):
    """Error dashboard response model."""
    overview: Dict[str, Any]
    error_breakdown: Dict[str, Any]
    service_health: Dict[str, Any]
    recent_errors: list
    trends: Dict[str, Any]


class ServiceDegradationResponse(BaseModel):
    """Service degradation status response."""
    overall_status: str
    critical_services: list
    degraded_services: list
    healthy_services: list


class CircuitBreakerResponse(BaseModel):
    """Circuit breaker status response."""
    service_type: str
    state: str
    failure_count: int
    success_count: int
    last_failure_time: Optional[str]
    next_retry_time: Optional[str]


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive system health status.
    
    This endpoint provides an overview of system health including
    service status, error rates, and recommendations.
    """
    try:
        from datetime import datetime
        
        monitoring_service = get_error_monitoring_service()
        ai_service_manager = get_ai_service_manager()
        
        # Get AI service status
        ai_status = {}
        if ai_service_manager:
            ai_status = await ai_service_manager.get_service_status()
        
        # Get error metrics
        error_metrics = get_error_metrics().get_metrics()
        
        # Get degradation status
        degradation_status = monitoring_service.get_service_degradation_status()
        
        # Determine overall system status
        overall_status = "healthy"
        if degradation_status["overall_status"] == "critical":
            overall_status = "critical"
        elif degradation_status["overall_status"] == "warning" or error_metrics["error_rate_per_hour"] > 20:
            overall_status = "warning"
        
        # Get recommendations
        analysis = monitoring_service.analyze_error_patterns()
        
        return SystemHealthResponse(
            status=overall_status,
            timestamp=datetime.utcnow().isoformat(),
            services=ai_status,
            error_summary={
                "total_errors": error_metrics["total_errors"],
                "error_rate_per_hour": error_metrics["error_rate_per_hour"],
                "degradation_status": degradation_status["overall_status"]
            },
            recommendations=analysis["recommendations"]
        )
        
    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system health: {str(e)}"
        )


@router.get("/errors/dashboard", response_model=ErrorDashboardResponse)
async def get_error_dashboard(
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive error dashboard data.
    
    This endpoint provides detailed error metrics, trends, and analysis
    for system monitoring and debugging.
    """
    try:
        monitoring_service = get_error_monitoring_service()
        dashboard_data = monitoring_service.get_error_dashboard()
        
        return ErrorDashboardResponse(**dashboard_data)
        
    except Exception as e:
        logger.error(f"Failed to get error dashboard: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get error dashboard: {str(e)}"
        )


@router.get("/errors/degradation", response_model=ServiceDegradationResponse)
async def get_service_degradation_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get current service degradation status.
    
    This endpoint provides information about which services are
    experiencing issues and their current health status.
    """
    try:
        monitoring_service = get_error_monitoring_service()
        degradation_status = monitoring_service.get_service_degradation_status()
        
        return ServiceDegradationResponse(**degradation_status)
        
    except Exception as e:
        logger.error(f"Failed to get degradation status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get degradation status: {str(e)}"
        )


@router.get("/errors/analysis")
async def get_error_analysis(
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed error pattern analysis.
    
    This endpoint provides insights into error patterns, service reliability,
    and recommendations for system improvements.
    """
    try:
        monitoring_service = get_error_monitoring_service()
        analysis = monitoring_service.analyze_error_patterns()
        
        return analysis
        
    except Exception as e:
        logger.error(f"Failed to get error analysis: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get error analysis: {str(e)}"
        )


@router.get("/circuit-breakers")
async def get_circuit_breaker_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get status of all circuit breakers.
    
    This endpoint provides information about circuit breaker states
    for all AI services.
    """
    try:
        ai_service_manager = get_ai_service_manager()
        if not ai_service_manager:
            raise HTTPException(
                status_code=503,
                detail="AI service manager not available"
            )
        
        circuit_breaker_status = {}
        for service_type, circuit_breaker in ai_service_manager.circuit_breakers.items():
            status = circuit_breaker.get_status()
            circuit_breaker_status[service_type.value] = CircuitBreakerResponse(
                service_type=service_type.value,
                **status
            )
        
        return circuit_breaker_status
        
    except Exception as e:
        logger.error(f"Failed to get circuit breaker status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get circuit breaker status: {str(e)}"
        )


@router.post("/circuit-breakers/{service_type}/reset")
async def reset_circuit_breaker(
    service_type: str,
    current_user: User = Depends(get_current_user)
):
    """
    Manually reset a circuit breaker for a specific service.
    
    This endpoint allows manual intervention to reset circuit breakers
    when services have recovered.
    """
    try:
        ai_service_manager = get_ai_service_manager()
        if not ai_service_manager:
            raise HTTPException(
                status_code=503,
                detail="AI service manager not available"
            )
        
        # Convert string to enum
        from ..ai.interfaces import AIServiceType
        try:
            service_enum = AIServiceType(service_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid service type: {service_type}"
            )
        
        success = ai_service_manager.reset_circuit_breaker(service_enum)
        
        if success:
            return {
                "message": f"Circuit breaker reset successfully for {service_type}",
                "service_type": service_type,
                "reset": True
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Circuit breaker not found for service: {service_type}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset circuit breaker for {service_type}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset circuit breaker: {str(e)}"
        )


@router.post("/circuit-breakers/reset-all")
async def reset_all_circuit_breakers(
    current_user: User = Depends(get_current_user)
):
    """
    Reset all circuit breakers.
    
    This endpoint resets all circuit breakers across all services.
    Use with caution as it may cause issues if services are still unhealthy.
    """
    try:
        ai_service_manager = get_ai_service_manager()
        if not ai_service_manager:
            raise HTTPException(
                status_code=503,
                detail="AI service manager not available"
            )
        
        ai_service_manager.reset_all_circuit_breakers()
        
        return {
            "message": "All circuit breakers reset successfully",
            "reset_count": len(ai_service_manager.circuit_breakers)
        }
        
    except Exception as e:
        logger.error(f"Failed to reset all circuit breakers: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset all circuit breakers: {str(e)}"
        )


@router.get("/performance")
async def get_performance_metrics(
    current_user: User = Depends(get_current_user)
):
    """
    Get performance metrics for all AI services.
    
    This endpoint provides detailed performance metrics including
    response times, success rates, and failure rates.
    """
    try:
        ai_service_manager = get_ai_service_manager()
        if not ai_service_manager:
            raise HTTPException(
                status_code=503,
                detail="AI service manager not available"
            )
        
        performance_metrics = ai_service_manager.get_performance_metrics()
        
        from datetime import datetime
        
        return {
            "performance_metrics": performance_metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get performance metrics: {str(e)}"
        )


@router.post("/performance/reset")
async def reset_performance_metrics(
    service_type: Optional[str] = Query(default=None, description="Optional service type to reset"),
    current_user: User = Depends(get_current_user)
):
    """
    Reset performance metrics for a specific service or all services.
    
    This endpoint allows resetting performance counters for monitoring
    and analysis purposes.
    """
    try:
        ai_service_manager = get_ai_service_manager()
        if not ai_service_manager:
            raise HTTPException(
                status_code=503,
                detail="AI service manager not available"
            )
        
        if service_type:
            # Convert string to enum
            from ..ai.interfaces import AIServiceType
            try:
                service_enum = AIServiceType(service_type)
                ai_service_manager.reset_performance_metrics(service_enum)
                return {
                    "message": f"Performance metrics reset for {service_type}",
                    "service_type": service_type
                }
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid service type: {service_type}"
                )
        else:
            ai_service_manager.reset_performance_metrics()
            return {
                "message": "All performance metrics reset successfully"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset performance metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset performance metrics: {str(e)}"
        )


@router.post("/errors/clear")
async def clear_error_metrics(
    current_user: User = Depends(get_current_user)
):
    """
    Clear all error metrics and history.
    
    This endpoint resets all error counters and history for a fresh start.
    Use with caution as historical data will be lost.
    """
    try:
        error_metrics = get_error_metrics()
        error_metrics.reset_metrics()
        
        from datetime import datetime
        
        return {
            "message": "Error metrics cleared successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to clear error metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear error metrics: {str(e)}"
        )


@router.get("/ai-services/test/{service_type}")
async def test_ai_service_connectivity(
    service_type: str,
    current_user: User = Depends(get_current_user)
):
    """
    Test connectivity to a specific AI service.
    
    This endpoint performs a health check on the specified AI service
    and returns detailed connectivity information.
    """
    try:
        ai_service_manager = get_ai_service_manager()
        if not ai_service_manager:
            raise HTTPException(
                status_code=503,
                detail="AI service manager not available"
            )
        
        # Convert string to enum
        from ..ai.interfaces import AIServiceType
        try:
            service_enum = AIServiceType(service_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid service type: {service_type}"
            )
        
        connectivity_result = await ai_service_manager.test_service_connectivity(service_enum)
        
        return connectivity_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test service connectivity for {service_type}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to test service connectivity: {str(e)}"
        )


@router.post("/ai-services/degradation/toggle")
async def toggle_service_degradation(
    enabled: bool = Query(..., description="Enable or disable service degradation"),
    current_user: User = Depends(get_current_user)
):
    """
    Enable or disable service degradation globally.
    
    This endpoint allows toggling the service degradation feature
    which provides fallback behavior when primary services fail.
    """
    try:
        ai_service_manager = get_ai_service_manager()
        if not ai_service_manager:
            raise HTTPException(
                status_code=503,
                detail="AI service manager not available"
            )
        
        ai_service_manager.enable_service_degradation(enabled)
        
        return {
            "message": f"Service degradation {'enabled' if enabled else 'disabled'}",
            "degradation_enabled": enabled
        }
        
    except Exception as e:
        logger.error(f"Failed to toggle service degradation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to toggle service degradation: {str(e)}"
        )