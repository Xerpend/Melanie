# Melanie CLI - Terminal AI Coder

A powerful command-line interface for AI-assisted coding with agent coordination, plan generation, and comprehensive project management.

## Features

- **Multi-Agent Coordination**: Orchestrate 1-3 AI agents for complex coding tasks
- **Intelligent Planning**: Automatic task breakdown and dependency analysis
- **Rich Terminal Interface**: Beautiful progress tracking and status displays
- **Session Management**: Persistent sessions with pause/resume capabilities
- **Cross-Platform**: Native binaries for macOS, Linux, and Windows
- **Project-Aware**: Context-sensitive code generation and testing

## Installation

### Binary Installation (Recommended)

Download the latest binary for your platform from the [releases page](https://github.com/melanie-ai/melanie-cli/releases):

- **macOS**: `melanie-cli-macos-arm64.zip` or `melanie-cli-macos-x86_64.zip`
- **Linux**: `melanie-cli-linux-x86_64.tar.gz`
- **Windows**: `melanie-cli-windows-x86_64.zip`

Extract and add to your PATH:

```bash
# macOS/Linux
tar -xzf melanie-cli-*.tar.gz
sudo mv melanie-cli /usr/local/bin/

# Windows
# Extract melanie-cli.exe and add to PATH
```

### Development Installation

```bash
# Clone repository
git clone https://github.com/melanie-ai/melanie-cli.git
cd melanie-cli

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

## Quick Start

### 1. Configuration

Set up your API endpoint and key:

```bash
# Configure API endpoint
melanie-cli config set api_endpoint http://localhost:8000

# Set API key (or use MELANIE_API_KEY environment variable)
melanie-cli config set api_key mel_your_api_key_here
```

### 2. Basic Usage

```bash
# Simple coding task
melanie-cli code "Create a REST API for user management"

# Specify project directory
melanie-cli code "Add unit tests for auth module" --project ./my-app

# Control agent behavior
melanie-cli code "Refactor database layer" --agents 2 --parallel
```

### 3. Session Management

```bash
# Create named session
melanie-cli code "Build web scraper" --session webscraper-project

# List sessions
melanie-cli session list

# Resume session
melanie-cli session load webscraper-project

# Delete session
melanie-cli session delete old-project
```

## Usage Examples

### Web Development

```bash
# Create a full-stack web application
melanie-cli code "Create a React frontend with Node.js backend for a todo app" \\
  --project ./todo-app --agents 3 --parallel

# Add authentication
melanie-cli code "Add JWT authentication with login/register endpoints" \\
  --project ./todo-app --session todo-auth
```

### API Development

```bash
# Build REST API
melanie-cli code "Create FastAPI server with CRUD operations for blog posts" \\
  --project ./blog-api

# Add testing
melanie-cli code "Add comprehensive unit tests with 80% coverage" \\
  --project ./blog-api
```

### Data Processing

```bash
# Create data pipeline
melanie-cli code "Build ETL pipeline to process CSV files and generate reports" \\
  --project ./data-pipeline --agents 2
```

### Code Refactoring

```bash
# Refactor existing code
melanie-cli code "Refactor legacy code to use modern Python patterns" \\
  --project ./legacy-app --agents 1
```

## Configuration

### Configuration File

The CLI stores configuration in:
- **macOS/Linux**: `~/.config/melanie-cli/config.json`
- **Windows**: `%APPDATA%\\melanie-cli\\config.json`

### Environment Variables

```bash
export MELANIE_API_ENDPOINT="http://localhost:8000"
export MELANIE_API_KEY="mel_your_api_key"
export MELANIE_MAX_AGENTS=3
export MELANIE_TIMEOUT=300
export MELANIE_VERBOSE=true
```

### Configuration Commands

```bash
# Show current configuration
melanie-cli config show

# Set configuration values
melanie-cli config set api_endpoint http://localhost:8000
melanie-cli config set max_agents 3

# Reset to defaults
melanie-cli config reset
```

## Agent Coordination

### Execution Strategies

**Parallel Execution**: Multiple agents work simultaneously on independent tasks
- Faster completion for complex projects
- Automatic dependency resolution
- Best for: Large projects, independent modules

**Sequential Execution**: Single agent works through tasks in order
- More predictable and controlled
- Better for: Simple tasks, learning, debugging

### Agent Capabilities

- **Agent 1-3**: Specialized coding agents using Melanie-3-code
- **Plan Generation**: Uses Melanie-3-light for task analysis
- **Tool Integration**: Access to multimodal processing and web search
- **Quality Assurance**: Automatic testing and code review

## Session Management

### Session Features

- **Persistence**: Full state preservation across restarts
- **Recovery**: Resume interrupted tasks
- **History**: Track all changes and decisions
- **Context**: Maintain project understanding

### Session Commands

```bash
# Create session
melanie-cli code "task description" --session session-name

# List all sessions
melanie-cli session list

# Load existing session
melanie-cli session load session-name

# Delete session
melanie-cli session delete session-name
```

## Building from Source

### Prerequisites

- Python 3.8+
- pip
- PyInstaller (for binary builds)

### Build Commands

```bash
# Install build dependencies
make dev-install

# Run tests
make test

# Build executable
make build

# Create distribution package
make package

# Full build pipeline
make all
```

### Platform-Specific Builds

```bash
# macOS
make build-macos

# Linux
make build-linux

# Windows
make build-windows
```

## Development

### Project Structure

```
CLI/
├── main.py              # Entry point
├── cli_app.py           # Main CLI application
├── theme.py             # Dark blue theme
├── config.py            # Configuration management
├── session.py           # Session persistence
├── api_client.py        # API communication
├── agent_coordinator.py # Agent orchestration
├── plan_generator.py    # Task planning
├── result_compiler.py   # Result processing
├── build.py             # Build script
├── requirements.txt     # Dependencies
└── README.md           # Documentation
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

### Code Style

```bash
# Format code
make format

# Run linting
make lint
```

## Troubleshooting

### Common Issues

**Connection Error**
```bash
# Check API endpoint
melanie-cli config show

# Test connection
curl http://localhost:8000/health
```

**Authentication Error**
```bash
# Verify API key
melanie-cli config show

# Set new API key
melanie-cli config set api_key mel_new_key
```

**Build Issues**
```bash
# Clean and rebuild
make clean
make build
```

### Debug Mode

```bash
# Enable verbose output
melanie-cli code "task" --verbose

# Or set environment variable
export MELANIE_VERBOSE=true
```

### Logs

Session logs are stored in:
- **macOS/Linux**: `~/.config/melanie-cli/logs/`
- **Windows**: `%APPDATA%\\melanie-cli\\logs\\`

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- **Documentation**: [docs.melanie.ai/cli](https://docs.melanie.ai/cli)
- **Issues**: [GitHub Issues](https://github.com/melanie-ai/melanie-cli/issues)
- **Discussions**: [GitHub Discussions](https://github.com/melanie-ai/melanie-cli/discussions)