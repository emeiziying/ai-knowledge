import { message } from 'antd';

export interface ApiError {
  status?: number;
  message: string;
  data?: any;
}

/**
 * Centralized error handler for API errors
 */
export const handleApiError = (error: ApiError, showNotification = true) => {
  let errorMessage = 'An unexpected error occurred';

  if (error.message) {
    errorMessage = error.message;
  } else if (error.status) {
    switch (error.status) {
      case 400:
        errorMessage = 'Bad request. Please check your input.';
        break;
      case 401:
        errorMessage = 'Unauthorized. Please log in again.';
        break;
      case 403:
        errorMessage = 'Access denied. You do not have permission.';
        break;
      case 404:
        errorMessage = 'Resource not found.';
        break;
      case 413:
        errorMessage = 'File too large. Please choose a smaller file.';
        break;
      case 500:
        errorMessage = 'Server error. Please try again later.';
        break;
      case 502:
        errorMessage = 'AI service unavailable. Please try again later.';
        break;
      case 503:
        errorMessage = 'Service temporarily unavailable.';
        break;
      default:
        errorMessage = `Error ${error.status}: ${error.message || 'Unknown error'}`;
    }
  }

  if (showNotification) {
    message.error(errorMessage);
  }

  return errorMessage;
};

/**
 * Success message handler
 */
export const handleApiSuccess = (successMessage: string, showNotification = true) => {
  if (showNotification) {
    message.success(successMessage);
  }
  return successMessage;
};