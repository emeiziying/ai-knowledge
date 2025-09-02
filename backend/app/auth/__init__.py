"""
Authentication module for user management and JWT handling.
"""
from .jwt import JWTManager
from .schemas import UserCreate, UserLogin, UserResponse, Token

# Import these only when needed to avoid circular imports
def get_router():
    from .router import router
    return router

def get_dependencies():
    from .dependencies import get_current_user, get_current_active_user, get_optional_current_user
    return get_current_user, get_current_active_user, get_optional_current_user

def get_service():
    from .service import AuthService
    return AuthService

__all__ = [
    "JWTManager",
    "UserCreate",
    "UserLogin", 
    "UserResponse",
    "Token",
    "get_router",
    "get_dependencies",
    "get_service"
]