"""
Conversation management service for handling chat sessions and message history.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from ..models import Conversation, Message, User
from ..database import get_db

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for managing conversations and messages."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def create_conversation(
        self,
        db: Session,
        user_id: str,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new conversation for a user.
        
        Args:
            db: Database session
            user_id: ID of the user creating the conversation
            title: Optional title for the conversation
            
        Returns:
            Dictionary containing conversation details
        """
        try:
            # Generate title if not provided
            if not title:
                # Count existing conversations to generate a default title
                conversation_count = db.query(Conversation).filter(
                    Conversation.user_id == user_id
                ).count()
                title = f"对话 {conversation_count + 1}"
            
            # Create new conversation
            conversation = Conversation(
                user_id=user_id,
                title=title
            )
            
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            
            self.logger.info(f"Created conversation {conversation.id} for user {user_id}")
            
            return {
                "id": str(conversation.id),
                "user_id": str(conversation.user_id),
                "title": conversation.title,
                "created_at": conversation.created_at.isoformat(),
                "updated_at": conversation.updated_at.isoformat(),
                "message_count": 0
            }
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Failed to create conversation for user {user_id}: {e}")
            raise Exception(f"Failed to create conversation: {str(e)}")
    
    async def get_conversations(
        self,
        db: Session,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get conversations for a user with pagination.
        
        Args:
            db: Database session
            user_id: ID of the user
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip
            
        Returns:
            Dictionary containing conversations list and metadata
        """
        try:
            # Query conversations with message count
            conversations_query = db.query(Conversation).filter(
                Conversation.user_id == user_id
            ).order_by(desc(Conversation.updated_at))
            
            # Get total count
            total_count = conversations_query.count()
            
            # Apply pagination
            conversations = conversations_query.offset(offset).limit(limit).all()
            
            # Format conversations with message counts
            conversation_list = []
            for conv in conversations:
                message_count = db.query(Message).filter(
                    Message.conversation_id == conv.id
                ).count()
                
                # Get last message for preview
                last_message = db.query(Message).filter(
                    Message.conversation_id == conv.id
                ).order_by(desc(Message.created_at)).first()
                
                conversation_data = {
                    "id": str(conv.id),
                    "user_id": str(conv.user_id),
                    "title": conv.title,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                    "message_count": message_count,
                    "last_message": None
                }
                
                if last_message:
                    conversation_data["last_message"] = {
                        "role": last_message.role,
                        "content": last_message.content[:100] + "..." if len(last_message.content) > 100 else last_message.content,
                        "created_at": last_message.created_at.isoformat()
                    }
                
                conversation_list.append(conversation_data)
            
            return {
                "conversations": conversation_list,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(conversations) < total_count
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get conversations for user {user_id}: {e}")
            raise Exception(f"Failed to get conversations: {str(e)}")
    
    async def get_conversation(
        self,
        db: Session,
        conversation_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get a specific conversation by ID.
        
        Args:
            db: Database session
            conversation_id: ID of the conversation
            user_id: ID of the user (for authorization)
            
        Returns:
            Dictionary containing conversation details
        """
        try:
            conversation = db.query(Conversation).filter(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id
                )
            ).first()
            
            if not conversation:
                raise Exception("Conversation not found or access denied")
            
            message_count = db.query(Message).filter(
                Message.conversation_id == conversation.id
            ).count()
            
            return {
                "id": str(conversation.id),
                "user_id": str(conversation.user_id),
                "title": conversation.title,
                "created_at": conversation.created_at.isoformat(),
                "updated_at": conversation.updated_at.isoformat(),
                "message_count": message_count
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get conversation {conversation_id}: {e}")
            raise Exception(f"Failed to get conversation: {str(e)}")
    
    async def update_conversation(
        self,
        db: Session,
        conversation_id: str,
        user_id: str,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update conversation details.
        
        Args:
            db: Database session
            conversation_id: ID of the conversation
            user_id: ID of the user (for authorization)
            title: New title for the conversation
            
        Returns:
            Dictionary containing updated conversation details
        """
        try:
            conversation = db.query(Conversation).filter(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id
                )
            ).first()
            
            if not conversation:
                raise Exception("Conversation not found or access denied")
            
            if title is not None:
                conversation.title = title
                conversation.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(conversation)
            
            message_count = db.query(Message).filter(
                Message.conversation_id == conversation.id
            ).count()
            
            return {
                "id": str(conversation.id),
                "user_id": str(conversation.user_id),
                "title": conversation.title,
                "created_at": conversation.created_at.isoformat(),
                "updated_at": conversation.updated_at.isoformat(),
                "message_count": message_count
            }
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Failed to update conversation {conversation_id}: {e}")
            raise Exception(f"Failed to update conversation: {str(e)}")
    
    async def delete_conversation(
        self,
        db: Session,
        conversation_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Delete a conversation and all its messages.
        
        Args:
            db: Database session
            conversation_id: ID of the conversation
            user_id: ID of the user (for authorization)
            
        Returns:
            Dictionary containing deletion confirmation
        """
        try:
            conversation = db.query(Conversation).filter(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id
                )
            ).first()
            
            if not conversation:
                raise Exception("Conversation not found or access denied")
            
            # Delete conversation (messages will be deleted due to cascade)
            db.delete(conversation)
            db.commit()
            
            self.logger.info(f"Deleted conversation {conversation_id} for user {user_id}")
            
            return {
                "message": "Conversation deleted successfully",
                "conversation_id": conversation_id
            }
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Failed to delete conversation {conversation_id}: {e}")
            raise Exception(f"Failed to delete conversation: {str(e)}")
    
    async def add_message(
        self,
        db: Session,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a message to a conversation.
        
        Args:
            db: Database session
            conversation_id: ID of the conversation
            user_id: ID of the user (for authorization)
            role: Role of the message sender ('user' or 'assistant')
            content: Content of the message
            metadata: Optional metadata (sources, references, etc.)
            
        Returns:
            Dictionary containing message details
        """
        try:
            # Verify conversation exists and user has access
            conversation = db.query(Conversation).filter(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id
                )
            ).first()
            
            if not conversation:
                raise Exception("Conversation not found or access denied")
            
            # Validate role
            if role not in ['user', 'assistant']:
                raise Exception("Invalid message role. Must be 'user' or 'assistant'")
            
            # Create message
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                metadata_json=metadata
            )
            
            db.add(message)
            
            # Update conversation timestamp
            conversation.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(message)
            
            self.logger.info(f"Added {role} message to conversation {conversation_id}")
            
            return {
                "id": str(message.id),
                "conversation_id": str(message.conversation_id),
                "role": message.role,
                "content": message.content,
                "metadata": message.metadata_json,
                "created_at": message.created_at.isoformat()
            }
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Failed to add message to conversation {conversation_id}: {e}")
            raise Exception(f"Failed to add message: {str(e)}")
    
    async def get_messages(
        self,
        db: Session,
        conversation_id: str,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Get messages from a conversation with pagination.
        
        Args:
            db: Database session
            conversation_id: ID of the conversation
            user_id: ID of the user (for authorization)
            limit: Maximum number of messages to return
            offset: Number of messages to skip
            include_metadata: Whether to include message metadata
            
        Returns:
            Dictionary containing messages list and metadata
        """
        try:
            # Verify conversation exists and user has access
            conversation = db.query(Conversation).filter(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id
                )
            ).first()
            
            if not conversation:
                raise Exception("Conversation not found or access denied")
            
            # Query messages
            messages_query = db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at)
            
            # Get total count
            total_count = messages_query.count()
            
            # Apply pagination
            messages = messages_query.offset(offset).limit(limit).all()
            
            # Format messages
            message_list = []
            for msg in messages:
                message_data = {
                    "id": str(msg.id),
                    "conversation_id": str(msg.conversation_id),
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat()
                }
                
                if include_metadata and msg.metadata_json:
                    message_data["metadata"] = msg.metadata_json
                
                message_list.append(message_data)
            
            return {
                "messages": message_list,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(messages) < total_count,
                "conversation": {
                    "id": str(conversation.id),
                    "title": conversation.title,
                    "created_at": conversation.created_at.isoformat(),
                    "updated_at": conversation.updated_at.isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get messages for conversation {conversation_id}: {e}")
            raise Exception(f"Failed to get messages: {str(e)}")
    
    async def get_conversation_context(
        self,
        db: Session,
        conversation_id: str,
        user_id: str,
        max_messages: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent conversation context for multi-turn dialogue.
        
        Args:
            db: Database session
            conversation_id: ID of the conversation
            user_id: ID of the user (for authorization)
            max_messages: Maximum number of recent messages to include
            
        Returns:
            List of recent messages for context
        """
        try:
            # Verify conversation exists and user has access
            conversation = db.query(Conversation).filter(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id
                )
            ).first()
            
            if not conversation:
                raise Exception("Conversation not found or access denied")
            
            # Get recent messages
            messages = db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(desc(Message.created_at)).limit(max_messages).all()
            
            # Reverse to get chronological order
            messages.reverse()
            
            # Format for context
            context = []
            for msg in messages:
                context.append({
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat()
                })
            
            return context
            
        except Exception as e:
            self.logger.error(f"Failed to get context for conversation {conversation_id}: {e}")
            raise Exception(f"Failed to get conversation context: {str(e)}")


# Global service instance
_conversation_service = None


def get_conversation_service() -> ConversationService:
    """Get the global conversation service instance."""
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service