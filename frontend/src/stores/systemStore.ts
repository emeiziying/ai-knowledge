import { create } from 'zustand';
import { SystemStatus } from '../types/api';
import { systemService } from '../services/systemService';

interface SystemState {
  // State
  status: SystemStatus | null;
  isLoading: boolean;
  error: string | null;
  lastChecked: Date | null;

  // Actions
  checkSystemStatus: () => Promise<void>;
  checkHealthStatus: () => Promise<void>;
  clearError: () => void;
}

export const useSystemStore = create<SystemState>((set) => ({
  // Initial state
  status: null,
  isLoading: false,
  error: null,
  lastChecked: null,

  // Actions
  checkSystemStatus: async () => {
    try {
      set({ isLoading: true, error: null });

      const status = await systemService.getSystemStatus();

      set({
        status,
        isLoading: false,
        lastChecked: new Date(),
      });
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.message || 'Failed to check system status',
      });
    }
  },

  checkHealthStatus: async () => {
    try {
      set({ isLoading: true, error: null });

      const status = await systemService.getHealthStatus();

      set({
        status,
        isLoading: false,
        lastChecked: new Date(),
      });
    } catch (error: any) {
      set({
        isLoading: false,
        error: error.message || 'Failed to check health status',
      });
    }
  },

  clearError: () => {
    set({ error: null });
  },
}));