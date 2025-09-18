'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { StudiosFile } from '@/types/chat';
import { apiClient } from '@/lib/api';
import { FileUploadResponse } from '@/types/api';

interface StudiosPanelProps {
  onClose: () => void;
}

interface ProcessingStatus {
  [fileId: string]: {
    status: 'uploading' | 'processing' | 'completed' | 'error';
    progress: number;
    message: string;
  };
}

interface RAGStats {
  totalFiles: number;
  ragIngestedFiles: number;
  isActive: boolean;
  lastUpdate?: Date;
}

export const StudiosPanel: React.FC<StudiosPanelProps> = ({ onClose }) => {
  const [files, setFiles] = useState<StudiosFile[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [processingStatus, setProcessingStatus] = useState<ProcessingStatus>({});
  const [ragStats, setRAGStats] = useState<RAGStats>({
    totalFiles: 0,
    ragIngestedFiles: 0,
    isActive: false
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFile, setSelectedFile] = useState<StudiosFile | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load files on component mount
  useEffect(() => {
    loadFiles();
  }, []);

  const loadFiles = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await apiClient.getFiles();
      if (response.success && response.data) {
        const studiosFiles: StudiosFile[] = response.data.map((file: FileUploadResponse) => ({
          id: file.id,
          filename: file.filename,
          contentType: file.content_type,
          size: file.size,
          processed: file.processed,
          ragIngested: file.rag_ingested,
          uploadedAt: new Date(),
          preview: generatePreview(file),
          metadata: {}
        }));
        
        setFiles(studiosFiles);
        updateRAGStats(studiosFiles);
      } else {
        setError(response.message || 'Failed to load files');
      }
    } catch (err) {
      setError('Failed to connect to API');
      console.error('Failed to load files:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const generatePreview = (file: FileUploadResponse): string => {
    if (file.content_type.startsWith('text/') || file.content_type === 'application/json') {
      return `Text file • ${file.processed ? 'Processed' : 'Ready for processing'}`;
    } else if (file.content_type === 'application/pdf') {
      return `PDF document • ${file.processed ? 'Metadata extracted' : 'Ready for analysis'}`;
    } else if (file.content_type.startsWith('image/')) {
      return `Image file • ${file.processed ? 'Ready for multimodal' : 'Processing...'}`;
    }
    return `${file.content_type} • ${(file.size / 1024).toFixed(1)} KB`;
  };

  const updateRAGStats = (fileList: StudiosFile[]) => {
    const stats: RAGStats = {
      totalFiles: fileList.length,
      ragIngestedFiles: fileList.filter(f => f.ragIngested).length,
      isActive: fileList.some(f => f.ragIngested),
      lastUpdate: new Date()
    };
    setRAGStats(stats);
  };

  const handleFileUpload = async (uploadedFiles: FileList) => {
    const fileArray = Array.from(uploadedFiles);
    
    for (const file of fileArray) {
      const tempId = `temp-${Date.now()}-${Math.random()}`;
      
      // Add processing status
      setProcessingStatus(prev => ({
        ...prev,
        [tempId]: {
          status: 'uploading',
          progress: 0,
          message: 'Uploading...'
        }
      }));

      try {
        // Update progress
        setProcessingStatus(prev => ({
          ...prev,
          [tempId]: {
            status: 'uploading',
            progress: 50,
            message: 'Uploading to server...'
          }
        }));

        const response = await apiClient.uploadFile(file);
        
        if (response.success && response.data) {
          // Update to processing
          setProcessingStatus(prev => ({
            ...prev,
            [tempId]: {
              status: 'processing',
              progress: 75,
              message: 'Processing file...'
            }
          }));

          // Add to files list
          const newFile: StudiosFile = {
            id: response.data.id,
            filename: response.data.filename,
            contentType: response.data.content_type,
            size: response.data.size,
            processed: response.data.processed,
            ragIngested: response.data.rag_ingested,
            uploadedAt: new Date(),
            preview: generatePreview(response.data),
            metadata: {}
          };

          setFiles(prev => [newFile, ...prev]);
          updateRAGStats([newFile, ...files]);

          // Complete processing
          setProcessingStatus(prev => ({
            ...prev,
            [tempId]: {
              status: 'completed',
              progress: 100,
              message: 'Upload completed'
            }
          }));

          // Remove processing status after delay
          setTimeout(() => {
            setProcessingStatus(prev => {
              const { [tempId]: removed, ...rest } = prev;
              return rest;
            });
          }, 2000);

        } else {
          throw new Error(response.message || 'Upload failed');
        }
      } catch (err) {
        console.error('Upload failed:', err);
        setProcessingStatus(prev => ({
          ...prev,
          [tempId]: {
            status: 'error',
            progress: 0,
            message: err instanceof Error ? err.message : 'Upload failed'
          }
        }));

        // Remove error status after delay
        setTimeout(() => {
          setProcessingStatus(prev => {
            const { [tempId]: removed, ...rest } = prev;
            return rest;
          });
        }, 5000);
      }
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    
    if (e.dataTransfer.files) {
      handleFileUpload(e.dataTransfer.files);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      handleFileUpload(e.target.files);
    }
  };

  const handleDeleteFile = async (fileId: string) => {
    try {
      const response = await apiClient.deleteFile(fileId);
      if (response.success) {
        setFiles(prev => prev.filter(f => f.id !== fileId));
        updateRAGStats(files.filter(f => f.id !== fileId));
      } else {
        setError(response.message || 'Failed to delete file');
      }
    } catch (err) {
      setError('Failed to delete file');
      console.error('Delete failed:', err);
    }
  };

  const handleFilePreview = (file: StudiosFile) => {
    setSelectedFile(file);
  };

  const filteredFiles = files.filter(file =>
    file.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
    file.contentType.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getFileIcon = (contentType: string) => {
    if (contentType.startsWith('text/')) return '📄';
    if (contentType === 'application/pdf') return '📕';
    if (contentType.startsWith('image/')) return '🖼️';
    if (contentType === 'application/json') return '📋';
    return '📎';
  };

  const getStatusColor = (file: StudiosFile) => {
    if (file.ragIngested) return 'text-green-400';
    if (file.processed) return 'text-blue-400';
    return 'text-yellow-400';
  };

  const getStatusText = (file: StudiosFile) => {
    if (file.ragIngested) return 'RAG Indexed';
    if (file.processed) return 'Processed';
    return 'Pending';
  };

  return (
    <div className="h-full bg-background-light flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <h2 className="text-lg font-semibold text-text">Studios</h2>
          {isLoading && (
            <div className="animate-spin w-4 h-4 border-2 border-accent border-t-transparent rounded-full"></div>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-text-muted hover:text-text transition-colors"
        >
          ✕
        </button>
      </div>

      {/* Error Display */}
      {error && (
        <div className="mx-4 mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
          <div className="text-red-400 text-sm">{error}</div>
          <button
            onClick={() => setError(null)}
            className="text-red-300 hover:text-red-200 text-xs mt-1"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Upload Area */}
      <div className="p-4 border-b border-border">
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
            dragOver
              ? 'border-accent bg-accent/10'
              : 'border-border hover:border-accent/50'
          }`}
        >
          <div className="text-4xl mb-2">📁</div>
          <div className="text-text mb-2">
            Drop files here or{' '}
            <label className="text-accent hover:text-accent-hover cursor-pointer">
              browse
              <input
                type="file"
                multiple
                onChange={handleFileInput}
                className="hidden"
                accept=".txt,.md,.pdf,.png,.jpg,.jpeg,.gif,.json"
              />
            </label>
          </div>
          <div className="text-sm text-text-muted">
            Supports TXT, MD, PDF, JSON, and images
          </div>
        </div>

        {/* Processing Status */}
        {Object.entries(processingStatus).map(([id, status]) => (
          <div key={id} className="mt-3 p-3 bg-background-card border border-border rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-text">{status.message}</span>
              <span className={`text-xs ${
                status.status === 'error' ? 'text-red-400' :
                status.status === 'completed' ? 'text-green-400' :
                'text-accent'
              }`}>
                {status.status === 'error' ? '✗' :
                 status.status === 'completed' ? '✓' : '⟳'}
              </span>
            </div>
            <div className="w-full bg-background-dark rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all duration-300 ${
                  status.status === 'error' ? 'bg-red-500' :
                  status.status === 'completed' ? 'bg-green-500' :
                  'bg-accent'
                }`}
                style={{ width: `${status.progress}%` }}
              ></div>
            </div>
          </div>
        ))}
      </div>

      {/* Search and Controls */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center space-x-2">
          <div className="flex-1 relative">
            <input
              type="text"
              placeholder="Search files..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-3 py-2 bg-background-card border border-border rounded-lg text-text placeholder-text-muted focus:outline-none focus:border-accent"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2 top-1/2 transform -translate-y-1/2 text-text-muted hover:text-text"
              >
                ✕
              </button>
            )}
          </div>
          <button
            onClick={loadFiles}
            className="px-3 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg transition-colors"
            disabled={isLoading}
          >
            🔄
          </button>
        </div>
      </div>

      {/* File List */}
      <div className="flex-1 overflow-y-auto">
        {filteredFiles.length === 0 ? (
          <div className="p-4 text-center text-text-muted">
            {files.length === 0 ? 'No files uploaded yet' : 'No files match your search'}
          </div>
        ) : (
          <div className="p-4 space-y-2">
            {filteredFiles.map((file) => (
              <div
                key={file.id}
                className="bg-background-card border border-border rounded-lg p-3 hover:border-accent/50 transition-colors cursor-pointer"
                onClick={() => handleFilePreview(file)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3 flex-1 min-w-0">
                    <span className="text-2xl">{getFileIcon(file.contentType)}</span>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-text truncate">
                        {file.filename}
                      </div>
                      <div className="text-sm text-text-muted">
                        {(file.size / 1024).toFixed(1)} KB • {file.contentType}
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    <span className={`text-xs px-2 py-1 rounded-full ${getStatusColor(file)} bg-current/10`}>
                      {getStatusText(file)}
                    </span>
                    <div className="relative">
                      <button 
                        className="text-text-muted hover:text-text p-1"
                        onClick={(e) => {
                          e.stopPropagation();
                          // Toggle dropdown menu
                        }}
                      >
                        ⋮
                      </button>
                      {/* Dropdown menu would go here */}
                    </div>
                  </div>
                </div>
                
                {file.preview && (
                  <div className="mt-2 text-sm text-text-secondary">
                    {file.preview}
                  </div>
                )}

                {/* File Actions */}
                <div className="mt-3 flex items-center space-x-2">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleFilePreview(file);
                    }}
                    className="text-xs text-accent hover:text-accent-hover"
                  >
                    Preview
                  </button>
                  <span className="text-text-muted">•</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteFile(file.id);
                    }}
                    className="text-xs text-red-400 hover:text-red-300"
                  >
                    Delete
                  </button>
                  {file.ragIngested && (
                    <>
                      <span className="text-text-muted">•</span>
                      <span className="text-xs text-green-400">Available in chat context</span>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* RAG Status */}
      <div className="p-4 border-t border-border">
        <div className="text-sm text-text-muted">
          <div className="flex items-center justify-between mb-2">
            <span className="font-medium">RAG Integration</span>
            <span className={ragStats.isActive ? 'text-green-400' : 'text-yellow-400'}>
              {ragStats.isActive ? '● Active' : '○ Inactive'}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <div className="text-text">Total Files</div>
              <div className="font-medium">{ragStats.totalFiles}</div>
            </div>
            <div>
              <div className="text-text">RAG Indexed</div>
              <div className="font-medium text-accent">{ragStats.ragIngestedFiles}</div>
            </div>
          </div>
          {ragStats.lastUpdate && (
            <div className="mt-2 text-xs text-text-muted">
              Last updated: {ragStats.lastUpdate.toLocaleTimeString()}
            </div>
          )}
        </div>
      </div>

      {/* File Preview Modal */}
      {selectedFile && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-background-light border border-border rounded-lg max-w-2xl max-h-[80vh] overflow-hidden">
            <div className="p-4 border-b border-border flex items-center justify-between">
              <h3 className="text-lg font-semibold text-text">{selectedFile.filename}</h3>
              <button
                onClick={() => setSelectedFile(null)}
                className="text-text-muted hover:text-text"
              >
                ✕
              </button>
            </div>
            <div className="p-4 overflow-y-auto max-h-96">
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-text-muted">Size</div>
                    <div className="text-text">{(selectedFile.size / 1024).toFixed(1)} KB</div>
                  </div>
                  <div>
                    <div className="text-text-muted">Type</div>
                    <div className="text-text">{selectedFile.contentType}</div>
                  </div>
                  <div>
                    <div className="text-text-muted">Status</div>
                    <div className={getStatusColor(selectedFile)}>{getStatusText(selectedFile)}</div>
                  </div>
                  <div>
                    <div className="text-text-muted">Uploaded</div>
                    <div className="text-text">{selectedFile.uploadedAt.toLocaleDateString()}</div>
                  </div>
                </div>
                {selectedFile.preview && (
                  <div>
                    <div className="text-text-muted text-sm mb-2">Preview</div>
                    <div className="text-text text-sm bg-background-card p-3 rounded border border-border">
                      {selectedFile.preview}
                    </div>
                  </div>
                )}
                {selectedFile.ragIngested && (
                  <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-lg">
                    <div className="text-green-400 text-sm font-medium">✓ Available in RAG Context</div>
                    <div className="text-green-300 text-xs mt-1">
                      This file's content is available for AI context injection in chat conversations.
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};