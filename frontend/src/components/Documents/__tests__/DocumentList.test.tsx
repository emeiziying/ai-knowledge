import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DocumentList from '../DocumentList';

// Mock document data
const mockDocuments = [
  {
    id: '1',
    original_name: 'Machine Learning Guide.pdf',
    file_size: 2048000,
    mime_type: 'application/pdf',
    status: 'completed',
    created_at: '2024-01-01T10:00:00Z',
    updated_at: '2024-01-01T10:30:00Z'
  },
  {
    id: '2',
    original_name: 'Deep Learning Notes.txt',
    file_size: 512000,
    mime_type: 'text/plain',
    status: 'processing',
    created_at: '2024-01-02T14:00:00Z',
    updated_at: '2024-01-02T14:15:00Z'
  },
  {
    id: '3',
    original_name: 'AI Research Paper.docx',
    file_size: 1024000,
    mime_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    status: 'failed',
    created_at: '2024-01-03T09:00:00Z',
    updated_at: '2024-01-03T09:05:00Z'
  }
];

// Mock the document store
const mockDocumentStore = {
  documents: mockDocuments,
  total: 3,
  page: 1,
  pageSize: 20,
  totalPages: 1,
  loading: false,
  error: null,
  selectedDocuments: [],
  fetchDocuments: jest.fn(),
  deleteDocument: jest.fn(),
  downloadDocument: jest.fn(),
  selectDocument: jest.fn(),
  selectAllDocuments: jest.fn(),
  clearSelection: jest.fn(),
  setPage: jest.fn(),
  setPageSize: jest.fn()
};

// Mock zustand store
jest.mock('../../stores/documentStore', () => ({
  useDocumentStore: () => mockDocumentStore
}));

// Mock antd components
const mockModal = {
  confirm: jest.fn()
};
jest.mock('antd', () => ({
  ...jest.requireActual('antd'),
  Modal: mockModal
}));

describe('DocumentList', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders document list correctly', () => {
    render(<DocumentList />);
    
    expect(screen.getByText('Machine Learning Guide.pdf')).toBeInTheDocument();
    expect(screen.getByText('Deep Learning Notes.txt')).toBeInTheDocument();
    expect(screen.getByText('AI Research Paper.docx')).toBeInTheDocument();
  });

  it('displays document information correctly', () => {
    render(<DocumentList />);
    
    // Check file sizes
    expect(screen.getByText('2.0 MB')).toBeInTheDocument();
    expect(screen.getByText('512 KB')).toBeInTheDocument();
    expect(screen.getByText('1.0 MB')).toBeInTheDocument();
    
    // Check status badges
    expect(screen.getByText('Completed')).toBeInTheDocument();
    expect(screen.getByText('Processing')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  it('shows correct status colors', () => {
    render(<DocumentList />);
    
    const completedBadge = screen.getByText('Completed');
    const processingBadge = screen.getByText('Processing');
    const failedBadge = screen.getByText('Failed');
    
    expect(completedBadge).toHaveClass('status-completed');
    expect(processingBadge).toHaveClass('status-processing');
    expect(failedBadge).toHaveClass('status-failed');
  });

  it('handles document selection', () => {
    render(<DocumentList />);
    
    const checkbox = screen.getAllByRole('checkbox')[1]; // First document checkbox
    fireEvent.click(checkbox);
    
    expect(mockDocumentStore.selectDocument).toHaveBeenCalledWith('1');
  });

  it('handles select all documents', () => {
    render(<DocumentList />);
    
    const selectAllCheckbox = screen.getAllByRole('checkbox')[0]; // Header checkbox
    fireEvent.click(selectAllCheckbox);
    
    expect(mockDocumentStore.selectAllDocuments).toHaveBeenCalled();
  });

  it('shows document actions menu', async () => {
    const user = userEvent.setup();
    render(<DocumentList />);
    
    const actionButton = screen.getAllByRole('button', { name: /more/i })[0];
    await user.click(actionButton);
    
    expect(screen.getByText('Download')).toBeInTheDocument();
    expect(screen.getByText('Delete')).toBeInTheDocument();
    expect(screen.getByText('View Details')).toBeInTheDocument();
  });

  it('handles document download', async () => {
    const user = userEvent.setup();
    mockDocumentStore.downloadDocument.mockResolvedValue(true);
    
    render(<DocumentList />);
    
    const actionButton = screen.getAllByRole('button', { name: /more/i })[0];
    await user.click(actionButton);
    
    const downloadButton = screen.getByText('Download');
    await user.click(downloadButton);
    
    expect(mockDocumentStore.downloadDocument).toHaveBeenCalledWith('1');
  });

  it('handles document deletion with confirmation', async () => {
    const user = userEvent.setup();
    mockDocumentStore.deleteDocument.mockResolvedValue(true);
    mockModal.confirm.mockImplementation(({ onOk }) => onOk());
    
    render(<DocumentList />);
    
    const actionButton = screen.getAllByRole('button', { name: /more/i })[0];
    await user.click(actionButton);
    
    const deleteButton = screen.getByText('Delete');
    await user.click(deleteButton);
    
    expect(mockModal.confirm).toHaveBeenCalled();
    expect(mockDocumentStore.deleteDocument).toHaveBeenCalledWith('1');
  });

  it('shows bulk actions when documents are selected', () => {
    const selectedStore = {
      ...mockDocumentStore,
      selectedDocuments: ['1', '2']
    };
    jest.mocked(require('../../stores/documentStore').useDocumentStore).mockReturnValue(selectedStore);
    
    render(<DocumentList />);
    
    expect(screen.getByText('2 selected')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /delete selected/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /clear selection/i })).toBeInTheDocument();
  });

  it('handles bulk deletion', async () => {
    const user = userEvent.setup();
    const selectedStore = {
      ...mockDocumentStore,
      selectedDocuments: ['1', '2'],
      deleteSelectedDocuments: jest.fn()
    };
    jest.mocked(require('../../stores/documentStore').useDocumentStore).mockReturnValue(selectedStore);
    mockModal.confirm.mockImplementation(({ onOk }) => onOk());
    
    render(<DocumentList />);
    
    const deleteSelectedButton = screen.getByRole('button', { name: /delete selected/i });
    await user.click(deleteSelectedButton);
    
    expect(mockModal.confirm).toHaveBeenCalled();
    expect(selectedStore.deleteSelectedDocuments).toHaveBeenCalled();
  });

  it('shows pagination when there are multiple pages', () => {
    const paginatedStore = {
      ...mockDocumentStore,
      total: 50,
      totalPages: 3,
      page: 1
    };
    jest.mocked(require('../../stores/documentStore').useDocumentStore).mockReturnValue(paginatedStore);
    
    render(<DocumentList />);
    
    expect(screen.getByRole('navigation')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('handles page change', async () => {
    const user = userEvent.setup();
    const paginatedStore = {
      ...mockDocumentStore,
      total: 50,
      totalPages: 3,
      page: 1
    };
    jest.mocked(require('../../stores/documentStore').useDocumentStore).mockReturnValue(paginatedStore);
    
    render(<DocumentList />);
    
    const page2Button = screen.getByText('2');
    await user.click(page2Button);
    
    expect(mockDocumentStore.setPage).toHaveBeenCalledWith(2);
  });

  it('shows loading state', () => {
    const loadingStore = {
      ...mockDocumentStore,
      loading: true,
      documents: []
    };
    jest.mocked(require('../../stores/documentStore').useDocumentStore).mockReturnValue(loadingStore);
    
    render(<DocumentList />);
    
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
  });

  it('shows error state', () => {
    const errorStore = {
      ...mockDocumentStore,
      error: 'Failed to load documents',
      documents: []
    };
    jest.mocked(require('../../stores/documentStore').useDocumentStore).mockReturnValue(errorStore);
    
    render(<DocumentList />);
    
    expect(screen.getByText('Failed to load documents')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('shows empty state when no documents', () => {
    const emptyStore = {
      ...mockDocumentStore,
      documents: [],
      total: 0
    };
    jest.mocked(require('../../stores/documentStore').useDocumentStore).mockReturnValue(emptyStore);
    
    render(<DocumentList />);
    
    expect(screen.getByText(/no documents found/i)).toBeInTheDocument();
    expect(screen.getByText(/upload your first document/i)).toBeInTheDocument();
  });

  it('formats dates correctly', () => {
    render(<DocumentList />);
    
    // Should show formatted dates
    expect(screen.getByText(/jan 1, 2024/i)).toBeInTheDocument();
    expect(screen.getByText(/jan 2, 2024/i)).toBeInTheDocument();
  });

  it('shows file type icons', () => {
    render(<DocumentList />);
    
    const pdfIcon = screen.getByTestId('pdf-icon');
    const txtIcon = screen.getByTestId('txt-icon');
    const docxIcon = screen.getByTestId('docx-icon');
    
    expect(pdfIcon).toBeInTheDocument();
    expect(txtIcon).toBeInTheDocument();
    expect(docxIcon).toBeInTheDocument();
  });

  it('handles sorting by different columns', async () => {
    const user = userEvent.setup();
    render(<DocumentList />);
    
    const nameHeader = screen.getByText('Name');
    await user.click(nameHeader);
    
    expect(mockDocumentStore.fetchDocuments).toHaveBeenCalledWith(
      expect.objectContaining({
        sortBy: 'name',
        sortOrder: 'asc'
      })
    );
  });

  it('shows processing progress for documents being processed', () => {
    const processingStore = {
      ...mockDocumentStore,
      documents: [
        {
          ...mockDocuments[1],
          processing_progress: 65
        }
      ]
    };
    jest.mocked(require('../../stores/documentStore').useDocumentStore).mockReturnValue(processingStore);
    
    render(<DocumentList />);
    
    expect(screen.getByText('65%')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });
});