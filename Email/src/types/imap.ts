export interface EmailAccount {
  id: string;
  name: string;
  email: string;
  imap_server: string;
  imap_port: number;
  smtp_server: string;
  smtp_port: number;
  username: string;
  encrypted_password: string;
  use_tls: boolean;
  last_sync?: string; // ISO date string
}

export interface EmailMessage {
  id: string;
  uid: number;
  subject: string;
  from: string;
  to: string[];
  cc: string[];
  bcc: string[];
  body: string;
  html_body?: string;
  timestamp: string; // ISO date string
  read: boolean;
  flagged: boolean;
  folder: string;
  message_id: string;
  in_reply_to?: string;
  references: string[];
  thread_id: string;
  has_attachments: boolean;
  size: number;
  labels: string[];
  priority: 'low' | 'normal' | 'high';
}

export interface EmailFolder {
  id: string;
  name: string;
  path: string;
  folder_type: 'inbox' | 'sent' | 'drafts' | 'trash' | 'spam' | 'archive' | 'custom';
  count: number;
  unread_count: number;
  children: EmailFolder[];
  selectable: boolean;
}

export interface EmailThread {
  id: string;
  subject: string;
  participants: string[];
  message_count: number;
  last_message_date: string; // ISO date string
  has_unread: boolean;
  is_flagged: boolean;
  folder: string;
  messages: string[]; // Message IDs
}

export interface SyncProgress {
  account_id: string;
  folder: string;
  current: number;
  total: number;
  status: string;
  error?: string;
}

export interface IMAPConnectionConfig {
  server: string;
  port: number;
  username: string;
  password: string;
  use_tls: boolean;
}

export interface SMTPConnectionConfig {
  server: string;
  port: number;
  username: string;
  password: string;
  use_tls: boolean;
}

export interface AccountSetupData {
  name: string;
  email: string;
  imap: IMAPConnectionConfig;
  smtp: SMTPConnectionConfig;
}

export interface MessageAction {
  type: 'markRead' | 'markUnread' | 'flag' | 'unflag' | 'move' | 'delete' | 'archive';
  messageUid: number;
  targetFolder?: string;
}

export interface SearchOptions {
  query: string;
  folder?: string;
  dateRange?: {
    start: Date;
    end: Date;
  };
  hasAttachments?: boolean;
  isUnread?: boolean;
  isFlagged?: boolean;
}

export interface ThreadingOptions {
  groupBySubject: boolean;
  groupByReferences: boolean;
  maxThreadDepth: number;
}

// Email provider presets
export const EMAIL_PROVIDERS = {
  gmail: {
    name: 'Gmail',
    imap: { server: 'imap.gmail.com', port: 993, use_tls: true },
    smtp: { server: 'smtp.gmail.com', port: 587, use_tls: true },
  },
  outlook: {
    name: 'Outlook/Hotmail',
    imap: { server: 'outlook.office365.com', port: 993, use_tls: true },
    smtp: { server: 'smtp-mail.outlook.com', port: 587, use_tls: true },
  },
  yahoo: {
    name: 'Yahoo Mail',
    imap: { server: 'imap.mail.yahoo.com', port: 993, use_tls: true },
    smtp: { server: 'smtp.mail.yahoo.com', port: 587, use_tls: true },
  },
  icloud: {
    name: 'iCloud Mail',
    imap: { server: 'imap.mail.me.com', port: 993, use_tls: true },
    smtp: { server: 'smtp.mail.me.com', port: 587, use_tls: true },
  },
} as const;

export type EmailProvider = keyof typeof EMAIL_PROVIDERS;