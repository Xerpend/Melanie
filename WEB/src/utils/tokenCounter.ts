import { ChatMessage } from '@/types/chat';

/**
 * Utility functions for token counting and management
 */

/**
 * Rough token estimation based on character count
 * This is a simplified approximation - in production, you'd use a proper tokenizer
 * GPT-style models typically use ~4 characters per token on average
 */
export function estimateTokens(text: string): number {
  if (!text) return 0;
  
  // Basic estimation: ~4 characters per token
  // This accounts for spaces, punctuation, and typical word lengths
  const baseTokens = Math.ceil(text.length / 4);
  
  // Add some overhead for special tokens, formatting, etc.
  const overhead = Math.ceil(baseTokens * 0.1);
  
  return baseTokens + overhead;
}

/**
 * Calculate total tokens for a conversation
 */
export function calculateConversationTokens(messages: ChatMessage[]): number {
  let totalTokens = 0;
  
  for (const message of messages) {
    // Count tokens for message content
    totalTokens += estimateTokens(message.content);
    
    // Add tokens for role and metadata (roughly 10-20 tokens per message)
    totalTokens += 15;
    
    // Count tokens for artifacts if present
    if (message.artifacts) {
      for (const artifact of message.artifacts) {
        totalTokens += estimateTokens(artifact.content);
        // Add overhead for artifact metadata
        totalTokens += 20;
      }
    }
  }
  
  // Add system message overhead (typically 50-100 tokens)
  totalTokens += 75;
  
  return totalTokens;
}

/**
 * Check if adding a new message would exceed the token limit
 */
export function wouldExceedLimit(
  currentMessages: ChatMessage[],
  newMessageContent: string,
  maxTokens: number = 500000
): boolean {
  const currentTokens = calculateConversationTokens(currentMessages);
  const newMessageTokens = estimateTokens(newMessageContent) + 15; // +15 for metadata
  
  return (currentTokens + newMessageTokens) > maxTokens;
}

/**
 * Get token usage percentage
 */
export function getTokenUsagePercentage(
  messages: ChatMessage[],
  maxTokens: number = 500000
): number {
  const currentTokens = calculateConversationTokens(messages);
  return (currentTokens / maxTokens) * 100;
}

/**
 * Check if conversation is approaching token limit
 */
export function isApproachingLimit(
  messages: ChatMessage[],
  maxTokens: number = 500000,
  warningThreshold: number = 80
): boolean {
  const percentage = getTokenUsagePercentage(messages, maxTokens);
  return percentage >= warningThreshold;
}

/**
 * Check if conversation has reached token limit
 */
export function hasReachedLimit(
  messages: ChatMessage[],
  maxTokens: number = 500000
): boolean {
  const currentTokens = calculateConversationTokens(messages);
  return currentTokens >= maxTokens;
}

/**
 * Generate markdown content from conversation
 */
export function generateMarkdownFromConversation(
  messages: ChatMessage[],
  title: string = 'Melanie AI Conversation'
): string {
  const timestamp = new Date().toISOString().split('T')[0];
  let markdown = `# ${title}\n\n`;
  markdown += `*Generated on ${timestamp}*\n\n`;
  markdown += `---\n\n`;
  
  for (const message of messages) {
    const roleLabel = message.role === 'user' ? '👤 **You**' : '🤖 **Melanie**';
    const timestamp = message.timestamp.toLocaleString();
    
    markdown += `## ${roleLabel}\n`;
    markdown += `*${timestamp}*\n\n`;
    markdown += `${message.content}\n\n`;
    
    // Include artifacts
    if (message.artifacts && message.artifacts.length > 0) {
      markdown += `### Artifacts\n\n`;
      for (const artifact of message.artifacts) {
        markdown += `#### ${artifact.title || artifact.type}\n\n`;
        if (artifact.type === 'code' && artifact.language) {
          markdown += `\`\`\`${artifact.language}\n${artifact.content}\n\`\`\`\n\n`;
        } else {
          markdown += `${artifact.content}\n\n`;
        }
      }
    }
    
    markdown += `---\n\n`;
  }
  
  return markdown;
}

/**
 * Download content as a file
 */
export function downloadAsFile(content: string, filename: string, mimeType: string = 'text/plain') {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  
  // Cleanup
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Generate a conversation summary (placeholder - would use AI in production)
 */
export function generateConversationSummary(messages: ChatMessage[]): string {
  if (messages.length === 0) {
    return 'No messages in this conversation.';
  }
  
  const userMessages = messages.filter(m => m.role === 'user');
  const assistantMessages = messages.filter(m => m.role === 'assistant');
  
  let summary = `# Conversation Summary\n\n`;
  summary += `**Total Messages:** ${messages.length}\n`;
  summary += `**User Messages:** ${userMessages.length}\n`;
  summary += `**Assistant Messages:** ${assistantMessages.length}\n`;
  summary += `**Duration:** ${messages[0]?.timestamp.toLocaleString()} - ${messages[messages.length - 1]?.timestamp.toLocaleString()}\n\n`;
  
  summary += `## Key Topics Discussed\n\n`;
  
  // Simple keyword extraction (in production, this would use AI)
  const allContent = messages.map(m => m.content).join(' ').toLowerCase();
  const commonWords = ['code', 'function', 'api', 'data', 'help', 'create', 'implement', 'error', 'fix', 'test'];
  const foundTopics = commonWords.filter(word => allContent.includes(word));
  
  if (foundTopics.length > 0) {
    foundTopics.forEach(topic => {
      summary += `- ${topic.charAt(0).toUpperCase() + topic.slice(1)}\n`;
    });
  } else {
    summary += `- General conversation\n`;
  }
  
  summary += `\n## First Message\n\n`;
  if (userMessages.length > 0) {
    summary += `"${userMessages[0].content.substring(0, 200)}${userMessages[0].content.length > 200 ? '...' : ''}"\n\n`;
  }
  
  summary += `## Last Message\n\n`;
  if (messages.length > 0) {
    const lastMessage = messages[messages.length - 1];
    summary += `"${lastMessage.content.substring(0, 200)}${lastMessage.content.length > 200 ? '...' : ''}"\n\n`;
  }
  
  return summary;
}