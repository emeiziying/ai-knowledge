import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .startup import lifespan, check_services_health

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Knowledge Base API",
    description="Backend API for AI Knowledge Base application",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "AI Knowledge Base API"}

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy"}

@app.get("/api/v1/health")
async def detailed_health_check():
    """Detailed health check that verifies all services."""
    try:
        services_healthy = await check_services_health()
        if services_healthy:
            return {
                "status": "healthy",
                "services": {
                    "database": "connected",
                    "vector_store": "connected", 
                    "object_storage": "connected"
                }
            }
        else:
            return {
                "status": "unhealthy",
                "message": "One or more services are not available"
            }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@app.get("/api/v1/status")
async def system_status():
    """Get system status and configuration."""
    from .config import settings
    return {
        "application": "AI Knowledge Base",
        "version": "1.0.0",
        "environment": "development",
        "services": {
            "database": {
                "type": "PostgreSQL",
                "host": settings.database_url.split("@")[1].split("/")[0] if "@" in settings.database_url else "localhost"
            },
            "vector_store": {
                "type": "Qdrant",
                "host": f"{settings.qdrant_host}:{settings.qdrant_port}"
            },
            "object_storage": {
                "type": "MinIO",
                "endpoint": settings.minio_endpoint
            }
        }
    }