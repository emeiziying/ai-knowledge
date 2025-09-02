import { createBrowserRouter, Navigate } from 'react-router-dom';
import { MainLayout } from '../components';
import { Dashboard, Documents, Chat, Settings } from '../pages';

export const router = createBrowserRouter([
  {
    path: '/',
    element: (
      <MainLayout>
        <Dashboard />
      </MainLayout>
    ),
  },
  {
    path: '/documents',
    element: (
      <MainLayout>
        <Documents />
      </MainLayout>
    ),
  },
  {
    path: '/chat',
    element: (
      <MainLayout>
        <Chat />
      </MainLayout>
    ),
  },
  {
    path: '/settings',
    element: (
      <MainLayout>
        <Settings />
      </MainLayout>
    ),
  },
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
]);

export default router;