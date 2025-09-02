"""
Simple tests for authentication components without database dependencies.
"""
import pytest
from datetime import datetime, timedelta

# Import JWT manager directly
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.auth.jwt import JWTManager, TokenData
from app.auth.schemas import UserCreate, UserLogin


class TestJWTManager:
    """Test JWT token management functionality."""
    
    def test_password_hashing(self):
        """Test password hashing and verification."""
        jwt_manager = JWTManager("test-secret-key")
        
        password = "testpassword123"
        hashed = jwt_manager.get_password_hash(password)
        
        # Verify correct password
        assert jwt_manager.verify_password(password, hashed)
        
        # Verify incorrect password
        assert not jwt_manager.verify_password("wrongpassword", hashed)
    
    def test_password_hashing_uniqueness(self):
        """Test that password hashing produces unique salts."""
        jwt_manager = JWTManager("test-secret-key")
        
        password = "testpassword123"
        hash1 = jwt_manager.get_password_hash(password)
        hash2 = jwt_manager.get_password_hash(password)
        
        # Hashes should be different due to unique salts
        assert hash1 != hash2
        
        # Both should verify correctly
        assert jwt_manager.verify_password(password, hash1)
        assert jwt_manager.verify_password(password, hash2)
    
    def test_token_creation_and_verification(self):
        """Test JWT token creation and verification."""
        jwt_manager = JWTManager("test-secret-key")
        
        token_data = {"sub": "test-user-id", "username": "testuser"}
        token = jwt_manager.create_access_token(token_data)
        
        assert token is not None
        assert isinstance(token, str)
        
        # Verify token
        decoded = jwt_manager.verify_token(token)
        assert decoded is not None
        assert decoded.user_id == "test-user-id"
        assert decoded.username == "testuser"
    
    def test_token_expiration(self):
        """Test token expiration handling."""
        jwt_manager = JWTManager("test-secret-key", access_token_expire_minutes=30)
        
        token_data = {"sub": "test-user-id", "username": "testuser"}
        token = jwt_manager.create_access_token(token_data)
        
        # Decode token manually to check expiration
        from jose import jwt
        decoded = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        
        assert "exp" in decoded
        assert "sub" in decoded
        assert decoded["sub"] == "test-user-id"
        assert decoded["username"] == "testuser"
        
        # Check expiration is in the future
        exp_timestamp = decoded["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp)
        assert exp_datetime > datetime.utcnow()
    
    def test_invalid_token_verification(self):
        """Test verification of invalid tokens."""
        jwt_manager = JWTManager("test-secret-key")
        
        # Test completely invalid token
        invalid_token = "invalid.token.here"
        decoded = jwt_manager.verify_token(invalid_token)
        assert decoded is None
        
        # Test token with wrong secret
        other_jwt = JWTManager("different-secret")
        token_data = {"sub": "test-user-id", "username": "testuser"}
        token = other_jwt.create_access_token(token_data)
        
        decoded = jwt_manager.verify_token(token)
        assert decoded is None
    
    def test_token_without_required_claims(self):
        """Test token verification when required claims are missing."""
        jwt_manager = JWTManager("test-secret-key")
        
        # Create token without 'sub' claim
        from jose import jwt
        token_data = {"username": "testuser"}  # Missing 'sub'
        token = jwt.encode(token_data, "test-secret-key", algorithm="HS256")
        
        decoded = jwt_manager.verify_token(token)
        assert decoded is None


class TestAuthSchemas:
    """Test authentication schemas."""
    
    def test_user_create_schema(self):
        """Test UserCreate schema validation."""
        # Valid user data
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpassword123"
        }
        
        user = UserCreate(**user_data)
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password == "testpassword123"
    
    def test_user_create_validation(self):
        """Test UserCreate schema validation rules."""
        # Test short username
        with pytest.raises(Exception):  # Pydantic validation error
            UserCreate(username="ab", email="test@example.com", password="testpass123")
        
        # Test short password
        with pytest.raises(Exception):  # Pydantic validation error
            UserCreate(username="testuser", email="test@example.com", password="short")
        
        # Test invalid email
        with pytest.raises(Exception):  # Pydantic validation error
            UserCreate(username="testuser", email="invalid-email", password="testpass123")
    
    def test_user_login_schema(self):
        """Test UserLogin schema."""
        login_data = {
            "username": "testuser",
            "password": "testpassword123"
        }
        
        login = UserLogin(**login_data)
        assert login.username == "testuser"
        assert login.password == "testpassword123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])