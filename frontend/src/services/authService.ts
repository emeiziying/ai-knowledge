import { api } from "./api";
import {
  AuthResponse,
  LoginRequest,
  RegisterRequest,
  User,
} from "../types/api";

export const authService = {
  // Login user
  login: async (credentials: LoginRequest): Promise<AuthResponse> => {
    const response = await api.post<AuthResponse>("/auth/login", credentials);

    // Store token in localStorage
    localStorage.setItem("access_token", response.access_token);

    return response;
  },

  // Register new user
  register: async (userData: RegisterRequest): Promise<AuthResponse> => {
    const response = await api.post<AuthResponse>("/auth/register", userData);

    // Store token in localStorage
    localStorage.setItem("access_token", response.access_token);

    return response;
  },

  // Logout user
  logout: async (): Promise<void> => {
    try {
      await api.post("/auth/logout");
    } catch (error) {
      // Even if logout fails on server, clear local tokens
      console.warn("Logout request failed:", error);
    } finally {
      localStorage.removeItem("access_token");
    }
  },

  // Get current user profile
  getCurrentUser: async (): Promise<User> => {
    return api.get<User>("/auth/me");
  },

  // Check if user is authenticated
  isAuthenticated: (): boolean => {
    return !!localStorage.getItem("access_token");
  },

  // Get stored access token
  getAccessToken: (): string | null => {
    return localStorage.getItem("access_token");
  },
};
