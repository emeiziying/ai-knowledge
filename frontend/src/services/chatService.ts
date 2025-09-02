import { api } from './api';
import { Conversation, Message, ChatRequest, ChatResponse, PaginatedResponse } from '../types/api';

export const chatService = {
  // Create new conversation
  createConversation: async (title?: string): Promise<Conversation> => {
    return api.post<Conversation>('/chat/conversations', { title });
  },

  // Get conversations list
  getConversations: async (): Promise<Conversation[]> => {
    return api.get<Conversation[]>('/chat/conversations');
  },

  // Get conversation by ID
  getConversation: async (conversationId: string): Promise<Conversation> => {
    return api.get<Conversation>(`/chat/conversations/${conversationId}`);
  },

  // Send message in conversation
  sendMessage: async (request: ChatRequest): Promise<ChatResponse> => {
    const url = request.conversation_id 
      ? `/chat/conversations/${request.conversation_id}/messages`
      : '/chat/conversations/messages';
    
    return api.post<ChatResponse>(url, { message: request.message });
  },

  // Get conversation messages
  getMessages: async (conversationId: string, page?: number, limit?: number): Promise<PaginatedResponse<Message>> => {
    const params = new URLSearchParams();
    if (page) params.append('page', page.toString());
    if (limit) params.append('limit', limit.toString());

    const url = `/chat/conversations/${conversationId}/messages${params.toString() ? `?${params.toString()}` : ''}`;
    return api.get<PaginatedResponse<Message>>(url);
  },

  // Delete conversation
  deleteConversation: async (conversationId: string): Promise<void> => {
    return api.delete(`/chat/conversations/${conversationId}`);
  },

  // Update conversation title
  updateConversation: async (conversationId: string, title: string): Promise<Conversation> => {
    return api.patch<Conversation>(`/chat/conversations/${conversationId}`, { title });
  },
};