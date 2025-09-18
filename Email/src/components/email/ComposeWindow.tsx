import React, { useState, useRef, useCallback } from 'react';
import { 
  Send, 
  Paperclip, 
  Image, 
  Smile, 
  Bold, 
  Italic, 
  Underline, 
  Link, 
  List, 
  ListOrdered,
  Quote,
  Code,
  X,
  Minimize2,
  Maximize2,
  Save,
  Trash2,
  Eye,
  EyeOff,
  Bot,
  Sparkles
} from 'lucide-react';
import { clsx } from 'clsx';

export interface ComposeData {
  to: string[];
  cc: string[];
  bcc: string[];
  subject: string;
  content: string;
  htmlContent?: string;
  attachments: File[];
  priority: 'low' | 'normal' | 'high';
  isHtml: boolean;
}

export interface ComposeWindowProps {
  initialData?: Partial<ComposeData>;
  isReply?: boolean;
  isReplyAll?: boolean;
  isForward?: boolean;
  originalMessage?: {
    id: string;
    subject: string;
    sender: { name: string; email: string };
    content: string;
    date: Date;
  };
  onSend: (data: ComposeData) => Promise<void>;
  onSaveDraft: (data: ComposeData) => Promise<void>;
  onClose: () => void;
  onAIAssist?: (action: 'improve' | 'summarize' | 'translate', content: string) => Promise<string>;
  className?: string;
}

const TOOLBAR_BUTTONS = [
  { icon: Bold, action: 'bold', title: 'Bold (Ctrl+B)' },
  { icon: Italic, action: 'italic', title: 'Italic (Ctrl+I)' },
  { icon: Underline, action: 'underline', title: 'Underline (Ctrl+U)' },
  { icon: Link, action: 'link', title: 'Insert Link' },
  { icon: List, action: 'unorderedList', title: 'Bullet List' },
  { icon: ListOrdered, action: 'orderedList', title: 'Numbered List' },
  { icon: Quote, action: 'blockquote', title: 'Quote' },
  { icon: Code, action: 'code', title: 'Code' },
];

export const ComposeWindow: React.FC<ComposeWindowProps> = ({
  initialData,
  isReply = false,
  isReplyAll = false,
  isForward = false,
  originalMessage,
  onSend,
  onSaveDraft,
  onClose,
  onAIAssist,
  className
}) => {
  const [composeData, setComposeData] = useState<ComposeData>(() => {
    const defaultData: ComposeData = {
      to: [],
      cc: [],
      bcc: [],
      subject: '',
      content: '',
      htmlContent: '',
      attachments: [],
      priority: 'normal',
      isHtml: true
    };

    if (initialData) {
      return { ...defaultData, ...initialData };
    }

    if (originalMessage) {
      if (isReply || isReplyAll) {
        return {
          ...defaultData,
          to: [originalMessage.sender.email],
          subject: originalMessage.subject.startsWith('Re:') 
            ? originalMessage.subject 
            : `Re: ${originalMessage.subject}`,
          content: `\n\n--- Original Message ---\nFrom: ${originalMessage.sender.name} <${originalMessage.sender.email}>\nDate: ${originalMessage.date.toLocaleString()}\nSubject: ${originalMessage.subject}\n\n${originalMessage.content}`
        };
      }

      if (isForward) {
        return {
          ...defaultData,
          subject: originalMessage.subject.startsWith('Fwd:') 
            ? originalMessage.subject 
            : `Fwd: ${originalMessage.subject}`,
          content: `\n\n--- Forwarded Message ---\nFrom: ${originalMessage.sender.name} <${originalMessage.sender.email}>\nDate: ${originalMessage.date.toLocaleString()}\nSubject: ${originalMessage.subject}\n\n${originalMessage.content}`
        };
      }
    }

    return defaultData;
  });

  const [isMinimized, setIsMinimized] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);
  const [showCc, setShowCc] = useState(composeData.cc.length > 0);
  const [showBcc, setShowBcc] = useState(composeData.bcc.length > 0);
  const [isSending, setIsSending] = useState(false);
  const [isDraftSaving, setIsDraftSaving] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [aiAssisting, setAiAssisting] = useState(false);

  const contentRef = useRef<HTMLTextAreaElement>(null);
  const htmlContentRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const updateField = useCallback((field: keyof ComposeData, value: any) => {
    setComposeData(prev => ({ ...prev, [field]: value }));
  }, []);

  const addRecipient = useCallback((field: 'to' | 'cc' | 'bcc', email: string) => {
    if (email.trim() && !composeData[field].includes(email.trim())) {
      updateField(field, [...composeData[field], email.trim()]);
    }
  }, [composeData, updateField]);

  const removeRecipient = useCallback((field: 'to' | 'cc' | 'bcc', email: string) => {
    updateField(field, composeData[field].filter(e => e !== email));
  }, [composeData, updateField]);

  const handleFileUpload = useCallback((files: FileList | null) => {
    if (files) {
      const newFiles = Array.from(files);
      updateField('attachments', [...composeData.attachments, ...newFiles]);
    }
  }, [composeData.attachments, updateField]);

  const removeAttachment = useCallback((index: number) => {
    updateField('attachments', composeData.attachments.filter((_, i) => i !== index));
  }, [composeData.attachments, updateField]);

  const executeCommand = useCallback((command: string, value?: string) => {
    if (composeData.isHtml && htmlContentRef.current) {
      document.execCommand(command, false, value);
      htmlContentRef.current.focus();
    }
  }, [composeData.isHtml]);

  const handleSend = useCallback(async () => {
    if (composeData.to.length === 0) {
      alert('Please add at least one recipient');
      return;
    }

    setIsSending(true);
    try {
      await onSend(composeData);
      onClose();
    } catch (error) {
      console.error('Failed to send email:', error);
      alert('Failed to send email. Please try again.');
    } finally {
      setIsSending(false);
    }
  }, [composeData, onSend, onClose]);

  const handleSaveDraft = useCallback(async () => {
    setIsDraftSaving(true);
    try {
      await onSaveDraft(composeData);
    } catch (error) {
      console.error('Failed to save draft:', error);
    } finally {
      setIsDraftSaving(false);
    }
  }, [composeData, onSaveDraft]);

  const handleAIAssist = useCallback(async (action: 'improve' | 'summarize' | 'translate') => {
    if (!onAIAssist || !composeData.content.trim()) return;

    setAiAssisting(true);
    try {
      const improvedContent = await onAIAssist(action, composeData.content);
      updateField('content', improvedContent);
    } catch (error) {
      console.error('AI assist failed:', error);
    } finally {
      setAiAssisting(false);
    }
  }, [composeData.content, onAIAssist, updateField]);

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  if (isMinimized) {
    return (
      <div className={clsx(
        'fixed bottom-4 right-4 bg-surface-800 border border-surface-600 rounded-lg shadow-lg',
        'w-80 p-3 cursor-pointer hover:bg-surface-700 transition-colors',
        className
      )}>
        <div className="flex items-center justify-between" onClick={() => setIsMinimized(false)}>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 bg-accent-500 rounded-full"></div>
            <span className="text-sm font-medium">
              {composeData.subject || 'New Message'}
            </span>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onClose();
            }}
            className="p-1 hover:bg-surface-600 rounded"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={clsx(
      'fixed bg-surface-900 border border-surface-600 rounded-lg shadow-2xl flex flex-col',
      isMaximized 
        ? 'inset-4' 
        : 'bottom-4 right-4 w-[600px] h-[500px]',
      className
    )}>
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-surface-700">
        <div className="flex items-center space-x-2">
          <h3 className="font-medium text-primary-50">
            {isReply ? 'Reply' : isReplyAll ? 'Reply All' : isForward ? 'Forward' : 'New Message'}
          </h3>
          {isDraftSaving && (
            <span className="text-xs text-surface-400">Saving draft...</span>
          )}
        </div>

        <div className="flex items-center space-x-1">
          <button
            onClick={() => setIsMinimized(true)}
            className="p-1 hover:bg-surface-700 rounded transition-colors"
            title="Minimize"
          >
            <Minimize2 className="w-4 h-4" />
          </button>
          
          <button
            onClick={() => setIsMaximized(!isMaximized)}
            className="p-1 hover:bg-surface-700 rounded transition-colors"
            title={isMaximized ? 'Restore' : 'Maximize'}
          >
            <Maximize2 className="w-4 h-4" />
          </button>
          
          <button
            onClick={onClose}
            className="p-1 hover:bg-surface-700 rounded transition-colors"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Recipients */}
      <div className="p-3 border-b border-surface-700 space-y-2">
        {/* To field */}
        <div className="flex items-center space-x-2">
          <label className="text-sm font-medium text-surface-300 w-12">To:</label>
          <div className="flex-1">
            <input
              type="email"
              placeholder="Enter email addresses..."
              className="w-full bg-surface-800 border border-surface-600 rounded px-3 py-1 text-sm focus:border-accent-500 focus:outline-none"
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ',') {
                  e.preventDefault();
                  addRecipient('to', e.currentTarget.value);
                  e.currentTarget.value = '';
                }
              }}
            />
            {composeData.to.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {composeData.to.map((email) => (
                  <span
                    key={email}
                    className="inline-flex items-center space-x-1 bg-accent-500/20 text-accent-400 px-2 py-1 rounded text-xs"
                  >
                    <span>{email}</span>
                    <button
                      onClick={() => removeRecipient('to', email)}
                      className="hover:text-accent-300"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
          
          <div className="flex items-center space-x-2 text-xs">
            <button
              onClick={() => setShowCc(!showCc)}
              className={clsx(
                'hover:text-accent-400 transition-colors',
                showCc ? 'text-accent-400' : 'text-surface-400'
              )}
            >
              Cc
            </button>
            <button
              onClick={() => setShowBcc(!showBcc)}
              className={clsx(
                'hover:text-accent-400 transition-colors',
                showBcc ? 'text-accent-400' : 'text-surface-400'
              )}
            >
              Bcc
            </button>
          </div>
        </div>

        {/* CC field */}
        {showCc && (
          <div className="flex items-center space-x-2">
            <label className="text-sm font-medium text-surface-300 w-12">Cc:</label>
            <input
              type="email"
              placeholder="Enter CC recipients..."
              className="flex-1 bg-surface-800 border border-surface-600 rounded px-3 py-1 text-sm focus:border-accent-500 focus:outline-none"
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ',') {
                  e.preventDefault();
                  addRecipient('cc', e.currentTarget.value);
                  e.currentTarget.value = '';
                }
              }}
            />
          </div>
        )}

        {/* BCC field */}
        {showBcc && (
          <div className="flex items-center space-x-2">
            <label className="text-sm font-medium text-surface-300 w-12">Bcc:</label>
            <input
              type="email"
              placeholder="Enter BCC recipients..."
              className="flex-1 bg-surface-800 border border-surface-600 rounded px-3 py-1 text-sm focus:border-accent-500 focus:outline-none"
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ',') {
                  e.preventDefault();
                  addRecipient('bcc', e.currentTarget.value);
                  e.currentTarget.value = '';
                }
              }}
            />
          </div>
        )}

        {/* Subject */}
        <div className="flex items-center space-x-2">
          <label className="text-sm font-medium text-surface-300 w-12">Subject:</label>
          <input
            type="text"
            placeholder="Enter subject..."
            value={composeData.subject}
            onChange={(e) => updateField('subject', e.target.value)}
            className="flex-1 bg-surface-800 border border-surface-600 rounded px-3 py-1 text-sm focus:border-accent-500 focus:outline-none"
          />
          
          <select
            value={composeData.priority}
            onChange={(e) => updateField('priority', e.target.value)}
            className="bg-surface-800 border border-surface-600 rounded px-2 py-1 text-xs"
          >
            <option value="low">Low Priority</option>
            <option value="normal">Normal</option>
            <option value="high">High Priority</option>
          </select>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between p-2 border-b border-surface-700">
        <div className="flex items-center space-x-1">
          {TOOLBAR_BUTTONS.map(({ icon: Icon, action, title }) => (
            <button
              key={action}
              onClick={() => executeCommand(action)}
              className="p-1.5 hover:bg-surface-700 rounded transition-colors"
              title={title}
              disabled={!composeData.isHtml}
            >
              <Icon className="w-4 h-4 text-surface-400" />
            </button>
          ))}
          
          <div className="w-px h-6 bg-surface-600 mx-2" />
          
          <button
            onClick={() => fileInputRef.current?.click()}
            className="p-1.5 hover:bg-surface-700 rounded transition-colors"
            title="Attach files"
          >
            <Paperclip className="w-4 h-4 text-surface-400" />
          </button>
          
          <button
            className="p-1.5 hover:bg-surface-700 rounded transition-colors"
            title="Insert image"
          >
            <Image className="w-4 h-4 text-surface-400" />
          </button>
          
          <button
            className="p-1.5 hover:bg-surface-700 rounded transition-colors"
            title="Insert emoji"
          >
            <Smile className="w-4 h-4 text-surface-400" />
          </button>
        </div>

        <div className="flex items-center space-x-2">
          {onAIAssist && (
            <div className="flex items-center space-x-1">
              <Bot className="w-4 h-4 text-accent-400" />
              <button
                onClick={() => handleAIAssist('improve')}
                disabled={aiAssisting || !composeData.content.trim()}
                className="px-2 py-1 bg-accent-500/20 hover:bg-accent-500/30 text-accent-400 rounded text-xs transition-colors disabled:opacity-50"
              >
                {aiAssisting ? 'Processing...' : 'Improve'}
              </button>
            </div>
          )}
          
          <button
            onClick={() => setShowPreview(!showPreview)}
            className={clsx(
              'p-1.5 rounded transition-colors',
              showPreview ? 'bg-accent-500/20 text-accent-400' : 'hover:bg-surface-700 text-surface-400'
            )}
            title="Toggle preview"
          >
            {showPreview ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
          
          <button
            onClick={() => updateField('isHtml', !composeData.isHtml)}
            className={clsx(
              'px-2 py-1 rounded text-xs transition-colors',
              composeData.isHtml 
                ? 'bg-accent-500/20 text-accent-400' 
                : 'bg-surface-700 text-surface-300'
            )}
          >
            {composeData.isHtml ? 'Rich' : 'Plain'}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex flex-col min-h-0">
        {showPreview ? (
          <div className="flex-1 p-4 overflow-y-auto prose prose-invert prose-sm max-w-none">
            <div dangerouslySetInnerHTML={{ __html: composeData.htmlContent || composeData.content }} />
          </div>
        ) : composeData.isHtml ? (
          <div
            ref={htmlContentRef}
            contentEditable
            className="flex-1 p-4 overflow-y-auto focus:outline-none text-surface-200"
            style={{ minHeight: '200px' }}
            onInput={(e) => {
              updateField('htmlContent', e.currentTarget.innerHTML);
              updateField('content', e.currentTarget.textContent || '');
            }}
            dangerouslySetInnerHTML={{ __html: composeData.htmlContent }}
          />
        ) : (
          <textarea
            ref={contentRef}
            value={composeData.content}
            onChange={(e) => updateField('content', e.target.value)}
            placeholder="Write your message..."
            className="flex-1 p-4 bg-transparent border-none resize-none focus:outline-none text-surface-200 placeholder-surface-500"
          />
        )}
      </div>

      {/* Attachments */}
      {composeData.attachments.length > 0 && (
        <div className="p-3 border-t border-surface-700">
          <div className="flex items-center space-x-2 mb-2">
            <Paperclip className="w-4 h-4 text-surface-400" />
            <span className="text-sm font-medium text-surface-300">
              Attachments ({composeData.attachments.length})
            </span>
          </div>
          <div className="space-y-1">
            {composeData.attachments.map((file, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-2 bg-surface-800 rounded"
              >
                <div className="flex items-center space-x-2">
                  <Paperclip className="w-3 h-3 text-surface-400" />
                  <span className="text-sm text-surface-200">{file.name}</span>
                  <span className="text-xs text-surface-400">
                    ({formatFileSize(file.size)})
                  </span>
                </div>
                <button
                  onClick={() => removeAttachment(index)}
                  className="p-1 hover:bg-surface-700 rounded transition-colors"
                >
                  <X className="w-3 h-3 text-surface-400" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between p-3 border-t border-surface-700">
        <div className="flex items-center space-x-2">
          <button
            onClick={handleSend}
            disabled={isSending || composeData.to.length === 0}
            className="flex items-center space-x-2 px-4 py-2 bg-accent-500 hover:bg-accent-600 disabled:bg-surface-600 text-white rounded-lg font-medium transition-colors"
          >
            <Send className="w-4 h-4" />
            <span>{isSending ? 'Sending...' : 'Send'}</span>
          </button>
          
          <button
            onClick={handleSaveDraft}
            disabled={isDraftSaving}
            className="flex items-center space-x-2 px-3 py-2 bg-surface-700 hover:bg-surface-600 text-surface-200 rounded-lg transition-colors"
          >
            <Save className="w-4 h-4" />
            <span>Draft</span>
          </button>
        </div>

        <button
          onClick={onClose}
          className="flex items-center space-x-2 px-3 py-2 text-surface-400 hover:text-surface-200 transition-colors"
        >
          <Trash2 className="w-4 h-4" />
          <span>Discard</span>
        </button>
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => handleFileUpload(e.target.files)}
      />
    </div>
  );
};

export default ComposeWindow;