"""
Authentication service layer.
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from ..models import User
from .jwt import JWTManager
from .schemas import UserCreate, UserLogin


class AuthService:
    """Authentication service for user management."""
    
    def __init__(self, jwt_manager: JWTManager):
        self.jwt_manager = jwt_manager
    
    async def create_user(self, db: Session, user_data: UserCreate) -> User:
        """Create a new user."""
        # Check if user already exists
        existing_user = db.query(User).filter(
            (User.username == user_data.username) | (User.email == user_data.email)
        ).first()
        
        if existing_user:
            if existing_user.username == user_data.username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already registered"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
        
        # Hash password
        hashed_password = self.jwt_manager.get_password_hash(user_data.password)
        
        # Create user
        db_user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=hashed_password
        )
        
        try:
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            return db_user
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User creation failed due to constraint violation"
            )
    
    async def authenticate_user(self, db: Session, login_data: UserLogin) -> Optional[User]:
        """Authenticate user with username and password."""
        user = db.query(User).filter(User.username == login_data.username).first()
        
        if not user:
            return None
        
        if not self.jwt_manager.verify_password(login_data.password, user.password_hash):
            return None
        
        return user
    
    async def get_user_by_id(self, db: Session, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return db.query(User).filter(User.id == user_id).first()
    
    async def get_user_by_username(self, db: Session, username: str) -> Optional[User]:
        """Get user by username."""
        return db.query(User).filter(User.username == username).first()
    
    def create_access_token(self, user: User) -> str:
        """Create access token for user."""
        token_data = {
            "sub": str(user.id),
            "username": user.username
        }
        return self.jwt_manager.create_access_token(token_data)