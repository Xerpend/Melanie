# Melanie AI Web Interface

A modern, responsive web chat interface for the Melanie AI Assistant Suite, built with Next.js 15, TypeScript, and Tailwind CSS.

## Features

- **Dark Blue Theme**: Consistent with Melanie AI branding (#001F3F, #007BFF, #F0F4F8)
- **Chat Interface**: Real-time messaging with AI models
- **Model Selection**: Choose between Melanie-3, Melanie-3-light, and Melanie-3-code
- **Artifact System**: Expandable code/diagram cards with download functionality
- **Studios Panel**: File upload and RAG integration management
- **Tailscale Integration**: Secure network binding for private deployment

## Technology Stack

- **Framework**: Next.js 15 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS 4
- **Fonts**: Inter (sans-serif), JetBrains Mono (monospace)
- **Network**: Tailscale integration for secure access

## Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn
- Tailscale running and connected

### Installation

1. Install dependencies:
```bash
cd WEB
npm install
```

2. Configure environment variables:
```bash
cp .env.example .env.local
# Edit .env.local with your API configuration
```

3. Start the development server:
```bash
# Regular development (localhost)
npm run dev

# Tailscale-bound server (production-like)
npm run start:tailscale
```

The application will be available at:
- Development: http://localhost:3000
- Tailscale: http://[tailscale-ip]:3000

## Project Structure

```
WEB/
├── src/
│   ├── app/                 # Next.js App Router
│   │   ├── globals.css      # Global styles with dark blue theme
│   │   ├── layout.tsx       # Root layout with metadata
│   │   └── page.tsx         # Main chat page
│   ├── components/          # React components
│   │   ├── chat/           # Chat-specific components
│   │   │   ├── ChatArea.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   ├── InputBar.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── ArtifactCard.tsx
│   │   │   └── StudiosPanel.tsx
│   │   ├── layout/         # Layout components
│   │   │   └── ChatLayout.tsx
│   │   └── ui/             # Reusable UI components
│   ├── lib/                # Utilities and API client
│   │   └── api.ts          # API client for backend communication
│   ├── types/              # TypeScript type definitions
│   │   ├── chat.ts         # Chat-related types
│   │   └── api.ts          # API response types
│   ├── hooks/              # Custom React hooks
│   └── utils/              # Utility functions
├── scripts/
│   └── start-server.js     # Tailscale detection and binding
├── public/                 # Static assets
├── tailwind.config.ts      # Tailwind configuration with theme
├── next.config.ts          # Next.js configuration
└── package.json           # Dependencies and scripts
```

## Component Architecture

### ChatLayout
Main layout component that orchestrates the entire chat interface:
- Manages chat sessions and messages
- Handles Studios panel visibility
- Coordinates between sidebar, chat area, and input bar

### Sidebar
Left panel for navigation and chat history:
- New chat creation
- Session search and selection
- Chat history with message counts

### ChatArea
Central message display area:
- Message bubbles with role-based styling
- Artifact rendering (code, diagrams, documents)
- Loading states and typing indicators
- Welcome screen for new chats

### InputBar
Bottom input area for user interaction:
- Model selection dropdown
- Web search toggle
- File upload button
- Auto-resizing textarea
- Token counter display

### StudiosPanel
Right panel for file management:
- Drag-and-drop file upload
- File processing status
- RAG integration indicators
- Document preview and metadata

### ArtifactCard
Expandable cards for AI-generated content:
- Syntax highlighting for code
- Download functionality
- Collapsible content display
- Type-specific icons and formatting

## Theme Configuration

The application uses a consistent dark blue theme:

```css
:root {
  --primary: #001F3F;      /* Dark navy blue */
  --accent: #007BFF;       /* Bright blue */
  --text: #F0F4F8;         /* Light text */
  --background: #001F3F;   /* Primary background */
  --background-light: #0A2A4A;  /* Lighter background */
  --background-card: #1A3A5A;   /* Card background */
}
```

## API Integration

The web interface communicates with the Melanie API server:

- **Chat Completions**: `/chat/completions` for AI conversations
- **File Operations**: `/files` for upload, retrieval, and deletion
- **Health Checks**: `/health` for system status monitoring

## Tailscale Integration

The application includes Tailscale detection and binding:

1. **Network Detection**: Automatically detects Tailscale interface
2. **Secure Binding**: Binds server to Tailscale IP address
3. **Graceful Failure**: Exits if Tailscale is not available
4. **CORS Configuration**: Restricts access to Tailscale network

## Development

### Adding New Components

1. Create component in appropriate directory (`components/chat/`, `components/ui/`)
2. Export from component file
3. Import and use in parent components
4. Add TypeScript types in `types/` directory

### Styling Guidelines

- Use Tailwind CSS classes with theme variables
- Follow dark blue color scheme
- Ensure responsive design for mobile/desktop
- Use consistent spacing and typography

### API Integration

- Use the `apiClient` from `lib/api.ts`
- Handle loading and error states
- Implement proper TypeScript typing
- Follow REST conventions

## Building for Production

```bash
# Build the application
npm run build

# Start production server
npm run start

# Or start with Tailscale binding
npm run start:tailscale
```

## Environment Variables

Create `.env.local` with:

```env
NEXT_PUBLIC_API_URL=http://[tailscale-ip]:8000
NEXT_PUBLIC_API_KEY=mel_your_api_key_here
```

## Security Considerations

- API keys are handled client-side (consider server-side proxy for production)
- Tailscale provides network-level security
- CORS restrictions limit access to authorized origins
- Input validation on all user inputs
- Secure headers configured in Next.js config

## Future Enhancements

- Real-time WebSocket connections for live chat
- Offline support with service workers
- Advanced artifact types (interactive diagrams, data visualizations)
- Collaborative features (shared chats, comments)
- Mobile app using React Native
- Advanced file processing (OCR, document analysis)