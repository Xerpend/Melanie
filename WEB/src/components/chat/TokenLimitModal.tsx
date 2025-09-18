'use client';

import React from 'react';
import { ChatMessage } from '@/types/chat';

interface TokenLimitModalProps {
  isOpen: boolean;
  onClose: () => void;
  tokenCount: number;
  maxTokens: number;
  messages: ChatMessage[];
  onStartNewChat: () => void;
  onSaveMarkdown: () => void;
  onDownloadSummary: () => void;
}

export const TokenLimitModal: React.FC<TokenLimitModalProps> = ({
  isOpen,
  onClose,
  tokenCount,
  maxTokens,
  messages,
  onStartNewChat,
  onSaveMarkdown,
  onDownloadSummary,
}) => {
  if (!isOpen) return null;

  const tokenPercentage = (tokenCount / maxTokens) * 100;

  const handleStartNewChat = () => {
    onStartNewChat();
    onClose();
  };

  const handleSaveMarkdown = () => {
    onSaveMarkdown();
    onClose();
  };

  const handleDownloadSummary = () => {
    onDownloadSummary();
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-background-card border border-border rounded-lg shadow-xl max-w-md w-full mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-yellow-500 rounded-full flex items-center justify-center">
              <span className="text-white text-sm">⚠️</span>
            </div>
            <h2 className="text-lg font-semibold text-text">
              Token Limit Reached
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text transition-colors"
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          <div className="mb-4">
            <p className="text-text-secondary mb-2">
              You've reached the 500k token limit for this conversation.
            </p>
            
            {/* Token Progress Bar */}
            <div className="mb-4">
              <div className="flex justify-between text-sm text-text-muted mb-1">
                <span>Token Usage</span>
                <span>{tokenCount.toLocaleString()} / {maxTokens.toLocaleString()}</span>
              </div>
              <div className="w-full bg-background-light rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all duration-300 ${
                    tokenPercentage >= 100 ? 'bg-red-500' : 
                    tokenPercentage >= 90 ? 'bg-yellow-500' : 'bg-accent'
                  }`}
                  style={{ width: `${Math.min(tokenPercentage, 100)}%` }}
                />
              </div>
            </div>

            <p className="text-text-muted text-sm">
              Choose an option below to continue:
            </p>
          </div>

          {/* Action Buttons */}
          <div className="space-y-3">
            <button
              onClick={handleStartNewChat}
              className="w-full bg-accent hover:bg-accent-hover text-text py-3 px-4 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-background-card"
            >
              <div className="flex items-center justify-center space-x-2">
                <span>🆕</span>
                <span>Start New Chat</span>
              </div>
              <div className="text-sm text-text-muted mt-1">
                Begin a fresh conversation with full token capacity
              </div>
            </button>

            <button
              onClick={handleSaveMarkdown}
              className="w-full bg-background-light hover:bg-border text-text py-3 px-4 rounded-lg transition-colors border border-border focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-background-card"
            >
              <div className="flex items-center justify-center space-x-2">
                <span>💾</span>
                <span>Save as Markdown</span>
              </div>
              <div className="text-sm text-text-muted mt-1">
                Download the conversation as a .md file
              </div>
            </button>

            <button
              onClick={handleDownloadSummary}
              className="w-full bg-background-light hover:bg-border text-text py-3 px-4 rounded-lg transition-colors border border-border focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-background-card"
            >
              <div className="flex items-center justify-center space-x-2">
                <span>📄</span>
                <span>Download Summary</span>
              </div>
              <div className="text-sm text-text-muted mt-1">
                Generate and download an AI-powered summary
              </div>
            </button>
          </div>

          {/* Message Count Info */}
          <div className="mt-4 pt-4 border-t border-border">
            <div className="text-sm text-text-muted text-center">
              This conversation contains {messages.length} message{messages.length !== 1 ? 's' : ''}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};