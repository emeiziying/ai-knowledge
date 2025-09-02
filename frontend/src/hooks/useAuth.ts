import { useEffect } from 'react';
import { useAuthStore } from '../stores/authStore';

/**
 * Custom hook for authentication functionality
 * Provides easy access to auth state and actions
 */
export const useAuth = () => {
  const {
    user,
    isAuthenticated,
    isLoading,
    error,
    login,
    register,
    logout,
    getCurrentUser,
    clearError,
  } = useAuthStore();

  // Auto-fetch user data on mount if authenticated
  useEffect(() => {
    if (isAuthenticated && !user && !isLoading) {
      getCurrentUser();
    }
  }, [isAuthenticated, user, isLoading, getCurrentUser]);

  return {
    // State
    user,
    isAuthenticated,
    isLoading,
    error,
    
    // Actions
    login,
    register,
    logout,
    getCurrentUser,
    clearError,
  };
};