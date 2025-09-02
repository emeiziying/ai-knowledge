"""
Application startup and shutdown handlers.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .database import init_db, close_db
from .vector_store import vector_store
from .storage import storage
from .processing.embeddings import initialize_default_embedding_service
from .processing.vector_storage import initialize_vector_storage
from .ai.factory import AIServiceFactory
from .config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    """
    # Startup
    logger.info("Starting up AI Knowledge Base application...")
    
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")
        
        # Initialize vector store
        await vector_store.connect()
        logger.info("Vector store connected")
        
        # Initialize object storage
        await storage.connect()
        logger.info("Object storage connected")
        
        # Initialize embedding services
        embedding_success = await initialize_default_embedding_service()
        if embedding_success:
            logger.info("Default embedding service initialized")
        else:
            logger.warning("Failed to initialize default embedding service")
        
        # Initialize vector storage service
        vector_storage_success = await initialize_vector_storage()
        if vector_storage_success:
            logger.info("Vector storage service initialized")
        else:
            logger.warning("Failed to initialize vector storage service")
        
        # Initialize AI service manager
        try:
            settings = get_settings()
            ai_service_manager = AIServiceFactory.create_service_manager(settings)
            await ai_service_manager.start_health_monitoring()
            app.state.ai_service_manager = ai_service_manager
            logger.info("AI service manager initialized and health monitoring started")
        except Exception as e:
            logger.warning(f"Failed to initialize AI service manager: {e}")
        
        logger.info("All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down AI Knowledge Base application...")
    
    try:
        # Stop AI service health monitoring
        if hasattr(app.state, 'ai_service_manager'):
            await app.state.ai_service_manager.stop_health_monitoring()
            logger.info("AI service health monitoring stopped")
        
        # Close vector store connection
        await vector_store.close()
        logger.info("Vector store connection closed")
        
        # Close database connections
        await close_db()
        logger.info("Database connections closed")
        
        logger.info("All services shut down successfully")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


async def check_services_health():
    """
    Check the health of all required services.
    Returns a dictionary with service status.
    """
    services_status = {
        "database": False,
        "vector_store": False,
        "object_storage": False,
        "redis": False,
        "ai_services": False
    }
    
    # Check database
    try:
        from .database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        services_status["database"] = True
        logger.debug("Database health check passed")
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
    
    # Check vector store
    try:
        await vector_store.get_collection_info()
        services_status["vector_store"] = True
        logger.debug("Vector store health check passed")
    except Exception as e:
        logger.warning(f"Vector store health check failed: {e}")
    
    # Check object storage
    try:
        await storage.list_files()
        services_status["object_storage"] = True
        logger.debug("Object storage health check passed")
    except Exception as e:
        logger.warning(f"Object storage health check failed: {e}")
    
    # Check Redis
    try:
        import redis.asyncio as redis
        from .config import get_settings
        settings = get_settings()
        redis_client = redis.from_url(settings.redis_url)
        await redis_client.ping()
        await redis_client.close()
        services_status["redis"] = True
        logger.debug("Redis health check passed")
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
    
    # Check AI services
    try:
        settings = get_settings()
        ai_service_manager = AIServiceFactory.create_service_manager(settings)
        ai_status = await ai_service_manager.get_service_status()
        # Consider AI services healthy if at least one service is available
        services_status["ai_services"] = any(
            status.status.value == "healthy" for status in ai_status.values()
        )
        logger.debug("AI services health check passed")
    except Exception as e:
        logger.warning(f"AI services health check failed: {e}")
    
    healthy_services = sum(services_status.values())
    total_services = len(services_status)
    
    logger.info(f"Service health check completed: {healthy_services}/{total_services} services healthy")
    return services_status