# Melanie AI Ecosystem

A unified, agentic AI platform designed for comprehensive AI-assisted tasks with emphasis on code quality, long-context handling, and secure modular architecture.

## Project Structure

```
├── AI/                 # Core AI functionality modules (existing)
├── API/                # FastAPI server implementation
├── CLI/                # Terminal CLI coder interface
├── WEB/                # React/Next.js web chat interface
├── Email/              # Desktop email client
├── RAG/                # Rust-based RAG engine with PyO3 bindings
├── tests/              # Test suites
│   ├── unit/           # Unit tests
│   ├── integration/    # Integration tests
│   └── e2e/            # End-to-end tests
├── venv/               # Python virtual environment
├── .env.example        # Environment configuration template
├── requirements.txt    # Python dependencies
├── pyproject.toml      # Python project configuration
├── Makefile           # Development commands
└── README.md          # This file
```

## Features

- **Multi-Model AI Access**: Integrates Grok 4, Grok 3 mini, Grok Code Fast, GPT-5-mini
- **OpenAI-Compatible API**: Standard endpoints for seamless integration
- **Advanced Tool Orchestration**: Intelligent agent coordination and tool calling
- **Production-Grade RAG**: Rust-based vector operations with 500k token context
- **Multiple Interfaces**: Web chat, terminal CLI, desktop email client
- **Deep Research**: Multi-agent research orchestration with PDF generation

## Quick Start

### 1. Environment Setup

```bash
# Clone and navigate to project
cd melanie-ai-ecosystem

# Set up development environment
make setup

# Edit .env with your API keys
cp .env.example .env
# Add your XAI_API_KEY, OPENAI_API_KEY, PERPLEXITY_API_KEY
```

### 2. Install Dependencies

```bash
# Install Python dependencies
make install-dev

# Build Rust RAG engine (requires Rust toolchain)
make build-rag
```

### 3. Run Services

```bash
# Start API server (port 8000)
make run-api

# Start web interface (port 3000) - when implemented
make run-web

# Start CLI interface - when implemented
make run-cli
```

## Development

### Available Commands

```bash
make help           # Show all available commands
make setup          # Complete development environment setup
make install        # Install production dependencies
make install-dev    # Install development dependencies
make test           # Run all tests
make lint           # Run linting checks
make format         # Format code with black and isort
make check          # Run all quality checks
make build          # Build Rust RAG engine and Python packages
make clean          # Clean build artifacts
```

### Testing

```bash
# Run all tests
make test

# Run specific test suites
make test-unit
make test-integration
make test-e2e
```

### Code Quality

```bash
# Format code
make format

# Run linting
make lint

# Run all quality checks
make check
```

## Architecture

### Core Components

1. **API Server** (FastAPI)
   - OpenAI-compatible endpoints
   - Authentication with mel_ prefixed keys
   - Tailscale network integration
   - Rate limiting and security

2. **AI Model Layer**
   - Melanie-3 (Grok 4) - General tasks
   - Melanie-3-light (Grok 3 mini) - Agent coordination
   - Melanie-3-code (Grok Code Fast) - Coding tasks
   - GPT-5-mini - Multimodal processing

3. **RAG System** (Rust)
   - Smart chunking (400-500 tokens)
   - Vector storage with FAISS/Sled
   - Parallel processing with rayon
   - PyO3 Python bindings

4. **Tool Orchestration**
   - Concurrent agent execution
   - Query diversity validation
   - Deep research workflows
   - Tool access matrix by model

### Interfaces

- **Web Chat**: React/Next.js with dark blue theme
- **Terminal CLI**: Rich terminal interface for coding
- **Desktop Email**: Cross-platform with AI features

## Configuration

### Environment Variables

See `.env.example` for all configuration options:

- **API Keys**: XAI, OpenAI, Perplexity, NVIDIA
- **Server Ports**: API (8000), Web (3000), CLI (4000)
- **RAG Settings**: Chunk size, overlap, similarity threshold
- **Security**: Rate limiting, authentication settings

### Model Selection

Choose base model via API requests:
- `Melanie-3`: Heavy computational tasks, full tool access
- `Melanie-3-light`: Lightweight operations, agent coordination
- `Melanie-3-code`: Specialized coding and debugging

## Requirements

- Python 3.11+
- Rust 1.70+ (for RAG engine)
- Node.js 18+ (for web interface)
- Tailscale (for network security)

## API Keys Required

- **XAI API Key**: For Grok models
- **OpenAI API Key**: For GPT-5-mini multimodal
- **Perplexity API Key**: For web search capabilities

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run quality checks: `make check`
5. Submit a pull request

## Support

For issues and questions:
- Check the documentation in each module
- Review the test suites for examples
- Open an issue on GitHub