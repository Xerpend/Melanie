# Melanie AI API Documentation Index

## Overview

This directory contains comprehensive documentation for the Melanie AI API, including specifications, guides, examples, and best practices. The documentation is organized to help developers quickly find the information they need to integrate with the API effectively.

## Documentation Structure

### 📋 Core Documentation

#### [OpenAPI Specification](./openapi_spec.yaml)
- **Format**: OpenAPI 3.0.3 YAML
- **Content**: Complete API specification with all endpoints, schemas, and examples
- **Use Cases**: 
  - Generate client SDKs
  - Import into API testing tools (Postman, Insomnia)
  - Validate API contracts
  - Generate documentation

#### [API Documentation](./API_DOCUMENTATION.md)
- **Format**: Comprehensive Markdown guide
- **Content**: Complete API reference with examples and best practices
- **Sections**:
  - Getting started guide
  - Authentication and security
  - All API endpoints with examples
  - Error handling
  - SDKs and libraries
  - Performance optimization
  - Troubleshooting

### 🔐 Security and Authentication

#### [Authentication Guide](./AUTHENTICATION_GUIDE.md)
- **Focus**: API key management and security
- **Content**:
  - API key generation and lifecycle
  - Authentication implementation
  - Security best practices
  - Client examples in multiple languages
  - Troubleshooting authentication issues

#### [Rate Limiting Guide](./RATE_LIMITING_GUIDE.md)
- **Focus**: Rate limit policies and handling
- **Content**:
  - Rate limit algorithms and policies
  - Response headers and monitoring
  - Client-side rate limiting strategies
  - Retry logic and backoff algorithms
  - Performance optimization

### 🚨 Error Handling

#### [Error Responses Guide](./ERROR_RESPONSES_GUIDE.md)
- **Focus**: Complete error handling reference
- **Content**:
  - All HTTP status codes and meanings
  - Error response formats
  - Common error scenarios
  - Error handling best practices
  - Debugging and troubleshooting

### 💻 Integration Examples

#### [Integration Examples](./INTEGRATION_EXAMPLES.md)
- **Focus**: Real-world integration examples
- **Content**:
  - Python integration (Django, FastAPI, async)
  - JavaScript/Node.js integration (Express, React, Vue)
  - Web frontend examples
  - Mobile integration patterns
  - Framework-specific implementations

## Quick Start Guide

### 1. First Steps
1. **Read the [API Documentation](./API_DOCUMENTATION.md)** for a complete overview
2. **Check the [OpenAPI Specification](./openapi_spec.yaml)** for technical details
3. **Review [Authentication Guide](./AUTHENTICATION_GUIDE.md)** for security setup

### 2. Implementation
1. **Choose your language/framework** from [Integration Examples](./INTEGRATION_EXAMPLES.md)
2. **Implement error handling** using [Error Responses Guide](./ERROR_RESPONSES_GUIDE.md)
3. **Add rate limiting** following [Rate Limiting Guide](./RATE_LIMITING_GUIDE.md)

### 3. Testing and Deployment
1. **Test with the interactive docs** at `http://your-tailscale-ip:8000/docs`
2. **Monitor rate limits** and error rates
3. **Implement proper logging** and monitoring

## API Endpoints Summary

### Core Endpoints
- `GET /` - Server information
- `GET /health` - Health check
- `GET /health/detailed` - Comprehensive health status
- `GET /health/performance` - Performance metrics
- `GET /tailscale/status` - Network status

### Authentication
- `POST /auth/keys` - Create API key
- `GET /auth/keys/{key_id}` - Get key information
- `DELETE /auth/keys/{key_id}` - Deactivate key

### Chat Completions
- `POST /chat/completions` - Create chat completion
  - **Models**: Melanie-3, Melanie-3-light, Melanie-3-code
  - **Features**: Tool calling, web search, RAG integration
  - **Advanced**: Deep research orchestration

### File Operations
- `POST /files` - Upload file
- `GET /files/{file_id}` - Get file info or download
- `DELETE /files/{file_id}` - Delete file

### MCP Integration
- `POST /mcp/documentation` - Query documentation
- `POST /mcp/security` - Query security guidelines
- `POST /mcp/performance` - Query performance recommendations
- `POST /mcp/versions` - Check version information

## Model Capabilities Matrix

| Model | Description | Use Cases | Tools Available |
|-------|-------------|-----------|-----------------|
| **Melanie-3** | Grok-4 based, general purpose | Complex reasoning, research, analysis | coder, multimodal, search*, agent |
| **Melanie-3-light** | Grok-3-mini, lightweight | Quick tasks, coordination | coder, multimodal, search*, agent |
| **Melanie-3-code** | Grok-Code-Fast, coding focused | Code generation, debugging | multimodal, search* |

*Available when `web_search=true`

## Authentication Quick Reference

### API Key Format
```
mel_[32-character-base64-string]
```

### Authentication Header
```
Authorization: Bearer mel_your_api_key_here
```

### Rate Limits
- **Default**: 100 requests per minute per API key
- **Window**: Sliding 60-second window
- **Headers**: Rate limit info in response headers

## Common Error Codes

| Code | Status | Description | Action |
|------|--------|-------------|---------|
| `validation_error` | 400 | Invalid request format | Check request structure |
| `unauthorized` | 401 | Invalid API key | Verify authentication |
| `forbidden` | 403 | Access denied | Check permissions |
| `not_found` | 404 | Resource not found | Verify resource ID |
| `rate_limit_exceeded` | 429 | Rate limit exceeded | Implement retry logic |
| `model_error` | 500 | AI model error | Retry with backoff |
| `service_unavailable` | 503 | Service unavailable | Check health endpoints |

## Integration Patterns

### Basic Chat Completion
```python
response = await client.chat_completion(
    model="Melanie-3",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Coding Assistant
```python
response = await client.chat_completion(
    model="Melanie-3-code",
    messages=[{"role": "user", "content": "Write a sorting function"}],
    temperature=0.3
)
```

### Research Query
```python
response = await client.chat_completion(
    model="Melanie-3",
    messages=[{"role": "user", "content": "Research AI developments"}],
    web_search=True
)
```

### File Processing
```python
# Upload file
file_result = await client.upload_file("document.pdf")

# Use in chat
response = await client.chat_completion(
    model="Melanie-3",
    messages=[{"role": "user", "content": "Analyze the uploaded document"}]
)
```

## Best Practices Checklist

### ✅ Security
- [ ] Store API keys securely (environment variables)
- [ ] Use HTTPS in production
- [ ] Implement proper CORS policies
- [ ] Rotate API keys regularly
- [ ] Monitor for unusual usage patterns

### ✅ Error Handling
- [ ] Implement retry logic with exponential backoff
- [ ] Handle all HTTP status codes appropriately
- [ ] Log errors with sufficient context
- [ ] Provide user-friendly error messages
- [ ] Monitor error rates and patterns

### ✅ Performance
- [ ] Implement client-side rate limiting
- [ ] Use appropriate models for tasks
- [ ] Cache responses when possible
- [ ] Monitor token usage
- [ ] Implement request queuing for high volume

### ✅ Monitoring
- [ ] Track API response times
- [ ] Monitor rate limit usage
- [ ] Log all API interactions
- [ ] Set up alerts for errors
- [ ] Monitor token consumption

## Support and Resources

### Interactive Documentation
- **Swagger UI**: `http://your-tailscale-ip:8000/docs`
- **ReDoc**: `http://your-tailscale-ip:8000/redoc`

### Health Monitoring
- **Basic Health**: `GET /health`
- **Detailed Health**: `GET /health/detailed`
- **Performance Metrics**: `GET /health/performance`

### Troubleshooting
1. **Check server health** endpoints first
2. **Verify Tailscale connectivity**
3. **Test API key validity**
4. **Review error logs**
5. **Check rate limit headers**

### Getting Help
1. **Review documentation** in this directory
2. **Check interactive docs** for endpoint details
3. **Test with health endpoints** for connectivity
4. **Review error responses** for specific guidance
5. **Contact support** with error IDs when available

## Version Information

- **API Version**: 1.0.0
- **OpenAPI Version**: 3.0.3
- **Documentation Version**: 1.0.0
- **Last Updated**: December 2023

## Contributing to Documentation

To improve this documentation:

1. **Update OpenAPI spec** for API changes
2. **Add examples** for new use cases
3. **Update guides** for new features
4. **Test all examples** before committing
5. **Keep version information** current

## File Organization

```
API/
├── openapi_spec.yaml              # OpenAPI 3.0.3 specification
├── API_DOCUMENTATION.md           # Complete API reference
├── AUTHENTICATION_GUIDE.md        # Authentication and security
├── RATE_LIMITING_GUIDE.md         # Rate limiting policies and handling
├── ERROR_RESPONSES_GUIDE.md       # Error handling reference
├── INTEGRATION_EXAMPLES.md        # Integration examples and patterns
├── API_DOCUMENTATION_INDEX.md     # This index file
└── README.md                      # Basic API information
```

This documentation provides everything needed to successfully integrate with the Melanie AI API, from basic setup to advanced use cases and troubleshooting.