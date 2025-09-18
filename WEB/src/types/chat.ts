export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  artifacts?: Artifact[];
}

export interface Artifact {
  id: string;
  type: 'code' | 'diagram' | 'document';
  content: string;
  language?: string;
  downloadable: boolean;
  title?: string;
  executable?: boolean;
  executionEnvironment?: 'javascript' | 'python' | 'html' | 'css';
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: Date;
  updatedAt: Date;
}

export interface ModelConfig {
  name: string;
  displayName: string;
  description: string;
  capabilities: string[];
}

export interface ToolConfig {
  name: string;
  enabled: boolean;
  description: string;
}

export interface ChatSettings {
  model: string;
  webSearch: boolean;
  tools: ToolConfig[];
  maxTokens?: number;
  temperature?: number;
}

export interface FileUpload {
  id: string;
  filename: string;
  contentType: string;
  size: number;
  processed: boolean;
  ragIngested: boolean;
  uploadedAt: Date;
}

export interface StudiosFile extends FileUpload {
  preview?: string;
  metadata?: Record<string, unknown>;
}