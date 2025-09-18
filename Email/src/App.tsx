import React, { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
import { Mail, Settings, Search, Plus, Bot, AlertCircle, CheckCircle } from 'lucide-react';
import { useAIFeatures } from './hooks/useAIFeatures';

interface AppConfig {
  theme: string;
  api_endpoint: string;
  version: string;
}

function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAIConfig, setShowAIConfig] = useState(false);
  
  // Initialize AI features
  const aiFeatures = useAIFeatures();

  useEffect(() => {
    const loadConfig = async () => {
      try {
        const appConfig = await invoke<Record<string, string>>('get_app_config');
        const apiEndpoint = appConfig.api_endpoint || 'http://localhost:8000';
        
        setConfig({
          theme: appConfig.theme || 'dark-blue',
          api_endpoint: apiEndpoint,
          version: appConfig.version || '1.0.0',
        });

        // Configure AI features with the API endpoint
        await aiFeatures.configure({
          apiUrl: apiEndpoint,
          apiKey: appConfig.melanie_api_key || 'mel_demo_key',
          timeout: 30000,
          enableRAG: true
        });
      } catch (error) {
        console.error('Failed to load app config:', error);
      } finally {
        setLoading(false);
      }
    };

    loadConfig();
  }, [aiFeatures]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-primary-950">
        <div className="text-center">
          <div className="spinner mx-auto mb-4"></div>
          <p className="text-primary-50">Loading Melanie Email...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen bg-primary-950 text-primary-50 flex flex-col">
      {/* Title Bar */}
      <div className="bg-primary-900 border-b border-surface-700 px-4 py-2 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Mail className="w-5 h-5 text-accent-500" />
          <h1 className="text-lg font-semibold text-gradient">Melanie Email</h1>
        </div>
        <div className="flex items-center space-x-2">
          {/* AI Status Indicator */}
          <div className="flex items-center space-x-1">
            <Bot className="w-4 h-4 text-accent-500" />
            {aiFeatures.state.isConnected ? (
              <CheckCircle className="w-3 h-3 text-green-400" />
            ) : (
              <AlertCircle className="w-3 h-3 text-red-400" />
            )}
            <span className="text-xs text-surface-400">
              AI {aiFeatures.state.isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
          
          <span className="text-xs text-surface-400">v{config?.version}</span>
          <button 
            className="p-1 hover:bg-surface-800 rounded"
            onClick={() => setShowAIConfig(!showAIConfig)}
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex">
        {/* Sidebar */}
        <div className="w-64 bg-primary-900 border-r border-surface-700 flex flex-col">
          {/* Search */}
          <div className="p-4 border-b border-surface-700">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-surface-400" />
              <input
                type="text"
                placeholder="Search emails..."
                className="w-full pl-10 pr-4 py-2 bg-surface-800 border border-surface-600 rounded-lg text-sm focus:border-accent-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Folder Tree */}
          <div className="flex-1 p-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-surface-300">Folders</h3>
                <button className="p-1 hover:bg-surface-800 rounded">
                  <Plus className="w-3 h-3" />
                </button>
              </div>
              
              <div className="space-y-1">
                {[
                  { name: 'Inbox', count: 12, color: 'text-unread' },
                  { name: 'Sent', count: 0, color: 'text-sent' },
                  { name: 'Drafts', count: 3, color: 'text-draft' },
                  { name: 'Flagged', count: 2, color: 'text-flagged' },
                  { name: 'Archive', count: 156, color: 'text-archived' },
                  { name: 'Trash', count: 8, color: 'text-surface-400' },
                ].map((folder) => (
                  <div
                    key={folder.name}
                    className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-surface-800 cursor-pointer transition-colors"
                  >
                    <span className="text-sm">{folder.name}</span>
                    {folder.count > 0 && (
                      <span className={`text-xs px-2 py-1 rounded-full bg-surface-800 ${folder.color}`}>
                        {folder.count}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Account Section */}
            <div className="mt-8">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-surface-300">Accounts</h3>
                <button className="p-1 hover:bg-surface-800 rounded">
                  <Plus className="w-3 h-3" />
                </button>
              </div>
              
              <div className="text-sm text-surface-400">
                No accounts configured
              </div>
            </div>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col">
          {/* Email List */}
          <div className="flex-1 bg-surface-900">
            <div className="h-full flex items-center justify-center">
              <div className="text-center">
                <Mail className="w-16 h-16 text-surface-600 mx-auto mb-4" />
                <h2 className="text-xl font-semibold text-surface-300 mb-2">
                  Welcome to Melanie Email
                </h2>
                <p className="text-surface-400 mb-6 max-w-md">
                  Your AI-enhanced email client is ready. Add an email account to get started
                  with intelligent email management.
                </p>
                <button className="bg-accent-500 hover:bg-accent-600 text-white px-6 py-2 rounded-lg font-medium transition-colors">
                  Add Email Account
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Status Bar */}
      <div className="bg-primary-900 border-t border-surface-700 px-4 py-2 flex items-center justify-between text-xs text-surface-400">
        <div className="flex items-center space-x-4">
          <span>Ready</span>
          <span>•</span>
          <span>Connected to {config?.api_endpoint}</span>
          {aiFeatures.state.lastError && (
            <>
              <span>•</span>
              <span className="text-red-400">AI Error: {aiFeatures.state.lastError}</span>
            </>
          )}
        </div>
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${
            aiFeatures.state.isConnected ? 'bg-green-400' : 'bg-red-400'
          }`}></div>
          <span>AI Assistant {aiFeatures.state.isConnected ? 'Active' : 'Inactive'}</span>
        </div>
      </div>
    </div>
  );
}

export default App;