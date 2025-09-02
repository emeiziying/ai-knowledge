import React, { useEffect } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Spin } from 'antd';
import { useAuth } from '../../hooks/useAuth';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, isLoading, getCurrentUser } = useAuth();
  const location = useLocation();

  useEffect(() => {
    // Try to get current user if we think we're authenticated but don't have user data
    if (isAuthenticated && !isLoading) {
      getCurrentUser();
    }
  }, [isAuthenticated, isLoading, getCurrentUser]);

  // Show loading spinner while checking authentication
  if (isLoading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh'
      }}>
        <Spin size="large" />
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return (
      <Navigate 
        to="/auth/login" 
        state={{ from: location }} 
        replace 
      />
    );
  }

  // Render protected content
  return <>{children}</>;
};

export default ProtectedRoute;