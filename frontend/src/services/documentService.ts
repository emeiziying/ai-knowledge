import { api } from './api';
import { Document, DocumentUploadResponse, PaginatedResponse, PaginationParams } from '../types/api';

export const documentService = {
  // Upload document
  uploadDocument: async (
    file: File,
    onUploadProgress?: (progress: number) => void
  ): Promise<DocumentUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    return api.upload<DocumentUploadResponse>('/documents/upload', formData, onUploadProgress);
  },

  // Get documents list with pagination and search
  getDocuments: async (params?: PaginationParams): Promise<PaginatedResponse<Document>> => {
    const queryParams = new URLSearchParams();
    
    if (params?.page) queryParams.append('page', params.page.toString());
    if (params?.limit) queryParams.append('limit', params.limit.toString());
    if (params?.search) queryParams.append('search', params.search);

    const url = `/documents${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;
    return api.get<PaginatedResponse<Document>>(url);
  },

  // Get document by ID
  getDocument: async (documentId: string): Promise<Document> => {
    return api.get<Document>(`/documents/${documentId}`);
  },

  // Delete document
  deleteDocument: async (documentId: string): Promise<void> => {
    return api.delete(`/documents/${documentId}`);
  },

  // Search documents by content
  searchDocuments: async (query: string, limit?: number): Promise<PaginatedResponse<Document>> => {
    const params = new URLSearchParams({ search: query });
    if (limit) params.append('limit', limit.toString());

    return api.get<PaginatedResponse<Document>>(`/documents/search?${params.toString()}`);
  },

  // Get document processing status
  getProcessingStatus: async (documentId: string): Promise<{ status: string; progress?: number }> => {
    return api.get(`/documents/${documentId}/status`);
  },
};