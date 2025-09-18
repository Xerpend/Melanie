# Melanie AI Ecosystem - Deployment Guide

This document provides comprehensive instructions for deploying the Melanie AI Ecosystem across different environments and platforms.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Deployment Methods](#deployment-methods)
5. [Configuration](#configuration)
6. [Security](#security)
7. [Monitoring](#monitoring)
8. [Troubleshooting](#troubleshooting)
9. [Maintenance](#maintenance)

## Overview

The Melanie AI Ecosystem consists of multiple components that can be deployed together or separately:

- **API Server**: FastAPI-based backend with AI model integrations
- **Web Interface**: Next.js frontend for chat interactions
- **RAG Engine**: Rust-based retrieval-augmented generation system
- **CLI Tools**: Cross-platform command-line interface
- **Email Client**: Desktop application with AI features

## Prerequisites

### System Requirements

#### Minimum Requirements
- **OS**: Linux (Ubuntu 18.04+), macOS (10.15+), or Windows 10+
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 10GB free space
- **CPU**: 2+ cores

#### Recommended for Production
- **OS**: Ubuntu 22.04 LTS
- **RAM**: 16GB+
- **Storage**: 50GB+ SSD
- **CPU**: 4+ cores
- **Network**: Gigabit connection

### Software Dependencies

#### Docker Deployment (Recommended)
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### Standalone Deployment
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3-pip nodejs npm cargo

# macOS (with Homebrew)
brew install python@3.11 node rust

# Windows (with Chocolatey)
choco install python nodejs rust
```

### Network Requirements

#### Tailscale Setup (Required)
```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Connect to your network
sudo tailscale up
```

#### API Keys
Obtain API keys from:
- [XAI](https://x.ai) for Grok models
- [OpenAI](https://openai.com) for GPT models
- [Perplexity](https://perplexity.ai) for search capabilities

## Quick Start

### 1. Download and Extract
```bash
# Download the deployment package
wget https://releases.melanie-ai.com/latest/melanie-deployment.tar.gz
tar -xzf melanie-deployment.tar.gz
cd melanie-deployment
```

### 2. Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit with your API keys
nano .env
```

### 3. Deploy with Docker (Recommended)
```bash
# Run deployment script
./deploy-docker.sh

# Or use Make
make docker-deploy
```

### 4. Access Services
- **Web Interface**: http://localhost:3000
- **API Server**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Deployment Methods

### Method 1: Docker Deployment (Recommended)

#### Advantages
- Isolated environments
- Easy scaling
- Consistent across platforms
- Simple updates

#### Steps
```bash
# 1. Build deployment package
make build

# 2. Deploy with Docker
cd deploy-package
./deploy-docker.sh

# 3. Verify deployment
make health-check
```

#### Docker Compose Configuration
```yaml
# docker-compose.yml
version: '3.8'
services:
  melanie-api:
    image: melanie-api:latest
    ports:
      - "8000:8000"
    environment:
      - PYTHONPATH=/app
    env_file:
      - .env
    volumes:
      - ./data/file_storage:/app/file_storage
      - ./data/rag_data:/app/rag_data
    restart: unless-stopped

  melanie-web:
    image: melanie-web:latest
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://melanie-api:8000
    depends_on:
      - melanie-api
    restart: unless-stopped
```

### Method 2: Standalone Deployment

#### Advantages
- Direct system integration
- Lower resource usage
- Easier debugging
- Custom configurations

#### Steps
```bash
# 1. Build standalone packages
make standalone-deploy

# 2. Deploy components
cd deploy-package
./deploy-standalone.sh

# 3. Configure services (Linux)
sudo systemctl enable melanie-api
sudo systemctl enable melanie-web
sudo systemctl start melanie-api
sudo systemctl start melanie-web
```

### Method 3: Development Deployment

#### For Development and Testing
```bash
# 1. Clone repository
git clone https://github.com/your-org/melanie-ai.git
cd melanie-ai

# 2. Setup development environment
make dev-setup

# 3. Start services
make dev-api    # Terminal 1
make dev-web    # Terminal 2
```

## Configuration

### Environment Variables

#### Core Configuration
```bash
# .env file
# API Keys
XAI_API_KEY=your_xai_key_here
OPENAI_API_KEY=your_openai_key_here
PERPLEXITY_API_KEY=your_perplexity_key_here

# Server Configuration
API_HOST=0.0.0.0
API_PORT=8000
WEB_PORT=3000

# Security
SECRET_KEY=your_secret_key_here
ALLOWED_ORIGINS=http://localhost:3000,https://your-domain.com

# Database
RAG_DATA_PATH=./rag_data
FILE_STORAGE_PATH=./file_storage

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/melanie.log
```

#### Advanced Configuration
```bash
# Performance
MAX_WORKERS=4
TIMEOUT_SECONDS=300
RATE_LIMIT_PER_MINUTE=100

# Features
ENABLE_WEB_SEARCH=true
ENABLE_MULTIMODAL=true
ENABLE_RAG=true

# Monitoring
ENABLE_METRICS=true
METRICS_PORT=9090
```

### Service Configuration

#### API Server (API/config.py)
```python
class Settings:
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: List[str] = ["http://localhost:3000"]
    rate_limit: int = 100
    max_file_size: int = 100 * 1024 * 1024  # 100MB
```

#### Web Interface (WEB/.env.local)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_ENABLE_ANALYTICS=false
NEXT_PUBLIC_THEME=dark-blue
```

## Security

### Network Security

#### Tailscale Configuration
```bash
# Configure Tailscale ACLs
{
  "acls": [
    {
      "action": "accept",
      "src": ["group:melanie-users"],
      "dst": ["tag:melanie-server:8000,3000"]
    }
  ],
  "tagOwners": {
    "tag:melanie-server": ["your-email@domain.com"]
  }
}
```

#### Firewall Configuration
```bash
# Ubuntu/Debian
sudo ufw allow from 100.64.0.0/10 to any port 8000
sudo ufw allow from 100.64.0.0/10 to any port 3000
sudo ufw enable

# CentOS/RHEL
sudo firewall-cmd --permanent --add-rich-rule="rule family='ipv4' source address='100.64.0.0/10' port protocol='tcp' port='8000' accept"
sudo firewall-cmd --permanent --add-rich-rule="rule family='ipv4' source address='100.64.0.0/10' port protocol='tcp' port='3000' accept"
sudo firewall-cmd --reload
```

### HTTPS Configuration

#### Nginx Reverse Proxy
```nginx
# /etc/nginx/sites-available/melanie
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;

    # API Server
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Web Interface
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### API Key Management

#### Key Generation
```bash
# Generate secure API keys
python3 -c "
import secrets
import bcrypt

# Generate API key
api_key = 'mel_' + secrets.token_urlsafe(32)
print(f'API Key: {api_key}')

# Generate hash for storage
key_hash = bcrypt.hashpw(api_key.encode(), bcrypt.gensalt())
print(f'Hash: {key_hash.decode()}')
"
```

#### Key Rotation
```bash
# Rotate API keys regularly
./scripts/rotate-keys.sh

# Update client configurations
# Update .env files with new keys
```

## Monitoring

### Health Checks

#### Service Health
```bash
# Check API server
curl -f http://localhost:8000/health

# Check web interface
curl -f http://localhost:3000

# Check all services
make health-check
```

#### Docker Health Checks
```bash
# Check container status
docker-compose ps

# View container health
docker inspect melanie-api | grep -A 10 Health
```

### Logging

#### Log Locations
```bash
# Docker deployment
docker-compose logs -f melanie-api
docker-compose logs -f melanie-web

# Standalone deployment
tail -f /var/log/melanie/api.log
tail -f /var/log/melanie/web.log

# Systemd services
journalctl -u melanie-api -f
journalctl -u melanie-web -f
```

#### Log Configuration
```python
# API/logging_config.py
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
        'file': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': 'logs/melanie.log',
        },
    },
    'loggers': {
        '': {
            'handlers': ['default', 'file'],
            'level': 'INFO',
            'propagate': False
        }
    }
}
```

### Metrics and Monitoring

#### Prometheus Integration
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'melanie-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

#### Grafana Dashboard
```json
{
  "dashboard": {
    "title": "Melanie AI Ecosystem",
    "panels": [
      {
        "title": "API Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"
          }
        ]
      }
    ]
  }
}
```

## Troubleshooting

### Common Issues

#### 1. Tailscale Not Detected
```bash
# Check Tailscale status
tailscale status

# Restart Tailscale
sudo systemctl restart tailscaled

# Check network interfaces
ip addr show | grep tailscale
```

#### 2. Port Conflicts
```bash
# Check port usage
sudo netstat -tlnp | grep :8000
sudo netstat -tlnp | grep :3000

# Change ports in configuration
# Edit docker-compose.yml or .env files
```

#### 3. API Key Issues
```bash
# Verify API keys
curl -H "Authorization: Bearer mel_your_key" http://localhost:8000/health

# Check key format
echo "mel_your_key" | grep -E "^mel_[A-Za-z0-9_-]{32,}$"
```

#### 4. Docker Issues
```bash
# Check Docker daemon
sudo systemctl status docker

# Check container logs
docker-compose logs melanie-api

# Restart containers
docker-compose restart
```

#### 5. Permission Errors
```bash
# Fix file permissions
sudo chown -R $USER:$USER ./data/
chmod -R 755 ./data/

# Fix Docker permissions
sudo usermod -aG docker $USER
newgrp docker
```

### Debug Mode

#### Enable Debug Logging
```bash
# Set environment variable
export LOG_LEVEL=DEBUG

# Or in .env file
LOG_LEVEL=DEBUG
```

#### API Debug Endpoints
```bash
# Check API status
curl http://localhost:8000/debug/status

# Check model availability
curl http://localhost:8000/debug/models

# Check system info
curl http://localhost:8000/debug/system
```

## Maintenance

### Updates

#### Docker Deployment
```bash
# Pull latest images
docker-compose pull

# Restart services
docker-compose up -d

# Clean old images
docker image prune -f
```

#### Standalone Deployment
```bash
# Update from repository
git pull origin main

# Rebuild components
make build

# Restart services
sudo systemctl restart melanie-api
sudo systemctl restart melanie-web
```

### Backups

#### Automated Backup Script
```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/melanie/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup data
cp -r ./data/file_storage "$BACKUP_DIR/"
cp -r ./data/rag_data "$BACKUP_DIR/"

# Backup configuration
cp .env "$BACKUP_DIR/"
cp docker-compose.yml "$BACKUP_DIR/"

# Create archive
tar -czf "$BACKUP_DIR.tar.gz" -C "$BACKUP_DIR" .
rm -rf "$BACKUP_DIR"

echo "Backup created: $BACKUP_DIR.tar.gz"
```

#### Restore from Backup
```bash
# Extract backup
tar -xzf backup_20240101_120000.tar.gz

# Stop services
docker-compose down

# Restore data
cp -r backup_data/file_storage ./data/
cp -r backup_data/rag_data ./data/

# Start services
docker-compose up -d
```

### Performance Optimization

#### Database Optimization
```bash
# RAG database maintenance
cd RAG
cargo run --bin optimize-db

# Clean old embeddings
cargo run --bin cleanup-embeddings --older-than 30d
```

#### Log Rotation
```bash
# Configure logrotate
sudo tee /etc/logrotate.d/melanie << EOF
/var/log/melanie/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 melanie melanie
    postrotate
        systemctl reload melanie-api
    endscript
}
EOF
```

### Scaling

#### Horizontal Scaling
```bash
# Scale API servers
docker-compose up -d --scale melanie-api=3

# Load balancer configuration (nginx)
upstream melanie_api {
    server localhost:8000;
    server localhost:8001;
    server localhost:8002;
}
```

#### Resource Limits
```yaml
# docker-compose.yml
services:
  melanie-api:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

## Support

### Getting Help

- **Documentation**: Check the docs/ directory
- **GitHub Issues**: https://github.com/your-org/melanie-ai/issues
- **Community**: Join our Discord server
- **Email**: support@melanie-ai.com

### Reporting Issues

When reporting issues, please include:
1. Deployment method (Docker/Standalone)
2. Operating system and version
3. Error messages and logs
4. Steps to reproduce
5. Configuration files (without API keys)

### Contributing

See CONTRIBUTING.md for guidelines on:
- Code contributions
- Bug reports
- Feature requests
- Documentation improvements