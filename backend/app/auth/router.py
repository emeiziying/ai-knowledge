"""
Authentication API routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from .schemas import UserCreate, UserLogin, UserResponse, Token
from .service import AuthService
from .dependencies import get_auth_service, get_current_active_user


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Register a new user."""
    user = await auth_service.create_user(db, user_data)
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        created_at=user.created_at,
        updated_at=user.updated_at
    )


@router.post("/login", response_model=Token)
async def login_user(
    login_data: UserLogin,
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Authenticate user and return access token."""
    user = await auth_service.authenticate_user(db, login_data)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth_service.create_access_token(user)
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user = Depends(get_current_active_user)
):
    """Get current user information."""
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )


@router.post("/logout")
async def logout_user():
    """Logout user (client-side token removal)."""
    # Since we're using stateless JWT tokens, logout is handled client-side
    # by removing the token from storage. This endpoint can be used for
    # logging purposes or future token blacklisting implementation.
    return {"message": "Successfully logged out"}