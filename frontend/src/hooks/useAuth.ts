import { useEffect, useRef } from "react";
import { useAuthStore } from "../stores/authStore";

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

  const hasAttemptedFetch = useRef(false);

  // Auto-fetch user data on mount if authenticated (only once)
  useEffect(() => {
    if (isAuthenticated && !user && !isLoading && !hasAttemptedFetch.current) {
      hasAttemptedFetch.current = true;
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
