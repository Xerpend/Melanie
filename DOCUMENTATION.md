# Melanie AI Ecosystem - Complete Documentation

## Table of Contents

1. [Quick Start Guide](#quick-start-guide)
2. [User Guides](#user-guides)
3. [Developer Documentation](#developer-documentation)
4. [Architecture Overview](#architecture-overview)
5. [Configuration Guide](#configuration-guide)
6. [Troubleshooting & FAQ](#troubleshooting--faq)

---

## Quick Start Guide

### Prerequisites

- Python 3.11+
- Tailscale network access
- API keys for AI services (XAI, OpenAI, Perplexity)
- Node.js 18+ (for web interface)
- Rust 1.70+ (for RAG engine)

### 5-Minute Setup

1. **Clone and Setup Environment**
   ```bash
   git clone <repository-url>
   cd melanie-ai-ecosystem
   cp .env.example .env
   # Edit .env with your API keys
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the API Server**
   ```bash
   python API/run_server.py
   ```

4. **Verify Installation**
   ```bash
   curl -H "Authorization: Bearer mel_your_key" \
        http://localhost:8000/health
   ```

---

## User Guides

### Web Chat Interface

The web interface provides an intuitive chat experience with AI models.

#### Getting Started
1. Navigate to `http://localhost:3000` (Tailscale IP)
2. Select your preferred model (Melanie-3, Melanie-3-light, or Melanie-3-code)
3. Start chatting!

#### Key Features
- **Model Selection**: Choose between different AI models based on your needs
- **File Upload**: Upload documents for RAG integration via Studios panel
- **Artifacts**: View and download generated code, diagrams, and documents
- **Web Search**: Enable real-time web search for current information
- **Token Management**: Monitor usage with 500k token limit handling

#### Interface Components
- **Sidebar**: Chat history and conversation management
- **Chat Area**: Message display with markdown support
- **Input Bar**: Text input with model selection and options
- **Studios Panel**: Document management and RAG integration

### Terminal CLI Coder

The CLI provides powerful coding assistance with agent orchestration.

#### Installation
```bash
# Install as binary
pip install -e CLI/
melanie-cli --help
```

#### Basic Usage
```bash
# Start a coding session
melanie-cli "Create a Python web scraper with tests"

# Interactive mode
melanie-cli --interactive
```

#### Features
- **Execution Planning**: AI generates detailed implementation plans
- **Agent Coordination**: Multiple AI agents work in parallel/sequential
- **Code Generation**: Automatic code creation with comments and tests
- **Testing Integration**: Automated test running with 80% coverage target
- **Progress Tracking**: Rich terminal interface with progress bars

### Desktop Email Client

AI-enhanced email management with intelligent features.

#### Setup
1. Download installer for your platform (MSI/DMG/DEB)
2. Install and launch the application
3. Configure IMAP settings for your email provider
4. Set up AI API credentials in preferences

#### AI Features
- **Summarize Thread**: Get bullet-point summaries of email conversations
- **Draft Reply**: AI-generated responses with context awareness
- **Analyze**: Sentiment analysis and email categorization
- **Smart Context**: RAG integration for relevant email history

---

## Developer Documentation

### Architecture Overview

The Melanie AI ecosystem follows a modular, security-first architecture:

```mermaid
graph TB
    subgraph "User Interfaces"
        WEB[Web Chat Interface<br/>Port 3000]
        CLI[Terminal CLI Coder<br/>Port 4000]
        EMAIL[Desktop Email Client<br/>Local]
    end
    
    subgraph "Core API Layer"
        API[FastAPI Server<br/>Port 8000]
        AUTH[Authentication<br/>mel_ keys]
        RATE[Rate Limiting<br/>100 req/min]
    end
    
    subgraph "AI Model Layer"
        GROK4[Melanie-3<br/>Grok 4]
        GROK3[Melanie-3-light<br/>Grok 3 mini]
        GROKCODE[Melanie-3-code<br/>Grok Code Fast]
        GPT5[GPT-5-mini<br/>Multimodal]
        EMBED[Embedding Model]
        RERANK[Reranking Model]
        PERP[Perplexity API<br/>Search]
    end
    
    subgraph "RAG System"
        RAGCORE[Rust RAG Engine<br/>PyO3 Bindings]
        VECTOR[Vector Database<br/>FAISS/Sled]
        CHUNK[Smart Chunking<br/>400-500 tokens]
    end
    
    WEB --> API
    CLI --> API
    EMAIL --> API
    API --> AUTH
    API --> GROK4
    API --> RAGCORE
```

### Development Setup

#### Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Required environment variables
XAI_API_KEY=your_xai_key_here
OPENAI_API_KEY=your_openai_key_here
PERPLEXITY_API_KEY=your_perplexity_key_here
```

#### Running Development Servers
```bash
# API Server (Port 8000)
python API/run_server.py

# Web Interface (Port 3000)
cd WEB && npm run dev

# CLI Development
cd CLI && python main.py

# Email Client Development
cd Email && npm run tauri dev
```

### API Integration

#### Authentication
All API requests require authentication with mel_ prefixed keys:

```python
import requests

headers = {
    "Authorization": "Bearer mel_your_api_key_here",
    "Content-Type": "application/json"
}

response = requests.post(
    "http://localhost:8000/chat/completions",
    headers=headers,
    json={
        "model": "Melanie-3",
        "messages": [{"role": "user", "content": "Hello!"}]
    }
)
```

#### Core Endpoints
- `POST /chat/completions` - Chat with AI models
- `POST /files` - Upload files for processing
- `GET /files/{file_id}` - Retrieve file information
- `DELETE /files/{file_id}` - Delete uploaded files
- `GET /health` - Health check endpoint

### Contributing Guidelines

#### Code Standards
- **Python**: Follow PEP 8, use type hints, 80% test coverage
- **TypeScript**: Use strict mode, follow ESLint rules
- **Rust**: Follow rustfmt, use clippy for linting
- **Documentation**: Update docs for all public APIs

#### Testing Requirements
```bash
# Python tests
pytest tests/ --cov=. --cov-report=html

# TypeScript tests
npm test -- --coverage

# Rust tests
cargo test
```

#### Pull Request Process
1. Fork the repository
2. Create feature branch: `git checkout -b feature/your-feature`
3. Implement changes with tests
4. Update documentation
5. Submit pull request with detailed description

### Extending the System

#### Adding New AI Models
1. Implement `BaseAIModel` interface
2. Add model configuration to settings
3. Update tool access matrix
4. Add comprehensive tests

```python
class NewAIModel(BaseAIModel):
    async def generate(self, messages: List[Dict], tools: Optional[List] = None) -> Dict:
        # Implementation here
        pass
```

#### Creating New Tools
1. Implement tool interface
2. Add to tool registry
3. Configure concurrency limits
4. Add validation and tests

```python
class CustomTool:
    async def execute(self, parameters: Dict) -> Dict:
        # Tool implementation
        pass
```

---

## Configuration Guide

### Environment Variables

#### Core API Configuration
```bash
# API Server
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1

# Security
SECRET_KEY=your_secret_key_here
RATE_LIMIT_PER_MINUTE=100

# Tailscale
TAILSCALE_REQUIRED=true
```

#### AI Model Configuration
```bash
# XAI (Grok Models)
XAI_API_KEY=your_xai_key
XAI_BASE_URL=https://api.x.ai/v1
XAI_TIMEOUT=3600

# OpenAI (Multimodal)
OPENAI_API_KEY=your_openai_key
OPENAI_BASE_URL=https://api.openai.com/v1

# Perplexity (Search)
PERPLEXITY_API_KEY=your_perplexity_key
PERPLEXITY_BASE_URL=https://api.perplexity.ai
```

#### RAG System Configuration
```bash
# Vector Database
VECTOR_DB_TYPE=faiss  # or sled
VECTOR_DB_PATH=./rag_data

# Chunking Settings
CHUNK_SIZE=500
CHUNK_OVERLAP=50
EMBEDDING_BATCH_SIZE=32

# Retrieval Settings
GENERAL_CONTEXT_CHUNKS=20
RESEARCH_CONTEXT_CHUNKS=100
RERANK_THRESHOLD=0.7
```

### Model-Specific Settings

#### Melanie-3 (Grok 4)
```json
{
  "model": "grok-4",
  "max_tokens": 128000,
  "temperature": 0.7,
  "tools_enabled": ["coder", "multimodal", "search"],
  "concurrency_limit": 1
}
```

#### Melanie-3-light (Grok 3 mini)
```json
{
  "model": "grok-3-mini",
  "max_tokens": 32000,
  "temperature": 0.5,
  "tools_enabled": ["coder", "multimodal", "search", "agent"],
  "concurrency_limit": 5
}
```

### Interface Configuration

#### Web Interface
```javascript
// WEB/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
NEXT_PUBLIC_MAX_FILE_SIZE=10485760  // 10MB
```

#### CLI Configuration
```yaml
# CLI/config.yaml
api:
  base_url: "http://localhost:8000"
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

#### Email Client Configuration
```json
{
  "imap": {
    "host": "imap.gmail.com",
    "port": 993,
    "secure": true
  },
  "ai": {
    "api_url": "http://localhost:8000",
    "features": {
      "summarize": true,
      "draft_reply": true,
      "analyze": true
    }
  }
}
```

---

## Troubleshooting & FAQ

### Common Issues

#### API Server Won't Start

**Problem**: Server fails to start with Tailscale error
```
ERROR: Tailscale network not detected. Server requires Tailscale for security.
```

**Solution**:
1. Install and start Tailscale: `sudo tailscale up`
2. Verify connection: `tailscale status`
3. Restart the API server

**Problem**: Port already in use
```
ERROR: Port 8000 is already in use
```

**Solution**:
```bash
# Find process using port
lsof -i :8000
# Kill process or change port in configuration
```

#### Authentication Issues

**Problem**: Invalid API key error
```json
{"error": "invalid_api_key", "message": "API key must start with 'mel_'"}
```

**Solution**:
1. Generate new API key: `python API/auth.py generate-key`
2. Update your client configuration
3. Ensure key starts with `mel_` prefix

#### Model Integration Issues

**Problem**: XAI API timeout
```
TimeoutError: Request to XAI API timed out after 60 seconds
```

**Solution**:
1. Check XAI API status
2. Increase timeout in configuration
3. Verify API key permissions

#### RAG System Issues

**Problem**: Vector database initialization fails
```
ERROR: Failed to initialize vector database
```

**Solution**:
1. Check disk space in `./rag_data` directory
2. Verify write permissions
3. Clear corrupted database: `rm -rf rag_data && mkdir rag_data`

### Performance Optimization

#### API Server Performance
```bash
# Increase worker processes
API_WORKERS=4

# Enable caching
REDIS_URL=redis://localhost:6379

# Optimize database connections
DB_POOL_SIZE=20
```

#### RAG System Performance
```bash
# Increase batch sizes
EMBEDDING_BATCH_SIZE=64
CHUNK_BATCH_SIZE=100

# Enable parallel processing
RAYON_NUM_THREADS=8
```

### Frequently Asked Questions

#### Q: Can I use the system without Tailscale?
A: No, Tailscale is required for security. The API server will refuse to start without it.

#### Q: What's the difference between the three Melanie models?
A: 
- **Melanie-3**: General purpose, most capable (Grok 4)
- **Melanie-3-light**: Lightweight, good for coordination (Grok 3 mini)
- **Melanie-3-code**: Specialized for coding tasks (Grok Code Fast)

#### Q: How do I increase the 500k token limit?
A: The limit is designed for memory management. Instead of increasing it, use the save/summary options when reached.

#### Q: Can I add custom AI models?
A: Yes, implement the `BaseAIModel` interface and add to the model registry.

#### Q: How do I backup my data?
A: 
```bash
# Backup RAG data
tar -czf rag_backup.tar.gz rag_data/

# Backup file storage
tar -czf files_backup.tar.gz file_storage/

# Backup configuration
cp .env .env.backup
```

#### Q: Is the system production-ready?
A: The core API and RAG system are production-ready. Web, CLI, and Email interfaces are in active development.

#### Q: How do I monitor system health?
A: Use the health endpoints:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/detailed
```

#### Q: Can I run multiple instances?
A: Yes, but ensure each instance has:
- Unique ports
- Separate data directories
- Load balancer for distribution

### Getting Help

#### Community Support
- GitHub Issues: Report bugs and feature requests
- Discussions: Ask questions and share experiences
- Wiki: Community-maintained documentation

#### Professional Support
- Enterprise support available for production deployments
- Custom integration services
- Training and consultation

#### Development Resources
- API Documentation: `/docs` endpoint
- Code Examples: `examples/` directory
- Test Suite: `tests/` directory
- Architecture Diagrams: `docs/architecture/`

---

## Appendix

### API Reference
Complete API documentation is available at `/docs` when the server is running.

### Configuration Schema
Detailed configuration schemas are available in `docs/config/`.

### Migration Guides
Version migration guides are available in `docs/migrations/`.

### Security Guidelines
Security best practices are documented in `docs/security/`.