# Melanie Email - Desktop Application

AI-enhanced email client with intelligent assistance features including thread summarization, reply drafting, and sentiment analysis.

## Features

- **AI-Enhanced Email Management**: Intelligent thread summarization, reply drafting, and email analysis
- **Cross-Platform**: Native desktop application for Windows, macOS, and Linux
- **Dark Blue Theme**: Consistent with Melanie AI brand colors (#001F3F, #007BFF)
- **System Tray Integration**: Minimize to system tray for background operation
- **IMAP/SMTP Support**: Connect to any email provider with IMAP/SMTP support
- **Secure Storage**: Encrypted credential storage using system keychain
- **RAG Integration**: Context-aware AI assistance using Melanie's RAG system

## Technology Stack

- **Frontend**: React 18 + TypeScript + Tailwind CSS
- **Backend**: Rust with Tauri framework
- **Email**: IMAP/SMTP with native-tls encryption
- **AI Integration**: Melanie API for intelligent features
- **Build System**: Vite + Tauri CLI

## Prerequisites

- **Node.js** 18+ and npm
- **Rust** 1.70+ with Cargo
- **System Dependencies**:
  - **Windows**: Visual Studio Build Tools or Visual Studio Community
  - **macOS**: Xcode Command Line Tools
  - **Linux**: `libgtk-3-dev libwebkit2gtk-4.0-dev libayatana-appindicator3-dev librsvg2-dev`

## Installation

### Development Setup

1. **Clone and navigate to the Email directory**:
   ```bash
   cd Email
   ```

2. **Install dependencies**:
   ```bash
   make install
   # or manually:
   npm install
   cd src-tauri && cargo fetch
   ```

3. **Start development server**:
   ```bash
   make dev
   # or manually:
   npm run tauri:dev
   ```

### Production Build

1. **Build for current platform**:
   ```bash
   make build
   # or manually:
   npm run build
   npm run tauri:build
   ```

2. **Build for all platforms** (requires cross-compilation setup):
   ```bash
   make build-all
   ```

## Configuration

### Email Account Setup

The application supports IMAP/SMTP email accounts. Configuration is handled through the UI with secure credential storage.

### AI Integration

Configure the Melanie API endpoint in the application settings:
- **Default**: `http://localhost:8000`
- **Authentication**: Uses mel_ prefixed API keys
- **Features**: Thread summarization, reply drafting, email analysis

### Theme Customization

The application uses a consistent dark blue theme:
- **Primary**: #001F3F (Dark Blue)
- **Accent**: #007BFF (Bright Blue)
- **Text**: #F0F4F8 (Light Gray)

## Build Artifacts

### Windows
- **MSI Installer**: `src-tauri/target/release/bundle/msi/`
- **NSIS Installer**: `src-tauri/target/release/bundle/nsis/`

### macOS
- **DMG**: `src-tauri/target/release/bundle/dmg/`
- **App Bundle**: `src-tauri/target/release/bundle/macos/`

### Linux
- **DEB Package**: `src-tauri/target/release/bundle/deb/`
- **AppImage**: `src-tauri/target/release/bundle/appimage/`

## Development Commands

```bash
# Development
make dev              # Start development server
make build            # Build for current platform
make clean            # Clean build artifacts

# Code Quality
make lint             # Run linters
make format           # Format code
make test             # Run tests

# Dependencies
make deps             # Check dependencies
make setup-dev        # Setup development environment
```

## Architecture

### Frontend (React + TypeScript)
- **Components**: Email interface components with AI features
- **Styling**: Tailwind CSS with custom Melanie theme
- **State Management**: React hooks and context
- **API Integration**: Tauri commands for backend communication

### Backend (Rust + Tauri)
- **Email Operations**: IMAP/SMTP client implementation
- **AI Integration**: HTTP client for Melanie API
- **System Integration**: System tray, notifications, file system
- **Security**: Encrypted credential storage

### AI Features
- **Thread Summarization**: Using Melanie-3-light model
- **Reply Drafting**: Context-aware response generation
- **Email Analysis**: Sentiment analysis and categorization
- **RAG Integration**: Relevant context injection from email history

## Security

- **Credential Storage**: System keychain integration
- **Network Security**: TLS encryption for email protocols
- **API Security**: Secure communication with Melanie API
- **Input Validation**: Comprehensive input sanitization

## Contributing

1. **Setup Development Environment**:
   ```bash
   make setup-dev
   ```

2. **Code Style**:
   - Follow Rust and TypeScript best practices
   - Use provided linting and formatting tools
   - Maintain consistent theme and UI patterns

3. **Testing**:
   - Write unit tests for new features
   - Test cross-platform compatibility
   - Verify AI integration functionality

## Troubleshooting

### Build Issues

1. **Missing System Dependencies**:
   - **Linux**: Install required GTK and WebKit libraries
   - **Windows**: Install Visual Studio Build Tools
   - **macOS**: Install Xcode Command Line Tools

2. **Rust Compilation Errors**:
   ```bash
   rustup update
   cargo clean
   ```

3. **Node.js Issues**:
   ```bash
   rm -rf node_modules package-lock.json
   npm install
   ```

### Runtime Issues

1. **Email Connection Problems**:
   - Verify IMAP/SMTP settings
   - Check firewall and network connectivity
   - Ensure proper authentication credentials

2. **AI Features Not Working**:
   - Verify Melanie API is running on localhost:8000
   - Check API key configuration
   - Review network connectivity to API endpoint

## License

MIT License - see LICENSE file for details.

## Support

For support and bug reports, please use the project's issue tracker or contact the Melanie AI team.