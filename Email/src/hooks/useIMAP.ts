import { useState, useEffect, useCallback, useRef } from 'react';
import { IMAPService } from '../services/imapService';
import { 
  EmailAccount, 
  EmailMessage, 
  EmailFolder, 
  EmailThread, 
  SyncProgress,
  MessageAction 
} from '../types/imap';

interface IMAPState {
  accounts: EmailAccount[];
  folders: Record<string, EmailFolder[]>;
  messages: Record<string, EmailMessage[]>;
  threads: Record<string, EmailThread[]>;
  syncProgress: Record<string, SyncProgress>;
  loading: boolean;
  error: string | null;
}

interface IMAPActions {
  addAccount: (account: Omit<EmailAccount, 'id'>) => Promise<string>;
  syncAccount: (accountId: string) => Promise<void>;
  syncFolder: (accountId: string, folderPath: string, incremental?: boolean) => Promise<void>;
  selectFolder: (accountId: string, folderPath: string) => Promise<void>;
  searchMessages: (accountId: string, query: string, folder?: string) => Promise<EmailMessage[]>;
  performMessageAction: (accountId: string, action: MessageAction) => Promise<void>;
  performBulkActions: (accountId: string, actions: MessageAction[]) => Promise<void>;
  markThreadRead: (accountId: string, threadId: string, read?: boolean) => Promise<void>;
  archiveThread: (accountId: string, threadId: string, archiveFolder?: string) => Promise<void>;
  refreshAccounts: () => Promise<void>;
  clearError: () => void;
}

export function useIMAP(): IMAPState & IMAPActions {
  const [state, setState] = useState<IMAPState>({
    accounts: [],
    folders: {},
    messages: {},
    threads: {},
    syncProgress: {},
    loading: false,
    error: null,
  });

  const syncIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Load accounts on mount
  useEffect(() => {
    refreshAccounts();
    
    // Set up periodic sync progress updates
    progressIntervalRef.current = setInterval(() => {
      updateSyncProgress();
    }, 1000);

    return () => {
      if (syncIntervalRef.current) {
        clearInterval(syncIntervalRef.current);
      }
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
    };
  }, []);

  const setLoading = (loading: boolean) => {
    setState(prev => ({ ...prev, loading }));
  };

  const setError = (error: string | null) => {
    setState(prev => ({ ...prev, error }));
  };

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const refreshAccounts = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      const accounts = await IMAPService.getAccounts();
      setState(prev => ({ ...prev, accounts }));
      
      // Load folders for each account
      for (const account of accounts) {
        try {
          const folders = await IMAPService.getFolders(account.id);
          setState(prev => ({
            ...prev,
            folders: { ...prev.folders, [account.id]: folders }
          }));
        } catch (error) {
          console.warn(`Failed to load folders for account ${account.id}:`, error);
        }
      }
    } catch (error) {
      setError(`Failed to load accounts: ${error}`);
    } finally {
      setLoading(false);
    }
  }, []);

  const addAccount = useCallback(async (account: Omit<EmailAccount, 'id'>): Promise<string> => {
    try {
      setLoading(true);
      setError(null);
      
      const accountId = await IMAPService.addAccount(account);
      await refreshAccounts();
      
      return accountId;
    } catch (error) {
      setError(`Failed to add account: ${error}`);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [refreshAccounts]);

  const syncAccount = useCallback(async (accountId: string) => {
    try {
      setError(null);
      
      const messages = await IMAPService.syncEmails(accountId);
      setState(prev => ({
        ...prev,
        messages: { ...prev.messages, [accountId]: messages }
      }));
      
      // Refresh folders to update counts
      const folders = await IMAPService.getFolders(accountId);
      setState(prev => ({
        ...prev,
        folders: { ...prev.folders, [accountId]: folders }
      }));
      
    } catch (error) {
      setError(`Failed to sync account: ${error}`);
      throw error;
    }
  }, []);

  const syncFolder = useCallback(async (
    accountId: string, 
    folderPath: string, 
    incremental: boolean = true
  ) => {
    try {
      setError(null);
      
      const messages = await IMAPService.syncFolder(accountId, folderPath, incremental);
      const folderKey = `${accountId}_${folderPath}`;
      
      setState(prev => ({
        ...prev,
        messages: { ...prev.messages, [folderKey]: messages }
      }));
      
    } catch (error) {
      setError(`Failed to sync folder: ${error}`);
      throw error;
    }
  }, []);

  const selectFolder = useCallback(async (accountId: string, folderPath: string) => {
    try {
      setError(null);
      
      // Load messages for the folder
      const messages = await IMAPService.getFolderMessages(accountId, folderPath);
      const folderKey = `${accountId}_${folderPath}`;
      
      setState(prev => ({
        ...prev,
        messages: { ...prev.messages, [folderKey]: messages }
      }));
      
      // Load threads for the folder
      const threads = await IMAPService.getThreads(accountId, folderPath);
      setState(prev => ({
        ...prev,
        threads: { ...prev.threads, [folderKey]: threads }
      }));
      
    } catch (error) {
      setError(`Failed to select folder: ${error}`);
      throw error;
    }
  }, []);

  const searchMessages = useCallback(async (
    accountId: string, 
    query: string, 
    folder?: string
  ): Promise<EmailMessage[]> => {
    try {
      setError(null);
      return await IMAPService.searchMessages(accountId, query, folder);
    } catch (error) {
      setError(`Failed to search messages: ${error}`);
      throw error;
    }
  }, []);

  const performMessageAction = useCallback(async (
    accountId: string, 
    action: MessageAction
  ) => {
    try {
      setError(null);
      await IMAPService.performMessageActions(accountId, [action]);
      
      // Update local state based on action
      setState(prev => {
        const newState = { ...prev };
        
        // Update messages in all relevant collections
        Object.keys(newState.messages).forEach(key => {
          if (key.startsWith(accountId)) {
            newState.messages[key] = newState.messages[key].map(msg => {
              if (msg.uid === action.messageUid) {
                const updatedMsg = { ...msg };
                
                switch (action.type) {
                  case 'markRead':
                    updatedMsg.read = true;
                    break;
                  case 'markUnread':
                    updatedMsg.read = false;
                    break;
                  case 'flag':
                    updatedMsg.flagged = true;
                    break;
                  case 'unflag':
                    updatedMsg.flagged = false;
                    break;
                  case 'move':
                  case 'archive':
                    if (action.targetFolder) {
                      updatedMsg.folder = action.targetFolder;
                    }
                    break;
                }
                
                return updatedMsg;
              }
              return msg;
            });
            
            // Remove deleted messages
            if (action.type === 'delete') {
              newState.messages[key] = newState.messages[key].filter(
                msg => msg.uid !== action.messageUid
              );
            }
          }
        });
        
        return newState;
      });
      
    } catch (error) {
      setError(`Failed to perform message action: ${error}`);
      throw error;
    }
  }, []);

  const performBulkActions = useCallback(async (
    accountId: string, 
    actions: MessageAction[]
  ) => {
    try {
      setError(null);
      await IMAPService.performMessageActions(accountId, actions);
      
      // Refresh the affected folders
      const affectedFolders = new Set<string>();
      actions.forEach(action => {
        // Find the folder for each message
        Object.keys(state.messages).forEach(key => {
          if (key.startsWith(accountId)) {
            const message = state.messages[key].find(msg => msg.uid === action.messageUid);
            if (message) {
              affectedFolders.add(message.folder);
            }
          }
        });
      });
      
      // Refresh each affected folder
      for (const folder of affectedFolders) {
        await selectFolder(accountId, folder);
      }
      
    } catch (error) {
      setError(`Failed to perform bulk actions: ${error}`);
      throw error;
    }
  }, [state.messages, selectFolder]);

  const markThreadRead = useCallback(async (
    accountId: string, 
    threadId: string, 
    read: boolean = true
  ) => {
    try {
      setError(null);
      await IMAPService.markThreadRead(accountId, threadId, read);
      
      // Update local state
      setState(prev => {
        const newState = { ...prev };
        
        Object.keys(newState.messages).forEach(key => {
          if (key.startsWith(accountId)) {
            newState.messages[key] = newState.messages[key].map(msg => {
              if (msg.thread_id === threadId) {
                return { ...msg, read };
              }
              return msg;
            });
          }
        });
        
        // Update threads
        Object.keys(newState.threads).forEach(key => {
          if (key.startsWith(accountId)) {
            newState.threads[key] = newState.threads[key].map(thread => {
              if (thread.id === threadId) {
                return { ...thread, has_unread: !read };
              }
              return thread;
            });
          }
        });
        
        return newState;
      });
      
    } catch (error) {
      setError(`Failed to mark thread read: ${error}`);
      throw error;
    }
  }, []);

  const archiveThread = useCallback(async (
    accountId: string, 
    threadId: string, 
    archiveFolder: string = 'Archive'
  ) => {
    try {
      setError(null);
      await IMAPService.archiveThread(accountId, threadId, archiveFolder);
      
      // Remove thread from current view and refresh
      setState(prev => {
        const newState = { ...prev };
        
        Object.keys(newState.threads).forEach(key => {
          if (key.startsWith(accountId)) {
            newState.threads[key] = newState.threads[key].filter(
              thread => thread.id !== threadId
            );
          }
        });
        
        return newState;
      });
      
    } catch (error) {
      setError(`Failed to archive thread: ${error}`);
      throw error;
    }
  }, []);

  const updateSyncProgress = useCallback(async () => {
    try {
      const progressUpdates: Record<string, SyncProgress> = {};
      
      for (const account of state.accounts) {
        const progress = await IMAPService.getSyncProgress(account.id);
        Object.assign(progressUpdates, progress);
      }
      
      setState(prev => ({
        ...prev,
        syncProgress: progressUpdates
      }));
      
    } catch (error) {
      // Silently fail for progress updates
      console.warn('Failed to update sync progress:', error);
    }
  }, [state.accounts]);

  return {
    ...state,
    addAccount,
    syncAccount,
    syncFolder,
    selectFolder,
    searchMessages,
    performMessageAction,
    performBulkActions,
    markThreadRead,
    archiveThread,
    refreshAccounts,
    clearError,
  };
}