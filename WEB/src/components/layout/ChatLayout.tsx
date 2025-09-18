'use client';

import React, { useState, useEffect } from 'react';
import { Sidebar } from '../chat/Sidebar';
import { ChatArea } from '../chat/ChatArea';
import { InputBar } from '../chat/InputBar';
import { StudiosPanel } from '../chat/StudiosPanel';
import { TokenLimitModal } from '../chat/TokenLimitModal';
import { ChatSession, ChatMessage, ChatSettings, FileUpload } from '@/types/chat';
import { 
  calculateConversationTokens, 
  wouldExceedLimit, 
  hasReachedLimit,
  generateMarkdownFromConversation,
  generateConversationSummary,
  downloadAsFile
} from '@/utils/tokenCounter';

interface ChatLayoutProps {
  className?: string;
}

export const ChatLayout: React.FC<ChatLayoutProps> = ({ className = '' }) => {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStudiosOpen, setIsStudiosOpen] = useState(false);
  const [settings, setSettings] = useState<ChatSettings>({
    model: 'Melanie-3',
    webSearch: false,
    tools: [],
  });

  const [isLoading, setIsLoading] = useState(false);
  const [typingText, setTypingText] = useState('');
  const [tokenCount, setTokenCount] = useState(0);
  const [showTokenLimitModal, setShowTokenLimitModal] = useState(false);
  const maxTokens = 500000;

  // Update token count when messages change
  useEffect(() => {
    const newTokenCount = calculateConversationTokens(messages);
    setTokenCount(newTokenCount);
    
    // Check if we've reached the limit
    if (hasReachedLimit(messages, maxTokens)) {
      setShowTokenLimitModal(true);
    }
  }, [messages, maxTokens]);

  const handleSendMessage = async (content: string, files?: FileUpload[]) => {
    // Check if sending this message would exceed the token limit
    if (wouldExceedLimit(messages, content, maxTokens)) {
      setShowTokenLimitModal(true);
      return;
    }

    // TODO: Implement message sending logic
    console.log('Sending message:', content, files);
    setIsLoading(true);
    setTypingText('Processing your request...');
    
    // Create user message
    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}-user`,
      role: 'user',
      content,
      timestamp: new Date(),
    };
    
    setMessages(prev => [...prev, userMessage]);
    
    // Simulate API call
    setTimeout(() => {
      const assistantMessage: ChatMessage = {
        id: `msg-${Date.now()}-assistant`,
        role: 'assistant',
        content: `I received your message: "${content}". This is a simulated response for testing token counting.`,
        timestamp: new Date(),
      };
      
      setMessages(prev => [...prev, assistantMessage]);
      setIsLoading(false);
      setTypingText('');
    }, 2000);
  };

  const handleNewSession = () => {
    const newSession: ChatSession = {
      id: `session-${Date.now()}`,
      title: 'New Chat',
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    setSessions(prev => [newSession, ...prev]);
    setCurrentSession(newSession);
    setMessages([]);
    setTokenCount(0);
  };

  const handleSaveMarkdown = () => {
    const markdown = generateMarkdownFromConversation(
      messages,
      currentSession?.title || 'Melanie AI Conversation'
    );
    const timestamp = new Date().toISOString().split('T')[0];
    const filename = `melanie-conversation-${timestamp}.md`;
    downloadAsFile(markdown, filename, 'text/markdown');
  };

  const handleDownloadSummary = async () => {
    // In production, this would call the AI API to generate a summary
    const summary = generateConversationSummary(messages);
    const timestamp = new Date().toISOString().split('T')[0];
    const filename = `melanie-summary-${timestamp}.md`;
    downloadAsFile(summary, filename, 'text/markdown');
  };

  return (
    <div className={`flex h-screen bg-primary text-text ${className}`}>
      {/* Sidebar */}
      <div className="w-80 border-r border-border flex-shrink-0">
        <Sidebar
          sessions={sessions}
          currentSession={currentSession}
          onSessionSelect={setCurrentSession}
          onNewSession={handleNewSession}
        />
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        <ChatArea
          messages={messages}
          isLoading={isLoading}
          typingText={typingText}
        />
        
        <InputBar
          onSendMessage={handleSendMessage}
          settings={settings}
          onSettingsChange={setSettings}
          onToggleStudios={() => setIsStudiosOpen(!isStudiosOpen)}
          isLoading={isLoading}
          tokenCount={tokenCount}
          maxTokens={maxTokens}
        />
      </div>

      {/* Studios Panel */}
      {isStudiosOpen && (
        <div className="w-96 border-l border-border flex-shrink-0">
          <StudiosPanel
            onClose={() => setIsStudiosOpen(false)}
          />
        </div>
      )}

      {/* Token Limit Modal */}
      <TokenLimitModal
        isOpen={showTokenLimitModal}
        onClose={() => setShowTokenLimitModal(false)}
        tokenCount={tokenCount}
        maxTokens={maxTokens}
        messages={messages}
        onStartNewChat={handleNewSession}
        onSaveMarkdown={handleSaveMarkdown}
        onDownloadSummary={handleDownloadSummary}
      />
    </div>
  );
};