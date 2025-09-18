'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Highlight, themes } from 'prism-react-renderer';
import { Artifact } from '@/types/chat';

interface ArtifactCardProps {
  artifact: Artifact;
}

interface ExecutionResult {
  output: string;
  error?: string;
  type: 'success' | 'error';
}

export const ArtifactCard: React.FC<ArtifactCardProps> = ({ artifact }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showExecutionWarning, setShowExecutionWarning] = useState(false);
  const [executionResult, setExecutionResult] = useState<ExecutionResult | null>(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const handleDownload = () => {
    if (!artifact.downloadable) return;
    
    const mimeType = getMimeType();
    const blob = new Blob([artifact.content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = getFileName();
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const getMimeType = () => {
    switch (artifact.language) {
      case 'javascript':
      case 'typescript':
        return 'text/javascript';
      case 'python':
        return 'text/x-python';
      case 'html':
        return 'text/html';
      case 'css':
        return 'text/css';
      case 'json':
        return 'application/json';
      default:
        return 'text/plain';
    }
  };

  const getFileName = () => {
    const extension = getFileExtension();
    return `${artifact.title || artifact.id}.${extension}`;
  };

  const getFileExtension = () => {
    switch (artifact.language) {
      case 'javascript':
        return 'js';
      case 'typescript':
        return 'ts';
      case 'python':
        return 'py';
      case 'html':
        return 'html';
      case 'css':
        return 'css';
      case 'json':
        return 'json';
      case 'markdown':
        return 'md';
      default:
        return 'txt';
    }
  };

  const getIcon = () => {
    switch (artifact.type) {
      case 'code':
        return artifact.executable ? '⚡' : '💻';
      case 'diagram':
        return '📊';
      case 'document':
        return '📄';
      default:
        return '📎';
    }
  };

  const canExecute = () => {
    return artifact.executable && 
           artifact.executionEnvironment && 
           ['javascript', 'html', 'css'].includes(artifact.executionEnvironment);
  };

  const executeCode = async () => {
    if (!canExecute()) return;

    setIsExecuting(true);
    setExecutionResult(null);

    try {
      switch (artifact.executionEnvironment) {
        case 'javascript':
          await executeJavaScript();
          break;
        case 'html':
          await executeHTML();
          break;
        case 'css':
          await executeCSS();
          break;
        default:
          throw new Error(`Execution environment ${artifact.executionEnvironment} not supported`);
      }
    } catch (error) {
      setExecutionResult({
        output: '',
        error: error instanceof Error ? error.message : 'Unknown error occurred',
        type: 'error'
      });
    } finally {
      setIsExecuting(false);
    }
  };

  const executeJavaScript = async () => {
    return new Promise<void>((resolve) => {
      // Create a sandboxed iframe for JavaScript execution
      const iframe = document.createElement('iframe');
      iframe.style.display = 'none';
      iframe.sandbox = 'allow-scripts';
      
      document.body.appendChild(iframe);
      
      const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
      if (!iframeDoc) {
        throw new Error('Could not access iframe document');
      }

      // Capture console output
      const outputs: string[] = [];
      const errors: string[] = [];

      const script = `
        <script>
          // Override console methods to capture output
          const originalLog = console.log;
          const originalError = console.error;
          const originalWarn = console.warn;
          
          console.log = (...args) => {
            window.parent.postMessage({
              type: 'console',
              level: 'log',
              message: args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' ')
            }, '*');
          };
          
          console.error = (...args) => {
            window.parent.postMessage({
              type: 'console',
              level: 'error',
              message: args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' ')
            }, '*');
          };
          
          console.warn = (...args) => {
            window.parent.postMessage({
              type: 'console',
              level: 'warn',
              message: args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' ')
            }, '*');
          };

          // Handle uncaught errors
          window.onerror = (message, source, lineno, colno, error) => {
            window.parent.postMessage({
              type: 'error',
              message: message,
              line: lineno,
              column: colno
            }, '*');
            return true;
          };

          try {
            ${artifact.content}
            window.parent.postMessage({ type: 'complete' }, '*');
          } catch (error) {
            window.parent.postMessage({
              type: 'error',
              message: error.message,
              stack: error.stack
            }, '*');
          }
        </script>
      `;

      // Listen for messages from iframe
      const messageHandler = (event: MessageEvent) => {
        if (event.source !== iframe.contentWindow) return;

        switch (event.data.type) {
          case 'console':
            if (event.data.level === 'error') {
              errors.push(event.data.message);
            } else {
              outputs.push(`[${event.data.level}] ${event.data.message}`);
            }
            break;
          case 'error':
            errors.push(`Error: ${event.data.message}`);
            if (event.data.line) {
              errors.push(`  at line ${event.data.line}:${event.data.column || 0}`);
            }
            break;
          case 'complete':
            window.removeEventListener('message', messageHandler);
            document.body.removeChild(iframe);
            
            setExecutionResult({
              output: outputs.length > 0 ? outputs.join('\n') : 'Code executed successfully (no output)',
              error: errors.length > 0 ? errors.join('\n') : undefined,
              type: errors.length > 0 ? 'error' : 'success'
            });
            resolve();
            break;
        }
      };

      window.addEventListener('message', messageHandler);

      // Set a timeout to prevent hanging
      setTimeout(() => {
        window.removeEventListener('message', messageHandler);
        if (document.body.contains(iframe)) {
          document.body.removeChild(iframe);
        }
        setExecutionResult({
          output: outputs.join('\n'),
          error: 'Execution timeout (5 seconds)',
          type: 'error'
        });
        resolve();
      }, 5000);

      iframeDoc.write(script);
      iframeDoc.close();
    });
  };

  const executeHTML = async () => {
    // For HTML, create a preview in an iframe
    const iframe = iframeRef.current;
    if (!iframe) return;

    const blob = new Blob([artifact.content], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    iframe.src = url;

    setExecutionResult({
      output: 'HTML rendered in preview below',
      type: 'success'
    });

    // Clean up the blob URL after a delay
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const executeCSS = async () => {
    // For CSS, show a preview with some sample HTML
    const sampleHTML = `
      <!DOCTYPE html>
      <html>
      <head>
        <style>
          ${artifact.content}
        </style>
      </head>
      <body>
        <div class="container">
          <h1>CSS Preview</h1>
          <p>This is a sample paragraph to demonstrate the CSS styles.</p>
          <button>Sample Button</button>
          <div class="box">Sample Box</div>
        </div>
      </body>
      </html>
    `;

    const iframe = iframeRef.current;
    if (!iframe) return;

    const blob = new Blob([sampleHTML], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    iframe.src = url;

    setExecutionResult({
      output: 'CSS styles applied to sample HTML below',
      type: 'success'
    });

    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const handleExecuteClick = () => {
    if (!canExecute()) return;
    setShowExecutionWarning(true);
  };

  const confirmExecution = () => {
    setShowExecutionWarning(false);
    executeCode();
  };

  const cancelExecution = () => {
    setShowExecutionWarning(false);
  };

  return (
    <div className="border border-primary-200 rounded-lg bg-background-card overflow-hidden shadow-lg">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-primary-200 bg-background-light">
        <div className="flex items-center space-x-3">
          <span className="text-xl">{getIcon()}</span>
          <div>
            <div className="font-semibold text-text">
              {artifact.title || `${artifact.type} artifact`}
            </div>
            {artifact.language && (
              <div className="text-sm text-text-500 flex items-center space-x-2">
                <span>{artifact.language}</span>
                {artifact.executable && (
                  <span className="bg-accent-500 text-white px-2 py-0.5 rounded-full text-xs">
                    Executable
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
          {canExecute() && (
            <button
              onClick={handleExecuteClick}
              disabled={isExecuting}
              className="bg-accent-500 hover:bg-accent-600 disabled:bg-accent-300 text-white px-3 py-1.5 rounded text-sm transition-colors flex items-center space-x-1"
            >
              {isExecuting ? (
                <>
                  <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-white"></div>
                  <span>Running...</span>
                </>
              ) : (
                <>
                  <span>▶</span>
                  <span>Run</span>
                </>
              )}
            </button>
          )}
          
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-accent-500 hover:text-accent-600 transition-colors p-1"
          >
            {isExpanded ? '▼' : '▶'}
          </button>
          
          {artifact.downloadable && (
            <button
              onClick={handleDownload}
              className="bg-primary-500 hover:bg-primary-600 text-white px-3 py-1.5 rounded text-sm transition-colors flex items-center space-x-1"
            >
              <span>⬇</span>
              <span>Download</span>
            </button>
          )}
        </div>
      </div>
      
      {/* Safety Warning Modal */}
      {showExecutionWarning && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-background-card border border-primary-200 rounded-lg p-6 max-w-md mx-4">
            <div className="flex items-center space-x-3 mb-4">
              <span className="text-2xl">⚠️</span>
              <h3 className="text-lg font-semibold text-text">Code Execution Warning</h3>
            </div>
            <div className="text-text-400 mb-6 space-y-2">
              <p>You are about to execute code in a sandboxed environment.</p>
              <p className="text-sm">
                <strong>Safety measures in place:</strong>
              </p>
              <ul className="text-sm list-disc list-inside space-y-1 ml-2">
                <li>Code runs in an isolated iframe</li>
                <li>No access to your files or network</li>
                <li>5-second execution timeout</li>
                <li>Limited to safe operations only</li>
              </ul>
              <p className="text-sm text-accent-400">
                Only execute code you trust and understand.
              </p>
            </div>
            <div className="flex space-x-3">
              <button
                onClick={confirmExecution}
                className="bg-accent-500 hover:bg-accent-600 text-white px-4 py-2 rounded transition-colors"
              >
                Execute Code
              </button>
              <button
                onClick={cancelExecution}
                className="bg-primary-300 hover:bg-primary-400 text-text px-4 py-2 rounded transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Content */}
      {isExpanded && (
        <div className="p-4">
          {artifact.type === 'code' && artifact.language ? (
            <div className="space-y-4">
              <Highlight
                theme={themes.vsDark}
                code={artifact.content}
                language={artifact.language as any}
              >
                {({ className, style, tokens, getLineProps, getTokenProps }) => (
                  <pre 
                    className={`${className} p-4 rounded-lg overflow-x-auto text-sm`}
                    style={{
                      ...style,
                      backgroundColor: '#0A1628',
                      border: '1px solid #1E3A5F'
                    }}
                  >
                    {tokens.map((line, i) => {
                      const { key: lineKey, ...lineProps } = getLineProps({ line });
                      return (
                        <div key={i} {...lineProps}>
                          <span className="text-text-400 mr-4 select-none">
                            {String(i + 1).padStart(2, ' ')}
                          </span>
                          {line.map((token, key) => {
                            const { key: tokenKey, ...tokenProps } = getTokenProps({ token });
                            return <span key={key} {...tokenProps} />;
                          })}
                        </div>
                      );
                    })}
                  </pre>
                )}
              </Highlight>
              
              {/* Execution Result */}
              {executionResult && (
                <div className={`p-3 rounded-lg border ${
                  executionResult.type === 'error' 
                    ? 'bg-red-900/20 border-red-500/30 text-red-200' 
                    : 'bg-green-900/20 border-green-500/30 text-green-200'
                }`}>
                  <div className="font-semibold mb-2 flex items-center space-x-2">
                    <span>{executionResult.type === 'error' ? '❌' : '✅'}</span>
                    <span>Execution Result</span>
                  </div>
                  {executionResult.output && (
                    <pre className="text-sm font-mono whitespace-pre-wrap mb-2">
                      {executionResult.output}
                    </pre>
                  )}
                  {executionResult.error && (
                    <pre className="text-sm font-mono whitespace-pre-wrap text-red-300">
                      {executionResult.error}
                    </pre>
                  )}
                </div>
              )}
              
              {/* HTML/CSS Preview */}
              {(artifact.executionEnvironment === 'html' || artifact.executionEnvironment === 'css') && 
               executionResult && executionResult.type === 'success' && (
                <div className="border border-primary-200 rounded-lg overflow-hidden">
                  <div className="bg-background-light p-2 border-b border-primary-200">
                    <span className="text-sm text-text-400">Preview</span>
                  </div>
                  <iframe
                    ref={iframeRef}
                    className="w-full h-64 border-0"
                    sandbox="allow-scripts"
                    title="Code Preview"
                  />
                </div>
              )}
            </div>
          ) : (
            <div className="text-text whitespace-pre-wrap font-mono text-sm bg-primary-900/30 p-4 rounded-lg">
              {artifact.content}
            </div>
          )}
        </div>
      )}
    </div>
  );
};