'use client';

import React, { useEffect, useRef, useState } from 'react';
import { ChatMessage } from '@/types/chat';
import { MessageBubble } from './MessageBubble';

interface ChatAreaProps {
  messages: ChatMessage[];
  isLoading: boolean;
  typingText?: string;
}

export const ChatArea: React.FC<ChatAreaProps> = ({ 
  messages, 
  isLoading, 
  typingText 
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  };

  const handleScroll = () => {
    if (!containerRef.current) return;
    
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
    
    setShowScrollButton(!isNearBottom);
    setAutoScroll(isNearBottom);
  };

  useEffect(() => {
    if (autoScroll) {
      scrollToBottom();
    }
  }, [messages, isLoading, autoScroll]);

  useEffect(() => {
    // Scroll to bottom immediately on first load
    scrollToBottom('auto');
  }, []);

  const TypingIndicator = () => (
    <div className="flex items-start space-x-3 mb-4">
      <div className="w-8 h-8 rounded-full bg-accent text-text flex items-center justify-center text-sm font-medium">
        M
      </div>
      <div className="bg-background-card rounded-lg p-4 max-w-xs">
        <div className="flex items-center space-x-1">
          <div className="flex space-x-1">
            <div className="w-2 h-2 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
            <div className="w-2 h-2 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
            <div className="w-2 h-2 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
          </div>
          {typingText && (
            <span className="ml-2 text-text-muted text-sm">{typingText}</span>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex-1 relative bg-primary">
      <div 
        ref={containerRef}
        className="h-full overflow-y-auto"
        onScroll={handleScroll}
      >
        {messages.length === 0 && !isLoading ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center max-w-md mx-auto px-4">
              <div className="text-6xl mb-4">🤖</div>
              <h2 className="text-2xl font-bold text-text mb-2">
                Welcome to Melanie AI
              </h2>
              <p className="text-text-secondary">
                Your intelligent assistant for coding, research, and creative tasks.
                Start a conversation to get started.
              </p>
              <div className="mt-6 text-sm text-text-muted">
                <p>Try asking me to:</p>
                <ul className="mt-2 space-y-1">
                  <li>• Write and debug code</li>
                  <li>• Research complex topics</li>
                  <li>• Analyze documents and images</li>
                  <li>• Generate creative content</li>
                </ul>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-4 space-y-4">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            
            {isLoading && <TypingIndicator />}
            
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Scroll to bottom button */}
      {showScrollButton && (
        <button
          onClick={() => {
            scrollToBottom();
            setAutoScroll(true);
          }}
          className="absolute bottom-4 right-4 bg-accent hover:bg-accent-hover text-text rounded-full p-2 shadow-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-primary"
          aria-label="Scroll to bottom"
        >
          <svg 
            className="w-5 h-5" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth={2} 
              d="M19 14l-7 7m0 0l-7-7m7 7V3" 
            />
          </svg>
        </button>
      )}
    </div>
  );
};