"""
Integration tests for authentication system with minimal database setup.
"""
import pytest
import tempfile
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Create test database
test_db_file = tempfile.NamedTemporaryFile(delete=False)
test_db_file.close()
SQLALCHEMY_DATABASE_URL = f"sqlite:///{test_db_file.name}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Set environment variables for testing
os.environ["DATABASE_URL"] = SQLALCHEMY_DATABASE_URL
os.environ["ENVIRONMENT"] = "testing"

# Import after setting environment
from app.database import get_db
from sqlalchemy import Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

# Create test-specific base and models for SQLite compatibility
TestBase = declarative_base()

class TestUser(TestBase):
    """Test user model compatible with SQLite."""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create tables
TestBase.metadata.create_all(bind=engine)

# Monkey patch the User model for testing
import app.models
app.models.User = TestUser

def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Import FastAPI app and override dependency
from app.main import app
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


class TestAuthenticationAPI:
    """Test authentication API endpoints."""
    
    def test_health_check(self):
        """Test basic health check endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_user_registration(self):
        """Test user registration endpoint."""
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpassword123"
        }
        
        response = client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 201
        
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert "id" in data
        assert "password" not in data
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_user_registration_duplicate_username(self):
        """Test registration with duplicate username."""
        user_data = {
            "username": "duplicate_user",
            "email": "duplicate@example.com",
            "password": "testpassword123"
        }
        
        # First registration should succeed
        response = client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 201
        
        # Second registration with same username should fail
        user_data["email"] = "different@example.com"
        response = client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 400
        assert "Username already registered" in response.json()["error"]["message"]
    
    def test_user_registration_duplicate_email(self):
        """Test registration with duplicate email."""
        user_data = {
            "username": "user1",
            "email": "duplicate_email@example.com",
            "password": "testpassword123"
        }
        
        # First registration should succeed
        response = client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 201
        
        # Second registration with same email should fail
        user_data["username"] = "user2"
        response = client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 400
        assert "Email already registered" in response.json()["error"]["message"]
    
    def test_user_login(self):
        """Test user login endpoint."""
        # First register a user
        user_data = {
            "username": "logintest",
            "email": "logintest@example.com",
            "password": "testpassword123"
        }
        client.post("/api/v1/auth/register", json=user_data)
        
        # Then login
        login_data = {
            "username": "logintest",
            "password": "testpassword123"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0
    
    def test_user_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        login_data = {
            "username": "nonexistent",
            "password": "wrongpassword"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["error"]["message"]
    
    def test_get_current_user(self):
        """Test getting current user info with valid token."""
        # Register and login to get token
        user_data = {
            "username": "currentuser",
            "email": "currentuser@example.com",
            "password": "testpassword123"
        }
        client.post("/api/v1/auth/register", json=user_data)
        
        login_response = client.post("/api/v1/auth/login", json={
            "username": "currentuser",
            "password": "testpassword123"
        })
        token = login_response.json()["access_token"]
        
        # Get current user info
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["username"] == "currentuser"
        assert data["email"] == "currentuser@example.com"
        assert "id" in data
        assert "password" not in data
    
    def test_get_current_user_invalid_token(self):
        """Test getting current user with invalid token."""
        headers = {"Authorization": "Bearer invalid-token"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
    
    def test_get_current_user_no_token(self):
        """Test getting current user without token."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 403  # No authorization header
    
    def test_logout(self):
        """Test logout endpoint."""
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        assert "Successfully logged out" in response.json()["message"]
    
    def test_user_registration_validation(self):
        """Test user registration input validation."""
        # Test short username
        user_data = {
            "username": "ab",  # Too short
            "email": "test@example.com",
            "password": "testpassword123"
        }
        response = client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 422  # Validation error
        
        # Test short password
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "short"  # Too short
        }
        response = client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 422  # Validation error
        
        # Test invalid email
        user_data = {
            "username": "testuser",
            "email": "invalid-email",  # Invalid format
            "password": "testpassword123"
        }
        response = client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 422  # Validation error


def teardown_module():
    """Clean up test database file."""
    try:
        os.unlink(test_db_file.name)
    except:
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])