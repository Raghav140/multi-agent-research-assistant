/** API client for backend communication */

import type {
  ResearchRequest,
  ResearchResponse,
  SystemHealth,
  ProvidersHealthResponse,
  MetricsSummary,
  MemoryHistoryResponse,
} from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (() => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('apiUrl') || 'http://127.0.0.1:8000';
  }
  return 'http://127.0.0.1:8000';
})();
const DEFAULT_TIMEOUT = 120000; // 120 seconds for research requests

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    timeoutMs: number = 30000
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorText = await response.text().catch(() => 'Unknown error');
        const error = new Error(`HTTP ${response.status}: ${errorText}`);
        error.cause = { status: response.status, text: errorText };
        throw error;
      }

      return response.json();
    } catch (error) {
      clearTimeout(timeoutId);

      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          const timeoutError = new Error(`Request timeout after ${timeoutMs}ms`);
          timeoutError.cause = error;
          throw timeoutError;
        }
        throw error;
      }

      const unknownError = new Error('Unknown error occurred');
      unknownError.cause = error;
      throw unknownError;
    }
  }

  async research(request: ResearchRequest): Promise<ResearchResponse> {
    return this.request<ResearchResponse>('/api/v1/research', {
      method: 'POST',
      body: JSON.stringify(request),
    }, DEFAULT_TIMEOUT);
  }

  async getSystemHealth(): Promise<SystemHealth> {
    return this.request<SystemHealth>('/api/v1/system/health');
  }

  async getProvidersHealth(): Promise<ProvidersHealthResponse> {
    return this.request<ProvidersHealthResponse>('/api/v1/system/providers/health');
  }

  async getMetricsSummary(): Promise<MetricsSummary> {
    return this.request<MetricsSummary>('/api/v1/system/metrics/summary');
  }

  async getMemoryHistory(limit: number = 20): Promise<MemoryHistoryResponse> {
    return this.request<MemoryHistoryResponse>(`/api/v1/system/memory/history?limit=${limit}`);
  }

  async getCacheStats(): Promise<Record<string, { hits: number; misses: number }>> {
    return this.request<Record<string, { hits: number; misses: number }>>('/api/v1/system/cache/stats');
  }
}

export const apiClient = new ApiClient();
