import { createBrowserRouter, Navigate } from 'react-router-dom';
import { MainLayout, ProtectedRoute, AuthRedirect } from '../components';
import { Dashboard, Documents, Chat, Settings, Login, Register } from '../pages';

export const router = createBrowserRouter([
  // Authentication routes (public)
  {
    path: '/auth/login',
    element: (
      <AuthRedirect>
        <Login />
      </AuthRedirect>
    ),
  },
  {
    path: '/auth/register',
    element: (
      <AuthRedirect>
        <Register />
      </AuthRedirect>
    ),
  },
  
  // Protected routes
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <MainLayout>
          <Dashboard />
        </MainLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: '/documents',
    element: (
      <ProtectedRoute>
        <MainLayout>
          <Documents />
        </MainLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: '/chat',
    element: (
      <ProtectedRoute>
        <MainLayout>
          <Chat />
        </MainLayout>
      </ProtectedRoute>
    ),
  },
  {
    path: '/settings',
    element: (
      <ProtectedRoute>
        <MainLayout>
          <Settings />
        </MainLayout>
      </ProtectedRoute>
    ),
  },
  
  // Catch all route - redirect to dashboard
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
]);

export default router;