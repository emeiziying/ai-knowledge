# Authentication Components

This directory contains the authentication-related components for the AI Knowledge Base frontend.

## Components

### ProtectedRoute
- Protects routes that require authentication
- Redirects unauthenticated users to login page
- Shows loading spinner while checking authentication status
- Automatically fetches user data if authenticated but user data is missing

### AuthRedirect
- Redirects authenticated users away from auth pages (login/register)
- Prevents logged-in users from accessing login/register pages
- Automatically redirects to dashboard if user is already authenticated

## Features Implemented

### 1. Login and Register Pages
- **Login Page** (`/auth/login`): User authentication with username/password
- **Register Page** (`/auth/register`): New user registration with username, email, password
- Form validation with proper error messages
- Responsive design with modern UI using Ant Design
- Automatic redirect after successful authentication

### 2. JWT Token Management
- Automatic token storage in localStorage
- Token refresh mechanism with 25-minute intervals
- Automatic token refresh on API 401 errors
- Proper token cleanup on logout

### 3. Route Guards and Permission Control
- **ProtectedRoute**: Protects authenticated routes
- **AuthRedirect**: Prevents access to auth pages when logged in
- Automatic redirection based on authentication status
- Preserves intended destination after login

### 4. User Information Display and Logout
- User information display in main layout header
- Dropdown menu with user options
- Logout functionality with proper cleanup
- Success/error messages for user actions

## Usage

### Protecting Routes
```tsx
import { ProtectedRoute } from '../components/Auth';

<ProtectedRoute>
  <YourProtectedComponent />
</ProtectedRoute>
```

### Auth Pages
```tsx
import { AuthRedirect } from '../components/Auth';

<AuthRedirect>
  <LoginOrRegisterComponent />
</AuthRedirect>
```

### Using Authentication Hook
```tsx
import { useAuth } from '../hooks/useAuth';

const MyComponent = () => {
  const { user, isAuthenticated, login, logout } = useAuth();
  
  // Use authentication state and methods
};
```

## Security Features

- Automatic token refresh to maintain session
- Secure token storage and cleanup
- Protection against accessing auth pages when logged in
- Proper error handling for authentication failures
- Automatic logout on token refresh failure