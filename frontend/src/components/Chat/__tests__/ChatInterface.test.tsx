import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import ChatInterface from '../ChatInterface';

// Mock the chat store
jest.mock('../../../stores/chatStore', () => ({
  useChatStore: () => ({
    messages: [],
    isSending: false,
    messagesLoading: false,
    error: null,
    sendMessage: jest.fn(),
    fetchMessages: jest.fn(),
    clearCurrentConversation: jest.fn(),
    clearError: jest.fn(),
  }),
}));

describe('ChatInterface', () => {
  it('renders empty state when no conversation is provided', () => {
    render(<ChatInterface conversation={null} />);
    
    expect(screen.getByText('开始新的对话')).toBeInTheDocument();
    expect(screen.getByText('向AI助手提问，获取基于您知识库的智能回答')).toBeInTheDocument();
  });

  it('renders chat interface when conversation is provided', () => {
    const mockConversation = {
      id: '1',
      user_id: 'user1',
      title: 'Test Conversation',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    };

    render(<ChatInterface conversation={mockConversation} />);
    
    expect(screen.getByText('Test Conversation')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('输入您的问题...')).toBeInTheDocument();
    expect(screen.getByText('发送')).toBeInTheDocument();
  });
});