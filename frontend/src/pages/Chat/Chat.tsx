import React, { useEffect, useState } from 'react';
import { Row, Col, message } from 'antd';
import { useChatStore } from '../../stores/chatStore';
import ConversationList from '../../components/Chat/ConversationList';
import ChatInterface from '../../components/Chat/ChatInterface';
import './Chat.css';

const Chat: React.FC = () => {
  const {
    conversations,
    currentConversation,
    fetchConversations,
    createConversation,
    selectConversation,
    error,
    clearError,
  } = useChatStore();

  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  useEffect(() => {
    fetchConversations();

    const handleResize = () => {
      setIsMobile(window.innerWidth < 768);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [fetchConversations]);

  useEffect(() => {
    if (error) {
      message.error(error);
      clearError();
    }
  }, [error, clearError]);

  const handleNewConversation = async () => {
    try {
      await createConversation();
    } catch (error) {
      // Error is handled by the store
    }
  };

  const handleSelectConversation = async (conversationId: string) => {
    try {
      await selectConversation(conversationId);
    } catch (error) {
      // Error is handled by the store
    }
  };

  return (
    <div className="chat-layout">
      <div className="chat-content">
        <Row className="chat-row" gutter={0}>
          {/* Conversation List - Hidden on mobile when a conversation is selected */}
          <Col 
            xs={currentConversation && isMobile ? 0 : 24} 
            sm={currentConversation && isMobile ? 0 : 24} 
            md={8} 
            lg={6} 
            xl={6}
            className="conversation-sidebar"
          >
            <ConversationList
              conversations={conversations}
              currentConversation={currentConversation}
              onNewConversation={handleNewConversation}
              onSelectConversation={handleSelectConversation}
            />
          </Col>

          {/* Chat Interface */}
          <Col 
            xs={currentConversation && isMobile ? 24 : 0} 
            sm={currentConversation && isMobile ? 24 : 0} 
            md={16} 
            lg={18} 
            xl={18}
            className="chat-main"
          >
            <ChatInterface 
              conversation={currentConversation}
              isMobile={isMobile}
            />
          </Col>
        </Row>
      </div>
    </div>
  );
};

export default Chat;