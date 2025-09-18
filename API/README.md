# Melanie AI FastAPI Server

This module implements the core FastAPI server for the Melanie AI ecosystem with Tailscale network integration and security features.

## Features

- **Tailscale Integration**: Automatic detection and binding to Tailscale network interface
- **Security**: Requires Tailscale for network access, refuses to start without it
- **CORS Configuration**: Properly configured for localhost and Tailscale origins
- **Graceful Lifecycle**: Startup validation and shutdown handlers
- **Health Monitoring**: Health check and status endpoints

## Quick Start

### Prerequisites

1. **Tailscale**: Must be installed and running
   ```bash
   # Install Tailscale (macOS)
   brew install tailscale
   
   # Start Tailscale
   sudo tailscale up
   ```

2. **Python Dependencies**: Install required packages
   ```bash
   pip install -r ../requirements.txt
   ```

### Running the Server

```bash
# Method 1: Direct execution
python3 server.py

# Method 2: Using the startup script
python3 run_server.py

# Method 3: Using Make (from project root)
make run-api
```

The server will:
1. Detect Tailscale network interface
2. Bind to Tailscale IP on port 8000
3. Configure CORS for secure access
4. Provide API documentation at `/docs`

### Testing

```bash
# Run all tests
python3 -m pytest test_server.py -v

# Validate server components
python3 validate_server.py

# Test from project root
make test-api
```

## API Endpoints

### Core Endpoints

- `GET /` - Server information and status
- `GET /health` - Health check with detailed server info
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation

### Tailscale Endpoints

- `GET /tailscale/status` - Tailscale network status and interface information

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# Server Configuration
API_PORT=8000                    # Server port (default: 8000)
API_HOST=auto                    # Auto-detect Tailscale IP

# Security Configuration  
API_KEY_PREFIX=mel_              # API key prefix
BCRYPT_ROUNDS=12                 # Password hashing rounds

# Logging
LOG_LEVEL=INFO                   # Logging level
```

### CORS Origins

The server automatically configures CORS for:
- `localhost:3000` and `localhost:8000` (development)
- `127.0.0.1:3000` and `127.0.0.1:8000` (local)
- Tailscale IP on ports 3000 and 8000 (both HTTP and HTTPS)

## Architecture

### Components

1. **TailscaleDetector**: Network interface detection and IP resolution
2. **ServerConfig**: Configuration management and CORS setup
3. **FastAPI App**: Main application with middleware and routes
4. **Lifespan Manager**: Startup validation and graceful shutdown

### Security Features

- **Network Isolation**: Only accessible via Tailscale network
- **Startup Validation**: Refuses to start without Tailscale
- **CORS Protection**: Restricted origins for cross-origin requests
- **Input Validation**: Pydantic models for request/response validation

## Development

### Project Structure

```
API/
├── server.py           # Main FastAPI server implementation
├── run_server.py       # Startup script with environment loading
├── test_server.py      # Comprehensive test suite
├── validate_server.py  # Server validation script
├── .env.example        # Environment configuration template
└── README.md          # This documentation
```

### Adding New Endpoints

1. Define Pydantic models for request/response
2. Add route handlers to `server.py`
3. Update tests in `test_server.py`
4. Run validation with `validate_server.py`

### Testing Strategy

- **Unit Tests**: Individual component testing with mocks
- **Integration Tests**: Endpoint testing with test client
- **Validation Tests**: End-to-end component validation

## Troubleshooting

### Common Issues

1. **"Tailscale network not detected"**
   - Ensure Tailscale is installed and running
   - Check `tailscale status` command
   - Verify network interfaces with `ip addr` or `ifconfig`

2. **CORS Errors**
   - Check that client origin matches configured CORS origins
   - Verify Tailscale IP detection is working
   - Use `/tailscale/status` endpoint to debug

3. **Port Already in Use**
   - Change `API_PORT` in `.env` file
   - Kill existing processes on port 8000

### Debug Commands

```bash
# Check Tailscale status
tailscale status

# Check network interfaces
python3 -c "import psutil; print(psutil.net_if_addrs())"

# Test server components
python3 validate_server.py

# Check server health
curl http://[tailscale-ip]:8000/health
```

## Next Steps

This server provides the foundation for:
- Authentication system (Task 3)
- Model integration (Tasks 5-9)
- Tool orchestration (Tasks 15-18)
- Chat completions API (Task 19)
- File operations API (Task 20)

See the main project tasks.md for the complete implementation roadmap.