import { ChatCompletionRequest, ChatCompletionResponse, APIResponse, FileUploadResponse, HealthStatus } from '@/types/api';

class APIClient {
  private baseURL: string;
  private apiKey: string;

  constructor() {
    // In production, this would be configured to use the Tailscale API server
    this.baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    this.apiKey = process.env.NEXT_PUBLIC_API_KEY || '';
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<APIResponse<T>> {
    try {
      const response = await fetch(`${this.baseURL}${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.apiKey}`,
          ...options.headers,
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        return {
          success: false,
          error: errorData.error || 'Request failed',
          message: errorData.message || `HTTP ${response.status}`,
        };
      }

      const data = await response.json();
      return {
        success: true,
        data,
      };
    } catch (error) {
      return {
        success: false,
        error: 'network_error',
        message: error instanceof Error ? error.message : 'Network error',
      };
    }
  }

  async chatCompletion(request: ChatCompletionRequest): Promise<APIResponse<ChatCompletionResponse>> {
    return this.request<ChatCompletionResponse>('/chat/completions', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async uploadFile(file: File): Promise<APIResponse<FileUploadResponse>> {
    const formData = new FormData();
    formData.append('file', file);

    return this.request<FileUploadResponse>('/files', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        // Don't set Content-Type for FormData
      },
      body: formData,
    });
  }

  async getFile(fileId: string): Promise<APIResponse<FileUploadResponse>> {
    return this.request<FileUploadResponse>(`/files/${fileId}`);
  }

  async deleteFile(fileId: string): Promise<APIResponse<void>> {
    return this.request<void>(`/files/${fileId}`, {
      method: 'DELETE',
    });
  }

  async getFiles(limit: number = 100, offset: number = 0): Promise<APIResponse<FileUploadResponse[]>> {
    return this.request<FileUploadResponse[]>(`/files?limit=${limit}&offset=${offset}`);
  }

  async getHealth(): Promise<APIResponse<HealthStatus>> {
    return this.request<HealthStatus>('/health');
  }
}

export const apiClient = new APIClient();