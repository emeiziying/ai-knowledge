"""
Tests for conversation management functionality.
"""
import pytest
import asyncio
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient

from backend.app.database import Base
from backend.app.models import User, Conversation, Message
from backend.app.auth.service import AuthService
from backend.app.chat.conversation_service import ConversationService


# Test fixtures
@pytest.fixture
def db_session():
    """Create a test database session using SQLite in memory."""
    # Create in-memory SQLite database for testing
    test_engine = create_engine("sqlite:///:memory:", echo=False)
    
    # Create tables
    Base.metadata.create_all(bind=test_engine)
    
    # Create session
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestSessionLocal()
    
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    auth_service = AuthService()
    
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=auth_service.hash_password("testpassword")
    )
    
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    return user


@pytest.fixture
def conversation_service():
    """Create conversation service instance."""
    return ConversationService()


@pytest.fixture
def client():
    """Create test client."""
    # Skip this for now since it requires the full app setup
    pass


class TestConversationService:
    """Test conversation service functionality."""
    
    @pytest.mark.asyncio
    async def test_create_conversation(self, db_session, test_user, conversation_service):
        """Test creating a new conversation."""
        result = await conversation_service.create_conversation(
            db=db_session,
            user_id=str(test_user.id),
            title="Test Conversation"
        )
        
        assert result["user_id"] == str(test_user.id)
        assert result["title"] == "Test Conversation"
        assert result["message_count"] == 0
        assert "id" in result
        assert "created_at" in result
        assert "updated_at" in result
    
    @pytest.mark.asyncio
    async def test_create_conversation_auto_title(self, db_session, test_user, conversation_service):
        """Test creating a conversation with auto-generated title."""
        result = await conversation_service.create_conversation(
            db=db_session,
            user_id=str(test_user.id)
        )
        
        assert result["title"] == "对话 1"
        
        # Create another conversation
        result2 = await conversation_service.create_conversation(
            db=db_session,
            user_id=str(test_user.id)
        )
        
        assert result2["title"] == "对话 2"
    
    @pytest.mark.asyncio
    async def test_get_conversations(self, db_session, test_user, conversation_service):
        """Test getting user conversations."""
        # Create test conversations
        conv1 = await conversation_service.create_conversation(
            db=db_session,
            user_id=str(test_user.id),
            title="First Conversation"
        )
        
        conv2 = await conversation_service.create_conversation(
            db=db_session,
            user_id=str(test_user.id),
            title="Second Conversation"
        )
        
        # Get conversations
        result = await conversation_service.get_conversations(
            db=db_session,
            user_id=str(test_user.id)
        )
        
        assert result["total_count"] == 2
        assert len(result["conversations"]) == 2
        assert result["conversations"][0]["title"] == "Second Conversation"  # Most recent first
        assert result["conversations"][1]["title"] == "First Conversation"
    
    @pytest.mark.asyncio
    async def test_get_conversation(self, db_session, test_user, conversation_service):
        """Test getting a specific conversation."""
        # Create test conversation
        created = await conversation_service.create_conversation(
            db=db_session,
            user_id=str(test_user.id),
            title="Test Conversation"
        )
        
        # Get conversation
        result = await conversation_service.get_conversation(
            db=db_session,
            conversation_id=created["id"],
            user_id=str(test_user.id)
        )
        
        assert result["id"] == created["id"]
        assert result["title"] == "Test Conversation"
        assert result["message_count"] == 0
    
    @pytest.mark.asyncio
    async def test_update_conversation(self, db_session, test_user, conversation_service):
        """Test updating a conversation."""
        # Create test conversation
        created = await conversation_service.create_conversation(
            db=db_session,
            user_id=str(test_user.id),
            title="Original Title"
        )
        
        # Update conversation
        result = await conversation_service.update_conversation(
            db=db_session,
            conversation_id=created["id"],
            user_id=str(test_user.id),
            title="Updated Title"
        )
        
        assert result["title"] == "Updated Title"
        assert result["id"] == created["id"]
    
    @pytest.mark.asyncio
    async def test_delete_conversation(self, db_session, test_user, conversation_service):
        """Test deleting a conversation."""
        # Create test conversation
        created = await conversation_service.create_conversation(
            db=db_session,
            user_id=str(test_user.id),
            title="To Delete"
        )
        
        # Delete conversation
        result = await conversation_service.delete_conversation(
            db=db_session,
            conversation_id=created["id"],
            user_id=str(test_user.id)
        )
        
        assert result["conversation_id"] == created["id"]
        
        # Verify deletion
        with pytest.raises(Exception, match="not found"):
            await conversation_service.get_conversation(
                db=db_session,
                conversation_id=created["id"],
                user_id=str(test_user.id)
            )
    
    @pytest.mark.asyncio
    async def test_add_message(self, db_session, test_user, conversation_service):
        """Test adding a message to a conversation."""
        # Create test conversation
        conversation = await conversation_service.create_conversation(
            db=db_session,
            user_id=str(test_user.id),
            title="Test Conversation"
        )
        
        # Add user message
        result = await conversation_service.add_message(
            db=db_session,
            conversation_id=conversation["id"],
            user_id=str(test_user.id),
            role="user",
            content="Hello, this is a test message",
            metadata={"source": "test"}
        )
        
        assert result["conversation_id"] == conversation["id"]
        assert result["role"] == "user"
        assert result["content"] == "Hello, this is a test message"
        assert result["metadata"]["source"] == "test"
        assert "id" in result
        assert "created_at" in result
    
    @pytest.mark.asyncio
    async def test_get_messages(self, db_session, test_user, conversation_service):
        """Test getting messages from a conversation."""
        # Create test conversation
        conversation = await conversation_service.create_conversation(
            db=db_session,
            user_id=str(test_user.id),
            title="Test Conversation"
        )
        
        # Add test messages
        msg1 = await conversation_service.add_message(
            db=db_session,
            conversation_id=conversation["id"],
            user_id=str(test_user.id),
            role="user",
            content="First message"
        )
        
        msg2 = await conversation_service.add_message(
            db=db_session,
            conversation_id=conversation["id"],
            user_id=str(test_user.id),
            role="assistant",
            content="Second message"
        )
        
        # Get messages
        result = await conversation_service.get_messages(
            db=db_session,
            conversation_id=conversation["id"],
            user_id=str(test_user.id)
        )
        
        assert result["total_count"] == 2
        assert len(result["messages"]) == 2
        assert result["messages"][0]["content"] == "First message"  # Chronological order
        assert result["messages"][1]["content"] == "Second message"
        assert result["conversation"]["title"] == "Test Conversation"
    
    @pytest.mark.asyncio
    async def test_get_conversation_context(self, db_session, test_user, conversation_service):
        """Test getting conversation context."""
        # Create test conversation
        conversation = await conversation_service.create_conversation(
            db=db_session,
            user_id=str(test_user.id),
            title="Test Conversation"
        )
        
        # Add multiple messages
        messages = [
            ("user", "Message 1"),
            ("assistant", "Response 1"),
            ("user", "Message 2"),
            ("assistant", "Response 2"),
            ("user", "Message 3")
        ]
        
        for role, content in messages:
            await conversation_service.add_message(
                db=db_session,
                conversation_id=conversation["id"],
                user_id=str(test_user.id),
                role=role,
                content=content
            )
        
        # Get context (limit to 3 messages)
        context = await conversation_service.get_conversation_context(
            db=db_session,
            conversation_id=conversation["id"],
            user_id=str(test_user.id),
            max_messages=3
        )
        
        assert len(context) == 3
        assert context[0]["content"] == "Response 1"  # Most recent 3 in chronological order
        assert context[1]["content"] == "Message 2"
        assert context[2]["content"] == "Response 2"
    
    @pytest.mark.asyncio
    async def test_unauthorized_access(self, db_session, conversation_service):
        """Test that users cannot access other users' conversations."""
        # Create two users
        user1 = User(
            username="user1",
            email="user1@example.com",
            password_hash="hash1"
        )
        user2 = User(
            username="user2",
            email="user2@example.com",
            password_hash="hash2"
        )
        
        db_session.add_all([user1, user2])
        db_session.commit()
        db_session.refresh(user1)
        db_session.refresh(user2)
        
        # Create conversation for user1
        conversation = await conversation_service.create_conversation(
            db=db_session,
            user_id=str(user1.id),
            title="User1's Conversation"
        )
        
        # Try to access with user2
        with pytest.raises(Exception, match="not found"):
            await conversation_service.get_conversation(
                db=db_session,
                conversation_id=conversation["id"],
                user_id=str(user2.id)
            )


if __name__ == "__main__":
    pytest.main([__file__])