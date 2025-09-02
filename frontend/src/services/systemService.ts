import { api } from './api';
import { SystemStatus } from '../types/api';

export const systemService = {
  // Get system health status
  getHealthStatus: async (): Promise<SystemStatus> => {
    return api.get<SystemStatus>('/health');
  },

  // Get system status
  getSystemStatus: async (): Promise<SystemStatus> => {
    return api.get<SystemStatus>('/status');
  },
};