#!/usr/bin/env python3
"""
Health check script for all database and storage services.
"""
import asyncio
import logging
import sys
import os

# Add the parent directory to the path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from app.vector_store import vector_store
from app.storage import storage
from app.config import settings
from sqlalchemy import text
import redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_postgresql():
    """Check PostgreSQL database connection."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        logger.info("✅ PostgreSQL: Connected successfully")
        return True
    except Exception as e:
        logger.error(f"❌ PostgreSQL: Connection failed - {e}")
        return False


async def check_redis():
    """Check Redis connection."""
    try:
        r = redis.from_url(settings.redis_url)
        r.ping()
        logger.info("✅ Redis: Connected successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Redis: Connection failed - {e}")
        return False


async def check_qdrant():
    """Check Qdrant vector database connection."""
    try:
        await vector_store.connect()
        info = await vector_store.get_collection_info()
        logger.info(f"✅ Qdrant: Connected successfully - Collection info: {info}")
        return True
    except Exception as e:
        logger.error(f"❌ Qdrant: Connection failed - {e}")
        return False


async def check_minio():
    """Check MinIO object storage connection."""
    try:
        await storage.connect()
        # Try to list objects to verify connection
        files = await storage.list_files()
        logger.info(f"✅ MinIO: Connected successfully - Found {len(files)} files")
        return True
    except Exception as e:
        logger.error(f"❌ MinIO: Connection failed - {e}")
        return False


async def check_database_tables():
    """Check if all required tables exist."""
    try:
        with engine.connect() as conn:
            # Check if main tables exist
            tables = ['users', 'documents', 'document_chunks', 'conversations', 'messages']
            for table in tables:
                result = conn.execute(text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = '{table}'
                    )
                """))
                exists = result.fetchone()[0]
                if not exists:
                    logger.error(f"❌ Table '{table}' does not exist")
                    return False
            
        logger.info("✅ Database Tables: All required tables exist")
        return True
    except Exception as e:
        logger.error(f"❌ Database Tables: Check failed - {e}")
        return False


async def main():
    """Run all health checks."""
    logger.info("Starting health checks for all services...")
    logger.info("=" * 50)
    
    checks = [
        ("PostgreSQL Database", check_postgresql()),
        ("Redis Cache", check_redis()),
        ("Qdrant Vector DB", check_qdrant()),
        ("MinIO Object Storage", check_minio()),
        ("Database Tables", check_database_tables()),
    ]
    
    results = []
    for name, check_coro in checks:
        logger.info(f"Checking {name}...")
        result = await check_coro
        results.append((name, result))
    
    logger.info("=" * 50)
    logger.info("Health Check Summary:")
    
    all_healthy = True
    for name, result in results:
        status = "✅ HEALTHY" if result else "❌ UNHEALTHY"
        logger.info(f"{name}: {status}")
        if not result:
            all_healthy = False
    
    logger.info("=" * 50)
    
    if all_healthy:
        logger.info("🎉 All services are healthy!")
        sys.exit(0)
    else:
        logger.error("⚠️  Some services are unhealthy. Please check the logs above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())