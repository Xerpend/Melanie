import { invoke } from '@tauri-apps/api/tauri';
import { 
  EmailAccount, 
  EmailMessage, 
  EmailFolder, 
  EmailThread, 
  SyncProgress, 
  MessageAction,
  SearchOptions 
} from '../types/imap';

export class IMAPService {
  /**
   * Get all configured email accounts
   */
  static async getAccounts(): Promise<EmailAccount[]> {
    try {
      return await invoke<EmailAccount[]>('get_email_accounts');
    } catch (error) {
      console.error('Failed to get email accounts:', error);
      throw new Error(`Failed to get email accounts: ${error}`);
    }
  }

  /**
   * Add a new email account
   */
  static async addAccount(account: Omit<EmailAccount, 'id'>): Promise<string> {
    try {
      return await invoke<string>('add_email_account', { account });
    } catch (error) {
      console.error('Failed to add email account:', error);
      throw new Error(`Failed to add email account: ${error}`);
    }
  }

  /**
   * Synchronize all emails for an account
   */
  static async syncEmails(accountId: string): Promise<EmailMessage[]> {
    try {
      return await invoke<EmailMessage[]>('sync_emails', { accountId });
    } catch (error) {
      console.error('Failed to sync emails:', error);
      throw new Error(`Failed to sync emails: ${error}`);
    }
  }

  /**
   * Synchronize a specific folder
   */
  static async syncFolder(
    accountId: string, 
    folderPath: string, 
    incremental: boolean = true
  ): Promise<EmailMessage[]> {
    try {
      return await invoke<EmailMessage[]>('sync_folder', { 
        accountId, 
        folderPath, 
        incremental 
      });
    } catch (error) {
      console.error('Failed to sync folder:', error);
      throw new Error(`Failed to sync folder: ${error}`);
    }
  }

  /**
   * Get folders for an account
   */
  static async getFolders(accountId: string): Promise<EmailFolder[]> {
    try {
      return await invoke<EmailFolder[]>('get_folders', { accountId });
    } catch (error) {
      console.error('Failed to get folders:', error);
      throw new Error(`Failed to get folders: ${error}`);
    }
  }

  /**
   * Get messages for a specific folder
   */
  static async getFolderMessages(accountId: string, folder: string): Promise<EmailMessage[]> {
    try {
      return await invoke<EmailMessage[]>('get_folder_messages', { accountId, folder });
    } catch (error) {
      console.error('Failed to get folder messages:', error);
      throw new Error(`Failed to get folder messages: ${error}`);
    }
  }

  /**
   * Search messages
   */
  static async searchMessages(
    accountId: string, 
    query: string, 
    folder?: string
  ): Promise<EmailMessage[]> {
    try {
      return await invoke<EmailMessage[]>('search_messages', { 
        accountId, 
        query, 
        folder 
      });
    } catch (error) {
      console.error('Failed to search messages:', error);
      throw new Error(`Failed to search messages: ${error}`);
    }
  }

  /**
   * Get email threads for a folder
   */
  static async getThreads(accountId: string, folder: string): Promise<EmailThread[]> {
    try {
      return await invoke<EmailThread[]>('get_threads', { accountId, folder });
    } catch (error) {
      console.error('Failed to get threads:', error);
      throw new Error(`Failed to get threads: ${error}`);
    }
  }

  /**
   * Mark message as read/unread
   */
  static async markMessageRead(
    accountId: string, 
    messageUid: number, 
    read: boolean
  ): Promise<void> {
    try {
      await invoke('mark_message_read', { accountId, messageUid, read });
    } catch (error) {
      console.error('Failed to mark message read:', error);
      throw new Error(`Failed to mark message read: ${error}`);
    }
  }

  /**
   * Flag/unflag message
   */
  static async flagMessage(
    accountId: string, 
    messageUid: number, 
    flagged: boolean
  ): Promise<void> {
    try {
      await invoke('flag_message', { accountId, messageUid, flagged });
    } catch (error) {
      console.error('Failed to flag message:', error);
      throw new Error(`Failed to flag message: ${error}`);
    }
  }

  /**
   * Move message to another folder
   */
  static async moveMessage(
    accountId: string, 
    messageUid: number, 
    targetFolder: string
  ): Promise<void> {
    try {
      await invoke('move_message', { accountId, messageUid, targetFolder });
    } catch (error) {
      console.error('Failed to move message:', error);
      throw new Error(`Failed to move message: ${error}`);
    }
  }

  /**
   * Delete message
   */
  static async deleteMessage(accountId: string, messageUid: number): Promise<void> {
    try {
      await invoke('delete_message', { accountId, messageUid });
    } catch (error) {
      console.error('Failed to delete message:', error);
      throw new Error(`Failed to delete message: ${error}`);
    }
  }

  /**
   * Get synchronization progress
   */
  static async getSyncProgress(accountId: string): Promise<Record<string, SyncProgress>> {
    try {
      return await invoke<Record<string, SyncProgress>>('get_sync_progress', { accountId });
    } catch (error) {
      console.error('Failed to get sync progress:', error);
      throw new Error(`Failed to get sync progress: ${error}`);
    }
  }

  /**
   * Perform multiple message actions
   */
  static async performMessageActions(
    accountId: string, 
    actions: MessageAction[]
  ): Promise<void> {
    const promises = actions.map(async (action) => {
      switch (action.type) {
        case 'markRead':
          return this.markMessageRead(accountId, action.messageUid, true);
        case 'markUnread':
          return this.markMessageRead(accountId, action.messageUid, false);
        case 'flag':
          return this.flagMessage(accountId, action.messageUid, true);
        case 'unflag':
          return this.flagMessage(accountId, action.messageUid, false);
        case 'move':
        case 'archive':
          if (!action.targetFolder) {
            throw new Error('Target folder required for move/archive action');
          }
          return this.moveMessage(accountId, action.messageUid, action.targetFolder);
        case 'delete':
          return this.deleteMessage(accountId, action.messageUid);
        default:
          throw new Error(`Unknown action type: ${action.type}`);
      }
    });

    try {
      await Promise.all(promises);
    } catch (error) {
      console.error('Failed to perform message actions:', error);
      throw new Error(`Failed to perform message actions: ${error}`);
    }
  }

  /**
   * Advanced search with multiple criteria
   */
  static async advancedSearch(
    accountId: string, 
    options: SearchOptions
  ): Promise<EmailMessage[]> {
    try {
      // For now, use basic search - can be extended later
      return await this.searchMessages(accountId, options.query, options.folder);
    } catch (error) {
      console.error('Failed to perform advanced search:', error);
      throw new Error(`Failed to perform advanced search: ${error}`);
    }
  }

  /**
   * Get message statistics for a folder
   */
  static async getFolderStats(accountId: string, folder: string): Promise<{
    total: number;
    unread: number;
    flagged: number;
    hasAttachments: number;
  }> {
    try {
      const messages = await this.getFolderMessages(accountId, folder);
      
      return {
        total: messages.length,
        unread: messages.filter(m => !m.read).length,
        flagged: messages.filter(m => m.flagged).length,
        hasAttachments: messages.filter(m => m.has_attachments).length,
      };
    } catch (error) {
      console.error('Failed to get folder stats:', error);
      throw new Error(`Failed to get folder stats: ${error}`);
    }
  }

  /**
   * Get recent activity (messages from last 24 hours)
   */
  static async getRecentActivity(accountId: string): Promise<EmailMessage[]> {
    try {
      const messages = await this.searchMessages(accountId, '');
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      
      return messages.filter(message => {
        const messageDate = new Date(message.timestamp);
        return messageDate >= yesterday;
      }).sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
    } catch (error) {
      console.error('Failed to get recent activity:', error);
      throw new Error(`Failed to get recent activity: ${error}`);
    }
  }

  /**
   * Validate email account configuration
   */
  static async validateAccount(account: Omit<EmailAccount, 'id'>): Promise<boolean> {
    try {
      // This will test the connection during account addition
      await this.addAccount(account);
      return true;
    } catch (error) {
      console.error('Account validation failed:', error);
      return false;
    }
  }

  /**
   * Get thread messages in chronological order
   */
  static async getThreadMessages(
    accountId: string, 
    threadId: string
  ): Promise<EmailMessage[]> {
    try {
      // Search for messages with the same thread ID
      const allMessages = await this.searchMessages(accountId, '');
      const threadMessages = allMessages.filter(msg => msg.thread_id === threadId);
      
      // Sort by timestamp
      return threadMessages.sort((a, b) => 
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      );
    } catch (error) {
      console.error('Failed to get thread messages:', error);
      throw new Error(`Failed to get thread messages: ${error}`);
    }
  }

  /**
   * Mark entire thread as read
   */
  static async markThreadRead(
    accountId: string, 
    threadId: string, 
    read: boolean = true
  ): Promise<void> {
    try {
      const threadMessages = await this.getThreadMessages(accountId, threadId);
      const actions: MessageAction[] = threadMessages.map(msg => ({
        type: read ? 'markRead' : 'markUnread',
        messageUid: msg.uid,
      }));
      
      await this.performMessageActions(accountId, actions);
    } catch (error) {
      console.error('Failed to mark thread read:', error);
      throw new Error(`Failed to mark thread read: ${error}`);
    }
  }

  /**
   * Archive entire thread
   */
  static async archiveThread(
    accountId: string, 
    threadId: string, 
    archiveFolder: string = 'Archive'
  ): Promise<void> {
    try {
      const threadMessages = await this.getThreadMessages(accountId, threadId);
      const actions: MessageAction[] = threadMessages.map(msg => ({
        type: 'archive',
        messageUid: msg.uid,
        targetFolder: archiveFolder,
      }));
      
      await this.performMessageActions(accountId, actions);
    } catch (error) {
      console.error('Failed to archive thread:', error);
      throw new Error(`Failed to archive thread: ${error}`);
    }
  }
}