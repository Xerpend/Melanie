import React, { useState } from 'react';
import { 
  Mail, 
  Reply, 
  ReplyAll, 
  Forward, 
  Archive, 
  Trash2, 
  Flag, 
  Star, 
  MoreHorizontal,
  Paperclip,
  Download,
  Eye,
  Calendar,
  User,
  Clock,
  ChevronDown,
  ChevronUp,
  Bot,
  Sparkles,
  FileText
} from 'lucide-react';
import { clsx } from 'clsx';
import { AIFeatures, AIThreadSummary, AIDraftReply, AIAnalysisResult } from './AIFeatures';
import { getAIService } from '../../services/aiService';
import { EmailMessage as IMAPEmailMessage } from '../../types/imap';

export interface EmailMessage {
  id: string;
  sender: {
    name: string;
    email: string;
    avatar?: string;
  };
  recipients: Array<{
    name: string;
    email: string;
    type: 'to' | 'cc' | 'bcc';
  }>;
  subject: string;
  content: string;
  htmlContent?: string;
  date: Date;
  attachments?: Array<{
    id: string;
    name: string;
    size: number;
    type: string;
    url?: string;
  }>;
  isRead: boolean;
  isFlagged: boolean;
  isStarred: boolean;
  priority: 'low' | 'normal' | 'high';
}

export interface EmailThread {
  id: string;
  subject: string;
  messages: EmailMessage[];
  participants: Array<{
    name: string;
    email: string;
    avatar?: string;
  }>;
}

interface PreviewPaneProps {
  thread?: EmailThread;
  onReply?: (messageId: string) => void;
  onReplyAll?: (messageId: string) => void;
  onForward?: (messageId: string) => void;
  onArchive?: (threadId: string) => void;
  onDelete?: (threadId: string) => void;
  onFlag?: (messageId: string) => void;
  onStar?: (messageId: string) => void;
  onAIAction?: (action: 'summarize' | 'draft-reply' | 'analyze', threadId: string) => void;
  onInsertReply?: (content: string) => void;
  accountId?: string; // For RAG integration
  className?: string;
}

const MessageItem: React.FC<{
  message: EmailMessage;
  isExpanded: boolean;
  onToggle: () => void;
  onReply?: () => void;
  onReplyAll?: () => void;
  onForward?: () => void;
  onFlag?: () => void;
  onStar?: () => void;
}> = ({ message, isExpanded, onToggle, onReply, onReplyAll, onForward, onFlag, onStar }) => {
  const formatDate = (date: Date) => {
    return date.toLocaleString([], {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getPriorityIndicator = (priority: EmailMessage['priority']) => {
    switch (priority) {
      case 'high':
        return <div className="w-2 h-2 bg-red-500 rounded-full" title="High priority" />;
      case 'low':
        return <div className="w-2 h-2 bg-blue-500 rounded-full" title="Low priority" />;
      default:
        return null;
    }
  };

  return (
    <div className="border-b border-surface-700/50 last:border-b-0">
      {/* Message header */}
      <div
        className={clsx(
          'p-4 cursor-pointer hover:bg-surface-800/30 transition-colors',
          isExpanded && 'bg-surface-800/20'
        )}
        onClick={onToggle}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-start space-x-3 flex-1">
            {/* Avatar */}
            <div className="flex-shrink-0">
              {message.sender.avatar ? (
                <img
                  src={message.sender.avatar}
                  alt={message.sender.name}
                  className="w-8 h-8 rounded-full"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-accent-500/20 flex items-center justify-center">
                  <span className="text-xs font-medium text-accent-400">
                    {message.sender.name.charAt(0).toUpperCase()}
                  </span>
                </div>
              )}
            </div>

            {/* Sender info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center space-x-2 mb-1">
                <span className="font-medium text-primary-50">
                  {message.sender.name}
                </span>
                <span className="text-sm text-surface-400">
                  &lt;{message.sender.email}&gt;
                </span>
                {getPriorityIndicator(message.priority)}
                {message.hasAttachments && (
                  <Paperclip className="w-3 h-3 text-surface-400" />
                )}
              </div>
              
              <div className="text-sm text-surface-400">
                <span>to </span>
                {message.recipients
                  .filter(r => r.type === 'to')
                  .map(r => r.name || r.email)
                  .join(', ')}
                {message.recipients.some(r => r.type === 'cc') && (
                  <span className="ml-2">
                    cc {message.recipients
                      .filter(r => r.type === 'cc')
                      .map(r => r.name || r.email)
                      .join(', ')}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Date and actions */}
          <div className="flex items-center space-x-2 flex-shrink-0">
            <span className="text-sm text-surface-400">
              {formatDate(message.date)}
            </span>
            
            <div className="flex items-center space-x-1">
              {message.isFlagged && (
                <Flag className="w-3 h-3 text-flagged fill-current" />
              )}
              {message.isStarred && (
                <Star className="w-3 h-3 text-flagged fill-current" />
              )}
              {isExpanded ? (
                <ChevronUp className="w-4 h-4 text-surface-400" />
              ) : (
                <ChevronDown className="w-4 h-4 text-surface-400" />
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Expanded message content */}
      {isExpanded && (
        <div className="px-4 pb-4">
          {/* Message actions */}
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-surface-700/30">
            <div className="flex items-center space-x-2">
              <button
                onClick={onReply}
                className="flex items-center space-x-1 px-3 py-1.5 bg-accent-500 hover:bg-accent-600 text-white rounded-lg text-sm transition-colors"
              >
                <Reply className="w-3 h-3" />
                <span>Reply</span>
              </button>
              
              <button
                onClick={onReplyAll}
                className="flex items-center space-x-1 px-3 py-1.5 bg-surface-700 hover:bg-surface-600 text-surface-200 rounded-lg text-sm transition-colors"
              >
                <ReplyAll className="w-3 h-3" />
                <span>Reply All</span>
              </button>
              
              <button
                onClick={onForward}
                className="flex items-center space-x-1 px-3 py-1.5 bg-surface-700 hover:bg-surface-600 text-surface-200 rounded-lg text-sm transition-colors"
              >
                <Forward className="w-3 h-3" />
                <span>Forward</span>
              </button>
            </div>

            <div className="flex items-center space-x-1">
              <button
                onClick={onFlag}
                className="p-2 hover:bg-surface-700 rounded-lg transition-colors"
                title="Toggle flag"
              >
                <Flag className={clsx(
                  'w-4 h-4',
                  message.isFlagged ? 'text-flagged fill-current' : 'text-surface-400'
                )} />
              </button>
              
              <button
                onClick={onStar}
                className="p-2 hover:bg-surface-700 rounded-lg transition-colors"
                title="Toggle star"
              >
                <Star className={clsx(
                  'w-4 h-4',
                  message.isStarred ? 'text-flagged fill-current' : 'text-surface-400'
                )} />
              </button>
              
              <button className="p-2 hover:bg-surface-700 rounded-lg transition-colors">
                <MoreHorizontal className="w-4 h-4 text-surface-400" />
              </button>
            </div>
          </div>

          {/* Attachments */}
          {message.attachments && message.attachments.length > 0 && (
            <div className="mb-4">
              <h4 className="text-sm font-medium text-surface-300 mb-2 flex items-center">
                <Paperclip className="w-4 h-4 mr-1" />
                Attachments ({message.attachments.length})
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {message.attachments.map((attachment) => (
                  <div
                    key={attachment.id}
                    className="flex items-center space-x-2 p-2 bg-surface-800 rounded-lg"
                  >
                    <FileText className="w-4 h-4 text-surface-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-surface-200 truncate">
                        {attachment.name}
                      </p>
                      <p className="text-xs text-surface-400">
                        {formatFileSize(attachment.size)}
                      </p>
                    </div>
                    <div className="flex items-center space-x-1">
                      <button
                        className="p-1 hover:bg-surface-700 rounded transition-colors"
                        title="Preview"
                      >
                        <Eye className="w-3 h-3 text-surface-400" />
                      </button>
                      <button
                        className="p-1 hover:bg-surface-700 rounded transition-colors"
                        title="Download"
                      >
                        <Download className="w-3 h-3 text-surface-400" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Message content */}
          <div className="prose prose-invert prose-sm max-w-none">
            {message.htmlContent ? (
              <div
                dangerouslySetInnerHTML={{ __html: message.htmlContent }}
                className="email-content"
              />
            ) : (
              <div className="whitespace-pre-wrap text-surface-200">
                {message.content}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export const PreviewPane: React.FC<PreviewPaneProps> = ({
  thread,
  onReply,
  onReplyAll,
  onForward,
  onArchive,
  onDelete,
  onFlag,
  onStar,
  onAIAction,
  onInsertReply,
  accountId,
  className
}) => {
  const [expandedMessages, setExpandedMessages] = useState<Set<string>>(new Set());

  // Convert EmailMessage to IMAPEmailMessage format for AI service
  const convertToIMAPMessages = (messages: EmailMessage[]): IMAPEmailMessage[] => {
    return messages.map(msg => ({
      id: msg.id,
      uid: parseInt(msg.id) || 0,
      subject: thread?.subject || 'No Subject',
      from: msg.sender.email,
      to: msg.recipients.filter(r => r.type === 'to').map(r => r.email),
      cc: msg.recipients.filter(r => r.type === 'cc').map(r => r.email),
      bcc: msg.recipients.filter(r => r.type === 'bcc').map(r => r.email),
      body: msg.content,
      html_body: msg.htmlContent,
      timestamp: msg.date.toISOString(),
      read: msg.isRead,
      flagged: msg.isFlagged,
      folder: 'INBOX',
      message_id: msg.id,
      references: [],
      thread_id: thread?.id || '',
      has_attachments: msg.attachments ? msg.attachments.length > 0 : false,
      size: msg.content.length,
      labels: [],
      priority: msg.priority
    }));
  };

  // AI feature handlers
  const handleSummarizeThread = async (threadId: string): Promise<AIThreadSummary> => {
    if (!thread) throw new Error('No thread available');
    
    const aiService = getAIService();
    const imapMessages = convertToIMAPMessages(thread.messages);
    
    // Ingest thread into RAG for future context
    if (accountId) {
      await aiService.ingestEmailThread(threadId, imapMessages);
    }
    
    return await aiService.summarizeThread(threadId, imapMessages);
  };

  const handleDraftReply = async (threadId: string, context?: string): Promise<AIDraftReply> => {
    if (!thread) throw new Error('No thread available');
    
    const aiService = getAIService();
    const imapMessages = convertToIMAPMessages(thread.messages);
    
    // Get relevant context from RAG if available
    let ragContext = '';
    if (accountId) {
      const contextChunks = await aiService.getRelevantEmailContext(
        thread.subject + ' ' + (context || ''),
        accountId
      );
      ragContext = contextChunks.join('\n\n');
    }
    
    const fullContext = [context, ragContext].filter(Boolean).join('\n\n');
    return await aiService.draftReply(threadId, imapMessages, fullContext);
  };

  const handleAnalyzeThread = async (threadId: string): Promise<AIAnalysisResult> => {
    if (!thread) throw new Error('No thread available');
    
    const aiService = getAIService();
    const imapMessages = convertToIMAPMessages(thread.messages);
    
    return await aiService.analyzeThread(threadId, imapMessages);
  };

  if (!thread) {
    return (
      <div className={clsx('flex items-center justify-center h-full bg-surface-900', className)}>
        <div className="text-center">
          <Mail className="w-16 h-16 text-surface-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-surface-300 mb-2">
            No email selected
          </h3>
          <p className="text-surface-400">
            Select an email from the list to view its contents
          </p>
        </div>
      </div>
    );
  }

  const toggleMessage = (messageId: string) => {
    const newExpanded = new Set(expandedMessages);
    if (newExpanded.has(messageId)) {
      newExpanded.delete(messageId);
    } else {
      newExpanded.add(messageId);
    }
    setExpandedMessages(newExpanded);
  };

  // Auto-expand the latest message
  React.useEffect(() => {
    if (thread.messages.length > 0) {
      const latestMessage = thread.messages[thread.messages.length - 1];
      setExpandedMessages(new Set([latestMessage.id]));
    }
  }, [thread.id]);

  return (
    <div className={clsx('flex flex-col h-full bg-surface-900', className)}>
      {/* Header */}
      <div className="p-4 border-b border-surface-700">
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-semibold text-primary-50 mb-2">
              {thread.subject}
            </h2>
            <div className="flex items-center space-x-4 text-sm text-surface-400">
              <div className="flex items-center space-x-1">
                <User className="w-4 h-4" />
                <span>{thread.participants.length} participants</span>
              </div>
              <div className="flex items-center space-x-1">
                <Mail className="w-4 h-4" />
                <span>{thread.messages.length} messages</span>
              </div>
              <div className="flex items-center space-x-1">
                <Clock className="w-4 h-4" />
                <span>
                  {thread.messages[thread.messages.length - 1]?.date.toLocaleDateString()}
                </span>
              </div>
            </div>
          </div>

          {/* Thread actions */}
          <div className="flex items-center space-x-2">
            <button
              onClick={() => onArchive?.(thread.id)}
              className="p-2 hover:bg-surface-800 rounded-lg transition-colors"
              title="Archive thread"
            >
              <Archive className="w-4 h-4 text-surface-400" />
            </button>
            
            <button
              onClick={() => onDelete?.(thread.id)}
              className="p-2 hover:bg-surface-800 rounded-lg transition-colors"
              title="Delete thread"
            >
              <Trash2 className="w-4 h-4 text-surface-400" />
            </button>
            
            <button className="p-2 hover:bg-surface-800 rounded-lg transition-colors">
              <MoreHorizontal className="w-4 h-4 text-surface-400" />
            </button>
          </div>
        </div>

        {/* AI Features */}
        <AIFeatures
          threadId={thread.id}
          threadSubject={thread.subject}
          threadMessages={thread.messages.map(msg => ({
            id: msg.id,
            sender: msg.sender,
            content: msg.content,
            date: msg.date
          }))}
          onSummarizeThread={handleSummarizeThread}
          onDraftReply={handleDraftReply}
          onAnalyzeThread={handleAnalyzeThread}
          onInsertReply={onInsertReply}
        />
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        {thread.messages.map((message) => (
          <MessageItem
            key={message.id}
            message={message}
            isExpanded={expandedMessages.has(message.id)}
            onToggle={() => toggleMessage(message.id)}
            onReply={() => onReply?.(message.id)}
            onReplyAll={() => onReplyAll?.(message.id)}
            onForward={() => onForward?.(message.id)}
            onFlag={() => onFlag?.(message.id)}
            onStar={() => onStar?.(message.id)}
          />
        ))}
      </div>
    </div>
  );
};

export default PreviewPane;