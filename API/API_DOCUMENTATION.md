# Melanie AI API Documentation

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Authentication](#authentication)
4. [Rate Limiting](#rate-limiting)
5. [Error Handling](#error-handling)
6. [API Endpoints](#api-endpoints)
7. [Integration Examples](#integration-examples)
8. [SDKs and Libraries](#sdks-and-libraries)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

## Overview

The Melanie AI API provides secure access to multiple AI models through a unified interface, featuring advanced orchestration, RAG capabilities, and enterprise-grade security.

### Key Features

- **Multi-Model Integration**: Access to Grok-4, Grok-3-mini, Grok-Code-Fast, and GPT-5-mini
- **OpenAI Compatibility**: Standard OpenAI API format for seamless integration
- **Advanced Orchestration**: Deep research workflows with multi-agent coordination
- **RAG System**: Production-grade retrieval-augmented generation
- **Tool System**: Intelligent tool calling with automatic selection
- **Security**: Tailscale network requirement with API key authentication
- **MCP Integration**: Access to current documentation and best practices

### Base URL

```
http://{your-tailscale-ip}:8000
```

Replace `{your-tailscale-ip}` with your actual Tailscale IP address.

## Getting Started

### Prerequisites

1. **Tailscale Network**: The API requires Tailscale for security
2. **API Key**: Generate an API key using the `/auth/keys` endpoint
3. **Network Access**: Ensure your client can reach the Tailscale network

### Quick Start

1. **Check Server Status**
   ```bash
   curl http://your-tailscale-ip:8000/health
   ```

2. **Create API Key**
   ```bash
   curl -X POST http://your-tailscale-ip:8000/auth/keys
   ```

3. **Make Your First Request**
   ```bash
   curl -X POST http://your-tailscale-ip:8000/chat/completions \
     -H "Authorization: Bearer mel_your_api_key" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "Melanie-3",
       "messages": [
         {"role": "user", "content": "Hello, world!"}
       ]
     }'
   ```

## Authentication

### API Key Format

All API keys use the `mel_` prefix format:
```
mel_abcdef1234567890abcdef1234567890abcdef12
```

### Authentication Header

Include your API key in the Authorization header:
```
Authorization: Bearer mel_your_api_key_here
```

### Key Management

#### Create API Key

```bash
curl -X POST http://your-tailscale-ip:8000/auth/keys
```

**Response:**
```json
{
  "api_key": "mel_abcdef1234567890abcdef1234567890abcdef12",
  "key_id": "mel_abcdef12",
  "message": "API key created successfully. Store this key securely - it cannot be retrieved again.",
  "rate_limit": 100
}
```

#### Get Key Information

```bash
curl -H "Authorization: Bearer mel_your_api_key" \
     http://your-tailscale-ip:8000/auth/keys/mel_abcdef12
```

#### Deactivate Key

```bash
curl -X DELETE \
     -H "Authorization: Bearer mel_your_api_key" \
     http://your-tailscale-ip:8000/auth/keys/mel_abcdef12
```

## Rate Limiting

### Default Limits

- **Rate**: 100 requests per minute per API key
- **Burst**: Short bursts allowed within the minute window
- **Enforcement**: Sliding window algorithm

### Rate Limit Headers

Response headers include rate limit information:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

### Rate Limit Exceeded

When rate limit is exceeded, you'll receive a `429 Too Many Requests` response:
```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit of 100 requests per minute exceeded",
  "details": {
    "limit": 100,
    "remaining": 0,
    "reset_at": "2023-12-01T10:05:00Z"
  },
  "timestamp": "2023-12-01T10:04:30Z"
}
```

## Error Handling

### Error Response Format

All errors follow a consistent format:
```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {
    "additional": "context"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

### Common Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `validation_error` | 400 | Invalid request format or parameters |
| `unauthorized` | 401 | Invalid or missing API key |
| `forbidden` | 403 | Access denied for requested resource |
| `not_found` | 404 | Requested resource not found |
| `rate_limit_exceeded` | 429 | Rate limit exceeded |
| `model_error` | 500 | AI model processing error |
| `service_unavailable` | 503 | Service temporarily unavailable |

### Error Handling Best Practices

1. **Check Status Codes**: Always check HTTP status codes
2. **Parse Error Messages**: Use error codes for programmatic handling
3. **Implement Retry Logic**: Use exponential backoff for retries
4. **Log Errors**: Log errors with timestamps for debugging

## API Endpoints

### Core Endpoints

#### GET /
Get basic server information.

**Response:**
```json
{
  "message": "Melanie AI API Server",
  "version": "1.0.0",
  "status": "running",
  "tailscale_ip": "100.64.1.2"
}
```

#### GET /health
Get server health status.

**Response:**
```json
{
  "status": "healthy",
  "message": "Melanie AI API Server is running",
  "tailscale_ip": "100.64.1.2",
  "server_info": {
    "host": "100.64.1.2",
    "port": 8000,
    "tailscale_available": true,
    "cors_origins": ["http://localhost:3000", "http://100.64.1.2:3000"]
  }
}
```

### Chat Completions

#### POST /chat/completions
Create a chat completion using the specified AI model.

**Request Body:**
```json
{
  "model": "Melanie-3",
  "messages": [
    {
      "role": "user",
      "content": "Write a Python function to calculate fibonacci numbers"
    }
  ],
  "max_tokens": 1000,
  "temperature": 0.7,
  "web_search": false
}
```

**Response:**
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "Melanie-3",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Here's a Python function to calculate Fibonacci numbers:\n\n```python\ndef fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)\n```"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 15,
    "completion_tokens": 45,
    "total_tokens": 60
  }
}
```

### Model Capabilities

| Model | Description | Use Cases | Tools Available |
|-------|-------------|-----------|-----------------|
| **Melanie-3** | Grok-4 based, general purpose | Complex reasoning, research, analysis | coder, multimodal, search*, agent |
| **Melanie-3-light** | Grok-3-mini, lightweight | Quick tasks, coordination | coder, multimodal, search*, agent |
| **Melanie-3-code** | Grok-Code-Fast, coding focused | Code generation, debugging | multimodal, search* |

*Available when `web_search=true`

### Deep Research Mode

When `web_search=true` and the query contains research keywords, the system automatically generates a research plan:

**Request:**
```json
{
  "model": "Melanie-3",
  "messages": [
    {
      "role": "user",
      "content": "Research the latest developments in quantum computing and their implications for cryptography"
    }
  ],
  "web_search": true
}
```

**Response includes research_plan:**
```json
{
  "id": "chatcmpl-456",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "Melanie-3",
  "choices": [...],
  "usage": {...},
  "research_plan": {
    "id": "research-789",
    "title": "Quantum Computing and Cryptography Research",
    "description": "Comprehensive analysis of recent quantum computing advances",
    "subtasks": [
      {
        "id": "subtask-1",
        "title": "Current Quantum Computing State",
        "description": "Research latest quantum computing hardware and software developments",
        "estimated_duration": 300,
        "tools_required": ["light-search", "medium-search"]
      }
    ],
    "estimated_agents": 3,
    "estimated_duration": 900
  }
}
```

### File Operations

#### POST /files
Upload a file for processing.

**Request:**
```bash
curl -X POST \
  -H "Authorization: Bearer mel_your_api_key" \
  -F "file=@document.txt" \
  http://your-tailscale-ip:8000/files
```

**Response:**
```json
{
  "id": "file-abc123",
  "filename": "document.txt",
  "content_type": "text/plain",
  "size": 1024,
  "uploaded_at": "2023-12-01T10:00:00Z",
  "processed": true,
  "rag_ingested": true,
  "message": "File uploaded successfully",
  "processing_status": "Auto-processed through RAG system"
}
```

#### GET /files/{file_id}
Get file information or download content.

**Get Info:**
```bash
curl -H "Authorization: Bearer mel_your_api_key" \
     http://your-tailscale-ip:8000/files/file-abc123
```

**Download:**
```bash
curl -H "Authorization: Bearer mel_your_api_key" \
     "http://your-tailscale-ip:8000/files/file-abc123?download=true" \
     -o downloaded_file.txt
```

### MCP Integration

#### POST /mcp/documentation
Query current documentation for technologies.

**Request:**
```json
{
  "technology": "fastapi",
  "topic": "authentication",
  "version": "0.104.1"
}
```

**Response:**
```json
{
  "query_id": "mcp-doc-123",
  "tool_type": "documentation",
  "success": true,
  "data": {
    "documentation": "FastAPI authentication guide...",
    "examples": [...],
    "references": [...]
  },
  "source": "fastapi.tiangolo.com",
  "timestamp": "2023-12-01T10:00:00Z",
  "cached": false
}
```

## Integration Examples

### Python SDK Example

```python
import requests
import json

class MelanieAI:
    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def chat_completion(self, model, messages, **kwargs):
        """Create a chat completion."""
        data = {
            "model": model,
            "messages": messages,
            **kwargs
        }
        
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self.headers,
            json=data
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"API Error: {response.status_code} - {response.text}")
    
    def upload_file(self, file_path):
        """Upload a file for processing."""
        with open(file_path, 'rb') as f:
            files = {'file': f}
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            response = requests.post(
                f"{self.base_url}/files",
                headers=headers,
                files=files
            )
            
            return response.json()

# Usage
client = MelanieAI("mel_your_api_key", "http://your-tailscale-ip:8000")

# Basic chat
response = client.chat_completion(
    model="Melanie-3",
    messages=[{"role": "user", "content": "Hello!"}]
)

# Coding task
response = client.chat_completion(
    model="Melanie-3-code",
    messages=[{"role": "user", "content": "Write a sorting algorithm"}],
    temperature=0.3
)

# Research query
response = client.chat_completion(
    model="Melanie-3",
    messages=[{"role": "user", "content": "Research AI safety developments"}],
    web_search=True
)

# File upload
file_info = client.upload_file("document.pdf")
```

### JavaScript/Node.js Example

```javascript
class MelanieAI {
    constructor(apiKey, baseUrl) {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
        this.headers = {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json'
        };
    }

    async chatCompletion(model, messages, options = {}) {
        const response = await fetch(`${this.baseUrl}/chat/completions`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                model,
                messages,
                ...options
            })
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.status} - ${await response.text()}`);
        }

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
const client = new MelanieAI('mel_your_api_key', 'http://your-tailscale-ip:8000');

// Basic chat
const response = await client.chatCompletion('Melanie-3', [
    { role: 'user', content: 'Hello!' }
]);

// With web search
const researchResponse = await client.chatCompletion('Melanie-3', [
    { role: 'user', content: 'Research quantum computing trends' }
], { web_search: true });
```

### cURL Examples

#### Basic Chat Completion
```bash
curl -X POST http://your-tailscale-ip:8000/chat/completions \
  -H "Authorization: Bearer mel_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Melanie-3",
    "messages": [
      {"role": "user", "content": "Explain quantum computing"}
    ],
    "max_tokens": 500,
    "temperature": 0.7
  }'
```

#### Coding Task
```bash
curl -X POST http://your-tailscale-ip:8000/chat/completions \
  -H "Authorization: Bearer mel_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Melanie-3-code",
    "messages": [
      {"role": "user", "content": "Write a Python class for a binary tree"}
    ],
    "temperature": 0.3
  }'
```

#### Research Query with Web Search
```bash
curl -X POST http://your-tailscale-ip:8000/chat/completions \
  -H "Authorization: Bearer mel_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Melanie-3",
    "messages": [
      {"role": "user", "content": "Research the latest AI safety developments and regulatory changes"}
    ],
    "web_search": true
  }'
```

#### File Upload
```bash
curl -X POST http://your-tailscale-ip:8000/files \
  -H "Authorization: Bearer mel_your_api_key" \
  -F "file=@research_paper.pdf"
```

#### MCP Documentation Query
```bash
curl -X POST http://your-tailscale-ip:8000/mcp/documentation \
  -H "Authorization: Bearer mel_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "technology": "rust",
    "topic": "async programming",
    "version": "1.75"
  }'
```

## SDKs and Libraries

### Official SDKs

Currently, the API is compatible with OpenAI SDKs by changing the base URL:

#### OpenAI Python SDK
```python
from openai import OpenAI

client = OpenAI(
    api_key="mel_your_api_key",
    base_url="http://your-tailscale-ip:8000"
)

response = client.chat.completions.create(
    model="Melanie-3",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

#### OpenAI Node.js SDK
```javascript
import OpenAI from 'openai';

const openai = new OpenAI({
    apiKey: 'mel_your_api_key',
    baseURL: 'http://your-tailscale-ip:8000'
});

const response = await openai.chat.completions.create({
    model: 'Melanie-3',
    messages: [{ role: 'user', content: 'Hello!' }]
});
```

### Community Libraries

- **melanie-python**: Full-featured Python client (coming soon)
- **melanie-js**: JavaScript/TypeScript client (coming soon)
- **melanie-go**: Go client library (coming soon)

## Best Practices

### Performance Optimization

1. **Use Appropriate Models**
   - Use `Melanie-3-light` for simple tasks
   - Use `Melanie-3-code` for coding-specific tasks
   - Use `Melanie-3` for complex reasoning

2. **Optimize Token Usage**
   - Set appropriate `max_tokens` limits
   - Use lower `temperature` for deterministic outputs
   - Implement token counting for cost management

3. **Leverage Caching**
   - RAG system automatically caches embeddings
   - MCP queries are cached for performance
   - Implement client-side caching for repeated queries

### Security Best Practices

1. **API Key Management**
   - Store API keys securely (environment variables)
   - Rotate keys regularly
   - Use different keys for different environments

2. **Network Security**
   - Always use Tailscale network
   - Implement proper CORS policies
   - Monitor API usage for anomalies

3. **Input Validation**
   - Validate inputs before sending to API
   - Sanitize user-generated content
   - Implement rate limiting on client side

### Error Handling

1. **Implement Retry Logic**
   ```python
   import time
   import random
   
   def retry_with_backoff(func, max_retries=3):
       for attempt in range(max_retries):
           try:
               return func()
           except Exception as e:
               if attempt == max_retries - 1:
                   raise e
               wait_time = (2 ** attempt) + random.uniform(0, 1)
               time.sleep(wait_time)
   ```

2. **Handle Rate Limits**
   ```python
   def handle_rate_limit(response):
       if response.status_code == 429:
           retry_after = int(response.headers.get('Retry-After', 60))
           time.sleep(retry_after)
           return True
       return False
   ```

### Monitoring and Logging

1. **Log API Calls**
   ```python
   import logging
   
   logging.basicConfig(level=logging.INFO)
   logger = logging.getLogger(__name__)
   
   def log_api_call(model, tokens_used, response_time):
       logger.info(f"API Call: model={model}, tokens={tokens_used}, time={response_time}ms")
   ```

2. **Monitor Usage**
   - Track token usage per model
   - Monitor response times
   - Set up alerts for errors

## Troubleshooting

### Common Issues

#### 1. "Tailscale network not detected"
**Problem**: Server refuses to start without Tailscale.

**Solution**:
```bash
# Check Tailscale status
tailscale status

# Start Tailscale if not running
sudo tailscale up

# Verify network interfaces
ip addr show tailscale0
```

#### 2. "Unauthorized" (401 Error)
**Problem**: Invalid or missing API key.

**Solutions**:
- Verify API key format (must start with `mel_`)
- Check Authorization header format
- Ensure key is active and not expired

```bash
# Test API key
curl -H "Authorization: Bearer mel_your_api_key" \
     http://your-tailscale-ip:8000/auth/keys/mel_your_key_id
```

#### 3. "Rate limit exceeded" (429 Error)
**Problem**: Too many requests per minute.

**Solutions**:
- Implement exponential backoff
- Reduce request frequency
- Use multiple API keys for higher throughput

#### 4. "Service unavailable" (503 Error)
**Problem**: AI models or services not available.

**Solutions**:
- Check server health: `GET /health/detailed`
- Verify model availability
- Try different model if one is down

#### 5. CORS Errors
**Problem**: Cross-origin requests blocked.

**Solutions**:
- Ensure client origin is in CORS allowlist
- Use Tailscale IP instead of localhost
- Check `/tailscale/status` for correct IP

### Debug Commands

```bash
# Check server health
curl http://your-tailscale-ip:8000/health/detailed

# Check Tailscale status
curl http://your-tailscale-ip:8000/tailscale/status

# Test authentication
curl -H "Authorization: Bearer mel_your_api_key" \
     http://your-tailscale-ip:8000/auth/keys/mel_your_key_id

# Check performance metrics
curl http://your-tailscale-ip:8000/health/performance

# View API documentation
open http://your-tailscale-ip:8000/docs
```

### Getting Help

1. **API Documentation**: Visit `/docs` for interactive documentation
2. **Health Endpoints**: Use `/health/*` endpoints for diagnostics
3. **Logs**: Check server logs for detailed error information
4. **GitHub Issues**: Report bugs and request features
5. **Community**: Join our Discord/Slack for community support

### Performance Tuning

#### Request Optimization
```python
# Optimize for speed
response = client.chat_completion(
    model="Melanie-3-light",  # Faster model
    messages=messages,
    max_tokens=100,           # Limit response length
    temperature=0.3           # More deterministic
)

# Optimize for quality
response = client.chat_completion(
    model="Melanie-3",        # More capable model
    messages=messages,
    temperature=0.7,          # More creative
    web_search=True           # Enable research
)
```

#### Batch Processing
```python
# Process multiple requests efficiently
import asyncio
import aiohttp

async def batch_completions(requests):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for req in requests:
            task = make_completion_request(session, req)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        return results
```

This documentation provides comprehensive coverage of the Melanie AI API, including authentication, endpoints, examples, and troubleshooting guidance. For the most up-to-date information, always refer to the interactive documentation at `/docs`.