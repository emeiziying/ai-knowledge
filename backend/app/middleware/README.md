# Middleware Documentation

This directory contains all middleware components for the AI Knowledge Base FastAPI application.

## Middleware Components

### 1. CORS Middleware (`cors.py`)
- Configures Cross-Origin Resource Sharing
- Allows frontend applications to communicate with the API
- Supports development and production origins
- Configurable allowed methods and headers

### 2. Logging Middleware (`logging.py`)
- Logs all HTTP requests and responses
- Generates unique request IDs for tracking
- Measures request processing time
- Adds request ID and processing time to response headers
- Configurable logging format and levels

### 3. Error Handler Middleware (`error_handler.py`)
- Standardized error response format
- Custom API error handling
- HTTP exception handling
- Request validation error handling
- General exception handling with logging
- Request ID tracking in error responses

### 4. Security Middleware (`security.py`)
- Security headers (X-Content-Type-Options, X-Frame-Options, etc.)
- Content Security Policy
- Trusted host middleware
- Session middleware for CSRF protection

## Middleware Order

The middleware is applied in the following order (important for proper functionality):

1. Security Middleware (TrustedHost, Session)
2. CORS Middleware
3. Security Headers
4. Logging Middleware

## Configuration

Middleware configuration is handled through the `config.py` settings:

- `frontend_url`: Frontend application URL for CORS
- `allowed_hosts`: List of allowed hosts
- `secret_key`: Secret key for session middleware
- `debug`: Enable/disable debug features

## Error Response Format

All errors follow a standardized format:

```json
{
  "error": {
    "message": "Error description",
    "code": "ERROR_CODE",
    "timestamp": "2024-01-01T00:00:00Z",
    "details": "Additional error details",
    "request_id": "uuid-request-id"
  }
}
```

## Request/Response Headers

### Added by Logging Middleware:
- `X-Request-ID`: Unique identifier for request tracking
- `X-Process-Time`: Request processing time in seconds

### Added by Security Middleware:
- `X-Content-Type-Options`: nosniff
- `X-Frame-Options`: DENY
- `X-XSS-Protection`: 1; mode=block
- `Referrer-Policy`: strict-origin-when-cross-origin
- `Content-Security-Policy`: Basic CSP rules