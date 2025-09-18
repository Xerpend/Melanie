import { invoke } from '@tauri-apps/api/tauri';
import { 
  AIThreadSummary, 
  AIDraftReply, 
  AIAnalysisResult 
} from '../components/email/AIFeatures';
import { EmailMessage, EmailThread } from '../types/imap';

export interface MelanieAPIConfig {
  baseUrl: string;
  apiKey: string;
  timeout?: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface ChatCompletionRequest {
  model: 'Melanie-3-light' | 'Melanie-3' | 'Melanie-3-code';
  messages: ChatMessage[];
  max_tokens?: number;
  temperature?: number;
}

export interface ChatCompletionResponse {
  id: string;
  choices: Array<{
    message: {
      role: string;
      content: string;
    };
    finish_reason: string;
  }>;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

export class AIService {
  private config: MelanieAPIConfig;

  constructor(config: MelanieAPIConfig) {
    this.config = {
      timeout: 30000, // 30 seconds default
      ...config
    };
  }

  /**
   * Make a request to the Melanie API
   */
  private async makeAPIRequest(request: ChatCompletionRequest): Promise<ChatCompletionResponse> {
    try {
      const response = await fetch(`${this.config.baseUrl}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.config.apiKey}`,
        },
        body: JSON.stringify(request),
        signal: AbortSignal.timeout(this.config.timeout || 30000),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`API request failed: ${response.status} ${response.statusText}. ${errorData.message || ''}`);
      }

      return await response.json();
    } catch (error) {
      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          throw new Error('Request timed out');
        }
        throw error;
      }
      throw new Error('Unknown error occurred');
    }
  }

  /**
   * Convert email thread to context string for AI processing
   */
  private formatThreadForAI(messages: EmailMessage[]): string {
    const sortedMessages = [...messages].sort((a, b) => 
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );

    return sortedMessages.map(msg => {
      const date = new Date(msg.timestamp).toLocaleString();
      const sender = msg.from;
      const content = msg.html_body || msg.body;
      
      return `[${date}] From: ${sender}\nSubject: ${msg.subject}\n\n${content}\n\n---\n`;
    }).join('\n');
  }

  /**
   * Extract relevant context from email thread for RAG integration
   */
  private extractEmailContext(messages: EmailMessage[]): string {
    const participants = [...new Set(messages.flatMap(msg => [msg.from, ...msg.to, ...msg.cc]))];
    const subjects = [...new Set(messages.map(msg => msg.subject))];
    const timeRange = messages.length > 0 ? {
      start: new Date(Math.min(...messages.map(msg => new Date(msg.timestamp).getTime()))),
      end: new Date(Math.max(...messages.map(msg => new Date(msg.timestamp).getTime())))
    } : null;

    let context = `Email Thread Context:\n`;
    context += `Participants: ${participants.join(', ')}\n`;
    context += `Subjects: ${subjects.join(', ')}\n`;
    if (timeRange) {
      context += `Time Range: ${timeRange.start.toLocaleDateString()} - ${timeRange.end.toLocaleDateString()}\n`;
    }
    context += `Message Count: ${messages.length}\n\n`;

    return context;
  }

  /**
   * Summarize an email thread using Melanie-3-light
   */
  async summarizeThread(threadId: string, messages: EmailMessage[]): Promise<AIThreadSummary> {
    if (messages.length === 0) {
      throw new Error('No messages to summarize');
    }

    const threadContext = this.formatThreadForAI(messages);
    const emailContext = this.extractEmailContext(messages);

    const systemPrompt = `You are an AI assistant specialized in email analysis. Your task is to summarize email threads concisely and extract key information.

Please analyze the following email thread and provide:
1. A brief summary (2-3 sentences)
2. Key points discussed
3. List of participants
4. Timeline description
5. Any action items mentioned

Format your response as JSON with the following structure:
{
  "summary": "Brief summary of the thread",
  "keyPoints": ["point 1", "point 2", ...],
  "participants": ["participant 1", "participant 2", ...],
  "timeline": "Description of the timeline",
  "actionItems": ["action 1", "action 2", ...] (optional)
}`;

    const userPrompt = `${emailContext}\n\nEmail Thread:\n${threadContext}`;

    const request: ChatCompletionRequest = {
      model: 'Melanie-3-light',
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt }
      ],
      max_tokens: 1000,
      temperature: 0.3
    };

    try {
      const response = await this.makeAPIRequest(request);
      const content = response.choices[0]?.message?.content;

      if (!content) {
        throw new Error('No response content received');
      }

      // Try to parse JSON response
      try {
        const parsed = JSON.parse(content);
        return {
          summary: parsed.summary || 'Summary not available',
          keyPoints: Array.isArray(parsed.keyPoints) ? parsed.keyPoints : [],
          participants: Array.isArray(parsed.participants) ? parsed.participants : [],
          timeline: parsed.timeline || 'Timeline not available',
          actionItems: Array.isArray(parsed.actionItems) ? parsed.actionItems : undefined
        };
      } catch (parseError) {
        // Fallback: treat the entire response as summary
        return {
          summary: content,
          keyPoints: [],
          participants: [...new Set(messages.map(msg => msg.from))],
          timeline: `${messages.length} messages over time`,
          actionItems: undefined
        };
      }
    } catch (error) {
      throw new Error(`Failed to summarize thread: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Draft a reply to an email thread using Melanie-3-light with context injection
   */
  async draftReply(threadId: string, messages: EmailMessage[], context?: string): Promise<AIDraftReply> {
    if (messages.length === 0) {
      throw new Error('No messages to draft reply for');
    }

    const lastMessage = messages[messages.length - 1];
    const threadContext = this.formatThreadForAI(messages.slice(-3)); // Last 3 messages for context
    const emailContext = this.extractEmailContext(messages);

    const systemPrompt = `You are an AI assistant specialized in drafting professional email replies. Your task is to generate appropriate, contextual responses to email threads.

Guidelines:
- Maintain a professional but friendly tone
- Address the key points from the previous messages
- Be concise and clear
- Include appropriate greetings and closings
- Consider the context and relationship between participants

Please draft a reply and provide your response as JSON with the following structure:
{
  "content": "The draft reply content",
  "tone": "professional|casual|formal",
  "confidence": 0.85,
  "suggestions": ["suggestion 1", "suggestion 2", ...] (optional)
}`;

    let userPrompt = `${emailContext}\n\nRecent Email Thread:\n${threadContext}`;
    
    if (context) {
      userPrompt += `\n\nAdditional Context:\n${context}`;
    }

    userPrompt += `\n\nPlease draft a reply to the most recent message in this thread.`;

    const request: ChatCompletionRequest = {
      model: 'Melanie-3-light',
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt }
      ],
      max_tokens: 800,
      temperature: 0.7
    };

    try {
      const response = await this.makeAPIRequest(request);
      const content = response.choices[0]?.message?.content;

      if (!content) {
        throw new Error('No response content received');
      }

      // Try to parse JSON response
      try {
        const parsed = JSON.parse(content);
        return {
          content: parsed.content || content,
          tone: parsed.tone || 'professional',
          confidence: parsed.confidence || 0.7,
          suggestions: Array.isArray(parsed.suggestions) ? parsed.suggestions : undefined
        };
      } catch (parseError) {
        // Fallback: treat the entire response as content
        return {
          content: content,
          tone: 'professional',
          confidence: 0.7,
          suggestions: undefined
        };
      }
    } catch (error) {
      throw new Error(`Failed to draft reply: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Analyze an email thread for sentiment, categorization, and priority using Melanie-3-light
   */
  async analyzeThread(threadId: string, messages: EmailMessage[]): Promise<AIAnalysisResult> {
    if (messages.length === 0) {
      throw new Error('No messages to analyze');
    }

    const threadContext = this.formatThreadForAI(messages);
    const emailContext = this.extractEmailContext(messages);

    const systemPrompt = `You are an AI assistant specialized in email analysis. Your task is to analyze email threads for sentiment, categorization, priority, and extract key insights.

Please analyze the following email thread and provide:
1. Overall sentiment (positive, negative, neutral)
2. Category/topic classification
3. Priority level (low, normal, high)
4. Key keywords/topics
5. Brief summary
6. Any action items identified

Format your response as JSON with the following structure:
{
  "sentiment": "positive|negative|neutral",
  "category": "Category name",
  "priority": "low|normal|high",
  "keywords": ["keyword1", "keyword2", ...],
  "summary": "Brief analysis summary",
  "actionItems": ["action 1", "action 2", ...] (optional)
}`;

    const userPrompt = `${emailContext}\n\nEmail Thread:\n${threadContext}`;

    const request: ChatCompletionRequest = {
      model: 'Melanie-3-light',
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt }
      ],
      max_tokens: 800,
      temperature: 0.3
    };

    try {
      const response = await this.makeAPIRequest(request);
      const content = response.choices[0]?.message?.content;

      if (!content) {
        throw new Error('No response content received');
      }

      // Try to parse JSON response
      try {
        const parsed = JSON.parse(content);
        return {
          sentiment: parsed.sentiment || 'neutral',
          category: parsed.category || 'General',
          priority: parsed.priority || 'normal',
          keywords: Array.isArray(parsed.keywords) ? parsed.keywords : [],
          summary: parsed.summary || 'Analysis not available',
          actionItems: Array.isArray(parsed.actionItems) ? parsed.actionItems : undefined
        };
      } catch (parseError) {
        // Fallback analysis
        return {
          sentiment: 'neutral',
          category: 'General',
          priority: 'normal',
          keywords: [],
          summary: content,
          actionItems: undefined
        };
      }
    } catch (error) {
      throw new Error(`Failed to analyze thread: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Get relevant email context using RAG integration
   * This method would integrate with the RAG system to find relevant past emails
   */
  async getRelevantEmailContext(query: string, accountId: string): Promise<string[]> {
    try {
      // This would integrate with the RAG system
      // For now, we'll return a placeholder
      // In a real implementation, this would:
      // 1. Query the RAG system with the email content
      // 2. Retrieve relevant past emails and conversations
      // 3. Return formatted context strings

      // Placeholder implementation
      return [
        `Previous email context related to: ${query}`,
        'Relevant conversation history would be retrieved from RAG system'
      ];
    } catch (error) {
      console.warn('Failed to get RAG context:', error);
      return [];
    }
  }

  /**
   * Ingest email thread into RAG system for future context
   */
  async ingestEmailThread(threadId: string, messages: EmailMessage[]): Promise<void> {
    try {
      const threadContent = this.formatThreadForAI(messages);
      const context = this.extractEmailContext(messages);
      
      // This would integrate with the RAG system to ingest the email content
      // For now, we'll just log the action
      console.log(`Ingesting email thread ${threadId} into RAG system`);
      console.log(`Content length: ${threadContent.length} characters`);
      
      // In a real implementation, this would:
      // 1. Format the email thread for RAG ingestion
      // 2. Send to the RAG system for processing and storage
      // 3. Handle any errors or confirmations
      
    } catch (error) {
      console.warn('Failed to ingest email thread into RAG:', error);
      // Don't throw error as this is a background operation
    }
  }

  /**
   * Test the connection to the Melanie API
   */
  async testConnection(): Promise<boolean> {
    try {
      const request: ChatCompletionRequest = {
        model: 'Melanie-3-light',
        messages: [
          { role: 'user', content: 'Hello, this is a connection test.' }
        ],
        max_tokens: 50,
        temperature: 0.1
      };

      await this.makeAPIRequest(request);
      return true;
    } catch (error) {
      console.error('AI Service connection test failed:', error);
      return false;
    }
  }

  /**
   * Get AI service status and configuration
   */
  getStatus(): { connected: boolean; config: Partial<MelanieAPIConfig> } {
    return {
      connected: true, // Would be determined by last successful request
      config: {
        baseUrl: this.config.baseUrl,
        timeout: this.config.timeout
        // Don't expose API key
      }
    };
  }
}

// Default AI service instance
let defaultAIService: AIService | null = null;

/**
 * Get or create the default AI service instance
 */
export function getAIService(): AIService {
  if (!defaultAIService) {
    // These would typically come from app configuration or environment
    const config: MelanieAPIConfig = {
      baseUrl: 'http://localhost:8000', // Default Melanie API URL
      apiKey: process.env.MELANIE_API_KEY || 'mel_demo_key', // Would be configured by user
      timeout: 30000
    };

    defaultAIService = new AIService(config);
  }

  return defaultAIService;
}

/**
 * Configure the default AI service
 */
export function configureAIService(config: MelanieAPIConfig): void {
  defaultAIService = new AIService(config);
}

export default AIService;