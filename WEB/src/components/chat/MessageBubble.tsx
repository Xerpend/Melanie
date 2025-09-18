'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { ChatMessage } from '@/types/chat';
import { ArtifactCard } from './ArtifactCard';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type MarkdownComponent = (props: any) => React.JSX.Element;

interface MessageBubbleProps {
  message: ChatMessage;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.role === 'user';
  
  const MarkdownContent = ({ content }: { content: string }) => (
    <div className="prose prose-invert max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
        // Custom styling for markdown elements
        h1: (({ children }) => <h1 className="text-xl font-bold mb-2 text-text">{children}</h1>) as MarkdownComponent,
        h2: (({ children }) => <h2 className="text-lg font-bold mb-2 text-text">{children}</h2>) as MarkdownComponent,
        h3: (({ children }) => <h3 className="text-base font-bold mb-1 text-text">{children}</h3>) as MarkdownComponent,
        p: (({ children }) => <p className="mb-2 text-text leading-relaxed">{children}</p>) as MarkdownComponent,
        ul: (({ children }) => <ul className="list-disc list-inside mb-2 text-text">{children}</ul>) as MarkdownComponent,
        ol: (({ children }) => <ol className="list-decimal list-inside mb-2 text-text">{children}</ol>) as MarkdownComponent,
        li: (({ children }) => <li className="mb-1 text-text">{children}</li>) as MarkdownComponent,
        blockquote: (({ children }) => (
          <blockquote className="border-l-4 border-accent pl-4 italic text-text-secondary mb-2">
            {children}
          </blockquote>
        )) as MarkdownComponent,
        code: (({ children, ...props }) => {
          const isInline = !String(children).includes('\n');
          if (isInline) {
            return (
              <code 
                className="bg-background-light px-1 py-0.5 rounded text-accent font-mono text-sm"
                {...props}
              >
                {children}
              </code>
            );
          }
          return (
            <code 
              className="block bg-background-light p-3 rounded-lg font-mono text-sm overflow-x-auto"
              {...props}
            >
              {children}
            </code>
          );
        }) as MarkdownComponent,
        pre: (({ children }) => (
          <pre className="bg-background-light p-3 rounded-lg overflow-x-auto mb-2">
            {children}
          </pre>
        )) as MarkdownComponent,
        a: (({ children, href }) => (
          <a 
            href={href} 
            className="text-accent hover:text-accent-light underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            {children}
          </a>
        )) as MarkdownComponent,
        table: (({ children }) => (
          <div className="overflow-x-auto mb-2">
            <table className="min-w-full border-collapse border border-border">
              {children}
            </table>
          </div>
        )) as MarkdownComponent,
        th: (({ children }) => (
          <th className="border border-border bg-background-light px-3 py-2 text-left font-medium text-text">
            {children}
          </th>
        )) as MarkdownComponent,
        td: (({ children }) => (
          <td className="border border-border px-3 py-2 text-text">
            {children}
          </td>
        )) as MarkdownComponent,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
  
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`max-w-4xl ${isUser ? 'order-2' : 'order-1'}`}>
        {/* Avatar */}
        <div className={`flex items-start space-x-3 ${isUser ? 'flex-row-reverse space-x-reverse' : ''}`}>
          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium flex-shrink-0 ${
            isUser 
              ? 'bg-text text-primary' 
              : 'bg-accent text-text'
          }`}>
            {isUser ? 'U' : 'M'}
          </div>
          
          <div className="flex-1 min-w-0">
            {/* Message Content */}
            <div className={`rounded-lg p-4 group ${
              isUser 
                ? 'bg-text text-primary ml-auto' 
                : 'bg-background-card text-text'
            }`}>
              <div className="break-words">
                {isUser ? (
                  // User messages: simple text with line breaks
                  <div className="whitespace-pre-wrap">{message.content}</div>
                ) : (
                  // AI messages: full markdown support
                  <MarkdownContent content={message.content} />
                )}
              </div>
              
              {/* Timestamp */}
              <div className={`text-xs mt-2 flex items-center justify-between ${
                isUser ? 'text-primary/70' : 'text-text-muted'
              }`}>
                <span>{message.timestamp.toLocaleTimeString()}</span>
                {!isUser && (
                  <button
                    onClick={() => navigator.clipboard.writeText(message.content)}
                    className="opacity-0 group-hover:opacity-100 hover:text-accent transition-all duration-200 ml-2"
                    aria-label="Copy message"
                    title="Copy message"
                  >
                    📋
                  </button>
                )}
              </div>
            </div>
            
            {/* Artifacts */}
            {message.artifacts && message.artifacts.length > 0 && (
              <div className="mt-3 space-y-2">
                {message.artifacts.map((artifact) => (
                  <ArtifactCard key={artifact.id} artifact={artifact} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};