import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import ConversationList from '../ConversationList';

// Mock the chat store
const mockChatStore = {
  conversations: [
    {
      id: '1',
      title: 'Machine Learning Basics',
      created_at: '2024-01-01T10:00:00Z',
      updated_at: '2024-01-01T10:30:00Z'
    },
    {
      id: '2', 
      title: 'Deep Learning Advanced',
      created_at: '2024-01-02T14:00:00Z',
      updated_at: '2024-01-02T14:45:00Z'
    }
  ],
  currentConversationId: '1',
  loading: false,
  error: null,
  fetchConversations: jest.fn(),
  createConversation: jest.fn(),
  deleteConversation: jest.fn(),
  setCurrentConversation: jest.fn()
};

// Mock zustand store
jest.mock('../../../stores/chatStore', () => ({
  useChatStore: () => mockChatStore
}));

// Mock react-router-dom
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate
}));

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  );
};

describe('ConversationList', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders conversation list correctly', () => {
    renderWithRouter(<ConversationList />);
    
    expect(screen.getByText('Conversations')).toBeInTheDocument();
    expect(screen.getByText('Machine Learning Basics')).toBeInTheDocument();
    expect(screen.getByText('Deep Learning Advanced')).toBeInTheDocument();
  });

  it('highlights current conversation', () => {
    renderWithRouter(<ConversationList />);
    
    const currentConversation = screen.getByText('Machine Learning Basics').closest('.conversation-item');
    expect(currentConversation).toHaveClass('active');
  });

  it('calls setCurrentConversation when conversation is clicked', () => {
    renderWithRouter(<ConversationList />);
    
    const conversation = screen.getByText('Deep Learning Advanced');
    fireEvent.click(conversation);
    
    expect(mockChatStore.setCurrentConversation).toHaveBeenCalledWith('2');
    expect(mockNavigate).toHaveBeenCalledWith('/chat/2');
  });

  it('shows new conversation button', () => {
    renderWithRouter(<ConversationList />);
    
    const newButton = screen.getByRole('button', { name: /new conversation/i });
    expect(newButton).toBeInTheDocument();
  });

  it('creates new conversation when button is clicked', async () => {
    mockChatStore.createConversation.mockResolvedValue({ id: '3', title: 'New Chat' });
    
    renderWithRouter(<ConversationList />);
    
    const newButton = screen.getByRole('button', { name: /new conversation/i });
    fireEvent.click(newButton);
    
    await waitFor(() => {
      expect(mockChatStore.createConversation).toHaveBeenCalled();
    });
  });

  it('shows delete button on hover', () => {
    renderWithRouter(<ConversationList />);
    
    const conversationItem = screen.getByText('Machine Learning Basics').closest('.conversation-item');
    fireEvent.mouseEnter(conversationItem!);
    
    const deleteButton = screen.getByRole('button', { name: /delete/i });
    expect(deleteButton).toBeInTheDocument();
  });

  it('deletes conversation when delete button is clicked', async () => {
    mockChatStore.deleteConversation.mockResolvedValue(true);
    
    renderWithRouter(<ConversationList />);
    
    const conversationItem = screen.getByText('Machine Learning Basics').closest('.conversation-item');
    fireEvent.mouseEnter(conversationItem!);
    
    const deleteButton = screen.getByRole('button', { name: /delete/i });
    fireEvent.click(deleteButton);
    
    await waitFor(() => {
      expect(mockChatStore.deleteConversation).toHaveBeenCalledWith('1');
    });
  });

  it('shows loading state', () => {
    const loadingStore = { ...mockChatStore, loading: true };
    jest.mocked(require('../../stores/chatStore').useChatStore).mockReturnValue(loadingStore);
    
    renderWithRouter(<ConversationList />);
    
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
  });

  it('shows error state', () => {
    const errorStore = { ...mockChatStore, error: 'Failed to load conversations' };
    jest.mocked(require('../../stores/chatStore').useChatStore).mockReturnValue(errorStore);
    
    renderWithRouter(<ConversationList />);
    
    expect(screen.getByText('Failed to load conversations')).toBeInTheDocument();
  });

  it('shows empty state when no conversations', () => {
    const emptyStore = { ...mockChatStore, conversations: [] };
    jest.mocked(require('../../stores/chatStore').useChatStore).mockReturnValue(emptyStore);
    
    renderWithRouter(<ConversationList />);
    
    expect(screen.getByText(/no conversations yet/i)).toBeInTheDocument();
  });

  it('formats conversation dates correctly', () => {
    renderWithRouter(<ConversationList />);
    
    // Should show relative time for recent conversations
    expect(screen.getByText(/jan 1/i)).toBeInTheDocument();
    expect(screen.getByText(/jan 2/i)).toBeInTheDocument();
  });

  it('truncates long conversation titles', () => {
    const longTitleStore = {
      ...mockChatStore,
      conversations: [{
        id: '1',
        title: 'This is a very long conversation title that should be truncated to fit in the sidebar',
        created_at: '2024-01-01T10:00:00Z',
        updated_at: '2024-01-01T10:30:00Z'
      }]
    };
    jest.mocked(require('../../stores/chatStore').useChatStore).mockReturnValue(longTitleStore);
    
    renderWithRouter(<ConversationList />);
    
    const titleElement = screen.getByText(/This is a very long conversation/);
    expect(titleElement).toHaveClass('truncated');
  });
});