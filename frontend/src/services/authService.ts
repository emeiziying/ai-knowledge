import { api } from './api';
import { AuthResponse, LoginRequest, RegisterRequest, User } from '../types/api';



export const authService = {
  // Login user
  login: async (credentials: LoginRequest): Promise<AuthResponse> => {
    const response = await api.post<AuthResponse>('/auth/login', credentials);

    // Store token in localStorage
    localStorage.setItem('access_token', response.access_token);

    return response;
  },

  // Register new user
  register: async (userData: RegisterRequest): Promise<AuthResponse> => {
    const response = await api.post<AuthResponse>('/auth/register', userData);

    // Store token in localStorage
    localStorage.setItem('access_token', response.access_token);

    return response;
  },

  // Logout user
  logout: async (): Promise<void> => {
    try {
      await api.post('/auth/logout');
    } catch (error) {
      // Even if logout fails on server, clear local tokens
      console.warn('Logout request failed:', error);
    } finally {
      localStorage.removeItem('access_token');
    }
  },

  // Get current user profile
  getCurrentUser: async (): Promise<User> => {
    return api.get<User>('/auth/me');
  },



  // Check if user is authenticated
  isAuthenticated: (): boolean => {
    return !!localStorage.getItem('access_token');
  },

  // Get stored access token
  getAccessToken: (): string | null => {
    return localStorage.getItem('access_token');
  },

  // Start automatic token refresh
  startTokenRefresh: (): void => {
    // Clear any existing timer
    authService.stopTokenRefresh();
    
    // Set up automatic refresh
    refreshTimer = setInterval(async () => {
      try {
        if (authService.isAuthenticated()) {
          await authService.refreshToken();
        } else {
          authService.stopTokenRefresh();
        }
      } catch (error) {
        console.warn('Automatic token refresh failed:', error);
        // Stop refresh timer if refresh fails
        authService.stopTokenRefresh();
      }
    }, TOKEN_REFRESH_INTERVAL);
  },

  // Stop automatic token refresh
  stopTokenRefresh: (): void => {
    if (refreshTimer) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  },

  // Initialize auth service (call on app startup)
  initialize: (): void => {
    if (authService.isAuthenticated()) {
      authService.startTokenRefresh();
    }
  },
};