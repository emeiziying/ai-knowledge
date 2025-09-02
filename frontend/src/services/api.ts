import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from "axios";

// API configuration
const API_BASE_URL =
  (typeof import.meta !== "undefined" &&
    (import.meta.env?.VITE_API_BASE_URL as string)) ||
  "/api/v1";

// Create axios instance with default configuration
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 seconds timeout
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor to add authentication token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling and token refresh
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    return response;
  },
  async (error) => {
    // Handle 401 errors (unauthorized) - redirect to login
    if (error.response?.status === 401) {
      // Clear tokens and redirect to login
      localStorage.removeItem("access_token");
      window.location.href = "/auth/login";
      return Promise.reject(error);
    }

    // Handle other errors
    const errorMessage =
      error.response?.data?.error?.message ||
      error.message ||
      "An error occurred";

    // Log error for debugging
    console.error("API Error:", {
      status: error.response?.status,
      message: errorMessage,
      url: error.config?.url,
    });

    return Promise.reject({
      status: error.response?.status,
      message: errorMessage,
      data: error.response?.data,
    });
  }
);

// Generic API methods
export const api = {
  get: <T = any>(url: string, config?: AxiosRequestConfig): Promise<T> =>
    apiClient.get(url, config).then((response) => response.data),

  post: <T = any>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<T> =>
    apiClient.post(url, data, config).then((response) => response.data),

  put: <T = any>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<T> =>
    apiClient.put(url, data, config).then((response) => response.data),

  patch: <T = any>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<T> =>
    apiClient.patch(url, data, config).then((response) => response.data),

  delete: <T = any>(url: string, config?: AxiosRequestConfig): Promise<T> =>
    apiClient.delete(url, config).then((response) => response.data),

  // File upload method
  upload: <T = any>(
    url: string,
    formData: FormData,
    onUploadProgress?: (progress: number) => void
  ): Promise<T> =>
    apiClient
      .post(url, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
        onUploadProgress: (progressEvent) => {
          if (onUploadProgress && progressEvent.total) {
            const progress = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            );
            onUploadProgress(progress);
          }
        },
      })
      .then((response) => response.data),
};

export default apiClient;
