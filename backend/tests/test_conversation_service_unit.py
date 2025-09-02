"""
Unit tests for conversation service functionality.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import uuid

from backend.app.chat.conversation_service import ConversationService
from backend.app.models import Conversation, Message, User


class TestConversationServiceUnit:
    """Unit tests for ConversationService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = ConversationService()
        self.mock_db = Mock()
        self.test_user_id = str(uuid.uuid4())
        self.test_conversation_id = str(uuid.uuid4())
        
    @pytest.mark.asyncio
    async def test_create_conversation_with_title(self):
        """Test creating a conversation with a custom title."""
        # Mock database operations
        mock_conversation = Mock()
        mock_conversation.id = uuid.uuid4()
        mock_conversation.user_id = self.test_user_id
        mock_conversation.title = "Custom Title"
        mock_conversation.created_at = datetime.utcnow()
        mock_conversation.updated_at = datetime.utcnow()
        
        self.mock_db.query.return_value.filter.return_value.count.return_value = 0
        self.mock_db.add = Mock()
        self.mock_db.commit = Mock()
        self.mock_db.refresh = Mock()
        
        # Mock the conversation object that gets created
        with patch('backend.app.chat.conversation_service.Conversation') as mock_conv_class:
            mock_conv_class.return_value = mock_conversation
            
            result = await self.service.create_conversation(
                db=self.mock_db,
                user_id=self.test_user_id,
                title="Custom Title"
            )
        
        # Verify the result
        assert result["user_id"] == self.test_user_id
        assert result["title"] == "Custom Title"
        assert result["message_count"] == 0
        assert "id" in result
        assert "created_at" in result
        assert "updated_at" in result
        
        # Verify database operations
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_conversation_auto_title(self):
        """Test creating a conversation with auto-generated title."""
        # Mock database operations
        mock_conversation = Mock()
        mock_conversation.id = uuid.uuid4()
        mock_conversation.user_id = self.test_user_id
        mock_conversation.title = "对话 1"
        mock_conversation.created_at = datetime.utcnow()
        mock_conversation.updated_at = datetime.utcnow()
        
        # Mock count query to return 0 existing conversations
        self.mock_db.query.return_value.filter.return_value.count.return_value = 0
        self.mock_db.add = Mock()
        self.mock_db.commit = Mock()
        self.mock_db.refresh = Mock()
        
        with patch('backend.app.chat.conversation_service.Conversation') as mock_conv_class:
            mock_conv_class.return_value = mock_conversation
            
            result = await self.service.create_conversation(
                db=self.mock_db,
                user_id=self.test_user_id
            )
        
        assert result["title"] == "对话 1"
    
    @pytest.mark.asyncio
    async def test_get_conversations(self):
        """Test getting user conversations."""
        # Mock conversations
        mock_conv1 = Mock()
        mock_conv1.id = uuid.uuid4()
        mock_conv1.user_id = self.test_user_id
        mock_conv1.title = "Conversation 1"
        mock_conv1.created_at = datetime.utcnow()
        mock_conv1.updated_at = datetime.utcnow()
        
        mock_conv2 = Mock()
        mock_conv2.id = uuid.uuid4()
        mock_conv2.user_id = self.test_user_id
        mock_conv2.title = "Conversation 2"
        mock_conv2.created_at = datetime.utcnow()
        mock_conv2.updated_at = datetime.utcnow()
        
        # Mock database queries
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value = mock_query
        mock_query.count.return_value = 2
        mock_query.offset.return_value.limit.return_value.all.return_value = [mock_conv1, mock_conv2]
        
        self.mock_db.query.return_value = mock_query
        
        # Mock message count queries
        self.mock_db.query.return_value.filter.return_value.count.side_effect = [1, 2]
        
        # Mock last message queries
        mock_last_msg = Mock()
        mock_last_msg.role = "user"
        mock_last_msg.content = "Last message content"
        mock_last_msg.created_at = datetime.utcnow()
        
        self.mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_last_msg
        
        result = await self.service.get_conversations(
            db=self.mock_db,
            user_id=self.test_user_id,
            limit=10,
            offset=0
        )
        
        assert result["total_count"] == 2
        assert len(result["conversations"]) == 2
        assert result["conversations"][0]["title"] == "Conversation 1"
        assert result["conversations"][1]["title"] == "Conversation 2"
    
    @pytest.mark.asyncio
    async def test_add_message(self):
        """Test adding a message to a conversation."""
        # Mock conversation
        mock_conversation = Mock()
        mock_conversation.id = self.test_conversation_id
        mock_conversation.user_id = self.test_user_id
        mock_conversation.updated_at = datetime.utcnow()
        
        # Mock message
        mock_message = Mock()
        mock_message.id = uuid.uuid4()
        mock_message.conversation_id = self.test_conversation_id
        mock_message.role = "user"
        mock_message.content = "Test message"
        mock_message.metadata_json = {"source": "test"}
        mock_message.created_at = datetime.utcnow()
        
        # Mock database operations
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_conversation
        self.mock_db.add = Mock()
        self.mock_db.commit = Mock()
        self.mock_db.refresh = Mock()
        
        with patch('backend.app.chat.conversation_service.Message') as mock_msg_class:
            mock_msg_class.return_value = mock_message
            
            result = await self.service.add_message(
                db=self.mock_db,
                conversation_id=self.test_conversation_id,
                user_id=self.test_user_id,
                role="user",
                content="Test message",
                metadata={"source": "test"}
            )
        
        assert result["conversation_id"] == self.test_conversation_id
        assert result["role"] == "user"
        assert result["content"] == "Test message"
        assert result["metadata"]["source"] == "test"
        
        # Verify database operations
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_add_message_invalid_role(self):
        """Test adding a message with invalid role."""
        # Mock conversation
        mock_conversation = Mock()
        mock_conversation.id = self.test_conversation_id
        mock_conversation.user_id = self.test_user_id
        
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_conversation
        
        with pytest.raises(Exception, match="Invalid message role"):
            await self.service.add_message(
                db=self.mock_db,
                conversation_id=self.test_conversation_id,
                user_id=self.test_user_id,
                role="invalid_role",
                content="Test message"
            )
    
    @pytest.mark.asyncio
    async def test_get_conversation_context(self):
        """Test getting conversation context."""
        # Mock conversation
        mock_conversation = Mock()
        mock_conversation.id = self.test_conversation_id
        mock_conversation.user_id = self.test_user_id
        
        # Mock messages
        mock_messages = []
        for i in range(3):
            msg = Mock()
            msg.role = "user" if i % 2 == 0 else "assistant"
            msg.content = f"Message {i}"
            msg.created_at = datetime.utcnow()
            mock_messages.append(msg)
        
        # Create separate mock queries for conversation and messages
        mock_conv_query = Mock()
        mock_conv_query.filter.return_value.first.return_value = mock_conversation
        
        mock_msg_query = Mock()
        mock_msg_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_messages
        
        # Set up query mock to return different objects for different calls
        self.mock_db.query.side_effect = [mock_conv_query, mock_msg_query]
        
        context = await self.service.get_conversation_context(
            db=self.mock_db,
            conversation_id=self.test_conversation_id,
            user_id=self.test_user_id,
            max_messages=3
        )
        
        assert len(context) == 3
        assert context[0]["content"] == "Message 2"  # Reversed order
        assert context[1]["content"] == "Message 1"
        assert context[2]["content"] == "Message 0"
    
    @pytest.mark.asyncio
    async def test_conversation_not_found(self):
        """Test accessing non-existent conversation."""
        # Mock database to return None
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(Exception, match="not found"):
            await self.service.get_conversation(
                db=self.mock_db,
                conversation_id=self.test_conversation_id,
                user_id=self.test_user_id
            )
    
    @pytest.mark.asyncio
    async def test_delete_conversation(self):
        """Test deleting a conversation."""
        # Mock conversation
        mock_conversation = Mock()
        mock_conversation.id = self.test_conversation_id
        mock_conversation.user_id = self.test_user_id
        
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_conversation
        self.mock_db.delete = Mock()
        self.mock_db.commit = Mock()
        
        result = await self.service.delete_conversation(
            db=self.mock_db,
            conversation_id=self.test_conversation_id,
            user_id=self.test_user_id
        )
        
        assert result["conversation_id"] == self.test_conversation_id
        assert "deleted successfully" in result["message"]
        
        # Verify database operations
        self.mock_db.delete.assert_called_once_with(mock_conversation)
        self.mock_db.commit.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])