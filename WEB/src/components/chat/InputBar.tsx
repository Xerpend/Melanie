'use client';

import React, { useState, useRef } from 'react';
import { ChatSettings, FileUpload } from '@/types/chat';

interface InputBarProps {
  onSendMessage: (content: string, files?: FileUpload[]) => void;
  settings: ChatSettings;
  onSettingsChange: (settings: ChatSettings) => void;
  onToggleStudios: () => void;
  isLoading?: boolean;
  tokenCount?: number;
  maxTokens?: number;
}

export const InputBar: React.FC<InputBarProps> = ({
  onSendMessage,
  settings,
  onSettingsChange,
  onToggleStudios,
  isLoading = false,
  tokenCount = 0,
  maxTokens = 500000,
}) => {
  const [message, setMessage] = useState('');
  const [isComposing, setIsComposing] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<FileUpload[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Check if we're at or near the token limit
    const isAtLimit = tokenCount >= maxTokens;
    const isNearLimit = tokenPercentage > 95;
    
    if (isAtLimit || isNearLimit) {
      // Don't send if at limit - the parent component will handle showing the modal
      return;
    }
    
    if ((message.trim() || attachedFiles.length > 0) && !isComposing && !isLoading) {
      onSendMessage(message.trim(), attachedFiles);
      setMessage('');
      setAttachedFiles([]);
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !isComposing) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
    
    // Auto-resize textarea
    const textarea = e.target;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    handleFiles(files);
  };

  const handleFiles = (files: File[]) => {
    const newFiles: FileUpload[] = files.map(file => ({
      id: `file-${Date.now()}-${Math.random()}`,
      filename: file.name,
      contentType: file.type,
      size: file.size,
      processed: false,
      ragIngested: false,
      uploadedAt: new Date(),
    }));
    
    setAttachedFiles(prev => [...prev, ...newFiles]);
  };

  const removeFile = (fileId: string) => {
    setAttachedFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    handleFiles(files);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const models = [
    { value: 'Melanie-3', label: 'Melanie-3 (Grok 4)' },
    { value: 'Melanie-3-light', label: 'Melanie-3-light (Grok 3 mini)' },
    { value: 'Melanie-3-code', label: 'Melanie-3-code (Grok Code Fast)' },
  ];

  const tokenPercentage = (tokenCount / maxTokens) * 100;
  const isNearLimit = tokenPercentage > 80;
  const isAtLimit = tokenCount >= maxTokens;
  const isCriticalLimit = tokenPercentage > 95;

  return (
    <div className="border-t border-border bg-background-light p-4">
      {/* Settings Row */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-4">
          {/* Model Selection */}
          <select
            value={settings.model}
            onChange={(e) => onSettingsChange({ ...settings, model: e.target.value })}
            className="bg-background-card border border-border rounded px-3 py-1 text-text text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            disabled={isLoading}
          >
            {models.map((model) => (
              <option key={model.value} value={model.value}>
                {model.label}
              </option>
            ))}
          </select>
          
          {/* Web Search Toggle */}
          <label className="flex items-center space-x-2 text-sm text-text">
            <input
              type="checkbox"
              checked={settings.webSearch}
              onChange={(e) => onSettingsChange({ ...settings, webSearch: e.target.checked })}
              className="rounded border-border text-accent focus:ring-accent"
              disabled={isLoading}
            />
            <span>Web Search</span>
          </label>
        </div>
        
        {/* Studios Toggle */}
        <button
          onClick={onToggleStudios}
          className="text-accent hover:text-accent-hover transition-colors text-sm focus:outline-none focus:ring-2 focus:ring-accent rounded"
          disabled={isLoading}
        >
          📁 Studios
        </button>
      </div>

      {/* Attached Files */}
      {attachedFiles.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-2">
          {attachedFiles.map((file) => (
            <div
              key={file.id}
              className="flex items-center space-x-2 bg-background-card border border-border rounded-lg px-3 py-2 text-sm"
            >
              <span className="text-text truncate max-w-32">{file.filename}</span>
              <span className="text-text-muted">({formatFileSize(file.size)})</span>
              <button
                onClick={() => removeFile(file.id)}
                className="text-text-muted hover:text-text transition-colors"
                aria-label={`Remove ${file.filename}`}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
      
      {/* Input Row */}
      <form onSubmit={handleSubmit} className="flex items-end space-x-3">
        {/* File Upload */}
        <div className="relative">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileSelect}
            className="hidden"
            accept=".txt,.md,.pdf,.png,.jpg,.jpeg,.gif,.webp"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="flex-shrink-0 w-10 h-10 bg-background-card hover:bg-border border border-border rounded-lg flex items-center justify-center text-text-muted hover:text-text transition-colors focus:outline-none focus:ring-2 focus:ring-accent"
            disabled={isLoading}
            aria-label="Attach files"
          >
            📎
          </button>
        </div>
        
        {/* Text Input */}
        <div 
          className={`flex-1 relative ${isDragOver ? 'ring-2 ring-accent' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <textarea
            ref={textareaRef}
            value={message}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            onCompositionStart={() => setIsComposing(true)}
            onCompositionEnd={() => setIsComposing(false)}
            placeholder={isLoading ? "Melanie is thinking..." : "Message Melanie..."}
            className="w-full bg-background-card border border-border rounded-lg px-4 py-3 text-text placeholder-text-muted resize-none focus:outline-none focus:ring-2 focus:ring-accent min-h-[48px] max-h-[200px] disabled:opacity-50"
            rows={1}
            disabled={isLoading}
          />
          {isDragOver && (
            <div className="absolute inset-0 bg-accent/10 border-2 border-dashed border-accent rounded-lg flex items-center justify-center">
              <span className="text-accent font-medium">Drop files here</span>
            </div>
          )}
        </div>
        
        {/* Send Button */}
        <button
          type="submit"
          disabled={(!message.trim() && attachedFiles.length === 0) || isComposing || isLoading || isAtLimit || isCriticalLimit}
          className={`flex-shrink-0 w-10 h-10 text-text rounded-lg flex items-center justify-center transition-colors focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-background-light ${
            isAtLimit || isCriticalLimit 
              ? 'bg-red-500 hover:bg-red-600 disabled:bg-red-300' 
              : 'bg-accent hover:bg-accent-hover disabled:bg-border disabled:text-text-muted'
          }`}
          aria-label={isAtLimit ? "Token limit reached" : "Send message"}
          title={isAtLimit ? "Token limit reached - start a new chat" : undefined}
        >
          {isLoading ? (
            <div className="animate-spin w-4 h-4 border-2 border-text border-t-transparent rounded-full"></div>
          ) : isAtLimit ? (
            '🚫'
          ) : (
            '➤'
          )}
        </button>
      </form>
      
      {/* Token Counter */}
      <div className="mt-2 flex items-center justify-between text-xs">
        <div className="text-text-muted">
          {attachedFiles.length > 0 && (
            <span>{attachedFiles.length} file{attachedFiles.length !== 1 ? 's' : ''} attached</span>
          )}
        </div>
        <div className="flex items-center space-x-2">
          {/* Token Progress Bar */}
          <div className="flex items-center space-x-2">
            <div className="w-16 bg-background-light rounded-full h-1.5">
              <div
                className={`h-1.5 rounded-full transition-all duration-300 ${
                  isAtLimit ? 'bg-red-500' : 
                  isCriticalLimit ? 'bg-red-400' :
                  isNearLimit ? 'bg-yellow-400' : 'bg-accent'
                }`}
                style={{ width: `${Math.min(tokenPercentage, 100)}%` }}
              />
            </div>
            <span className={`${
              isAtLimit ? 'text-red-400' : 
              isCriticalLimit ? 'text-red-300' :
              isNearLimit ? 'text-yellow-400' : 'text-text-muted'
            }`}>
              {tokenCount.toLocaleString()} / {maxTokens.toLocaleString()}
            </span>
            {isAtLimit && (
              <span className="text-red-400" title="Token limit reached">
                🚫
              </span>
            )}
            {isCriticalLimit && !isAtLimit && (
              <span className="text-red-300" title="Critical: Near token limit">
                ⚠️
              </span>
            )}
            {isNearLimit && !isCriticalLimit && (
              <span className="text-yellow-400" title="Warning: Approaching token limit">
                ⚠️
              </span>
            )}
          </div>
        </div>
      </div>
      
      {/* Token Limit Warning */}
      {(isNearLimit || isAtLimit) && (
        <div className={`mt-2 p-2 rounded-lg text-xs ${
          isAtLimit ? 'bg-red-500/10 border border-red-500/20 text-red-400' :
          isCriticalLimit ? 'bg-red-400/10 border border-red-400/20 text-red-300' :
          'bg-yellow-500/10 border border-yellow-500/20 text-yellow-400'
        }`}>
          {isAtLimit ? (
            <div className="flex items-center space-x-2">
              <span>🚫</span>
              <span>Token limit reached. Start a new chat to continue.</span>
            </div>
          ) : isCriticalLimit ? (
            <div className="flex items-center space-x-2">
              <span>⚠️</span>
              <span>Critical: Very close to token limit. Consider starting a new chat.</span>
            </div>
          ) : (
            <div className="flex items-center space-x-2">
              <span>⚠️</span>
              <span>Approaching token limit ({tokenPercentage.toFixed(1)}% used).</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};