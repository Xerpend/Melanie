'use client';

import React, { useState, useMemo } from 'react';
import { ChatSession } from '@/types/chat';

interface SidebarProps {
  sessions: ChatSession[];
  currentSession: ChatSession | null;
  onSessionSelect: (session: ChatSession) => void;
  onNewSession: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  sessions,
  currentSession,
  onSessionSelect,
  onNewSession,
}) => {
  const [searchQuery, setSearchQuery] = useState('');

  // Filter sessions based on search query
  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions;
    
    const query = searchQuery.toLowerCase();
    return sessions.filter(session => 
      session.title.toLowerCase().includes(query) ||
      session.messages.some(message => 
        message.content.toLowerCase().includes(query)
      )
    );
  }, [sessions, searchQuery]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
  };

  const clearSearch = () => {
    setSearchQuery('');
  };

  return (
    <div className="h-full bg-background-light flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <button
          onClick={onNewSession}
          className="w-full bg-accent hover:bg-accent-hover text-text font-medium py-2 px-4 rounded-lg transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-background-light"
          aria-label="Start new chat"
        >
          + New Chat
        </button>
      </div>

      {/* Search */}
      <div className="p-4 border-b border-border">
        <div className="relative">
          <input
            type="text"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={handleSearchChange}
            className="w-full bg-background-card border border-border rounded-lg px-3 py-2 pr-8 text-text placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent"
            aria-label="Search conversations"
          />
          {searchQuery && (
            <button
              onClick={clearSearch}
              className="absolute right-2 top-1/2 transform -translate-y-1/2 text-text-muted hover:text-text transition-colors"
              aria-label="Clear search"
            >
              ✕
            </button>
          )}
        </div>
        {searchQuery && (
          <div className="mt-2 text-xs text-text-muted">
            {filteredSessions.length} of {sessions.length} conversations
          </div>
        )}
      </div>

      {/* Chat History */}
      <div className="flex-1 overflow-y-auto">
        {sessions.length === 0 ? (
          <div className="p-4 text-text-muted text-center">
            No conversations yet
          </div>
        ) : filteredSessions.length === 0 ? (
          <div className="p-4 text-text-muted text-center">
            No conversations match your search
          </div>
        ) : (
          <div className="p-2">
            {filteredSessions.map((session) => (
              <button
                key={session.id}
                onClick={() => onSessionSelect(session)}
                className={`w-full text-left p-3 rounded-lg mb-2 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-accent ${
                  currentSession?.id === session.id
                    ? 'bg-accent text-text'
                    : 'hover:bg-background-card text-text-secondary'
                }`}
                aria-label={`Select conversation: ${session.title}`}
              >
                <div className="font-medium truncate">{session.title}</div>
                <div className="text-sm text-text-muted mt-1 flex items-center justify-between">
                  <span>{session.messages.length} messages</span>
                  <span className="text-xs">
                    {session.updatedAt.toLocaleDateString()}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-border">
        <div className="text-xs text-text-muted text-center">
          Melanie AI Assistant
        </div>
      </div>
    </div>
  );
};