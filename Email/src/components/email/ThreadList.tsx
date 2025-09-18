import React, { useState, useMemo } from 'react';
import { 
  Mail, 
  MailOpen, 
  Flag, 
  Paperclip, 
  Star, 
  Archive, 
  Trash2,
  MoreHorizontal,
  ChevronDown,
  Search,
  Filter,
  SortAsc,
  SortDesc
} from 'lucide-react';
import { clsx } from 'clsx';

export interface EmailThread {
  id: string;
  subject: string;
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
  preview: string;
  date: Date;
  isRead: boolean;
  isFlagged: boolean;
  isStarred: boolean;
  hasAttachments: boolean;
  messageCount: number;
  labels?: string[];
  priority: 'low' | 'normal' | 'high';
}

interface ThreadListProps {
  threads: EmailThread[];
  selectedThreadId?: string;
  onThreadSelect: (threadId: string) => void;
  onThreadAction?: (threadId: string, action: 'flag' | 'star' | 'archive' | 'delete' | 'markRead' | 'markUnread') => void;
  className?: string;
}

type SortField = 'date' | 'sender' | 'subject';
type SortDirection = 'asc' | 'desc';

interface FilterOptions {
  unreadOnly: boolean;
  flaggedOnly: boolean;
  hasAttachments: boolean;
  priority: 'all' | 'high' | 'normal' | 'low';
}

const ThreadItem: React.FC<{
  thread: EmailThread;
  isSelected: boolean;
  onSelect: () => void;
  onAction?: (action: 'flag' | 'star' | 'archive' | 'delete' | 'markRead' | 'markUnread') => void;
}> = ({ thread, isSelected, onSelect, onAction }) => {
  const [showActions, setShowActions] = useState(false);

  const formatDate = (date: Date) => {
    const now = new Date();
    const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60);
    
    if (diffInHours < 24) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (diffInHours < 24 * 7) {
      return date.toLocaleDateString([], { weekday: 'short' });
    } else {
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
  };

  const getPriorityColor = (priority: EmailThread['priority']) => {
    switch (priority) {
      case 'high':
        return 'border-l-red-500';
      case 'low':
        return 'border-l-blue-500';
      default:
        return 'border-l-transparent';
    }
  };

  const handleAction = (action: 'flag' | 'star' | 'archive' | 'delete' | 'markRead' | 'markUnread') => {
    if (onAction) {
      onAction(action);
    }
  };

  return (
    <div
      className={clsx(
        'border-l-2 bg-surface-900 hover:bg-surface-800/50 cursor-pointer transition-all duration-200',
        'border-b border-surface-700/50',
        isSelected && 'bg-accent-500/10 border-r-2 border-r-accent-500',
        !thread.isRead && 'bg-surface-800/30',
        getPriorityColor(thread.priority)
      )}
      onClick={onSelect}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      <div className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-start space-x-3 flex-1 min-w-0">
            {/* Avatar */}
            <div className="flex-shrink-0">
              {thread.sender.avatar ? (
                <img
                  src={thread.sender.avatar}
                  alt={thread.sender.name}
                  className="w-8 h-8 rounded-full"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-accent-500/20 flex items-center justify-center">
                  <span className="text-xs font-medium text-accent-400">
                    {thread.sender.name.charAt(0).toUpperCase()}
                  </span>
                </div>
              )}
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center space-x-2 min-w-0">
                  <span className={clsx(
                    'text-sm font-medium truncate',
                    !thread.isRead ? 'text-primary-50' : 'text-surface-300'
                  )}>
                    {thread.sender.name}
                  </span>
                  {thread.messageCount > 1 && (
                    <span className="text-xs text-surface-400 bg-surface-700 px-2 py-0.5 rounded-full">
                      {thread.messageCount}
                    </span>
                  )}
                </div>
                
                <div className="flex items-center space-x-1 flex-shrink-0">
                  <span className="text-xs text-surface-400">
                    {formatDate(thread.date)}
                  </span>
                </div>
              </div>

              <div className="mb-2">
                <h4 className={clsx(
                  'text-sm truncate',
                  !thread.isRead ? 'font-semibold text-primary-50' : 'font-medium text-surface-200'
                )}>
                  {thread.subject}
                </h4>
              </div>

              <p className="text-xs text-surface-400 line-clamp-2 mb-2">
                {thread.preview}
              </p>

              {/* Labels and indicators */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  {thread.labels && thread.labels.length > 0 && (
                    <div className="flex items-center space-x-1">
                      {thread.labels.slice(0, 2).map((label) => (
                        <span
                          key={label}
                          className="text-xs px-2 py-0.5 rounded-full bg-accent-500/20 text-accent-400"
                        >
                          {label}
                        </span>
                      ))}
                      {thread.labels.length > 2 && (
                        <span className="text-xs text-surface-400">
                          +{thread.labels.length - 2}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                <div className="flex items-center space-x-1">
                  {thread.hasAttachments && (
                    <Paperclip className="w-3 h-3 text-surface-400" />
                  )}
                  {thread.isFlagged && (
                    <Flag className="w-3 h-3 text-flagged fill-current" />
                  )}
                  {thread.isStarred && (
                    <Star className="w-3 h-3 text-flagged fill-current" />
                  )}
                  {!thread.isRead && (
                    <div className="w-2 h-2 bg-accent-500 rounded-full"></div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Actions */}
          {showActions && (
            <div className="flex items-center space-x-1 ml-2 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleAction(thread.isRead ? 'markUnread' : 'markRead');
                }}
                className="p-1 hover:bg-surface-700 rounded transition-colors"
                title={thread.isRead ? 'Mark as unread' : 'Mark as read'}
              >
                {thread.isRead ? <Mail className="w-3 h-3" /> : <MailOpen className="w-3 h-3" />}
              </button>
              
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleAction('flag');
                }}
                className="p-1 hover:bg-surface-700 rounded transition-colors"
                title="Toggle flag"
              >
                <Flag className={clsx(
                  'w-3 h-3',
                  thread.isFlagged ? 'text-flagged fill-current' : 'text-surface-400'
                )} />
              </button>
              
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleAction('star');
                }}
                className="p-1 hover:bg-surface-700 rounded transition-colors"
                title="Toggle star"
              >
                <Star className={clsx(
                  'w-3 h-3',
                  thread.isStarred ? 'text-flagged fill-current' : 'text-surface-400'
                )} />
              </button>
              
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleAction('archive');
                }}
                className="p-1 hover:bg-surface-700 rounded transition-colors"
                title="Archive"
              >
                <Archive className="w-3 h-3 text-surface-400" />
              </button>
              
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleAction('delete');
                }}
                className="p-1 hover:bg-surface-700 rounded transition-colors"
                title="Delete"
              >
                <Trash2 className="w-3 h-3 text-surface-400" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export const ThreadList: React.FC<ThreadListProps> = ({
  threads,
  selectedThreadId,
  onThreadSelect,
  onThreadAction,
  className
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState<SortField>('date');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [filters, setFilters] = useState<FilterOptions>({
    unreadOnly: false,
    flaggedOnly: false,
    hasAttachments: false,
    priority: 'all'
  });
  const [showFilters, setShowFilters] = useState(false);

  const filteredAndSortedThreads = useMemo(() => {
    let filtered = threads;

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(thread =>
        thread.subject.toLowerCase().includes(query) ||
        thread.sender.name.toLowerCase().includes(query) ||
        thread.sender.email.toLowerCase().includes(query) ||
        thread.preview.toLowerCase().includes(query)
      );
    }

    // Apply filters
    if (filters.unreadOnly) {
      filtered = filtered.filter(thread => !thread.isRead);
    }
    if (filters.flaggedOnly) {
      filtered = filtered.filter(thread => thread.isFlagged);
    }
    if (filters.hasAttachments) {
      filtered = filtered.filter(thread => thread.hasAttachments);
    }
    if (filters.priority !== 'all') {
      filtered = filtered.filter(thread => thread.priority === filters.priority);
    }

    // Apply sorting
    filtered.sort((a, b) => {
      let comparison = 0;
      
      switch (sortField) {
        case 'date':
          comparison = a.date.getTime() - b.date.getTime();
          break;
        case 'sender':
          comparison = a.sender.name.localeCompare(b.sender.name);
          break;
        case 'subject':
          comparison = a.subject.localeCompare(b.subject);
          break;
      }
      
      return sortDirection === 'asc' ? comparison : -comparison;
    });

    return filtered;
  }, [threads, searchQuery, sortField, sortDirection, filters]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const activeFiltersCount = Object.values(filters).filter(value => 
    typeof value === 'boolean' ? value : value !== 'all'
  ).length;

  return (
    <div className={clsx('flex flex-col h-full', className)}>
      {/* Header with search and controls */}
      <div className="p-4 border-b border-surface-700 space-y-3">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-surface-400" />
          <input
            type="text"
            placeholder="Search emails..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-surface-800 border border-surface-600 rounded-lg text-sm focus:border-accent-500 focus:outline-none"
          />
        </div>

        {/* Controls */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={clsx(
                'flex items-center space-x-1 px-3 py-1.5 rounded-lg text-sm transition-colors',
                showFilters || activeFiltersCount > 0
                  ? 'bg-accent-500/20 text-accent-400'
                  : 'bg-surface-800 text-surface-300 hover:bg-surface-700'
              )}
            >
              <Filter className="w-3 h-3" />
              <span>Filter</span>
              {activeFiltersCount > 0 && (
                <span className="bg-accent-500 text-white text-xs px-1.5 py-0.5 rounded-full">
                  {activeFiltersCount}
                </span>
              )}
            </button>

            <div className="flex items-center space-x-1">
              <span className="text-xs text-surface-400">Sort by:</span>
              {(['date', 'sender', 'subject'] as SortField[]).map((field) => (
                <button
                  key={field}
                  onClick={() => handleSort(field)}
                  className={clsx(
                    'flex items-center space-x-1 px-2 py-1 rounded text-xs transition-colors',
                    sortField === field
                      ? 'bg-accent-500/20 text-accent-400'
                      : 'text-surface-400 hover:text-surface-300'
                  )}
                >
                  <span className="capitalize">{field}</span>
                  {sortField === field && (
                    sortDirection === 'asc' ? <SortAsc className="w-3 h-3" /> : <SortDesc className="w-3 h-3" />
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="text-xs text-surface-400">
            {filteredAndSortedThreads.length} of {threads.length} emails
          </div>
        </div>

        {/* Filter options */}
        {showFilters && (
          <div className="bg-surface-800 rounded-lg p-3 space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={filters.unreadOnly}
                  onChange={(e) => setFilters(prev => ({ ...prev, unreadOnly: e.target.checked }))}
                  className="rounded border-surface-600 bg-surface-700 text-accent-500 focus:ring-accent-500"
                />
                <span className="text-sm">Unread only</span>
              </label>
              
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={filters.flaggedOnly}
                  onChange={(e) => setFilters(prev => ({ ...prev, flaggedOnly: e.target.checked }))}
                  className="rounded border-surface-600 bg-surface-700 text-accent-500 focus:ring-accent-500"
                />
                <span className="text-sm">Flagged only</span>
              </label>
              
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={filters.hasAttachments}
                  onChange={(e) => setFilters(prev => ({ ...prev, hasAttachments: e.target.checked }))}
                  className="rounded border-surface-600 bg-surface-700 text-accent-500 focus:ring-accent-500"
                />
                <span className="text-sm">Has attachments</span>
              </label>
              
              <div className="flex items-center space-x-2">
                <span className="text-sm">Priority:</span>
                <select
                  value={filters.priority}
                  onChange={(e) => setFilters(prev => ({ ...prev, priority: e.target.value as FilterOptions['priority'] }))}
                  className="bg-surface-700 border border-surface-600 rounded text-sm px-2 py-1"
                >
                  <option value="all">All</option>
                  <option value="high">High</option>
                  <option value="normal">Normal</option>
                  <option value="low">Low</option>
                </select>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Thread list */}
      <div className="flex-1 overflow-y-auto">
        {filteredAndSortedThreads.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <Mail className="w-12 h-12 text-surface-600 mx-auto mb-3" />
              <p className="text-surface-400">
                {searchQuery || activeFiltersCount > 0 ? 'No emails match your criteria' : 'No emails in this folder'}
              </p>
            </div>
          </div>
        ) : (
          <div className="group">
            {filteredAndSortedThreads.map((thread) => (
              <ThreadItem
                key={thread.id}
                thread={thread}
                isSelected={selectedThreadId === thread.id}
                onSelect={() => onThreadSelect(thread.id)}
                onAction={onThreadAction ? (action) => onThreadAction(thread.id, action) : undefined}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ThreadList;