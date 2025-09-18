use std::collections::HashMap;
use std::sync::Arc;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use tokio::sync::{RwLock, Mutex};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmailAccount {
    pub id: String,
    pub name: String,
    pub email: String,
    pub imap_server: String,
    pub imap_port: u16,
    pub smtp_server: String,
    pub smtp_port: u16,
    pub username: String,
    pub encrypted_password: String,
    pub use_tls: bool,
    pub last_sync: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmailMessage {
    pub id: String,
    pub uid: u32,
    pub subject: String,
    pub from: String,
    pub to: Vec<String>,
    pub cc: Vec<String>,
    pub bcc: Vec<String>,
    pub body: String,
    pub html_body: Option<String>,
    pub timestamp: DateTime<Utc>,
    pub read: bool,
    pub flagged: bool,
    pub folder: String,
    pub message_id: String,
    pub in_reply_to: Option<String>,
    pub references: Vec<String>,
    pub thread_id: String,
    pub has_attachments: bool,
    pub size: usize,
    pub labels: Vec<String>,
    pub priority: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmailFolder {
    pub id: String,
    pub name: String,
    pub path: String,
    pub folder_type: String, // inbox, sent, drafts, trash, etc.
    pub count: u32,
    pub unread_count: u32,
    pub children: Vec<EmailFolder>,
    pub selectable: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmailThread {
    pub id: String,
    pub subject: String,
    pub participants: Vec<String>,
    pub message_count: u32,
    pub last_message_date: DateTime<Utc>,
    pub has_unread: bool,
    pub is_flagged: bool,
    pub folder: String,
    pub messages: Vec<String>, // Message IDs
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncProgress {
    pub account_id: String,
    pub folder: String,
    pub current: u32,
    pub total: u32,
    pub status: String,
    pub error: Option<String>,
}

pub struct IMAPManager {
    accounts: Arc<RwLock<HashMap<String, EmailAccount>>>,
    messages: Arc<RwLock<HashMap<String, EmailMessage>>>,
    folders: Arc<RwLock<HashMap<String, Vec<EmailFolder>>>>,
    threads: Arc<RwLock<HashMap<String, Vec<EmailThread>>>>,
    sync_progress: Arc<RwLock<HashMap<String, SyncProgress>>>,
}

impl IMAPManager {
    pub fn new() -> Self {
        Self {
            accounts: Arc::new(RwLock::new(HashMap::new())),
            messages: Arc::new(RwLock::new(HashMap::new())),
            folders: Arc::new(RwLock::new(HashMap::new())),
            threads: Arc::new(RwLock::new(HashMap::new())),
            sync_progress: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Add a new email account
    pub async fn add_account(&self, mut account: EmailAccount) -> Result<String, String> {
        // TODO: Test connection before adding
        // For now, just simulate successful connection
        
        account.id = Uuid::new_v4().to_string();
        let account_id = account.id.clone();
        
        let mut accounts = self.accounts.write().await;
        accounts.insert(account_id.clone(), account);
        
        log::info!("Added email account: {}", account_id);
        Ok(account_id)
    }

    /// Synchronize folders for an account
    pub async fn sync_folders(&self, account_id: &str) -> Result<Vec<EmailFolder>, String> {
        // TODO: Implement actual IMAP folder synchronization
        // For now, return mock folders
        
        let folders = vec![
            EmailFolder {
                id: format!("{}_INBOX", account_id),
                name: "INBOX".to_string(),
                path: "INBOX".to_string(),
                folder_type: "inbox".to_string(),
                count: 10,
                unread_count: 3,
                children: Vec::new(),
                selectable: true,
            },
            EmailFolder {
                id: format!("{}_Sent", account_id),
                name: "Sent".to_string(),
                path: "Sent".to_string(),
                folder_type: "sent".to_string(),
                count: 5,
                unread_count: 0,
                children: Vec::new(),
                selectable: true,
            },
        ];
        
        // Store folders
        let mut stored_folders = self.folders.write().await;
        stored_folders.insert(account_id.to_string(), folders.clone());
        
        log::info!("Synchronized {} folders for account {}", folders.len(), account_id);
        Ok(folders)
    }

    /// Determine folder type based on name
    fn determine_folder_type(&self, folder_name: &str) -> String {
        let name_lower = folder_name.to_lowercase();
        
        if name_lower.contains("inbox") {
            "inbox".to_string()
        } else if name_lower.contains("sent") {
            "sent".to_string()
        } else if name_lower.contains("draft") {
            "drafts".to_string()
        } else if name_lower.contains("trash") || name_lower.contains("deleted") {
            "trash".to_string()
        } else if name_lower.contains("spam") || name_lower.contains("junk") {
            "spam".to_string()
        } else if name_lower.contains("archive") {
            "archive".to_string()
        } else {
            "custom".to_string()
        }
    }

    /// Synchronize messages for a specific folder
    pub async fn sync_folder_messages(&self, account_id: &str, folder_path: &str, _incremental: bool) -> Result<Vec<EmailMessage>, String> {
        // TODO: Implement actual IMAP message synchronization
        // For now, return mock messages
        
        self.update_sync_progress(account_id, folder_path, 0, 2, "Fetching messages").await;
        
        let messages = vec![
            EmailMessage {
                id: format!("{}_{}_1", account_id, folder_path),
                uid: 1,
                subject: "Welcome to Melanie Email".to_string(),
                from: "welcome@melanie.ai".to_string(),
                to: vec!["user@example.com".to_string()],
                cc: vec![],
                bcc: vec![],
                body: "Welcome to your new AI-enhanced email client!".to_string(),
                html_body: None,
                timestamp: Utc::now(),
                read: false,
                flagged: false,
                folder: folder_path.to_string(),
                message_id: "<welcome@melanie.ai>".to_string(),
                in_reply_to: None,
                references: vec![],
                thread_id: "thread_1".to_string(),
                has_attachments: false,
                size: 1024,
                labels: vec![],
                priority: "normal".to_string(),
            },
            EmailMessage {
                id: format!("{}_{}_2", account_id, folder_path),
                uid: 2,
                subject: "Getting Started Guide".to_string(),
                from: "support@melanie.ai".to_string(),
                to: vec!["user@example.com".to_string()],
                cc: vec![],
                bcc: vec![],
                body: "Here's how to get started with Melanie Email...".to_string(),
                html_body: None,
                timestamp: Utc::now(),
                read: true,
                flagged: false,
                folder: folder_path.to_string(),
                message_id: "<guide@melanie.ai>".to_string(),
                in_reply_to: None,
                references: vec![],
                thread_id: "thread_2".to_string(),
                has_attachments: false,
                size: 2048,
                labels: vec![],
                priority: "normal".to_string(),
            },
        ];
        
        // Store messages
        let mut stored_messages = self.messages.write().await;
        for message in &messages {
            stored_messages.insert(message.id.clone(), message.clone());
        }
        
        // Update account last sync time
        let mut accounts = self.accounts.write().await;
        if let Some(account) = accounts.get_mut(account_id) {
            account.last_sync = Some(Utc::now());
        }
        
        self.update_sync_progress(account_id, folder_path, 2, 2, "Complete").await;
        
        log::info!("Synchronized {} messages from folder {} for account {}", messages.len(), folder_path, account_id);
        Ok(messages)
    }

    /// Generate thread ID based on subject and references
    fn generate_thread_id(&self, subject: &str, references: &[String], in_reply_to: &Option<String>) -> String {
        // Use the first reference or in-reply-to as thread ID
        if let Some(ref_id) = references.first() {
            return ref_id.clone();
        }
        
        if let Some(reply_to) = in_reply_to {
            return reply_to.clone();
        }
        
        // Generate based on normalized subject
        let normalized_subject = subject
            .to_lowercase()
            .trim_start_matches("re:")
            .trim_start_matches("fwd:")
            .trim_start_matches("fw:")
            .trim();
        
        format!("thread_{}", Uuid::new_v4())
    }

    /// Update sync progress
    async fn update_sync_progress(&self, account_id: &str, folder: &str, current: u32, total: u32, status: &str) {
        let progress = SyncProgress {
            account_id: account_id.to_string(),
            folder: folder.to_string(),
            current,
            total,
            status: status.to_string(),
            error: None,
        };
        
        let mut sync_progress = self.sync_progress.write().await;
        sync_progress.insert(format!("{}_{}", account_id, folder), progress);
    }

    /// Search messages across all folders
    pub async fn search_messages(&self, account_id: &str, query: &str, folder: Option<&str>) -> Result<Vec<EmailMessage>, String> {
        let messages = self.messages.read().await;
        let query_lower = query.to_lowercase();
        
        let filtered: Vec<EmailMessage> = messages
            .values()
            .filter(|msg| {
                // Filter by account
                msg.id.starts_with(account_id) &&
                // Filter by folder if specified
                folder.map_or(true, |f| msg.folder == f) &&
                // Search in subject, from, body
                (msg.subject.to_lowercase().contains(&query_lower) ||
                 msg.from.to_lowercase().contains(&query_lower) ||
                 msg.body.to_lowercase().contains(&query_lower) ||
                 msg.to.iter().any(|to| to.to_lowercase().contains(&query_lower)))
            })
            .cloned()
            .collect();
        
        Ok(filtered)
    }

    /// Group messages into threads
    pub async fn get_threads(&self, account_id: &str, folder: &str) -> Result<Vec<EmailThread>, String> {
        let messages = self.messages.read().await;
        let mut thread_map: HashMap<String, Vec<EmailMessage>> = HashMap::new();
        
        // Group messages by thread ID
        for message in messages.values() {
            if message.id.starts_with(account_id) && message.folder == folder {
                thread_map.entry(message.thread_id.clone())
                    .or_insert_with(Vec::new)
                    .push(message.clone());
            }
        }
        
        // Convert to EmailThread structs
        let mut threads = Vec::new();
        for (thread_id, mut thread_messages) in thread_map {
            thread_messages.sort_by(|a, b| a.timestamp.cmp(&b.timestamp));
            
            let participants: Vec<String> = thread_messages.iter()
                .flat_map(|msg| {
                    let mut p = vec![msg.from.clone()];
                    p.extend(msg.to.clone());
                    p
                })
                .collect::<std::collections::HashSet<_>>()
                .into_iter()
                .collect();
            
            let has_unread = thread_messages.iter().any(|msg| !msg.read);
            let is_flagged = thread_messages.iter().any(|msg| msg.flagged);
            let last_message_date = thread_messages.last().unwrap().timestamp;
            let subject = thread_messages.first().unwrap().subject.clone();
            
            let thread = EmailThread {
                id: thread_id,
                subject,
                participants,
                message_count: thread_messages.len() as u32,
                last_message_date,
                has_unread,
                is_flagged,
                folder: folder.to_string(),
                messages: thread_messages.iter().map(|msg| msg.id.clone()).collect(),
            };
            
            threads.push(thread);
        }
        
        // Sort threads by last message date (newest first)
        threads.sort_by(|a, b| b.last_message_date.cmp(&a.last_message_date));
        
        Ok(threads)
    }

    /// Get sync progress for an account
    pub async fn get_sync_progress(&self, account_id: &str) -> HashMap<String, SyncProgress> {
        let sync_progress = self.sync_progress.read().await;
        sync_progress.iter()
            .filter(|(key, _)| key.starts_with(account_id))
            .map(|(key, progress)| (key.clone(), progress.clone()))
            .collect()
    }

    /// Get all accounts
    pub async fn get_accounts(&self) -> Vec<EmailAccount> {
        let accounts = self.accounts.read().await;
        accounts.values().cloned().collect()
    }

    /// Get folders for an account
    pub async fn get_folders(&self, account_id: &str) -> Option<Vec<EmailFolder>> {
        let folders = self.folders.read().await;
        folders.get(account_id).cloned()
    }

    /// Get messages for a folder
    pub async fn get_folder_messages(&self, account_id: &str, folder: &str) -> Vec<EmailMessage> {
        let messages = self.messages.read().await;
        messages.values()
            .filter(|msg| msg.id.starts_with(account_id) && msg.folder == folder)
            .cloned()
            .collect()
    }

    /// Mark message as read/unread
    pub async fn mark_message_read(&self, _account_id: &str, message_uid: u32, read: bool) -> Result<(), String> {
        // TODO: Implement actual IMAP flag update
        // For now, just update local cache
        
        let mut messages = self.messages.write().await;
        for message in messages.values_mut() {
            if message.uid == message_uid {
                message.read = read;
                break;
            }
        }
        
        Ok(())
    }

    /// Flag/unflag message
    pub async fn flag_message(&self, _account_id: &str, message_uid: u32, flagged: bool) -> Result<(), String> {
        // TODO: Implement actual IMAP flag update
        // For now, just update local cache
        
        let mut messages = self.messages.write().await;
        for message in messages.values_mut() {
            if message.uid == message_uid {
                message.flagged = flagged;
                break;
            }
        }
        
        Ok(())
    }

    /// Move message to folder
    pub async fn move_message(&self, _account_id: &str, message_uid: u32, target_folder: &str) -> Result<(), String> {
        // TODO: Implement actual IMAP move operation
        // For now, just update local cache
        
        let mut messages = self.messages.write().await;
        if let Some(message) = messages.values_mut()
            .find(|msg| msg.uid == message_uid) {
            message.folder = target_folder.to_string();
        }
        
        Ok(())
    }

    /// Delete message
    pub async fn delete_message(&self, account_id: &str, message_uid: u32) -> Result<(), String> {
        // TODO: Implement actual IMAP delete operation
        // For now, just remove from local cache
        
        let mut messages = self.messages.write().await;
        messages.retain(|_, msg| !(msg.uid == message_uid && msg.id.starts_with(account_id)));
        
        Ok(())
    }
}