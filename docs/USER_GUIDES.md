# User Guides - Melanie AI Ecosystem

## Table of Contents

1. [Web Chat Interface Guide](#web-chat-interface-guide)
2. [Terminal CLI Coder Guide](#terminal-cli-coder-guide)
3. [Desktop Email Client Guide](#desktop-email-client-guide)
4. [API Usage Guide](#api-usage-guide)

---

## Web Chat Interface Guide

### Getting Started

The web interface provides the most user-friendly way to interact with Melanie AI models.

#### Accessing the Interface
1. Ensure the API server is running: `python API/run_server.py`
2. Start the web interface: `cd WEB && npm run dev`
3. Open your browser to `http://localhost:3000` (or your Tailscale IP)

#### First Steps
1. **Select a Model**: Choose from the dropdown in the input bar
   - **Melanie-3**: Best for complex reasoning and general tasks
   - **Melanie-3-light**: Faster responses, good for quick questions
   - **Melanie-3-code**: Specialized for programming tasks

2. **Start Chatting**: Type your message and press Enter or click Send

3. **Upload Documents**: Use the Studios panel to upload files for context

### Interface Components

#### Main Chat Area
- **Message Bubbles**: Your messages appear on the right (gray), AI responses on the left (blue)
- **Markdown Support**: AI responses support rich formatting, code blocks, and tables
- **Artifacts**: Generated code, diagrams, and documents appear as expandable cards
- **Typing Indicators**: Shows when the AI is processing your request

#### Sidebar Features
- **Chat History**: Access previous conversations
- **Search**: Find specific conversations or messages
- **New Chat**: Start fresh conversations
- **Settings**: Adjust preferences and themes

#### Input Bar
- **Text Area**: Type your messages (supports multi-line with Shift+Enter)
- **Model Selection**: Switch between AI models
- **Web Search Toggle**: Enable real-time web search
- **File Upload**: Attach documents, images, or code files
- **Send Button**: Submit your message

#### Studios Panel
- **Document Upload**: Drag and drop files or click to browse
- **Processing Status**: See which files are being processed
- **RAG Integration**: View how documents are being used for context
- **File Management**: Organize and delete uploaded files

### Advanced Features

#### Working with Artifacts
Artifacts are special outputs like code, diagrams, or documents:

1. **Viewing**: Click to expand artifact cards
2. **Downloading**: Use the download button to save artifacts
3. **Copying**: Copy code directly from syntax-highlighted blocks
4. **Editing**: Some artifacts support inline editing

#### Token Management
The system tracks your token usage to prevent memory issues:

- **Token Counter**: Shows current usage in the input bar
- **Limit Warning**: Alerts when approaching 500k token limit
- **Limit Reached Modal**: Options to:
  - Start new chat (clears context)
  - Save conversation as Markdown
  - Download summary PDF

#### Web Search Integration
Enable web search for current information:

1. Toggle "Web Search" in the input bar
2. AI will automatically search when needed
3. Search results are integrated into responses
4. Sources are cited in the response

### Best Practices

#### Getting Better Responses
- **Be Specific**: Provide clear, detailed requests
- **Use Context**: Reference previous messages or uploaded documents
- **Break Down Complex Tasks**: Split large requests into smaller parts
- **Provide Examples**: Show the AI what you're looking for

#### Managing Context
- **Upload Relevant Documents**: Use Studios panel for background information
- **Reference Previous Work**: The AI remembers your conversation history
- **Start New Chats**: When switching topics completely
- **Use Summaries**: Ask for summaries of long conversations

#### File Upload Tips
- **Supported Formats**: TXT, MD, PDF, images, code files
- **Automatic Processing**: Text files are automatically indexed for search
- **Image Analysis**: Upload images for visual analysis
- **Code Review**: Upload code files for analysis and suggestions

### Troubleshooting

#### Common Issues

**Interface Won't Load**
- Check that both API server and web server are running
- Verify Tailscale connection
- Clear browser cache and cookies

**Messages Not Sending**
- Check API key configuration
- Verify network connection
- Look for error messages in browser console

**Files Won't Upload**
- Check file size (10MB limit)
- Verify file format is supported
- Ensure sufficient disk space

**Slow Responses**
- Try switching to Melanie-3-light for faster responses
- Check network connection
- Reduce context size by starting new chat

---

## Terminal CLI Coder Guide

### Installation and Setup

#### Installing the CLI
```bash
# From the project root
cd CLI
pip install -e .

# Verify installation
melanie-cli --version
```

#### Configuration
Create a configuration file at `~/.melanie-cli/config.yaml`:

```yaml
api:
  base_url: "http://localhost:8000"
  api_key: "mel_your_api_key_here"
  timeout: 300

display:
  theme: "dark_blue"
  progress_bars: true
  rich_output: true

agents:
  max_parallel: 3
  retry_attempts: 2
  timeout_per_agent: 300
```

### Basic Usage

#### Simple Coding Requests
```bash
# Basic request
melanie-cli "Create a Python function to calculate fibonacci numbers"

# With specific requirements
melanie-cli "Build a REST API with FastAPI that handles user authentication"

# Interactive mode
melanie-cli --interactive
```

#### Advanced Options
```bash
# Specify output directory
melanie-cli "Create a web scraper" --output ./my-project

# Enable verbose logging
melanie-cli "Build a CLI tool" --verbose

# Use specific model
melanie-cli "Write unit tests" --model melanie-3-code

# Enable web search
melanie-cli "Create a modern React app" --web-search
```

### Understanding the Workflow

#### 1. Plan Generation
When you make a request, the CLI:
1. Analyzes your requirements using Melanie-3-light
2. Creates a detailed execution plan
3. Determines if tasks can run in parallel or must be sequential
4. Shows you the plan for approval

#### 2. Agent Orchestration
After plan approval:
1. Spawns 1-3 Melanie-3-code agents based on complexity
2. Each agent works on specific parts of the project
3. Agents can access web search and documentation
4. Progress is shown with rich terminal displays

#### 3. Code Generation
Each agent:
1. Generates code with comprehensive comments
2. Creates unit tests for all functions
3. Runs tests and iterates on failures (1-3 attempts)
4. Aims for 80% test coverage

#### 4. Results Compilation
After all agents complete:
1. Results are compiled into a coherent project
2. Summary is generated with key decisions
3. You're prompted for next actions

### Interactive Features

#### Plan Review and Modification
```
┌─ Execution Plan ─────────────────────────────────────┐
│ Project: Python Web Scraper                         │
│                                                      │
│ Phase 1 (Parallel):                                 │
│   Agent 1: Core scraping logic                      │
│   Agent 2: Data processing utilities                │
│                                                      │
│ Phase 2 (Sequential):                               │
│   Agent 3: Integration and testing                  │
│                                                      │
│ Estimated time: 5-8 minutes                         │
└──────────────────────────────────────────────────────┘

Approve this plan? [Y/n/edit]:
```

#### Real-time Progress Tracking
```
┌─ Agent Execution ────────────────────────────────────┐
│ Agent 1: Core Logic        ████████████░░░░  75%     │
│ Agent 2: Data Processing   ██████████████░░  85%     │
│ Agent 3: Testing          ░░░░░░░░░░░░░░░░░░   0%     │
│                                                      │
│ Current: Running unit tests for scraper.py          │
└──────────────────────────────────────────────────────┘
```

#### Result Actions
```
┌─ Execution Complete ─────────────────────────────────┐
│ ✓ Generated 5 Python files                          │
│ ✓ Created 12 unit tests (85% coverage)              │
│ ✓ All tests passing                                  │
│                                                      │
│ Next action:                                         │
│   [e] Edit code                                      │
│   [r] Run project                                    │
│   [t] Add more tests                                 │
│   [d] Generate documentation                         │
│   [x] Exit                                           │
└──────────────────────────────────────────────────────┘
```

### Advanced Features

#### Session Management
```bash
# Save current session
melanie-cli --save-session my-project

# Resume previous session
melanie-cli --resume-session my-project

# List saved sessions
melanie-cli --list-sessions
```

#### Custom Templates
```bash
# Use project template
melanie-cli "Create FastAPI app" --template fastapi-starter

# Create custom template
melanie-cli --create-template my-template
```

#### Integration with Development Tools
```bash
# Initialize git repository
melanie-cli "Create Python package" --git-init

# Set up virtual environment
melanie-cli "Build Django app" --venv

# Install dependencies automatically
melanie-cli "Create React app" --install-deps
```

### Best Practices

#### Writing Effective Requests
- **Be Specific**: "Create a REST API with user auth, rate limiting, and PostgreSQL"
- **Include Context**: "Build on the existing Flask app in ./current-project"
- **Specify Technologies**: "Use FastAPI, SQLAlchemy, and pytest"
- **Mention Requirements**: "Include Docker configuration and CI/CD setup"

#### Managing Complex Projects
- **Break into Phases**: Request one feature at a time for large projects
- **Use Sessions**: Save progress for multi-day development
- **Review Plans**: Always review execution plans before approval
- **Iterate**: Use edit mode to refine generated code

#### Optimizing Performance
- **Parallel Tasks**: Let the CLI determine parallelization automatically
- **Specific Models**: Use melanie-3-code for pure coding tasks
- **Web Search**: Enable for current framework/library information
- **Resource Limits**: Monitor system resources during execution

### Troubleshooting

#### Common Issues

**CLI Won't Connect to API**
```bash
# Check API server status
curl http://localhost:8000/health

# Verify configuration
melanie-cli --check-config

# Test connection
melanie-cli --test-connection
```

**Agents Failing or Timing Out**
- Reduce complexity of request
- Check network connectivity
- Increase timeout in configuration
- Try sequential execution instead of parallel

**Generated Code Has Issues**
- Use edit mode to refine code
- Request additional tests
- Ask for code review and improvements
- Enable web search for current best practices

**Performance Issues**
- Reduce number of parallel agents
- Use melanie-3-light for planning phase
- Close other resource-intensive applications
- Check system memory and CPU usage

---

## Desktop Email Client Guide

### Installation

#### System Requirements
- Windows 10+, macOS 10.15+, or Linux (Ubuntu 18.04+)
- 4GB RAM minimum, 8GB recommended
- 500MB disk space
- Internet connection for AI features

#### Download and Install
1. Download installer for your platform:
   - Windows: `melanie-email-setup.msi`
   - macOS: `melanie-email.dmg`
   - Linux: `melanie-email.deb` or `melanie-email.AppImage`

2. Run installer and follow setup wizard

3. Launch application from desktop or applications menu

### Initial Setup

#### Email Account Configuration
1. **Launch Setup Wizard**: First run opens account setup
2. **Choose Provider**: Select from common providers or manual setup
3. **Enter Credentials**: Provide email and password
4. **IMAP Settings**: Configure server settings (auto-detected for common providers)
5. **Test Connection**: Verify settings work correctly

#### AI Features Setup
1. **API Configuration**: Enter your Melanie API endpoint and key
2. **Feature Selection**: Choose which AI features to enable
3. **Privacy Settings**: Configure data handling preferences
4. **Test AI Connection**: Verify AI features are working

### Interface Overview

#### Main Window Layout
```
┌─ Folder Tree ─┬─ Thread List ──────┬─ Preview Pane ─┐
│ Inbox         │ Subject: Meeting   │ From: John     │
│ ├─ Important  │ From: John Smith   │ Date: Today    │
│ ├─ Sent       │ Date: 2 hours ago  │                │
│ ├─ Drafts     │ ✓ Read             │ Hi team,       │
│ └─ Archive    │                    │                │
│               │ Subject: Project   │ Let's discuss  │
│ Custom Labels │ From: Sarah Jones  │ the quarterly  │
│ ├─ Work       │ Date: 1 day ago    │ results...     │
│ ├─ Personal   │ ⭐ Starred         │                │
│ └─ Travel     │                    │ [AI Features]  │
│               │ Subject: Invoice   │ [Summarize]    │
│               │ From: Accounting   │ [Draft Reply]  │
│               │ Date: 3 days ago   │ [Analyze]      │
└───────────────┴────────────────────┴────────────────┘
```

#### Folder Tree
- **Standard Folders**: Inbox, Sent, Drafts, Trash
- **Custom Labels**: Create and organize with custom labels
- **Smart Folders**: Auto-generated based on rules
- **Search**: Quick search across all folders

#### Thread List
- **Conversation View**: Related emails grouped together
- **Sorting Options**: Date, sender, subject, importance
- **Filtering**: Unread, starred, attachments, date ranges
- **Bulk Actions**: Select multiple emails for batch operations

#### Preview Pane
- **Email Content**: Rich text display with images and attachments
- **AI Features Bar**: Quick access to AI-powered tools
- **Attachment Handling**: Preview and download attachments
- **Reply/Forward**: Quick action buttons

### AI-Enhanced Features

#### Summarize Thread
Condenses long email conversations into key points:

1. **Select Thread**: Click on email conversation
2. **Click Summarize**: Use AI features bar or right-click menu
3. **Review Summary**: AI generates bullet-point summary
4. **Save Summary**: Option to save summary as note

**Example Output**:
```
Thread Summary: Q4 Planning Meeting
• Meeting scheduled for Friday 2 PM
• Agenda includes budget review and team assignments
• Sarah will present marketing metrics
• John needs to prepare development timeline
• Decision needed on new hire approvals
```

#### Draft Reply
Generates contextual email responses:

1. **Select Email**: Choose email to reply to
2. **Click Draft Reply**: AI analyzes context and tone
3. **Review Draft**: AI generates appropriate response
4. **Edit and Send**: Modify as needed before sending

**Features**:
- **Tone Matching**: Matches formality level of original
- **Context Awareness**: References previous conversation points
- **Action Items**: Identifies and addresses requests
- **Personalization**: Uses your writing style over time

#### Analyze Email
Provides insights about email content and sender:

1. **Select Email**: Choose email for analysis
2. **Click Analyze**: AI examines content and metadata
3. **View Insights**: See analysis results

**Analysis Includes**:
- **Sentiment**: Positive, neutral, or negative tone
- **Urgency**: High, medium, or low priority
- **Category**: Work, personal, promotional, etc.
- **Action Required**: Whether response is needed
- **Key Topics**: Main subjects discussed

### Advanced Features

#### Smart Filtering and Rules
- **Auto-Categorization**: AI automatically labels incoming emails
- **Priority Detection**: Important emails highlighted automatically
- **Spam Enhancement**: AI-powered spam detection beyond standard filters
- **Custom Rules**: Create rules based on AI analysis results

#### Context Integration
- **RAG Integration**: AI remembers previous conversations
- **Cross-Reference**: Links related emails across time
- **Contact Intelligence**: Builds profiles of frequent contacts
- **Project Tracking**: Groups emails by project or topic

#### Productivity Tools
- **Email Templates**: AI-generated templates for common responses
- **Scheduling Assistant**: Finds meeting times from email content
- **Follow-up Reminders**: AI suggests when to follow up
- **Email Insights**: Analytics on your email patterns

### Customization and Settings

#### AI Feature Configuration
```
┌─ AI Settings ────────────────────────────────────────┐
│ ✓ Enable thread summarization                       │
│ ✓ Enable draft reply generation                     │
│ ✓ Enable email analysis                             │
│ ✓ Enable smart categorization                       │
│                                                      │
│ Privacy Settings:                                    │
│ ○ Process emails locally only                       │
│ ● Send to AI service (encrypted)                    │
│ ○ Opt out of AI features                            │
│                                                      │
│ Response Style:                                      │
│ ○ Formal                                             │
│ ● Professional                                       │
│ ○ Casual                                             │
│ ○ Match sender's tone                                │
└──────────────────────────────────────────────────────┘
```

#### Interface Customization
- **Theme Selection**: Light, dark, or system theme
- **Layout Options**: Adjust pane sizes and positions
- **Font Settings**: Customize reading font and size
- **Notification Preferences**: Configure alerts and sounds

#### Account Management
- **Multiple Accounts**: Add and manage multiple email accounts
- **Sync Settings**: Configure sync frequency and offline storage
- **Backup Options**: Export emails and settings
- **Security Settings**: Two-factor authentication and encryption

### Troubleshooting

#### Common Issues

**Email Sync Problems**
1. Check internet connection
2. Verify IMAP settings
3. Check email provider status
4. Restart application

**AI Features Not Working**
1. Verify API key configuration
2. Check API server status
3. Test network connectivity
4. Review privacy settings

**Performance Issues**
1. Reduce sync frequency
2. Archive old emails
3. Clear application cache
4. Check system resources

**Missing Emails**
1. Check spam/junk folder
2. Verify folder sync settings
3. Check email provider filters
4. Force manual sync

#### Getting Support
- **Help Menu**: Built-in help and tutorials
- **Log Files**: Export logs for troubleshooting
- **Community Forum**: User community and support
- **Professional Support**: Enterprise support options

---

## API Usage Guide

### Authentication

#### Getting API Keys
```bash
# Generate new API key
python API/auth.py generate-key --name "my-app"

# List existing keys
python API/auth.py list-keys

# Deactivate key
python API/auth.py deactivate-key mel_abc123...
```

#### Using API Keys
All requests must include the API key in the Authorization header:

```bash
curl -H "Authorization: Bearer mel_your_api_key_here" \
     -H "Content-Type: application/json" \
     http://localhost:8000/health
```

### Core Endpoints

#### Chat Completions
Send messages to AI models:

```bash
curl -X POST http://localhost:8000/chat/completions \
  -H "Authorization: Bearer mel_your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Melanie-3",
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ],
    "web_search": false,
    "max_tokens": 1000
  }'
```

**Response**:
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1699123456,
  "model": "Melanie-3",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! I'm doing well, thank you for asking..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 25,
    "total_tokens": 37
  }
}
```

#### File Operations
Upload and manage files:

```bash
# Upload file
curl -X POST http://localhost:8000/files \
  -H "Authorization: Bearer mel_your_key" \
  -F "file=@document.pdf"

# Get file info
curl -X GET http://localhost:8000/files/file_id_here \
  -H "Authorization: Bearer mel_your_key"

# Delete file
curl -X DELETE http://localhost:8000/files/file_id_here \
  -H "Authorization: Bearer mel_your_key"
```

### Programming Language Examples

#### Python
```python
import requests
import json

class MelanieClient:
    def __init__(self, api_key, base_url="http://localhost:8000"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def chat(self, messages, model="Melanie-3", web_search=False):
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self.headers,
            json={
                "model": model,
                "messages": messages,
                "web_search": web_search
            }
        )
        return response.json()
    
    def upload_file(self, file_path):
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(
                f"{self.base_url}/files",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files=files
            )
        return response.json()

# Usage
client = MelanieClient("mel_your_api_key_here")
response = client.chat([
    {"role": "user", "content": "Explain quantum computing"}
])
print(response["choices"][0]["message"]["content"])
```

#### JavaScript/Node.js
```javascript
class MelanieClient {
    constructor(apiKey, baseUrl = 'http://localhost:8000') {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
        this.headers = {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json'
        };
    }

    async chat(messages, model = 'Melanie-3', webSearch = false) {
        const response = await fetch(`${this.baseUrl}/chat/completions`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                model,
                messages,
                web_search: webSearch
            })
        });
        return await response.json();
    }

    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${this.baseUrl}/files`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.apiKey}`
            },
            body: formData
        });
        return await response.json();
    }
}

// Usage
const client = new MelanieClient('mel_your_api_key_here');
const response = await client.chat([
    { role: 'user', content: 'Write a JavaScript function' }
]);
console.log(response.choices[0].message.content);
```

### Advanced Usage

#### Tool Calling
Request specific tools for enhanced capabilities:

```python
response = client.chat(
    messages=[
        {"role": "user", "content": "Analyze this image and write code to process it"}
    ],
    tools=[
        {
            "type": "function",
            "function": {
                "name": "multimodal",
                "description": "Analyze images and documents"
            }
        },
        {
            "type": "function", 
            "function": {
                "name": "coder",
                "description": "Generate and debug code"
            }
        }
    ]
)
```

#### Deep Research Mode
Enable comprehensive research with multiple agents:

```python
response = client.chat(
    messages=[
        {"role": "user", "content": "Research the latest developments in quantum computing"}
    ],
    model="Melanie-3",
    web_search=True,
    # This will trigger deep research orchestration
    tools=[
        {"type": "function", "function": {"name": "light-search"}},
        {"type": "function", "function": {"name": "medium-search"}}
    ]
)

# Response includes research_plan field
print(response.get("research_plan", {}).get("summary"))
```

#### Streaming Responses
For real-time response streaming:

```python
import sseclient

def stream_chat(client, messages):
    response = requests.post(
        f"{client.base_url}/chat/completions",
        headers=client.headers,
        json={
            "model": "Melanie-3",
            "messages": messages,
            "stream": True
        },
        stream=True
    )
    
    client_stream = sseclient.SSEClient(response)
    for event in client_stream.events():
        if event.data != '[DONE]':
            chunk = json.loads(event.data)
            content = chunk["choices"][0]["delta"].get("content", "")
            print(content, end="", flush=True)
```

### Error Handling

#### Common Error Responses
```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit of 100 requests per minute exceeded",
  "details": {
    "retry_after": 60,
    "current_usage": 101,
    "limit": 100
  }
}
```

#### Robust Error Handling
```python
import time
from typing import Optional

class MelanieClientWithRetry(MelanieClient):
    def chat_with_retry(self, messages, max_retries=3, **kwargs):
        for attempt in range(max_retries):
            try:
                response = self.chat(messages, **kwargs)
                
                # Check for API errors
                if "error" in response:
                    error_type = response["error"]
                    
                    if error_type == "rate_limit_exceeded":
                        retry_after = response.get("details", {}).get("retry_after", 60)
                        print(f"Rate limited, waiting {retry_after} seconds...")
                        time.sleep(retry_after)
                        continue
                    
                    elif error_type == "model_timeout":
                        print(f"Model timeout, retrying... (attempt {attempt + 1})")
                        continue
                    
                    else:
                        raise Exception(f"API Error: {response['message']}")
                
                return response
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                print(f"Network error, retrying... (attempt {attempt + 1})")
                time.sleep(2 ** attempt)  # Exponential backoff
        
        raise Exception("Max retries exceeded")
```

### Best Practices

#### Performance Optimization
- **Batch Requests**: Group multiple operations when possible
- **Appropriate Models**: Use Melanie-3-light for simple tasks
- **Context Management**: Keep conversations focused to reduce token usage
- **Caching**: Cache responses for repeated queries

#### Security Best Practices
- **Secure Key Storage**: Never hardcode API keys
- **Environment Variables**: Use environment variables for configuration
- **Key Rotation**: Regularly rotate API keys
- **Network Security**: Use HTTPS in production

#### Rate Limit Management
- **Respect Limits**: Stay within 100 requests per minute
- **Implement Backoff**: Use exponential backoff for retries
- **Monitor Usage**: Track your request patterns
- **Multiple Keys**: Use different keys for different applications

This comprehensive user guide covers all major interfaces and usage patterns for the Melanie AI ecosystem. Each section provides practical examples and troubleshooting guidance to help users get the most out of the system.