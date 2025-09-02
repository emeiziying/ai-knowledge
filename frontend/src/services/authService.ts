import { api } from './api';
import { AuthResponse, LoginRequest, RegisterRequest, User } from '../types/api';

// Token refresh interval (in milliseconds) - refresh 5 minutes before expiry
const TOKEN_REFRESH_INTERVAL = 25 * 60 * 1000; // 25 minutes
let refreshTimer: NodeJS.Timeout | null = null;

export const authService = {
  // Login user
  login: async (credentials: LoginRequest): Promise<AuthResponse> => {
    const formData = new FormData();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);

    const response = await api.post<AuthResponse>('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });

    // Store tokens in localStorage
    localStorage.setItem('access_token', response.access_token);
    localStorage.setItem('refresh_token', response.refresh_token);

    // Start automatic token refresh
    authService.startTokenRefresh();

    return response;
  },

  // Register new user
  register: async (userData: RegisterRequest): Promise<AuthResponse> => {
    const response = await api.post<AuthResponse>('/auth/register', userData);

    // Store tokens in localStorage
    localStorage.setItem('access_token', response.access_token);
    localStorage.setItem('refresh_token', response.refresh_token);

    // Start automatic token refresh
    authService.startTokenRefresh();

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
      localStorage.removeItem('refresh_token');
      authService.stopTokenRefresh();
    }
  },

  // Get current user profile
  getCurrentUser: async (): Promise<User> => {
    return api.get<User>('/auth/me');
  },

  // Refresh access token
  refreshToken: async (): Promise<AuthResponse> => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await api.post<AuthResponse>('/auth/refresh', {
      refresh_token: refreshToken,
    });

    // Update stored tokens
    localStorage.setItem('access_token', response.access_token);
    localStorage.setItem('refresh_token', response.refresh_token);

    return response;
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