import { useState, useCallback, useEffect } from 'react';
import { AIService, getAIService, configureAIService, MelanieAPIConfig } from '../services/aiService';
import { AIThreadSummary, AIDraftReply, AIAnalysisResult } from '../components/email/AIFeatures';
import { EmailMessage } from '../types/imap';

export interface AIFeaturesConfig {
  apiUrl?: string;
  apiKey?: string;
  timeout?: number;
  enableRAG?: boolean;
}

export interface AIFeaturesState {
  isConfigured: boolean;
  isConnected: boolean;
  lastError: string | null;
  isLoading: boolean;
}

export interface UseAIFeaturesReturn {
  state: AIFeaturesState;
  configure: (config: AIFeaturesConfig) => Promise<void>;
  testConnection: () => Promise<boolean>;
  summarizeThread: (threadId: string, messages: EmailMessage[]) => Promise<AIThreadSummary>;
  draftReply: (threadId: string, messages: EmailMessage[], context?: string) => Promise<AIDraftReply>;
  analyzeThread: (threadId: string, messages: EmailMessage[]) => Promise<AIAnalysisResult>;
  ingestEmailThread: (threadId: string, messages: EmailMessage[]) => Promise<void>;
  getRelevantContext: (query: string, accountId: string) => Promise<string[]>;
  clearError: () => void;
}

/**
 * Hook for managing AI features in the email client
 */
export function useAIFeatures(): UseAIFeaturesReturn {
  const [state, setState] = useState<AIFeaturesState>({
    isConfigured: false,
    isConnected: false,
    lastError: null,
    isLoading: false
  });

  const [aiService, setAIService] = useState<AIService | null>(null);

  // Initialize with default configuration
  useEffect(() => {
    const defaultConfig: MelanieAPIConfig = {
      baseUrl: 'http://localhost:8000',
      apiKey: 'mel_demo_key', // This should be configured by the user
      timeout: 30000
    };

    try {
      configureAIService(defaultConfig);
      const service = getAIService();
      setAIService(service);
      
      setState(prev => ({
        ...prev,
        isConfigured: true
      }));
    } catch (error) {
      setState(prev => ({
        ...prev,
        lastError: error instanceof Error ? error.message : 'Failed to initialize AI service'
      }));
    }
  }, []);

  const configure = useCallback(async (config: AIFeaturesConfig): Promise<void> => {
    setState(prev => ({ ...prev, isLoading: true, lastError: null }));

    try {
      const melanieConfig: MelanieAPIConfig = {
        baseUrl: config.apiUrl || 'http://localhost:8000',
        apiKey: config.apiKey || 'mel_demo_key',
        timeout: config.timeout || 30000
      };

      configureAIService(melanieConfig);
      const service = getAIService();
      setAIService(service);

      // Test the connection
      const connected = await service.testConnection();

      setState(prev => ({
        ...prev,
        isConfigured: true,
        isConnected: connected,
        isLoading: false,
        lastError: connected ? null : 'Failed to connect to AI service'
      }));
    } catch (error) {
      setState(prev => ({
        ...prev,
        isConfigured: false,
        isConnected: false,
        isLoading: false,
        lastError: error instanceof Error ? error.message : 'Configuration failed'
      }));
    }
  }, []);

  const testConnection = useCallback(async (): Promise<boolean> => {
    if (!aiService) {
      setState(prev => ({ ...prev, lastError: 'AI service not configured' }));
      return false;
    }

    setState(prev => ({ ...prev, isLoading: true, lastError: null }));

    try {
      const connected = await aiService.testConnection();
      
      setState(prev => ({
        ...prev,
        isConnected: connected,
        isLoading: false,
        lastError: connected ? null : 'Connection test failed'
      }));

      return connected;
    } catch (error) {
      setState(prev => ({
        ...prev,
        isConnected: false,
        isLoading: false,
        lastError: error instanceof Error ? error.message : 'Connection test failed'
      }));
      return false;
    }
  }, [aiService]);

  const summarizeThread = useCallback(async (
    threadId: string, 
    messages: EmailMessage[]
  ): Promise<AIThreadSummary> => {
    if (!aiService) {
      throw new Error('AI service not configured');
    }

    setState(prev => ({ ...prev, isLoading: true, lastError: null }));

    try {
      const summary = await aiService.summarizeThread(threadId, messages);
      
      setState(prev => ({ ...prev, isLoading: false }));
      return summary;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to summarize thread';
      setState(prev => ({
        ...prev,
        isLoading: false,
        lastError: errorMessage
      }));
      throw error;
    }
  }, [aiService]);

  const draftReply = useCallback(async (
    threadId: string, 
    messages: EmailMessage[], 
    context?: string
  ): Promise<AIDraftReply> => {
    if (!aiService) {
      throw new Error('AI service not configured');
    }

    setState(prev => ({ ...prev, isLoading: true, lastError: null }));

    try {
      const draft = await aiService.draftReply(threadId, messages, context);
      
      setState(prev => ({ ...prev, isLoading: false }));
      return draft;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to draft reply';
      setState(prev => ({
        ...prev,
        isLoading: false,
        lastError: errorMessage
      }));
      throw error;
    }
  }, [aiService]);

  const analyzeThread = useCallback(async (
    threadId: string, 
    messages: EmailMessage[]
  ): Promise<AIAnalysisResult> => {
    if (!aiService) {
      throw new Error('AI service not configured');
    }

    setState(prev => ({ ...prev, isLoading: true, lastError: null }));

    try {
      const analysis = await aiService.analyzeThread(threadId, messages);
      
      setState(prev => ({ ...prev, isLoading: false }));
      return analysis;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to analyze thread';
      setState(prev => ({
        ...prev,
        isLoading: false,
        lastError: errorMessage
      }));
      throw error;
    }
  }, [aiService]);

  const ingestEmailThread = useCallback(async (
    threadId: string, 
    messages: EmailMessage[]
  ): Promise<void> => {
    if (!aiService) {
      console.warn('AI service not configured, skipping RAG ingestion');
      return;
    }

    try {
      await aiService.ingestEmailThread(threadId, messages);
    } catch (error) {
      console.warn('Failed to ingest email thread into RAG:', error);
      // Don't throw error as this is a background operation
    }
  }, [aiService]);

  const getRelevantContext = useCallback(async (
    query: string, 
    accountId: string
  ): Promise<string[]> => {
    if (!aiService) {
      return [];
    }

    try {
      return await aiService.getRelevantEmailContext(query, accountId);
    } catch (error) {
      console.warn('Failed to get relevant context:', error);
      return [];
    }
  }, [aiService]);

  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, lastError: null }));
  }, []);

  return {
    state,
    configure,
    testConnection,
    summarizeThread,
    draftReply,
    analyzeThread,
    ingestEmailThread,
    getRelevantContext,
    clearError
  };
}

export default useAIFeatures;