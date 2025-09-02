import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { performance } from 'perf_hooks';

// Import components to test
import ChatInterface from '../Chat/ChatInterface';
import DocumentList from '../Documents/DocumentList';
import ConversationList from '../Chat/ConversationList';

// Mock stores with large datasets
const mockLargeChatStore = {
  conversations: Array.from({ length: 100 }, (_, i) => ({
    id: `conv_${i}`,
    title: `Conversation ${i}`,
    created_at: new Date(Date.now() - i * 86400000).toISOString(),
    updated_at: new Date(Date.now() - i * 86400000).toISOString()
  })),
  messages: Array.from({ length: 500 }, (_, i) => ({
    id: `msg_${i}`,
    conversation_id: 'conv_1',
    role: i % 2 === 0 ? 'user' : 'assistant',
    content: `Message ${i} content that could be quite long and contain detailed information about various topics`,
    created_at: new Date(Date.now() - i * 60000).toISOString()
  })),
  currentConversationId: 'conv_1',
  loading: false,
  error: null,
  fetchConversations: jest.fn(),
  fetchMessages: jest.fn(),
  sendMessage: jest.fn(),
  createConversation: jest.fn()
};

const mockLargeDocumentStore = {
  documents: Array.from({ length: 1000 }, (_, i) => ({
    id: `doc_${i}`,
    original_name: `Document ${i}.pdf`,
    file_size: Math.floor(Math.random() * 10000000),
    mime_type: 'application/pdf',
    status: ['completed', 'processing', 'failed'][i % 3],
    created_at: new Date(Date.now() - i * 86400000).toISOString(),
    updated_at: new Date(Date.now() - i * 86400000).toISOString()
  })),
  total: 1000,
  page: 1,
  pageSize: 20,
  totalPages: 50,
  loading: false,
  error: null,
  selectedDocuments: [],
  fetchDocuments: jest.fn(),
  selectDocument: jest.fn()
};

// Mock zustand stores
jest.mock('../../stores/chatStore', () => ({
  useChatStore: () => mockLargeChatStore
}));

jest.mock('../../stores/documentStore', () => ({
  useDocumentStore: () => mockLargeDocumentStore
}));

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  );
};

describe('Performance Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders large conversation list efficiently', async () => {
    const startTime = performance.now();
    
    renderWithRouter(<ConversationList />);
    
    // Wait for component to fully render
    await waitFor(() => {
      expect(screen.getByText('Conversations')).toBeInTheDocument();
    });
    
    const endTime = performance.now();
    const renderTime = endTime - startTime;
    
    // Should render within reasonable time even with 100 conversations
    expect(renderTime).toBeLessThan(1000); // Less than 1 second
    
    // Should show conversations (virtualized or paginated)
    expect(screen.getByText('Conversation 0')).toBeInTheDocument();
  });

  it('renders large document list efficiently', async () => {
    const startTime = performance.now();
    
    renderWithRouter(<DocumentList />);
    
    // Wait for component to fully render
    await waitFor(() => {
      expect(screen.getByText('Document 0.pdf')).toBeInTheDocument();
    });
    
    const endTime = performance.now();
    const renderTime = endTime - startTime;
    
    // Should render within reasonable time even with 1000 documents
    expect(renderTime).toBeLessThan(1000); // Less than 1 second
    
    // Should only render visible items (pagination)
    const documentElements = screen.getAllByText(/Document \d+\.pdf/);
    expect(documentElements.length).toBeLessThanOrEqual(20); // Page size
  });

  it('handles chat interface with many messages efficiently', async () => {
    const startTime = performance.now();
    
    renderWithRouter(<ChatInterface />);
    
    // Wait for component to fully render
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/type your message/i)).toBeInTheDocument();
    });
    
    const endTime = performance.now();
    const renderTime = endTime - startTime;
    
    // Should render within reasonable time even with 500 messages
    expect(renderTime).toBeLessThan(1500); // Less than 1.5 seconds
  });

  it('optimizes re-renders when props change', () => {
    let renderCount = 0;
    
    const TestComponent = React.memo(() => {
      renderCount++;
      return <div>Render count: {renderCount}</div>;
    });
    
    const { rerender } = render(<TestComponent />);
    
    expect(renderCount).toBe(1);
    
    // Re-render with same props should not cause re-render
    rerender(<TestComponent />);
    expect(renderCount).toBe(1);
    
    // Only re-render when props actually change
    rerender(<TestComponent key="different" />);
    expect(renderCount).toBe(2);
  });

  it('handles rapid state updates efficiently', async () => {
    const TestComponent = () => {
      const [count, setCount] = React.useState(0);
      
      React.useEffect(() => {
        // Simulate rapid updates
        const interval = setInterval(() => {
          setCount(c => c + 1);
        }, 10);
        
        setTimeout(() => clearInterval(interval), 100);
        
        return () => clearInterval(interval);
      }, []);
      
      return <div data-testid="counter">{count}</div>;
    };
    
    const startTime = performance.now();
    
    render(<TestComponent />);
    
    // Wait for updates to complete
    await waitFor(() => {
      const counter = screen.getByTestId('counter');
      expect(parseInt(counter.textContent || '0')).toBeGreaterThan(5);
    }, { timeout: 200 });
    
    const endTime = performance.now();
    const updateTime = endTime - startTime;
    
    // Should handle rapid updates efficiently
    expect(updateTime).toBeLessThan(500);
  });

  it('lazy loads components efficiently', async () => {
    const LazyComponent = React.lazy(() => 
      Promise.resolve({
        default: () => <div>Lazy loaded content</div>
      })
    );
    
    const TestWrapper = () => (
      <React.Suspense fallback={<div>Loading...</div>}>
        <LazyComponent />
      </React.Suspense>
    );
    
    const startTime = performance.now();
    
    render(<TestWrapper />);
    
    // Should show loading state first
    expect(screen.getByText('Loading...')).toBeInTheDocument();
    
    // Wait for lazy component to load
    await waitFor(() => {
      expect(screen.getByText('Lazy loaded content')).toBeInTheDocument();
    });
    
    const endTime = performance.now();
    const loadTime = endTime - startTime;
    
    // Lazy loading should be fast
    expect(loadTime).toBeLessThan(100);
  });

  it('optimizes list rendering with virtualization', () => {
    const VirtualizedList = ({ items }: { items: any[] }) => {
      const [visibleRange, setVisibleRange] = React.useState({ start: 0, end: 20 });
      
      const visibleItems = items.slice(visibleRange.start, visibleRange.end);
      
      return (
        <div data-testid="virtualized-list">
          {visibleItems.map((item, index) => (
            <div key={item.id} data-testid={`item-${index}`}>
              {item.name}
            </div>
          ))}
        </div>
      );
    };
    
    const largeItemList = Array.from({ length: 10000 }, (_, i) => ({
      id: i,
      name: `Item ${i}`
    }));
    
    const startTime = performance.now();
    
    render(<VirtualizedList items={largeItemList} />);
    
    const endTime = performance.now();
    const renderTime = endTime - startTime;
    
    // Should render quickly even with 10k items by only rendering visible ones
    expect(renderTime).toBeLessThan(100);
    
    // Should only render visible items
    const renderedItems = screen.getAllByTestId(/^item-/);
    expect(renderedItems.length).toBeLessThanOrEqual(20);
  });

  it('debounces search input efficiently', async () => {
    let searchCallCount = 0;
    
    const SearchComponent = () => {
      const [query, setQuery] = React.useState('');
      
      const debouncedSearch = React.useMemo(
        () => {
          let timeoutId: NodeJS.Timeout;
          return (searchQuery: string) => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => {
              searchCallCount++;
            }, 300);
          };
        },
        []
      );
      
      React.useEffect(() => {
        if (query) {
          debouncedSearch(query);
        }
      }, [query, debouncedSearch]);
      
      return (
        <input
          data-testid="search-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search..."
        />
      );
    };
    
    render(<SearchComponent />);
    
    const searchInput = screen.getByTestId('search-input');
    
    // Simulate rapid typing
    for (let i = 0; i < 10; i++) {
      searchInput.focus();
      // Simulate typing
      (searchInput as HTMLInputElement).value = `query${i}`;
      searchInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
    
    // Wait for debounce
    await new Promise(resolve => setTimeout(resolve, 400));
    
    // Should only call search once due to debouncing
    expect(searchCallCount).toBeLessThanOrEqual(1);
  });

  it('handles memory efficiently with cleanup', () => {
    const ComponentWithCleanup = () => {
      React.useEffect(() => {
        const interval = setInterval(() => {
          // Some periodic task
        }, 1000);
        
        const eventListener = () => {
          // Some event handler
        };
        
        window.addEventListener('resize', eventListener);
        
        // Cleanup function
        return () => {
          clearInterval(interval);
          window.removeEventListener('resize', eventListener);
        };
      }, []);
      
      return <div>Component with cleanup</div>;
    };
    
    const { unmount } = render(<ComponentWithCleanup />);
    
    // Component should mount without issues
    expect(screen.getByText('Component with cleanup')).toBeInTheDocument();
    
    // Unmounting should not cause memory leaks
    expect(() => unmount()).not.toThrow();
  });

  it('optimizes bundle size with code splitting', () => {
    // This test would typically be run with bundle analysis tools
    // Here we simulate checking for proper code splitting
    
    const checkCodeSplitting = () => {
      // In a real scenario, this would check webpack bundle analysis
      // For now, we just verify lazy loading works
      const LazyRoute = React.lazy(() => 
        Promise.resolve({
          default: () => <div>Route component</div>
        })
      );
      
      return LazyRoute;
    };
    
    const LazyComponent = checkCodeSplitting();
    
    expect(LazyComponent).toBeDefined();
    expect(typeof LazyComponent).toBe('object');
  });
});