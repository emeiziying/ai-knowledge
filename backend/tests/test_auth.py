"""
Tests for authentication system.
"""
import pytest
import os
import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.auth.jwt import JWTManager
from app.auth.schemas import UserCreate, UserLogin


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

# Create tables
Base.metadata.create_all(bind=engine)


def get_test_db():
    """Get test database session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestAuthentication:
    """Test authentication functionality."""
    
    def test_jwt_manager(self):
        """Test JWT token creation and verification."""
        jwt_manager = JWTManager("test-secret-key")
        
        # Test password hashing
        password = "testpassword123"
        hashed = jwt_manager.get_password_hash(password)
        assert jwt_manager.verify_password(password, hashed)
        assert not jwt_manager.verify_password("wrongpassword", hashed)
        
        # Test token creation and verification
        token_data = {"sub": "test-user-id", "username": "testuser"}
        token = jwt_manager.create_access_token(token_data)
        assert token is not None
        
        decoded = jwt_manager.verify_token(token)
        assert decoded is not None
        assert decoded.user_id == "test-user-id"
        assert decoded.username == "testuser"
    
    @pytest.mark.asyncio
    async def test_user_service_create_user(self):
        """Test user creation through service."""
        jwt_manager = JWTManager("test-secret-key")
        auth_service = AuthService(jwt_manager)
        
        db = next(get_test_db())
        
        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="testpassword123"
        )
        
        user = await auth_service.create_user(db, user_data)
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password_hash != "testpassword123"  # Should be hashed
        
        db.close()
    
    @pytest.mark.asyncio
    async def test_user_service_duplicate_username(self):
        """Test duplicate username handling."""
        jwt_manager = JWTManager("test-secret-key")
        auth_service = AuthService(jwt_manager)
        
        db = next(get_test_db())
        
        user_data = UserCreate(
            username="duplicate_test",
            email="duplicate@example.com",
            password="testpassword123"
        )
        
        # First creation should succeed
        await auth_service.create_user(db, user_data)
        
        # Second creation with same username should fail
        user_data2 = UserCreate(
            username="duplicate_test",
            email="different@example.com",
            password="testpassword123"
        )
        
        with pytest.raises(Exception):  # Should raise HTTPException
            await auth_service.create_user(db, user_data2)
        
        db.close()
    
    @pytest.mark.asyncio
    async def test_user_authentication(self):
        """Test user authentication."""
        jwt_manager = JWTManager("test-secret-key")
        auth_service = AuthService(jwt_manager)
        
        db = next(get_test_db())
        
        # Create user
        user_data = UserCreate(
            username="authtest",
            email="authtest@example.com",
            password="testpassword123"
        )
        
        created_user = await auth_service.create_user(db, user_data)
        
        # Test successful authentication
        login_data = UserLogin(username="authtest", password="testpassword123")
        authenticated_user = await auth_service.authenticate_user(db, login_data)
        
        assert authenticated_user is not None
        assert authenticated_user.id == created_user.id
        
        # Test failed authentication
        wrong_login = UserLogin(username="authtest", password="wrongpassword")
        failed_auth = await auth_service.authenticate_user(db, wrong_login)
        
        assert failed_auth is None
        
        db.close()
    
    @pytest.mark.asyncio
    async def test_access_token_creation(self):
        """Test access token creation and user retrieval."""
        jwt_manager = JWTManager("test-secret-key")
        auth_service = AuthService(jwt_manager)
        
        db = next(get_test_db())
        
        # Create user
        user_data = UserCreate(
            username="tokentest",
            email="tokentest@example.com",
            password="testpassword123"
        )
        
        user = await auth_service.create_user(db, user_data)
        
        # Create access token
        token = auth_service.create_access_token(user)
        assert token is not None
        
        # Verify token
        token_data = jwt_manager.verify_token(token)
        assert token_data is not None
        assert token_data.username == "tokentest"
        
        # Get user by ID
        retrieved_user = await auth_service.get_user_by_id(db, str(user.id))
        assert retrieved_user is not None
        assert retrieved_user.username == "tokentest"
        
        db.close()
    
    def test_password_hashing_security(self):
        """Test password hashing security features."""
        jwt_manager = JWTManager("test-secret-key")
        
        password = "testpassword123"
        
        # Hash the same password multiple times
        hash1 = jwt_manager.get_password_hash(password)
        hash2 = jwt_manager.get_password_hash(password)
        
        # Hashes should be different (due to salt)
        assert hash1 != hash2
        
        # Both should verify correctly
        assert jwt_manager.verify_password(password, hash1)
        assert jwt_manager.verify_password(password, hash2)
        
        # Wrong password should not verify
        assert not jwt_manager.verify_password("wrongpassword", hash1)
    
    def test_token_expiration_data(self):
        """Test token contains proper expiration data."""
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


def teardown_module():
    """Clean up test database file."""
    try:
        os.unlink(test_db_file.name)
    except:
        pass


if __name__ == "__main__":
    pytest.main([__file__])