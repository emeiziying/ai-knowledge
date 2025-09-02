import React from 'react';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import ProtectedRoute from '../ProtectedRoute';

// Mock the auth store
const mockAuthStore = {
  isAuthenticated: true,
  user: {
    id: '1',
    username: 'testuser',
    email: 'test@example.com'
  },
  token: 'mock-jwt-token',
  loading: false,
  error: null
};

// Mock zustand store
jest.mock('../../../stores/authStore', () => ({
  useAuthStore: () => mockAuthStore
}));

// Mock react-router-dom
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
  Navigate: ({ to }: { to: string }) => <div data-testid="navigate-to">{to}</div>
}));

const TestComponent = () => <div data-testid="protected-content">Protected Content</div>;

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  );
};

describe('ProtectedRoute', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders children when user is authenticated', () => {
    renderWithRouter(
      <ProtectedRoute>
        <TestComponent />
      </ProtectedRoute>
    );
    
    expect(screen.getByTestId('protected-content')).toBeInTheDocument();
  });

  it('redirects to login when user is not authenticated', () => {
    const unauthenticatedStore = {
      ...mockAuthStore,
      isAuthenticated: false,
      user: null,
      token: null
    };
    jest.mocked(require('../../stores/authStore').useAuthStore).mockReturnValue(unauthenticatedStore);
    
    renderWithRouter(
      <ProtectedRoute>
        <TestComponent />
      </ProtectedRoute>
    );
    
    expect(screen.getByTestId('navigate-to')).toHaveTextContent('/login');
    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();
  });

  it('shows loading spinner when auth is loading', () => {
    const loadingStore = {
      ...mockAuthStore,
      loading: true
    };
    jest.mocked(require('../../stores/authStore').useAuthStore).mockReturnValue(loadingStore);
    
    renderWithRouter(
      <ProtectedRoute>
        <TestComponent />
      </ProtectedRoute>
    );
    
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();
  });

  it('redirects to custom path when specified', () => {
    const unauthenticatedStore = {
      ...mockAuthStore,
      isAuthenticated: false,
      user: null,
      token: null
    };
    jest.mocked(require('../../stores/authStore').useAuthStore).mockReturnValue(unauthenticatedStore);
    
    renderWithRouter(
      <ProtectedRoute redirectTo="/custom-login">
        <TestComponent />
      </ProtectedRoute>
    );
    
    expect(screen.getByTestId('navigate-to')).toHaveTextContent('/custom-login');
  });

  it('preserves current location for redirect after login', () => {
    const unauthenticatedStore = {
      ...mockAuthStore,
      isAuthenticated: false,
      user: null,
      token: null
    };
    jest.mocked(require('../../stores/authStore').useAuthStore).mockReturnValue(unauthenticatedStore);
    
    // Mock location
    const mockLocation = { pathname: '/documents', search: '?page=2' };
    jest.spyOn(require('react-router-dom'), 'useLocation').mockReturnValue(mockLocation);
    
    renderWithRouter(
      <ProtectedRoute>
        <TestComponent />
      </ProtectedRoute>
    );
    
    const navigateElement = screen.getByTestId('navigate-to');
    expect(navigateElement).toHaveTextContent('/login');
    // Should preserve the current location in state for redirect after login
  });

  it('handles role-based access control', () => {
    const adminStore = {
      ...mockAuthStore,
      user: {
        ...mockAuthStore.user,
        role: 'admin'
      }
    };
    jest.mocked(require('../../stores/authStore').useAuthStore).mockReturnValue(adminStore);
    
    renderWithRouter(
      <ProtectedRoute requiredRole="admin">
        <TestComponent />
      </ProtectedRoute>
    );
    
    expect(screen.getByTestId('protected-content')).toBeInTheDocument();
  });

  it('denies access when user lacks required role', () => {
    const userStore = {
      ...mockAuthStore,
      user: {
        ...mockAuthStore.user,
        role: 'user'
      }
    };
    jest.mocked(require('../../stores/authStore').useAuthStore).mockReturnValue(userStore);
    
    renderWithRouter(
      <ProtectedRoute requiredRole="admin">
        <TestComponent />
      </ProtectedRoute>
    );
    
    expect(screen.getByText(/access denied/i)).toBeInTheDocument();
    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();
  });

  it('handles multiple required roles', () => {
    const moderatorStore = {
      ...mockAuthStore,
      user: {
        ...mockAuthStore.user,
        role: 'moderator'
      }
    };
    jest.mocked(require('../../stores/authStore').useAuthStore).mockReturnValue(moderatorStore);
    
    renderWithRouter(
      <ProtectedRoute requiredRoles={['admin', 'moderator']}>
        <TestComponent />
      </ProtectedRoute>
    );
    
    expect(screen.getByTestId('protected-content')).toBeInTheDocument();
  });

  it('shows error message when authentication fails', () => {
    const errorStore = {
      ...mockAuthStore,
      isAuthenticated: false,
      error: 'Authentication failed',
      loading: false
    };
    jest.mocked(require('../../stores/authStore').useAuthStore).mockReturnValue(errorStore);
    
    renderWithRouter(
      <ProtectedRoute>
        <TestComponent />
      </ProtectedRoute>
    );
    
    expect(screen.getByText('Authentication failed')).toBeInTheDocument();
  });

  it('handles token expiration', () => {
    const expiredTokenStore = {
      ...mockAuthStore,
      isAuthenticated: false,
      token: null,
      error: 'Token expired'
    };
    jest.mocked(require('../../stores/authStore').useAuthStore).mockReturnValue(expiredTokenStore);
    
    renderWithRouter(
      <ProtectedRoute>
        <TestComponent />
      </ProtectedRoute>
    );
    
    expect(screen.getByTestId('navigate-to')).toHaveTextContent('/login');
  });
});