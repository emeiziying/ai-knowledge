import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

interface AuthRedirectProps {
  children: React.ReactNode;
}

/**
 * Component that redirects authenticated users away from auth pages
 * Used to prevent logged-in users from accessing login/register pages
 */
const AuthRedirect: React.FC<AuthRedirectProps> = ({ children }) => {
  const { isAuthenticated } = useAuth();

  // If user is already authenticated, redirect to dashboard
  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  // If not authenticated, show the auth page
  return <>{children}</>;
};

export default AuthRedirect;