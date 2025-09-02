#!/usr/bin/env python3
"""
Create test user script.
This script creates a test user for development purposes.
"""
import asyncio
import logging
import sys
import os

# Add the parent directory to the path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
            logger.info("Test user created successfully")
            logger.info("Username: testuser")
            logger.info("Password: testpassword")
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to create test user: {e}")
        return False


async def main():
    """Main function."""
    logger.info("Creating test user...")
    
    # Test database connection
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            logger.info(f"Database connection successful. PostgreSQL version: {version}")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)
    
    # Create test user
    if await create_test_user():
        logger.info("Test user creation completed successfully!")
    else:
        logger.error("Test user creation failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())