import React, { useState } from 'react';
import { 
  Folder, 
  FolderOpen, 
  Inbox, 
  Send, 
  FileText, 
  Flag, 
  Archive, 
  Trash2, 
  Plus,
  ChevronRight,
  ChevronDown
} from 'lucide-react';
import { clsx } from 'clsx';

export interface EmailFolder {
  id: string;
  name: string;
  type: 'inbox' | 'sent' | 'drafts' | 'flagged' | 'archive' | 'trash' | 'custom';
  count: number;
  unreadCount?: number;
  children?: EmailFolder[];
  expanded?: boolean;
}

interface FolderTreeProps {
  folders: EmailFolder[];
  selectedFolderId?: string;
  onFolderSelect: (folderId: string) => void;
  onFolderToggle?: (folderId: string) => void;
  onCreateFolder?: () => void;
  className?: string;
}

const FolderIcon: React.FC<{ type: EmailFolder['type']; expanded?: boolean }> = ({ type, expanded }) => {
  const iconClass = "w-4 h-4";
  
  switch (type) {
    case 'inbox':
      return <Inbox className={iconClass} />;
    case 'sent':
      return <Send className={iconClass} />;
    case 'drafts':
      return <FileText className={iconClass} />;
    case 'flagged':
      return <Flag className={iconClass} />;
    case 'archive':
      return <Archive className={iconClass} />;
    case 'trash':
      return <Trash2 className={iconClass} />;
    case 'custom':
    default:
      return expanded ? <FolderOpen className={iconClass} /> : <Folder className={iconClass} />;
  }
};

const FolderItem: React.FC<{
  folder: EmailFolder;
  level: number;
  selectedFolderId?: string;
  onFolderSelect: (folderId: string) => void;
  onFolderToggle?: (folderId: string) => void;
}> = ({ folder, level, selectedFolderId, onFolderSelect, onFolderToggle }) => {
  const isSelected = selectedFolderId === folder.id;
  const hasChildren = folder.children && folder.children.length > 0;
  const isExpanded = folder.expanded;

  const handleClick = () => {
    onFolderSelect(folder.id);
  };

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (hasChildren && onFolderToggle) {
      onFolderToggle(folder.id);
    }
  };

  const getCountColor = (type: EmailFolder['type']) => {
    switch (type) {
      case 'inbox':
        return 'text-unread bg-accent-500/20';
      case 'sent':
        return 'text-sent bg-sent/20';
      case 'drafts':
        return 'text-draft bg-draft/20';
      case 'flagged':
        return 'text-flagged bg-flagged/20';
      case 'archive':
        return 'text-archived bg-archived/20';
      default:
        return 'text-surface-400 bg-surface-800';
    }
  };

  return (
    <div>
      <div
        className={clsx(
          'flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-all duration-200',
          'hover:bg-surface-800/50',
          isSelected && 'bg-accent-500/20 border border-accent-500/30',
          level > 0 && 'ml-4'
        )}
        onClick={handleClick}
        style={{ paddingLeft: `${12 + level * 16}px` }}
      >
        <div className="flex items-center space-x-2 flex-1 min-w-0">
          {hasChildren && (
            <button
              onClick={handleToggle}
              className="p-0.5 hover:bg-surface-700 rounded transition-colors"
            >
              {isExpanded ? (
                <ChevronDown className="w-3 h-3" />
              ) : (
                <ChevronRight className="w-3 h-3" />
              )}
            </button>
          )}
          
          <FolderIcon type={folder.type} expanded={isExpanded} />
          
          <span className="text-sm font-medium truncate">
            {folder.name}
          </span>
        </div>

        {(folder.count > 0 || folder.unreadCount) && (
          <div className="flex items-center space-x-1">
            {folder.unreadCount && folder.unreadCount > 0 && (
              <span className={clsx(
                'text-xs px-2 py-0.5 rounded-full font-medium',
                getCountColor(folder.type)
              )}>
                {folder.unreadCount}
              </span>
            )}
            {folder.count > 0 && !folder.unreadCount && (
              <span className="text-xs text-surface-400 px-2 py-0.5 rounded-full bg-surface-800">
                {folder.count}
              </span>
            )}
          </div>
        )}
      </div>

      {hasChildren && isExpanded && (
        <div className="mt-1">
          {folder.children!.map((child) => (
            <FolderItem
              key={child.id}
              folder={child}
              level={level + 1}
              selectedFolderId={selectedFolderId}
              onFolderSelect={onFolderSelect}
              onFolderToggle={onFolderToggle}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export const FolderTree: React.FC<FolderTreeProps> = ({
  folders,
  selectedFolderId,
  onFolderSelect,
  onFolderToggle,
  onCreateFolder,
  className
}) => {
  return (
    <div className={clsx('space-y-1', className)}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-surface-300">Folders</h3>
        {onCreateFolder && (
          <button
            onClick={onCreateFolder}
            className="p-1 hover:bg-surface-800 rounded transition-colors"
            title="Create new folder"
          >
            <Plus className="w-3 h-3" />
          </button>
        )}
      </div>
      
      <div className="space-y-1">
        {folders.map((folder) => (
          <FolderItem
            key={folder.id}
            folder={folder}
            level={0}
            selectedFolderId={selectedFolderId}
            onFolderSelect={onFolderSelect}
            onFolderToggle={onFolderToggle}
          />
        ))}
      </div>
    </div>
  );
};

export default FolderTree;