"""
Application startup and shutdown handlers.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .database import init_db, close_db
from .vector_store import vector_store
from .storage import storage

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
        
        logger.info("All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down AI Knowledge Base application...")
    
    try:
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
    Returns True if all services are healthy, False otherwise.
    """
    try:
        # Check database
        from .database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        # Check vector store
        await vector_store.get_collection_info()
        
        # Check storage
        await storage.list_files()
        
        logger.info("All services are healthy")
        return True
        
    except Exception as e:
        logger.error(f"Service health check failed: {e}")
        return False