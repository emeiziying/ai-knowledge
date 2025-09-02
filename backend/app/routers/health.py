"""Health check and system status endpoints."""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from ..startup import check_services_health
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def basic_health_check() -> Dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "healthy", "message": "AI Knowledge Base API is running"}


@router.get("/health/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check that verifies all services."""
    try:
        services_status = await check_services_health()
        
        if all(services_status.values()):
            return {
                "status": "healthy",
                "services": {
                    "database": "connected" if services_status.get("database") else "disconnected",
                    "vector_store": "connected" if services_status.get("vector_store") else "disconnected",
                    "object_storage": "connected" if services_status.get("object_storage") else "disconnected",
                    "redis": "connected" if services_status.get("redis") else "disconnected"
                },
                "timestamp": None  # Will be set by client
            }
        else:
            failed_services = [
                service for service, status in services_status.items() 
                if not status
            ]
            
            return {
                "status": "degraded",
                "services": {
                    "database": "connected" if services_status.get("database") else "disconnected",
                    "vector_store": "connected" if services_status.get("vector_store") else "disconnected", 
                    "object_storage": "connected" if services_status.get("object_storage") else "disconnected",
                    "redis": "connected" if services_status.get("redis") else "disconnected"
                },
                "failed_services": failed_services,
                "timestamp": None
            }
            
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "message": "健康检查失败",
                "error": str(e)
            }
        )


@router.get("/status")
async def system_status() -> Dict[str, Any]:
    """Get system status and configuration information."""
    try:
        return {
            "application": {
                "name": "AI Knowledge Base",
                "version": "1.0.0",
                "environment": "development" if settings.debug else "production",
                "debug_mode": settings.debug
            },
            "services": {
                "database": {
                    "type": "PostgreSQL",
                    "host": _extract_host_from_url(settings.database_url)
                },
                "vector_store": {
                    "type": "Qdrant", 
                    "host": f"{settings.qdrant_host}:{settings.qdrant_port}"
                },
                "object_storage": {
                    "type": "MinIO",
                    "endpoint": settings.minio_endpoint,
                    "bucket": settings.minio_bucket
                },
                "cache": {
                    "type": "Redis",
                    "url": _extract_host_from_url(settings.redis_url)
                }
            },
            "features": {
                "ai_services": {
                    "openai_configured": bool(settings.openai_api_key),
                    "ollama_endpoint": settings.ollama_base_url
                },
                "authentication": {
                    "jwt_enabled": True,
                    "token_expire_minutes": settings.access_token_expire_minutes
                }
            }
        }
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "无法获取系统状态",
                "error": str(e)
            }
        )


def _extract_host_from_url(url: str) -> str:
    """Extract host information from database/redis URL."""
    try:
        if "@" in url:
            # Format: protocol://user:pass@host:port/db
            host_part = url.split("@")[1]
            return host_part.split("/")[0]
        else:
            # Format: protocol://host:port/db
            return url.split("://")[1].split("/")[0]
    except (IndexError, AttributeError):
        return "unknown"