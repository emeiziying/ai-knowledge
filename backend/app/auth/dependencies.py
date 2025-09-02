"""
Authentication dependencies for FastAPI.
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from .jwt import JWTManager
from .service import AuthService
from ..config import get_settings


# Security scheme
security = HTTPBearer()

# Get settings
settings = get_settings()

# Initialize JWT manager
jwt_manager = JWTManager(
    secret_key=settings.SECRET_KEY,
    algorithm=settings.ALGORITHM,
    access_token_expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
)

# Initialize auth service
auth_service = AuthService(jwt_manager)


def get_jwt_manager() -> JWTManager:
    """Get JWT manager instance."""
    return jwt_manager


def get_auth_service() -> AuthService:
    """Get authentication service instance."""
    return auth_service


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
    auth_service: AuthService = Depends(get_auth_service)
) -> User:
    """Get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Verify token
    token_data = jwt_manager.verify_token(credentials.credentials)
    if token_data is None or token_data.user_id is None:
        raise credentials_exception
    
    # Get user from database
    user = await auth_service.get_user_by_id(db, token_data.user_id)
    if user is None:
        raise credentials_exception
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user (can be extended for user status checks)."""
    # Here you can add additional checks like user.is_active, user.is_verified, etc.
    return current_user


# Optional dependency for routes that may or may not require authentication
async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
    auth_service: AuthService = Depends(get_auth_service)
) -> Optional[User]:
    """Get current user if authenticated, None otherwise."""
    if credentials is None:
        return None
    
    try:
        token_data = jwt_manager.verify_token(credentials.credentials)
        if token_data is None or token_data.user_id is None:
            return None
        
        user = await auth_service.get_user_by_id(db, token_data.user_id)
        return user
    except Exception:
        return None