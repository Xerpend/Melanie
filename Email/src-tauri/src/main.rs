// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod imap_manager;

use std::collections::HashMap;
use std::sync::Arc;
use tauri::{Manager, State};
use serde::{Deserialize, Serialize};

use imap_manager::{IMAPManager, EmailAccount, EmailMessage, EmailFolder, EmailThread, SyncProgress};

#[derive(Debug, Serialize, Deserialize)]
struct AIAnalysis {
    sentiment: String,
    category: String,
    priority: String,
    summary: String,
    suggested_actions: Vec<String>,
}

// Application state
struct AppState {
    imap_manager: Arc<IMAPManager>,
}

impl AppState {
    fn new() -> Self {
        Self {
            imap_manager: Arc::new(IMAPManager::new()),
        }
    }
}

// Tauri commands for email operations
#[tauri::command]
async fn get_email_accounts(state: State<'_, AppState>) -> Result<Vec<EmailAccount>, String> {
    Ok(state.imap_manager.get_accounts().await)
}

#[tauri::command]
async fn add_email_account(account: EmailAccount, state: State<'_, AppState>) -> Result<String, String> {
    log::info!("Adding email account: {}", account.email);
    state.imap_manager.add_account(account).await
}

#[tauri::command]
async fn sync_emails(account_id: String, state: State<'_, AppState>) -> Result<Vec<EmailMessage>, String> {
    log::info!("Syncing emails for account: {}", account_id);
    
    // First sync folders
    let folders = state.imap_manager.sync_folders(&account_id).await?;
    
    // Then sync messages for each folder
    let mut all_messages = Vec::new();
    for folder in folders {
        if folder.selectable {
            let messages = state.imap_manager.sync_folder_messages(&account_id, &folder.path, true).await?;
            all_messages.extend(messages);
        }
    }
    
    Ok(all_messages)
}

#[tauri::command]
async fn sync_folder(account_id: String, folder_path: String, incremental: bool, state: State<'_, AppState>) -> Result<Vec<EmailMessage>, String> {
    log::info!("Syncing folder {} for account: {}", folder_path, account_id);
    state.imap_manager.sync_folder_messages(&account_id, &folder_path, incremental).await
}

#[tauri::command]
async fn get_folders(account_id: String, state: State<'_, AppState>) -> Result<Vec<EmailFolder>, String> {
    state.imap_manager.get_folders(&account_id).await
        .ok_or_else(|| "No folders found for account".to_string())
}

#[tauri::command]
async fn get_folder_messages(account_id: String, folder: String, state: State<'_, AppState>) -> Result<Vec<EmailMessage>, String> {
    Ok(state.imap_manager.get_folder_messages(&account_id, &folder).await)
}

#[tauri::command]
async fn search_messages(account_id: String, query: String, folder: Option<String>, state: State<'_, AppState>) -> Result<Vec<EmailMessage>, String> {
    state.imap_manager.search_messages(&account_id, &query, folder.as_deref()).await
}

#[tauri::command]
async fn get_threads(account_id: String, folder: String, state: State<'_, AppState>) -> Result<Vec<EmailThread>, String> {
    state.imap_manager.get_threads(&account_id, &folder).await
}

#[tauri::command]
async fn mark_message_read(account_id: String, message_uid: u32, read: bool, state: State<'_, AppState>) -> Result<(), String> {
    state.imap_manager.mark_message_read(&account_id, message_uid, read).await
}

#[tauri::command]
async fn flag_message(account_id: String, message_uid: u32, flagged: bool, state: State<'_, AppState>) -> Result<(), String> {
    state.imap_manager.flag_message(&account_id, message_uid, flagged).await
}

#[tauri::command]
async fn move_message(account_id: String, message_uid: u32, target_folder: String, state: State<'_, AppState>) -> Result<(), String> {
    state.imap_manager.move_message(&account_id, message_uid, &target_folder).await
}

#[tauri::command]
async fn delete_message(account_id: String, message_uid: u32, state: State<'_, AppState>) -> Result<(), String> {
    state.imap_manager.delete_message(&account_id, message_uid).await
}

#[tauri::command]
async fn get_sync_progress(account_id: String, state: State<'_, AppState>) -> Result<HashMap<String, SyncProgress>, String> {
    Ok(state.imap_manager.get_sync_progress(&account_id).await)
}

#[tauri::command]
async fn send_email(
    account_id: String,
    to: Vec<String>,
    _cc: Vec<String>,
    _bcc: Vec<String>,
    _subject: String,
    _body: String,
    _html_body: Option<String>,
) -> Result<String, String> {
    // TODO: Implement SMTP email sending
    log::info!("Sending email from account: {} to: {:?}", account_id, to);
    Ok("message_id".to_string())
}

#[tauri::command]
async fn analyze_email_with_ai(message_id: String) -> Result<AIAnalysis, String> {
    // TODO: Implement AI analysis integration with Melanie API
    log::info!("Analyzing email with AI: {}", message_id);
    Ok(AIAnalysis {
        sentiment: "neutral".to_string(),
        category: "general".to_string(),
        priority: "normal".to_string(),
        summary: "Email analysis pending".to_string(),
        suggested_actions: vec!["Reply".to_string(), "Archive".to_string()],
    })
}

#[tauri::command]
async fn summarize_thread(thread_id: String) -> Result<String, String> {
    // TODO: Implement thread summarization using Melanie-3-light
    log::info!("Summarizing thread: {}", thread_id);
    Ok("Thread summary pending".to_string())
}

#[tauri::command]
async fn draft_reply(message_id: String, _context: String) -> Result<String, String> {
    // TODO: Implement reply drafting with RAG context
    log::info!("Drafting reply for message: {}", message_id);
    Ok("Reply draft pending".to_string())
}

#[tauri::command]
async fn get_app_config() -> Result<HashMap<String, String>, String> {
    let mut config = HashMap::new();
    config.insert("theme".to_string(), "dark-blue".to_string());
    config.insert("api_endpoint".to_string(), "http://localhost:8000".to_string());
    config.insert("version".to_string(), env!("CARGO_PKG_VERSION").to_string());
    Ok(config)
}



fn main() {
    env_logger::init();
    
    tauri::Builder::default()
        .manage(AppState::new())
        .invoke_handler(tauri::generate_handler![
            get_email_accounts,
            add_email_account,
            sync_emails,
            sync_folder,
            get_folders,
            get_folder_messages,
            search_messages,
            get_threads,
            mark_message_read,
            flag_message,
            move_message,
            delete_message,
            get_sync_progress,
            send_email,
            analyze_email_with_ai,
            summarize_thread,
            draft_reply,
            get_app_config
        ])
        .setup(|app| {
            let window = app.get_window("main").unwrap();
            
            // Set up window event handlers
            let window_clone = window.clone();
            window.on_window_event(move |event| {
                match event {
                    tauri::WindowEvent::CloseRequested { api, .. } => {
                        // Hide to system tray instead of closing
                        window_clone.hide().unwrap();
                        api.prevent_close();
                    }
                    _ => {}
                }
            });
            
            Ok(())
        })
        .on_window_event(|event| {
            if let tauri::WindowEvent::Destroyed = event.event() {
                // Clean up IMAP connections when window is destroyed
                log::info!("Window destroyed, cleaning up resources");
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}