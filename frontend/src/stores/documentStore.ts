import { create } from 'zustand';
import { Document, PaginatedResponse } from '../types/api';
import { documentService } from '../services/documentService';

interface DocumentState {
  // State
  documents: Document[];
  currentDocument: Document | null;
  isLoading: boolean;
  isUploading: boolean;
  uploadProgress: number;
  error: string | null;
  pagination: {
    total: number;
    page: number;
    limit: number;
    pages: number;
  };
  searchQuery: string;

  // Actions
  fetchDocuments: (page?: number, limit?: number, search?: string) => Promise<void>;
  uploadDocument: (file: File) => Promise<Document>;
  deleteDocument: (documentId: string) => Promise<void>;
  getDocument: (documentId: string) => Promise<void>;
  searchDocuments: (query: string) => Promise<void>;
  clearError: () => void;
  setSearchQuery: (query: string) => void;
  clearCurrentDocument: () => void;
}

export const useDocumentStore = create<DocumentState>((set, get) => ({
  // Initial state
  documents: [],
  currentDocument: null,
  isLoading: false,
  isUploading: false,
  uploadProgress: 0,
  error: null,
  pagination: {
    total: 0,
    page: 1,
    limit: 20,
    pages: 0,
  },
  searchQuery: '',

  // Actions
  fetchDocuments: async (page = 1, limit = 20, search?: string) => {
    try {
      set({ isLoading: true, error: null });

      const response: PaginatedResponse<Document> = await documentService.getDocuments({
        page,
        limit,
        search: search || get().searchQuery,
      });

      set({
        documents: response.items,
        pagination: {
          total: response.total,
          page: response.page,
          limit: response.limit,
          pages: response.pages,
        },
        isLoading: false,
      });
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.message || 'Failed to fetch documents',
      });
    }
  },

  uploadDocument: async (file: File) => {
    try {
      set({ isUploading: true, uploadProgress: 0, error: null });

      const response = await documentService.uploadDocument(file, (progress) => {
        set({ uploadProgress: progress });
      });

      // Add new document to the list
      const currentDocuments = get().documents;
      set({
        documents: [response.document, ...currentDocuments],
        isUploading: false,
        uploadProgress: 0,
      });

      return response.document;
    } catch (error: any) {
      set({
        isUploading: false,
        uploadProgress: 0,
        error: error.message || 'Failed to upload document',
      });
      throw error;
    }
  },

  deleteDocument: async (documentId: string) => {
    try {
      set({ isLoading: true, error: null });

      await documentService.deleteDocument(documentId);

      // Remove document from the list
      const currentDocuments = get().documents;
      set({
        documents: currentDocuments.filter(doc => doc.id !== documentId),
        isLoading: false,
      });

      // Clear current document if it was deleted
      if (get().currentDocument?.id === documentId) {
        set({ currentDocument: null });
      }
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.message || 'Failed to delete document',
      });
      throw error;
    }
  },

  getDocument: async (documentId: string) => {
    try {
      set({ isLoading: true, error: null });

      const document = await documentService.getDocument(documentId);

      set({
        currentDocument: document,
        isLoading: false,
      });
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.message || 'Failed to fetch document',
      });
    }
  },

  searchDocuments: async (query: string) => {
    try {
      set({ isLoading: true, error: null, searchQuery: query });

      const response: PaginatedResponse<Document> = await documentService.searchDocuments(query);

      set({
        documents: response.items,
        pagination: {
          total: response.total,
          page: response.page,
          limit: response.limit,
          pages: response.pages,
        },
        isLoading: false,
      });
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.message || 'Failed to search documents',
      });
    }
  },

  clearError: () => {
    set({ error: null });
  },

  setSearchQuery: (query: string) => {
    set({ searchQuery: query });
  },

  clearCurrentDocument: () => {
    set({ currentDocument: null });
  },
}));