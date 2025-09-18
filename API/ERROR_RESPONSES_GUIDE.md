# Error Responses and Status Codes Guide

## Overview

The Melanie AI API uses standard HTTP status codes and provides detailed error responses to help developers understand and handle errors effectively. This guide covers all error types, status codes, and best practices for error handling.

## Error Response Format

### Standard Error Structure

All API errors follow a consistent JSON format:

```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {
    "additional": "context",
    "field": "specific_field_info"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

### Validation Error Structure

For validation errors, additional detail is provided:

```json
{
  "error": "validation_error",
  "message": "Request validation failed",
  "details": {
    "validation_errors": [
      {
        "field": "messages",
        "message": "At least one message is required",
        "invalid_value": []
      },
      {
        "field": "model",
        "message": "Invalid model type",
        "invalid_value": "invalid-model"
      }
    ]
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

## HTTP Status Codes

### 2xx Success Codes

#### 200 OK
Successful request with response body.

**Example:**
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "Melanie-3",
  "choices": [...],
  "usage": {...}
}
```

#### 201 Created
Resource successfully created (e.g., file upload, API key creation).

**Example:**
```json
{
  "api_key": "mel_abcdef1234567890abcdef1234567890abcdef12",
  "key_id": "mel_abcdef12",
  "message": "API key created successfully",
  "rate_limit": 100
}
```

### 4xx Client Error Codes

#### 400 Bad Request
Invalid request format, missing required fields, or validation errors.

**Common Causes:**
- Invalid JSON format
- Missing required fields
- Invalid parameter values
- Malformed request body

**Examples:**

**Invalid JSON:**
```json
{
  "error": "invalid_json",
  "message": "Request body contains invalid JSON",
  "details": {
    "json_error": "Expecting ',' delimiter: line 3 column 5 (char 45)"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**Missing Required Field:**
```json
{
  "error": "validation_error",
  "message": "Request validation failed",
  "details": {
    "validation_errors": [
      {
        "field": "model",
        "message": "Field required",
        "invalid_value": null
      }
    ]
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**Invalid Model:**
```json
{
  "error": "validation_error",
  "message": "Request validation failed",
  "details": {
    "validation_errors": [
      {
        "field": "model",
        "message": "Invalid model type. Must be one of: Melanie-3, Melanie-3-light, Melanie-3-code",
        "invalid_value": "gpt-4"
      }
    ]
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**Invalid Message Content:**
```json
{
  "error": "validation_error",
  "message": "Request validation failed",
  "details": {
    "validation_errors": [
      {
        "field": "messages[0].content",
        "message": "Message content cannot be empty",
        "invalid_value": ""
      }
    ]
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

#### 401 Unauthorized
Authentication failed or missing credentials.

**Common Causes:**
- Missing Authorization header
- Invalid API key format
- API key not found
- Deactivated API key

**Examples:**

**Missing Authorization Header:**
```json
{
  "error": "unauthorized",
  "message": "Authorization header required",
  "details": {
    "required_format": "Authorization: Bearer mel_your_api_key"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**Invalid API Key Format:**
```json
{
  "error": "unauthorized",
  "message": "Invalid API key format",
  "details": {
    "expected_format": "mel_[32-character-string]",
    "provided_format": "invalid_key"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**API Key Not Found:**
```json
{
  "error": "unauthorized",
  "message": "Invalid API key",
  "details": {
    "key_id": "mel_invalid12"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**Deactivated API Key:**
```json
{
  "error": "unauthorized",
  "message": "API key is deactivated",
  "details": {
    "key_id": "mel_abcdef12",
    "deactivated_at": "2023-11-30T15:30:00Z"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

#### 403 Forbidden
Valid authentication but insufficient permissions.

**Common Causes:**
- Accessing another user's resources
- Insufficient permissions for operation
- Resource access denied

**Examples:**

**Accessing Another User's Key:**
```json
{
  "error": "forbidden",
  "message": "You can only view information about your own API key",
  "details": {
    "requested_key": "mel_other123",
    "your_key": "mel_abcdef12"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**Operation Not Allowed:**
```json
{
  "error": "forbidden",
  "message": "Operation not allowed for this resource",
  "details": {
    "operation": "DELETE",
    "resource": "/system/config"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

#### 404 Not Found
Requested resource does not exist.

**Common Causes:**
- Invalid endpoint URL
- Resource ID not found
- File not found

**Examples:**

**Invalid Endpoint:**
```json
{
  "error": "not_found",
  "message": "Endpoint not found",
  "details": {
    "path": "/invalid/endpoint",
    "method": "GET"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**API Key Not Found:**
```json
{
  "error": "not_found",
  "message": "API key not found",
  "details": {
    "key_id": "mel_notfound"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**File Not Found:**
```json
{
  "error": "not_found",
  "message": "File not found",
  "details": {
    "file_id": "file-nonexistent"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

#### 413 Payload Too Large
Request payload exceeds size limits.

**Common Causes:**
- File upload too large
- Request body too large
- Too many messages in chat completion

**Examples:**

**File Too Large:**
```json
{
  "error": "payload_too_large",
  "message": "File size exceeds maximum limit",
  "details": {
    "file_size": 52428800,
    "max_size": 50000000,
    "size_limit": "50MB"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**Request Body Too Large:**
```json
{
  "error": "payload_too_large",
  "message": "Request body too large",
  "details": {
    "body_size": 1048576,
    "max_size": 1000000,
    "size_limit": "1MB"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

#### 415 Unsupported Media Type
Invalid content type for the request.

**Common Causes:**
- Wrong Content-Type header
- Unsupported file format
- Invalid multipart format

**Examples:**

**Invalid Content Type:**
```json
{
  "error": "unsupported_media_type",
  "message": "Unsupported content type",
  "details": {
    "provided_type": "text/plain",
    "expected_types": ["application/json", "multipart/form-data"]
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**Unsupported File Type:**
```json
{
  "error": "unsupported_media_type",
  "message": "Unsupported file type",
  "details": {
    "file_type": "application/exe",
    "supported_types": ["text/plain", "text/markdown", "application/pdf", "image/jpeg", "image/png"]
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

#### 422 Unprocessable Entity
Valid request format but semantic errors.

**Common Causes:**
- Business logic validation failures
- Conflicting parameters
- Invalid state transitions

**Examples:**

**Conflicting Parameters:**
```json
{
  "error": "unprocessable_entity",
  "message": "Conflicting parameters provided",
  "details": {
    "conflict": "Cannot use both 'tools' and 'web_search=false' with Melanie-3-code model",
    "suggestion": "Either enable web_search or remove tools parameter"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**Invalid State:**
```json
{
  "error": "unprocessable_entity",
  "message": "Cannot perform operation in current state",
  "details": {
    "current_state": "processing",
    "required_state": "idle",
    "operation": "delete_file"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

#### 429 Too Many Requests
Rate limit exceeded.

**Common Causes:**
- Exceeding requests per minute limit
- Burst limit exceeded
- Concurrent request limit exceeded

**Examples:**

**Rate Limit Exceeded:**
```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit of 100 requests per minute exceeded",
  "details": {
    "limit": 100,
    "remaining": 0,
    "reset_at": "2023-12-01T10:05:00Z",
    "retry_after": 45
  },
  "timestamp": "2023-12-01T10:04:15Z"
}
```

**Concurrent Limit Exceeded:**
```json
{
  "error": "concurrent_limit_exceeded",
  "message": "Too many concurrent requests",
  "details": {
    "concurrent_limit": 5,
    "current_concurrent": 6,
    "retry_after": 10
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

### 5xx Server Error Codes

#### 500 Internal Server Error
Unexpected server error.

**Common Causes:**
- Unhandled exceptions
- Database errors
- Configuration issues

**Examples:**

**General Server Error:**
```json
{
  "error": "internal_server_error",
  "message": "An unexpected error occurred",
  "details": {
    "error_id": "err_abc123",
    "support_message": "Please contact support with this error ID"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**Database Error:**
```json
{
  "error": "database_error",
  "message": "Database operation failed",
  "details": {
    "operation": "insert",
    "table": "api_keys",
    "error_id": "db_err_456"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

#### 502 Bad Gateway
Error from upstream service.

**Common Causes:**
- AI model service unavailable
- External API errors
- Network connectivity issues

**Examples:**

**AI Model Error:**
```json
{
  "error": "bad_gateway",
  "message": "AI model service unavailable",
  "details": {
    "model": "Melanie-3",
    "upstream_error": "Connection timeout",
    "retry_suggested": true
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**External API Error:**
```json
{
  "error": "bad_gateway",
  "message": "External service error",
  "details": {
    "service": "perplexity_search",
    "upstream_status": 503,
    "upstream_message": "Service temporarily unavailable"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

#### 503 Service Unavailable
Service temporarily unavailable.

**Common Causes:**
- Server maintenance
- System overload
- Dependency failures

**Examples:**

**Maintenance Mode:**
```json
{
  "error": "service_unavailable",
  "message": "Service temporarily unavailable for maintenance",
  "details": {
    "maintenance_window": "2023-12-01T10:00:00Z to 2023-12-01T11:00:00Z",
    "estimated_completion": "2023-12-01T11:00:00Z"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**System Overload:**
```json
{
  "error": "service_unavailable",
  "message": "System temporarily overloaded",
  "details": {
    "retry_after": 30,
    "load_level": "high",
    "suggestion": "Please retry in 30 seconds"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**AI Models Unavailable:**
```json
{
  "error": "service_unavailable",
  "message": "AI models not available",
  "details": {
    "affected_models": ["Melanie-3", "Melanie-3-light"],
    "available_models": ["Melanie-3-code"],
    "estimated_recovery": "2023-12-01T10:15:00Z"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

#### 504 Gateway Timeout
Timeout from upstream service.

**Common Causes:**
- AI model response timeout
- Long-running operations
- Network timeouts

**Examples:**

**Model Timeout:**
```json
{
  "error": "gateway_timeout",
  "message": "AI model response timeout",
  "details": {
    "model": "Melanie-3",
    "timeout_duration": 60,
    "suggestion": "Try reducing request complexity or using a lighter model"
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**Research Timeout:**
```json
{
  "error": "gateway_timeout",
  "message": "Research operation timeout",
  "details": {
    "operation": "deep_research",
    "timeout_duration": 300,
    "partial_results_available": true
  },
  "timestamp": "2023-12-01T10:00:00Z"
}
```

## Error Handling Best Practices

### 1. Implement Proper Error Handling

#### Python Example

```python
import requests
from typing import Optional, Dict, Any

class MelanieAPIError(Exception):
    """Base exception for Melanie API errors."""
    def __init__(self, message: str, status_code: int, error_code: str, details: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class ValidationError(MelanieAPIError):
    """Validation error (400)."""
    pass

class AuthenticationError(MelanieAPIError):
    """Authentication error (401)."""
    pass

class AuthorizationError(MelanieAPIError):
    """Authorization error (403)."""
    pass

class NotFoundError(MelanieAPIError):
    """Not found error (404)."""
    pass

class RateLimitError(MelanieAPIError):
    """Rate limit error (429)."""
    def __init__(self, message: str, retry_after: int, **kwargs):
        super().__init__(message, 429, "rate_limit_exceeded", **kwargs)
        self.retry_after = retry_after

class ServerError(MelanieAPIError):
    """Server error (5xx)."""
    pass

def handle_api_response(response: requests.Response) -> Dict[Any, Any]:
    """Handle API response and raise appropriate exceptions."""
    
    if response.status_code == 200:
        return response.json()
    
    try:
        error_data = response.json()
        error_code = error_data.get('error', 'unknown_error')
        message = error_data.get('message', 'Unknown error occurred')
        details = error_data.get('details', {})
    except ValueError:
        # Non-JSON error response
        error_code = 'unknown_error'
        message = f"HTTP {response.status_code}: {response.text}"
        details = {}
    
    # Map status codes to exception types
    if response.status_code == 400:
        raise ValidationError(message, response.status_code, error_code, details)
    elif response.status_code == 401:
        raise AuthenticationError(message, response.status_code, error_code, details)
    elif response.status_code == 403:
        raise AuthorizationError(message, response.status_code, error_code, details)
    elif response.status_code == 404:
        raise NotFoundError(message, response.status_code, error_code, details)
    elif response.status_code == 429:
        retry_after = int(response.headers.get('Retry-After', 60))
        raise RateLimitError(message, retry_after, details=details)
    elif response.status_code >= 500:
        raise ServerError(message, response.status_code, error_code, details)
    else:
        raise MelanieAPIError(message, response.status_code, error_code, details)

# Usage example
def make_api_request(url: str, headers: Dict, data: Dict) -> Dict:
    """Make API request with proper error handling."""
    try:
        response = requests.post(url, headers=headers, json=data)
        return handle_api_response(response)
    
    except ValidationError as e:
        print(f"Validation error: {e.message}")
        if 'validation_errors' in e.details:
            for error in e.details['validation_errors']:
                print(f"  - {error['field']}: {error['message']}")
        raise
    
    except AuthenticationError as e:
        print(f"Authentication error: {e.message}")
        # Handle re-authentication
        raise
    
    except RateLimitError as e:
        print(f"Rate limited: {e.message}")
        print(f"Retry after: {e.retry_after} seconds")
        # Implement retry logic
        raise
    
    except ServerError as e:
        print(f"Server error: {e.message}")
        if 'error_id' in e.details:
            print(f"Error ID: {e.details['error_id']}")
        # Implement retry with exponential backoff
        raise
```

#### JavaScript Example

```javascript
class MelanieAPIError extends Error {
    constructor(message, statusCode, errorCode, details = {}) {
        super(message);
        this.name = 'MelanieAPIError';
        this.statusCode = statusCode;
        this.errorCode = errorCode;
        this.details = details;
    }
}

class ValidationError extends MelanieAPIError {
    constructor(message, details) {
        super(message, 400, 'validation_error', details);
        this.name = 'ValidationError';
    }
}

class AuthenticationError extends MelanieAPIError {
    constructor(message, details) {
        super(message, 401, 'unauthorized', details);
        this.name = 'AuthenticationError';
    }
}

class RateLimitError extends MelanieAPIError {
    constructor(message, retryAfter, details) {
        super(message, 429, 'rate_limit_exceeded', details);
        this.name = 'RateLimitError';
        this.retryAfter = retryAfter;
    }
}

async function handleApiResponse(response) {
    if (response.ok) {
        return await response.json();
    }

    let errorData;
    try {
        errorData = await response.json();
    } catch {
        errorData = {
            error: 'unknown_error',
            message: `HTTP ${response.status}: ${response.statusText}`,
            details: {}
        };
    }

    const { error: errorCode, message, details = {} } = errorData;

    switch (response.status) {
        case 400:
            throw new ValidationError(message, details);
        case 401:
            throw new AuthenticationError(message, details);
        case 403:
            throw new MelanieAPIError(message, 403, 'forbidden', details);
        case 404:
            throw new MelanieAPIError(message, 404, 'not_found', details);
        case 429:
            const retryAfter = parseInt(response.headers.get('Retry-After') || '60');
            throw new RateLimitError(message, retryAfter, details);
        default:
            if (response.status >= 500) {
                throw new MelanieAPIError(message, response.status, errorCode, details);
            }
            throw new MelanieAPIError(message, response.status, errorCode, details);
    }
}

// Usage example
async function makeApiRequest(url, headers, data) {
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers,
            body: JSON.stringify(data)
        });

        return await handleApiResponse(response);

    } catch (error) {
        if (error instanceof ValidationError) {
            console.error('Validation error:', error.message);
            if (error.details.validation_errors) {
                error.details.validation_errors.forEach(err => {
                    console.error(`  - ${err.field}: ${err.message}`);
                });
            }
        } else if (error instanceof AuthenticationError) {
            console.error('Authentication error:', error.message);
            // Handle re-authentication
        } else if (error instanceof RateLimitError) {
            console.error('Rate limited:', error.message);
            console.error(`Retry after: ${error.retryAfter} seconds`);
            // Implement retry logic
        } else {
            console.error('API error:', error.message);
        }
        throw error;
    }
}
```

### 2. Implement Retry Logic

```python
import asyncio
import random
from typing import Callable, Any

async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True
) -> Any:
    """Retry function with exponential backoff."""
    
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func()
        
        except RateLimitError as e:
            if attempt < max_retries:
                # Use retry_after from rate limit error
                delay = e.retry_after
                if jitter:
                    delay += random.uniform(0, delay * 0.1)
                
                print(f"Rate limited. Retrying in {delay:.2f}s (attempt {attempt + 1})")
                await asyncio.sleep(delay)
                last_exception = e
                continue
            else:
                raise e
        
        except (ServerError, MelanieAPIError) as e:
            if attempt < max_retries and e.status_code >= 500:
                # Exponential backoff for server errors
                delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                if jitter:
                    delay += random.uniform(0, delay * 0.1)
                
                print(f"Server error. Retrying in {delay:.2f}s (attempt {attempt + 1})")
                await asyncio.sleep(delay)
                last_exception = e
                continue
            else:
                raise e
        
        except Exception as e:
            # Don't retry on other exceptions
            raise e
    
    raise last_exception
```

### 3. Log Errors Properly

```python
import logging
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def log_api_error(error: MelanieAPIError, request_data: Dict = None):
    """Log API error with context."""
    
    error_info = {
        'timestamp': datetime.utcnow().isoformat(),
        'error_type': type(error).__name__,
        'status_code': error.status_code,
        'error_code': error.error_code,
        'message': error.message,
        'details': error.details
    }
    
    if request_data:
        error_info['request_data'] = {
            'model': request_data.get('model'),
            'message_count': len(request_data.get('messages', [])),
            'has_tools': bool(request_data.get('tools')),
            'web_search': request_data.get('web_search', False)
        }
    
    if error.status_code >= 500:
        logger.error(f"Server error: {json.dumps(error_info, indent=2)}")
    elif error.status_code == 429:
        logger.warning(f"Rate limit exceeded: {json.dumps(error_info, indent=2)}")
    elif error.status_code >= 400:
        logger.info(f"Client error: {json.dumps(error_info, indent=2)}")
```

## Troubleshooting Common Errors

### Validation Errors

**Problem**: Getting validation errors for seemingly correct requests.

**Solutions:**
1. Check field names and types
2. Verify required fields are present
3. Validate parameter ranges
4. Check message format

```python
# Good request
{
    "model": "Melanie-3",
    "messages": [
        {"role": "user", "content": "Hello"}
    ],
    "max_tokens": 100,
    "temperature": 0.7
}

# Bad request - missing required field
{
    "messages": [
        {"role": "user", "content": "Hello"}
    ]
    # Missing "model" field
}
```

### Authentication Errors

**Problem**: Getting 401 errors despite having an API key.

**Solutions:**
1. Check Authorization header format
2. Verify API key starts with `mel_`
3. Ensure key is active
4. Check for extra spaces or characters

```bash
# Correct format
curl -H "Authorization: Bearer mel_your_api_key" \
     http://your-tailscale-ip:8000/health

# Incorrect format
curl -H "Authorization: mel_your_api_key" \
     http://your-tailscale-ip:8000/health
```

### Rate Limit Errors

**Problem**: Consistently hitting rate limits.

**Solutions:**
1. Implement proper retry logic
2. Monitor rate limit headers
3. Use request queuing
4. Consider multiple API keys

### Server Errors

**Problem**: Getting 5xx errors intermittently.

**Solutions:**
1. Implement retry with exponential backoff
2. Check server health endpoints
3. Monitor for maintenance windows
4. Contact support with error IDs

## Error Monitoring and Alerting

### Error Tracking

```python
class ErrorTracker:
    def __init__(self):
        self.error_counts = defaultdict(int)
        self.error_history = []
    
    def track_error(self, error: MelanieAPIError):
        """Track error occurrence."""
        error_key = f"{error.status_code}_{error.error_code}"
        self.error_counts[error_key] += 1
        
        self.error_history.append({
            'timestamp': datetime.utcnow(),
            'status_code': error.status_code,
            'error_code': error.error_code,
            'message': error.message
        })
        
        # Keep only last 1000 errors
        if len(self.error_history) > 1000:
            self.error_history = self.error_history[-1000:]
    
    def get_error_summary(self):
        """Get error summary statistics."""
        total_errors = sum(self.error_counts.values())
        
        return {
            'total_errors': total_errors,
            'error_types': dict(self.error_counts),
            'most_common': max(self.error_counts.items(), key=lambda x: x[1]) if self.error_counts else None,
            'recent_errors': self.error_history[-10:]  # Last 10 errors
        }
```

This comprehensive error handling guide provides detailed information about all error types, status codes, and best practices for handling errors in the Melanie AI API.