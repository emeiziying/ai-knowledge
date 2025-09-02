import { create } from 'zustand';
import { Conversation, Message } from '../types/api';
import { chatService } from '../services/chatService';

interface ChatState {
  // State
  conversations: Conversation[];
  currentConversation: Conversation | null;
  messages: Message[];
  isLoading: boolean;
  isSending: boolean;
  error: string | null;
  messagesLoading: boolean;

  // Actions
  fetchConversations: () => Promise<void>;
  createConversation: (title?: string) => Promise<Conversation>;
  selectConversation: (conversationId: string) => Promise<void>;
  sendMessage: (message: string, conversationId?: string) => Promise<void>;
  fetchMessages: (conversationId: string) => Promise<void>;
  deleteConversation: (conversationId: string) => Promise<void>;
  updateConversationTitle: (conversationId: string, title: string) => Promise<void>;
  clearError: () => void;
  clearCurrentConversation: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  // Initial state
  conversations: [],
  currentConversation: null,
  messages: [],
  isLoading: false,
  isSending: false,
  error: null,
  messagesLoading: false,

  // Actions
  fetchConversations: async () => {
    try {
      set({ isLoading: true, error: null });

      const conversations = await chatService.getConversations();

      set({
        conversations,
        isLoading: false,
      });
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.message || 'Failed to fetch conversations',
      });
    }
  },

  createConversation: async (title?: string) => {
    try {
      set({ isLoading: true, error: null });

      const conversation = await chatService.createConversation(title);

      // Add new conversation to the list
      const currentConversations = get().conversations;
      set({
        conversations: [conversation, ...currentConversations],
        currentConversation: conversation,
        messages: [],
        isLoading: false,
      });

      return conversation;
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.message || 'Failed to create conversation',
      });
      throw error;
    }
  },

  selectConversation: async (conversationId: string) => {
    try {
      set({ messagesLoading: true, error: null });

      // Find conversation in current list or fetch it
      let conversation = get().conversations.find(c => c.id === conversationId);
      
      if (!conversation) {
        conversation = await chatService.getConversation(conversationId);
      }

      // Fetch messages for this conversation
      const messagesResponse = await chatService.getMessages(conversationId);

      set({
        currentConversation: conversation,
        messages: messagesResponse.items,
        messagesLoading: false,
      });
    } catch (error: any) {
      set({
        messagesLoading: false,
        error: error.message || 'Failed to load conversation',
      });
    }
  },

  sendMessage: async (message: string, conversationId?: string) => {
    try {
      set({ isSending: true, error: null });

      const response = await chatService.sendMessage({
        message,
        conversation_id: conversationId,
      });

      // Update current conversation if it was created
      if (!conversationId) {
        set({ currentConversation: response.conversation });
        
        // Add to conversations list if new
        const conversations = get().conversations;
        const existingIndex = conversations.findIndex(c => c.id === response.conversation.id);
        if (existingIndex === -1) {
          set({ conversations: [response.conversation, ...conversations] });
        }
      }

      // Add the new message to the messages list
      const currentMessages = get().messages;
      set({
        messages: [...currentMessages, response.message],
        isSending: false,
      });
    } catch (error: any) {
      set({
        isSending: false,
        error: error.message || 'Failed to send message',
      });
      throw error;
    }
  },

  fetchMessages: async (conversationId: string) => {
    try {
      set({ messagesLoading: true, error: null });

      const response = await chatService.getMessages(conversationId);

      set({
        messages: response.items,
        messagesLoading: false,
      });
    } catch (error: any) {
      set({
        messagesLoading: false,
        error: error.message || 'Failed to fetch messages',
      });
    }
  },

  deleteConversation: async (conversationId: string) => {
    try {
      set({ isLoading: true, error: null });

      await chatService.deleteConversation(conversationId);

      // Remove conversation from the list
      const currentConversations = get().conversations;
      set({
        conversations: currentConversations.filter(c => c.id !== conversationId),
        isLoading: false,
      });

      // Clear current conversation if it was deleted
      if (get().currentConversation?.id === conversationId) {
        set({ currentConversation: null, messages: [] });
      }
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.message || 'Failed to delete conversation',
      });
      throw error;
    }
  },

  updateConversationTitle: async (conversationId: string, title: string) => {
    try {
      const updatedConversation = await chatService.updateConversation(conversationId, title);

      // Update conversation in the list
      const conversations = get().conversations;
      const updatedConversations = conversations.map(c => 
        c.id === conversationId ? updatedConversation : c
      );

      set({ conversations: updatedConversations });

      // Update current conversation if it's the same one
      if (get().currentConversation?.id === conversationId) {
        set({ currentConversation: updatedConversation });
      }
    } catch (error: any) {
      set({
        error: error.message || 'Failed to update conversation title',
      });
      throw error;
    }
  },

  clearError: () => {
    set({ error: null });
  },

  clearCurrentConversation: () => {
    set({ currentConversation: null, messages: [] });
  },
}));