import React, { useState, useRef, useEffect } from 'react';
import {
  Input,
  Button,
  Typography,
  Space,
  Spin,
  Alert,
  Empty,
  Avatar,
  Tag,
  Tooltip,
  message,
} from 'antd';
import {
  SendOutlined,
  UserOutlined,
  RobotOutlined,
  ArrowLeftOutlined,
  FileTextOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { Conversation, Message } from '../../types/api';
import { useChatStore } from '../../stores/chatStore';
import { useDocumentStore } from '../../stores/documentStore';
import './ChatInterface.css';

const { TextArea } = Input;
const { Text, Title } = Typography;

interface ChatInterfaceProps {
  conversation: Conversation | null;
  isMobile?: boolean;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ 
  conversation, 
  isMobile = false 
}) => {
  const navigate = useNavigate();
  const {
    messages,
    isSending,
    messagesLoading,
    error,
    sendMessage,
    fetchMessages,
    clearCurrentConversation,
    clearError,
  } = useChatStore();
  
  const { } = useDocumentStore();

  const [inputMessage, setInputMessage] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textAreaRef = useRef<any>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Focus input when conversation changes
  useEffect(() => {
    if (conversation && textAreaRef.current) {
      textAreaRef.current.focus();
    }
  }, [conversation]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim()) {
      message.warning('请输入消息内容');
      return;
    }

    const messageText = inputMessage.trim();
    setInputMessage('');

    try {
      await sendMessage(messageText, conversation?.id);
    } catch (error) {
      // Error is handled by the store
      setInputMessage(messageText); // Restore message on error
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleRetry = async () => {
    if (conversation) {
      try {
        await fetchMessages(conversation.id);
      } catch (error) {
        // Error is handled by the store
      }
    }
  };

  const formatMessageTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('zh-CN', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  const handleSourceClick = async (documentId: string, documentName: string) => {
    try {
      // Navigate to documents page and highlight the specific document
      navigate(`/documents?highlight=${documentId}`);
      message.success(`正在跳转到文档：${documentName}`);
    } catch (error) {
      message.error('跳转失败，请稍后重试');
    }
  };

  const renderMessageSources = (metadata?: Message['metadata']) => {
    if (!metadata?.sources || metadata.sources.length === 0) {
      return null;
    }

    return (
      <div className="message-sources">
        <Text type="secondary" className="sources-label">
          参考来源：
        </Text>
        <Space wrap size={[4, 4]}>
          {metadata.sources.map((source, index) => (
            <Tooltip 
              key={index}
              title={`点击查看文档：${source.document_name} | 相关度：${(source.relevance_score * 100).toFixed(1)}%`}
            >
              <Tag 
                icon={<FileTextOutlined />}
                className="source-tag clickable"
                color="blue"
                onClick={() => handleSourceClick(source.document_id, source.document_name)}
              >
                {source.document_name}
              </Tag>
            </Tooltip>
          ))}
        </Space>
      </div>
    );
  };

  const renderMessage = (msg: Message) => {
    const isUser = msg.role === 'user';
    
    return (
      <div 
        key={msg.id} 
        className={`message-wrapper ${isUser ? 'user-message' : 'assistant-message'}`}
      >
        <div className="message-content">
          <Avatar 
            icon={isUser ? <UserOutlined /> : <RobotOutlined />}
            className={`message-avatar ${isUser ? 'user-avatar' : 'assistant-avatar'}`}
          />
          <div className="message-bubble">
            <div className="message-text">
              {msg.content}
            </div>
            {!isUser && renderMessageSources(msg.metadata)}
            <div className="message-time">
              {formatMessageTime(msg.created_at)}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderEmptyState = () => (
    <div className="chat-empty-state">
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          <div>
            <Title level={4} type="secondary">
              开始新的对话
            </Title>
            <Text type="secondary">
              向AI助手提问，获取基于您知识库的智能回答
            </Text>
          </div>
        }
      />
    </div>
  );

  const renderError = () => (
    <div className="chat-error">
      <Alert
        message="加载失败"
        description={error}
        type="error"
        showIcon
        action={
          <Button size="small" onClick={handleRetry}>
            <ReloadOutlined /> 重试
          </Button>
        }
        onClose={clearError}
        closable
      />
    </div>
  );

  if (!conversation) {
    return (
      <div className="chat-interface no-conversation">
        {renderEmptyState()}
      </div>
    );
  }

  return (
    <div className="chat-interface">
      {/* Header */}
      <div className="chat-header">
        {isMobile && (
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={clearCurrentConversation}
            className="back-button"
          />
        )}
        <div className="chat-title">
          <Title level={5} ellipsis className="conversation-title">
            {conversation.title || '新对话'}
          </Title>
        </div>
      </div>

      {/* Messages Area */}
      <div className="chat-messages">
        {messagesLoading ? (
          <div className="messages-loading">
            <Spin size="large" tip="加载对话历史..." />
          </div>
        ) : error ? (
          renderError()
        ) : messages.length === 0 ? (
          <div className="messages-empty">
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="还没有消息，开始对话吧！"
            />
          </div>
        ) : (
          <div className="messages-list">
            {messages.map(renderMessage)}
            {isSending && (
              <div className="message-wrapper assistant-message">
                <div className="message-content">
                  <Avatar 
                    icon={<RobotOutlined />}
                    className="message-avatar assistant-avatar"
                  />
                  <div className="message-bubble typing">
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="chat-input">
        <div className="input-container">
          <TextArea
            ref={textAreaRef}
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入您的问题..."
            autoSize={{ minRows: 1, maxRows: 4 }}
            disabled={isSending}
            className="message-input"
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSendMessage}
            loading={isSending}
            disabled={!inputMessage.trim() || isSending}
            className="send-button"
          >
            发送
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;