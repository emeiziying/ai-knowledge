import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FileUpload from '../FileUpload';

// Mock the document store
const mockDocumentStore = {
  uploadProgress: {},
  uploading: false,
  error: null,
  uploadDocument: jest.fn(),
  clearError: jest.fn()
};

// Mock zustand store
jest.mock('../../../stores/documentStore', () => ({
  useDocumentStore: () => mockDocumentStore
}));

// Mock antd message
const mockMessage = {
  success: jest.fn(),
  error: jest.fn(),
  warning: jest.fn()
};
jest.mock('antd', () => ({
  ...jest.requireActual('antd'),
  message: mockMessage
}));

describe('FileUpload', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders upload area correctly', () => {
    render(<FileUpload />);
    
    expect(screen.getByText(/drag & drop files here/i)).toBeInTheDocument();
    expect(screen.getByText(/or click to select/i)).toBeInTheDocument();
    expect(screen.getByText(/supported formats/i)).toBeInTheDocument();
  });

  it('shows supported file formats', () => {
    render(<FileUpload />);
    
    expect(screen.getByText(/pdf/i)).toBeInTheDocument();
    expect(screen.getByText(/word/i)).toBeInTheDocument();
    expect(screen.getByText(/text/i)).toBeInTheDocument();
    expect(screen.getByText(/markdown/i)).toBeInTheDocument();
  });

  it('handles file selection via click', async () => {
    const user = userEvent.setup();
    mockDocumentStore.uploadDocument.mockResolvedValue({ id: '1', status: 'uploaded' });
    
    render(<FileUpload />);
    
    const file = new File(['test content'], 'test.pdf', { type: 'application/pdf' });
    const input = screen.getByLabelText(/upload/i);
    
    await user.upload(input, file);
    
    await waitFor(() => {
      expect(mockDocumentStore.uploadDocument).toHaveBeenCalledWith(file);
    });
  });

  it('handles drag and drop', async () => {
    mockDocumentStore.uploadDocument.mockResolvedValue({ id: '1', status: 'uploaded' });
    
    render(<FileUpload />);
    
    const dropZone = screen.getByTestId('upload-dropzone');
    const file = new File(['test content'], 'test.pdf', { type: 'application/pdf' });
    
    // Simulate drag enter
    fireEvent.dragEnter(dropZone, {
      dataTransfer: {
        files: [file],
        types: ['Files']
      }
    });
    
    expect(dropZone).toHaveClass('drag-over');
    
    // Simulate drop
    fireEvent.drop(dropZone, {
      dataTransfer: {
        files: [file]
      }
    });
    
    await waitFor(() => {
      expect(mockDocumentStore.uploadDocument).toHaveBeenCalledWith(file);
    });
  });

  it('validates file types', async () => {
    const user = userEvent.setup();
    
    render(<FileUpload />);
    
    const invalidFile = new File(['test'], 'test.exe', { type: 'application/x-executable' });
    const input = screen.getByLabelText(/upload/i);
    
    await user.upload(input, invalidFile);
    
    expect(mockMessage.error).toHaveBeenCalledWith(
      expect.stringContaining('unsupported file type')
    );
    expect(mockDocumentStore.uploadDocument).not.toHaveBeenCalled();
  });

  it('validates file size', async () => {
    const user = userEvent.setup();
    
    render(<FileUpload />);
    
    // Create a large file (over 50MB)
    const largeFile = new File(['x'.repeat(51 * 1024 * 1024)], 'large.pdf', { 
      type: 'application/pdf' 
    });
    const input = screen.getByLabelText(/upload/i);
    
    await user.upload(input, largeFile);
    
    expect(mockMessage.error).toHaveBeenCalledWith(
      expect.stringContaining('file size exceeds')
    );
    expect(mockDocumentStore.uploadDocument).not.toHaveBeenCalled();
  });

  it('shows upload progress', () => {
    const progressStore = {
      ...mockDocumentStore,
      uploading: true,
      uploadProgress: { 'test.pdf': 45 }
    };
    jest.mocked(require('../../stores/documentStore').useDocumentStore).mockReturnValue(progressStore);
    
    render(<FileUpload />);
    
    expect(screen.getByText('45%')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('handles multiple file uploads', async () => {
    const user = userEvent.setup();
    mockDocumentStore.uploadDocument.mockResolvedValue({ id: '1', status: 'uploaded' });
    
    render(<FileUpload />);
    
    const files = [
      new File(['content1'], 'test1.pdf', { type: 'application/pdf' }),
      new File(['content2'], 'test2.txt', { type: 'text/plain' })
    ];
    const input = screen.getByLabelText(/upload/i);
    
    await user.upload(input, files);
    
    await waitFor(() => {
      expect(mockDocumentStore.uploadDocument).toHaveBeenCalledTimes(2);
    });
  });

  it('shows error state', () => {
    const errorStore = {
      ...mockDocumentStore,
      error: 'Upload failed: Network error'
    };
    jest.mocked(require('../../stores/documentStore').useDocumentStore).mockReturnValue(errorStore);
    
    render(<FileUpload />);
    
    expect(screen.getByText('Upload failed: Network error')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('clears error when retry is clicked', () => {
    const errorStore = {
      ...mockDocumentStore,
      error: 'Upload failed: Network error'
    };
    jest.mocked(require('../../stores/documentStore').useDocumentStore).mockReturnValue(errorStore);
    
    render(<FileUpload />);
    
    const retryButton = screen.getByRole('button', { name: /retry/i });
    fireEvent.click(retryButton);
    
    expect(mockDocumentStore.clearError).toHaveBeenCalled();
  });

  it('disables upload during processing', () => {
    const uploadingStore = {
      ...mockDocumentStore,
      uploading: true
    };
    jest.mocked(require('../../stores/documentStore').useDocumentStore).mockReturnValue(uploadingStore);
    
    render(<FileUpload />);
    
    const dropZone = screen.getByTestId('upload-dropzone');
    expect(dropZone).toHaveClass('disabled');
  });

  it('shows success message after upload', async () => {
    const user = userEvent.setup();
    mockDocumentStore.uploadDocument.mockResolvedValue({ 
      id: '1', 
      status: 'uploaded',
      original_name: 'test.pdf'
    });
    
    render(<FileUpload />);
    
    const file = new File(['test content'], 'test.pdf', { type: 'application/pdf' });
    const input = screen.getByLabelText(/upload/i);
    
    await user.upload(input, file);
    
    await waitFor(() => {
      expect(mockMessage.success).toHaveBeenCalledWith(
        expect.stringContaining('uploaded successfully')
      );
    });
  });

  it('handles upload cancellation', () => {
    const uploadingStore = {
      ...mockDocumentStore,
      uploading: true,
      uploadProgress: { 'test.pdf': 30 },
      cancelUpload: jest.fn()
    };
    jest.mocked(require('../../stores/documentStore').useDocumentStore).mockReturnValue(uploadingStore);
    
    render(<FileUpload />);
    
    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    fireEvent.click(cancelButton);
    
    expect(uploadingStore.cancelUpload).toHaveBeenCalled();
  });

  it('shows file preview during upload', () => {
    const uploadingStore = {
      ...mockDocumentStore,
      uploading: true,
      uploadProgress: { 'test.pdf': 30 },
      currentFile: {
        name: 'test.pdf',
        size: 1024000,
        type: 'application/pdf'
      }
    };
    jest.mocked(require('../../stores/documentStore').useDocumentStore).mockReturnValue(uploadingStore);
    
    render(<FileUpload />);
    
    expect(screen.getByText('test.pdf')).toBeInTheDocument();
    expect(screen.getByText('1.0 MB')).toBeInTheDocument();
  });
});