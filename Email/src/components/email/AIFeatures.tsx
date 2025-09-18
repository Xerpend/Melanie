import React, { useState } from 'react';
import { 
  Bot, 
  Sparkles, 
  Reply, 
  FileText, 
  Loader2, 
  CheckCircle, 
  AlertCircle,
  Copy,
  Download,
  X
} from 'lucide-react';
import { clsx } from 'clsx';

export interface AIAnalysisResult {
  sentiment: 'positive' | 'negative' | 'neutral';
  category: string;
  priority: 'low' | 'normal' | 'high';
  keywords: string[];
  summary: string;
  actionItems?: string[];
}

export interface AIDraftReply {
  content: string;
  tone: 'professional' | 'casual' | 'formal';
  confidence: number;
  suggestions?: string[];
}

export interface AIThreadSummary {
  summary: string;
  keyPoints: string[];
  participants: string[];
  timeline: string;
  actionItems?: string[];
}

interface AIFeaturesProps {
  threadId: string;
  threadSubject: string;
  threadMessages: Array<{
    id: string;
    sender: { name: string; email: string };
    content: string;
    date: Date;
  }>;
  onSummarizeThread?: (threadId: string) => Promise<AIThreadSummary>;
  onDraftReply?: (threadId: string, context?: string) => Promise<AIDraftReply>;
  onAnalyzeThread?: (threadId: string) => Promise<AIAnalysisResult>;
  onInsertReply?: (content: string) => void;
  className?: string;
}

interface AIResultModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

const AIResultModal: React.FC<AIResultModalProps> = ({ isOpen, onClose, title, children }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-surface-800 rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-surface-700">
          <h3 className="text-lg font-semibold text-primary-50">{title}</h3>
          <button
            onClick={onClose}
            className="p-2 hover:bg-surface-700 rounded-lg transition-colors"
          >
            <X className="w-4 h-4 text-surface-400" />
          </button>
        </div>
        <div className="p-4 overflow-y-auto max-h-[60vh]">
          {children}
        </div>
      </div>
    </div>
  );
};

const ThreadSummaryResult: React.FC<{ summary: AIThreadSummary }> = ({ summary }) => {
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <div className="space-y-4">
      <div>
        <h4 className="font-medium text-surface-200 mb-2">Summary</h4>
        <p className="text-surface-300 leading-relaxed">{summary.summary}</p>
        <button
          onClick={() => copyToClipboard(summary.summary)}
          className="mt-2 flex items-center space-x-1 text-xs text-accent-400 hover:text-accent-300"
        >
          <Copy className="w-3 h-3" />
          <span>Copy summary</span>
        </button>
      </div>

      {summary.keyPoints.length > 0 && (
        <div>
          <h4 className="font-medium text-surface-200 mb-2">Key Points</h4>
          <ul className="space-y-1">
            {summary.keyPoints.map((point, index) => (
              <li key={index} className="text-surface-300 text-sm flex items-start">
                <span className="text-accent-400 mr-2">•</span>
                {point}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <h4 className="font-medium text-surface-200 mb-2">Participants</h4>
          <div className="space-y-1">
            {summary.participants.map((participant, index) => (
              <span key={index} className="text-surface-300 text-sm block">
                {participant}
              </span>
            ))}
          </div>
        </div>

        <div>
          <h4 className="font-medium text-surface-200 mb-2">Timeline</h4>
          <p className="text-surface-300 text-sm">{summary.timeline}</p>
        </div>
      </div>

      {summary.actionItems && summary.actionItems.length > 0 && (
        <div>
          <h4 className="font-medium text-surface-200 mb-2">Action Items</h4>
          <ul className="space-y-1">
            {summary.actionItems.map((item, index) => (
              <li key={index} className="text-surface-300 text-sm flex items-start">
                <CheckCircle className="w-3 h-3 text-green-400 mr-2 mt-0.5 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

const DraftReplyResult: React.FC<{ 
  draft: AIDraftReply; 
  onInsert?: (content: string) => void;
}> = ({ draft, onInsert }) => {
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const getToneColor = (tone: string) => {
    switch (tone) {
      case 'professional': return 'text-blue-400';
      case 'casual': return 'text-green-400';
      case 'formal': return 'text-purple-400';
      default: return 'text-surface-400';
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-400';
    if (confidence >= 0.6) return 'text-yellow-400';
    return 'text-red-400';
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-1">
            <span className="text-sm text-surface-400">Tone:</span>
            <span className={clsx('text-sm font-medium capitalize', getToneColor(draft.tone))}>
              {draft.tone}
            </span>
          </div>
          <div className="flex items-center space-x-1">
            <span className="text-sm text-surface-400">Confidence:</span>
            <span className={clsx('text-sm font-medium', getConfidenceColor(draft.confidence))}>
              {Math.round(draft.confidence * 100)}%
            </span>
          </div>
        </div>
      </div>

      <div>
        <h4 className="font-medium text-surface-200 mb-2">Draft Reply</h4>
        <div className="bg-surface-900 rounded-lg p-3 border border-surface-700">
          <p className="text-surface-300 leading-relaxed whitespace-pre-wrap">
            {draft.content}
          </p>
        </div>
      </div>

      <div className="flex items-center space-x-2">
        <button
          onClick={() => copyToClipboard(draft.content)}
          className="flex items-center space-x-1 px-3 py-1.5 bg-surface-700 hover:bg-surface-600 text-surface-200 rounded-lg text-sm transition-colors"
        >
          <Copy className="w-3 h-3" />
          <span>Copy</span>
        </button>
        
        {onInsert && (
          <button
            onClick={() => onInsert(draft.content)}
            className="flex items-center space-x-1 px-3 py-1.5 bg-accent-500 hover:bg-accent-600 text-white rounded-lg text-sm transition-colors"
          >
            <Reply className="w-3 h-3" />
            <span>Use as Reply</span>
          </button>
        )}
      </div>

      {draft.suggestions && draft.suggestions.length > 0 && (
        <div>
          <h4 className="font-medium text-surface-200 mb-2">Suggestions</h4>
          <ul className="space-y-1">
            {draft.suggestions.map((suggestion, index) => (
              <li key={index} className="text-surface-300 text-sm flex items-start">
                <span className="text-accent-400 mr-2">•</span>
                {suggestion}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

const AnalysisResult: React.FC<{ analysis: AIAnalysisResult }> = ({ analysis }) => {
  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'positive': return 'text-green-400';
      case 'negative': return 'text-red-400';
      case 'neutral': return 'text-yellow-400';
      default: return 'text-surface-400';
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high': return 'text-red-400';
      case 'normal': return 'text-yellow-400';
      case 'low': return 'text-green-400';
      default: return 'text-surface-400';
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <div>
          <h4 className="font-medium text-surface-200 mb-1">Sentiment</h4>
          <span className={clsx('text-sm font-medium capitalize', getSentimentColor(analysis.sentiment))}>
            {analysis.sentiment}
          </span>
        </div>
        
        <div>
          <h4 className="font-medium text-surface-200 mb-1">Category</h4>
          <span className="text-surface-300 text-sm">{analysis.category}</span>
        </div>
        
        <div>
          <h4 className="font-medium text-surface-200 mb-1">Priority</h4>
          <span className={clsx('text-sm font-medium capitalize', getPriorityColor(analysis.priority))}>
            {analysis.priority}
          </span>
        </div>
      </div>

      <div>
        <h4 className="font-medium text-surface-200 mb-2">Summary</h4>
        <p className="text-surface-300 leading-relaxed">{analysis.summary}</p>
      </div>

      {analysis.keywords.length > 0 && (
        <div>
          <h4 className="font-medium text-surface-200 mb-2">Keywords</h4>
          <div className="flex flex-wrap gap-2">
            {analysis.keywords.map((keyword, index) => (
              <span
                key={index}
                className="px-2 py-1 bg-accent-500/20 text-accent-400 rounded text-xs"
              >
                {keyword}
              </span>
            ))}
          </div>
        </div>
      )}

      {analysis.actionItems && analysis.actionItems.length > 0 && (
        <div>
          <h4 className="font-medium text-surface-200 mb-2">Action Items</h4>
          <ul className="space-y-1">
            {analysis.actionItems.map((item, index) => (
              <li key={index} className="text-surface-300 text-sm flex items-start">
                <CheckCircle className="w-3 h-3 text-green-400 mr-2 mt-0.5 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export const AIFeatures: React.FC<AIFeaturesProps> = ({
  threadId,
  threadSubject,
  threadMessages,
  onSummarizeThread,
  onDraftReply,
  onAnalyzeThread,
  onInsertReply,
  className
}) => {
  const [loadingStates, setLoadingStates] = useState<{
    summarize: boolean;
    draft: boolean;
    analyze: boolean;
  }>({
    summarize: false,
    draft: false,
    analyze: false
  });

  const [results, setResults] = useState<{
    summary?: AIThreadSummary;
    draft?: AIDraftReply;
    analysis?: AIAnalysisResult;
  }>({});

  const [activeModal, setActiveModal] = useState<'summary' | 'draft' | 'analysis' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSummarizeThread = async () => {
    if (!onSummarizeThread) return;

    setLoadingStates(prev => ({ ...prev, summarize: true }));
    setError(null);

    try {
      const summary = await onSummarizeThread(threadId);
      setResults(prev => ({ ...prev, summary }));
      setActiveModal('summary');
    } catch (err) {
      setError(`Failed to summarize thread: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setLoadingStates(prev => ({ ...prev, summarize: false }));
    }
  };

  const handleDraftReply = async () => {
    if (!onDraftReply) return;

    setLoadingStates(prev => ({ ...prev, draft: true }));
    setError(null);

    try {
      // Create context from recent messages
      const recentMessages = threadMessages.slice(-3);
      const context = recentMessages.map(msg => 
        `${msg.sender.name}: ${msg.content}`
      ).join('\n\n');

      const draft = await onDraftReply(threadId, context);
      setResults(prev => ({ ...prev, draft }));
      setActiveModal('draft');
    } catch (err) {
      setError(`Failed to draft reply: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setLoadingStates(prev => ({ ...prev, draft: false }));
    }
  };

  const handleAnalyzeThread = async () => {
    if (!onAnalyzeThread) return;

    setLoadingStates(prev => ({ ...prev, analyze: true }));
    setError(null);

    try {
      const analysis = await onAnalyzeThread(threadId);
      setResults(prev => ({ ...prev, analysis }));
      setActiveModal('analysis');
    } catch (err) {
      setError(`Failed to analyze thread: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setLoadingStates(prev => ({ ...prev, analyze: false }));
    }
  };

  const closeModal = () => {
    setActiveModal(null);
  };

  return (
    <>
      <div className={clsx('flex items-center space-x-2', className)}>
        <div className="flex items-center space-x-1 text-xs text-surface-400">
          <Bot className="w-3 h-3" />
          <span>AI Assistant:</span>
        </div>
        
        <button
          onClick={handleSummarizeThread}
          disabled={loadingStates.summarize || !onSummarizeThread}
          className="flex items-center space-x-1 px-2 py-1 bg-accent-500/20 hover:bg-accent-500/30 disabled:bg-surface-700 disabled:text-surface-500 text-accent-400 rounded text-xs transition-colors"
        >
          {loadingStates.summarize ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <Sparkles className="w-3 h-3" />
          )}
          <span>Summarize Thread</span>
        </button>
        
        <button
          onClick={handleDraftReply}
          disabled={loadingStates.draft || !onDraftReply}
          className="flex items-center space-x-1 px-2 py-1 bg-accent-500/20 hover:bg-accent-500/30 disabled:bg-surface-700 disabled:text-surface-500 text-accent-400 rounded text-xs transition-colors"
        >
          {loadingStates.draft ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <Reply className="w-3 h-3" />
          )}
          <span>Draft Reply</span>
        </button>
        
        <button
          onClick={handleAnalyzeThread}
          disabled={loadingStates.analyze || !onAnalyzeThread}
          className="flex items-center space-x-1 px-2 py-1 bg-accent-500/20 hover:bg-accent-500/30 disabled:bg-surface-700 disabled:text-surface-500 text-accent-400 rounded text-xs transition-colors"
        >
          {loadingStates.analyze ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <FileText className="w-3 h-3" />
          )}
          <span>Analyze</span>
        </button>

        {error && (
          <div className="flex items-center space-x-1 text-xs text-red-400">
            <AlertCircle className="w-3 h-3" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Modals */}
      <AIResultModal
        isOpen={activeModal === 'summary'}
        onClose={closeModal}
        title="Thread Summary"
      >
        {results.summary && <ThreadSummaryResult summary={results.summary} />}
      </AIResultModal>

      <AIResultModal
        isOpen={activeModal === 'draft'}
        onClose={closeModal}
        title="Draft Reply"
      >
        {results.draft && (
          <DraftReplyResult 
            draft={results.draft} 
            onInsert={onInsertReply}
          />
        )}
      </AIResultModal>

      <AIResultModal
        isOpen={activeModal === 'analysis'}
        onClose={closeModal}
        title="Thread Analysis"
      >
        {results.analysis && <AnalysisResult analysis={results.analysis} />}
      </AIResultModal>
    </>
  );
};

export default AIFeatures;