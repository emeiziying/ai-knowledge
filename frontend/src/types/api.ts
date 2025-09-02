// User types
export interface User {
  id: string;
  username: string;
  email: string;
  created_at: string;
  updated_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

// Document types
export interface Document {
  id: string;
  user_id: string;
  filename: string;
  original_name: string;
  file_size: number;
  mime_type: string;
  file_path: string;
  status: 'processing' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
}

export interface DocumentUploadResponse {
  document: Document;
  message: string;
}

// Chat types
export interface Conversation {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  metadata?: {
    sources?: Array<{
      document_id: string;
      document_name: string;
      chunk_index: number;
      relevance_score: number;
    }>;
  };
  created_at: string;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
}

export interface ChatResponse {
  message: Message;
  conversation: Conversation;
}

// API Error types
export interface ApiError {
  code: string;
  message: string;
  details?: string;
  timestamp: string;
}

export interface ApiErrorResponse {
  error: ApiError;
}

// Pagination types
export interface PaginationParams {
  page?: number;
  limit?: number;
  search?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

// System status types
export interface SystemStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  services: {
    database: boolean;
    vector_db: boolean;
    ai_service: boolean;
    file_storage: boolean;
  };
  timestamp: string;
}