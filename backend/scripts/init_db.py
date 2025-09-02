#!/usr/bin/env python3
"""
Database initialization script.
This script initializes the database, runs migrations, and sets up initial data.
"""
import asyncio
import logging
import sys
import os

# Add the parent directory to the path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, engine
from app.vector_store import vector_store
from app.storage import storage
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_database_connection():
    """Check if database is accessible."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            logger.info(f"Database connection successful. PostgreSQL version: {version}")
            return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


async def run_migrations():
    """Run database migrations using Alembic."""
    try:
        import subprocess
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Database migrations completed successfully")
            logger.info(result.stdout)
            return True
        else:
            logger.error(f"Migration failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to run migrations: {e}")
        return False


async def initialize_vector_store():
    """Initialize Qdrant vector store."""
    try:
        await vector_store.connect()
        logger.info("Vector store initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize vector store: {e}")
        return False


async def initialize_object_storage():
    """Initialize MinIO object storage."""
    try:
        await storage.connect()
        logger.info("Object storage initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize object storage: {e}")
        return False


async def create_test_user():
    """Create a test user for development."""
    try:
        from app.models import User
        from app.database import SessionLocal
        from passlib.context import CryptContext
        
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        db = SessionLocal()
        try:
            # Check if test user already exists
            existing_user = db.query(User).filter(User.username == "testuser").first()
            if existing_user:
                logger.info("Test user already exists")
                return True
            
            # Create test user
            hashed_password = pwd_context.hash("testpassword")
            test_user = User(
                username="testuser",
                email="test@example.com",
                password_hash=hashed_password
            )
            
            db.add(test_user)
            db.commit()
            logger.info("Test user created successfully (username: testuser, password: testpassword)")
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to create test user: {e}")
        return False


async def main():
    """Main initialization function."""
    logger.info("Starting database initialization...")
    
    # Check database connection
    if not await check_database_connection():
        logger.error("Cannot proceed without database connection")
        sys.exit(1)
    
    # Run migrations
    if not await run_migrations():
        logger.error("Migration failed, stopping initialization")
        sys.exit(1)
    
    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)
    
    # Initialize vector store
    if not await initialize_vector_store():
        logger.warning("Vector store initialization failed, but continuing...")
    
    # Initialize object storage
    if not await initialize_object_storage():
        logger.warning("Object storage initialization failed, but continuing...")
    
    # Create test user for development
    if not await create_test_user():
        logger.warning("Test user creation failed, but continuing...")
    
    logger.info("Database initialization completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())