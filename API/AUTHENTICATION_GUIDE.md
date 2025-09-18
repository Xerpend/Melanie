# Authentication Guide

## Overview

The Melanie AI API uses API key authentication with mel_ prefixed tokens and bcrypt hashing for secure key storage. This guide covers key generation, management, and best practices.

## API Key Format

All API keys follow the format:
```
mel_[32-character-base64-string]
```

Example: `mel_abcdef1234567890abcdef1234567890abcdef12`

## Key Management

### Creating API Keys

#### Using cURL
```bash
curl -X POST http://your-tailscale-ip:8000/auth/keys
```

#### Using Python
```python
import requests

response = requests.post("http://your-tailscale-ip:8000/auth/keys")
key_data = response.json()

print(f"API Key: {key_data['api_key']}")
print(f"Key ID: {key_data['key_id']}")
print(f"Rate Limit: {key_data['rate_limit']} req/min")
```

#### Response Format
```json
{
  "api_key": "mel_abcdef1234567890abcdef1234567890abcdef12",
  "key_id": "mel_abcdef12",
  "message": "API key created successfully. Store this key securely - it cannot be retrieved again.",
  "rate_limit": 100
}
```

**Important**: Store the API key securely immediately. It cannot be retrieved again.

### Using API Keys

#### HTTP Header Format
```
Authorization: Bearer mel_your_api_key_here
```

#### Example Request
```bash
curl -H "Authorization: Bearer mel_abcdef1234567890abcdef1234567890abcdef12" \
     http://your-tailscale-ip:8000/chat/completions \
     -d '{"model": "Melanie-3", "messages": [{"role": "user", "content": "Hello"}]}'
```

### Key Information

#### Get Key Details
```bash
curl -H "Authorization: Bearer mel_your_api_key" \
     http://your-tailscale-ip:8000/auth/keys/mel_abcdef12
```

#### Response
```json
{
  "key_id": "mel_abcdef12",
  "created_at": "2023-12-01T10:00:00Z",
  "last_used": "2023-12-01T10:30:00Z",
  "is_active": true,
  "rate_limit": 100
}
```

### Key Deactivation

#### Deactivate Key
```bash
curl -X DELETE \
     -H "Authorization: Bearer mel_your_api_key" \
     http://your-tailscale-ip:8000/auth/keys/mel_abcdef12
```

#### Response
```json
{
  "message": "API key mel_abcdef12 has been deactivated.",
  "key_id": "mel_abcdef12",
  "deactivated_at": "2023-12-01T11:00:00Z"
}
```

## Security Implementation

### Key Storage

API keys are stored using bcrypt hashing:

```python
import bcrypt

# Key generation
raw_key = f"mel_{secrets.token_urlsafe(32)}"
key_hash = bcrypt.hashpw(raw_key.encode('utf-8'), bcrypt.gensalt())

# Key validation
def validate_key(provided_key: str, stored_hash: str) -> bool:
    return bcrypt.checkpw(provided_key.encode('utf-8'), stored_hash.encode('utf-8'))
```

### Authentication Middleware

The API uses FastAPI's security system:

```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import HTTPException, Depends

security = HTTPBearer()

async def api_key_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validate API key and return key information."""
    token = credentials.credentials
    
    # Validate key format
    if not token.startswith('mel_'):
        raise HTTPException(status_code=401, detail="Invalid API key format")
    
    # Check key in database
    api_key = api_key_manager.validate_key(token)
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Check if key is active
    if not api_key.is_active:
        raise HTTPException(status_code=401, detail="API key is deactivated")
    
    # Update last used timestamp
    api_key_manager.update_last_used(api_key.key_id)
    
    return api_key
```

## Best Practices

### Key Management

1. **Secure Storage**
   ```python
   import os
   from dotenv import load_dotenv
   
   load_dotenv()
   API_KEY = os.getenv('MELANIE_API_KEY')
   
   if not API_KEY:
       raise ValueError("MELANIE_API_KEY environment variable not set")
   ```

2. **Environment Variables**
   ```bash
   # .env file
   MELANIE_API_KEY=mel_your_api_key_here
   MELANIE_BASE_URL=http://your-tailscale-ip:8000
   ```

3. **Key Rotation**
   ```python
   class APIKeyRotator:
       def __init__(self):
           self.primary_key = os.getenv('MELANIE_API_KEY_PRIMARY')
           self.backup_key = os.getenv('MELANIE_API_KEY_BACKUP')
       
       def get_active_key(self):
           # Try primary key first
           if self.test_key(self.primary_key):
               return self.primary_key
           
           # Fallback to backup key
           if self.test_key(self.backup_key):
               return self.backup_key
           
           raise Exception("No valid API keys available")
       
       def test_key(self, key):
           try:
               response = requests.get(
                   f"{BASE_URL}/auth/keys/{key[:12]}",
                   headers={"Authorization": f"Bearer {key}"}
               )
               return response.status_code == 200
           except:
               return False
   ```

### Client Implementation

#### Python Client with Authentication
```python
class AuthenticatedMelanieClient:
    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })
    
    def _make_request(self, method, endpoint, **kwargs):
        """Make authenticated request with error handling."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid API key")
            elif response.status_code == 403:
                raise AuthorizationError("Access denied")
            elif response.status_code == 429:
                raise RateLimitError("Rate limit exceeded")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise APIError(f"Request failed: {e}")
    
    def chat_completion(self, **kwargs):
        return self._make_request("POST", "/chat/completions", json=kwargs)
    
    def upload_file(self, file_path):
        with open(file_path, 'rb') as f:
            files = {'file': f}
            # Remove Content-Type header for multipart
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.post(
                f"{self.base_url}/files",
                headers=headers,
                files=files
            )
            return response.json()
```

#### JavaScript Client with Authentication
```javascript
class AuthenticatedMelanieClient {
    constructor(apiKey, baseUrl) {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
        this.headers = {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json'
        };
    }

    async makeRequest(method, endpoint, data = null) {
        const url = `${this.baseUrl}${endpoint}`;
        const options = {
            method,
            headers: this.headers
        };

        if (data) {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, options);
            
            if (response.status === 401) {
                throw new Error('Invalid API key');
            } else if (response.status === 403) {
                throw new Error('Access denied');
            } else if (response.status === 429) {
                throw new Error('Rate limit exceeded');
            }

            if (!response.ok) {
                const error = await response.json();
                throw new Error(`API Error: ${error.message}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    async chatCompletion(data) {
        return await this.makeRequest('POST', '/chat/completions', data);
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
```

## Error Handling

### Authentication Errors

#### 401 Unauthorized
```json
{
  "error": "unauthorized",
  "message": "Invalid API key",
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**Causes:**
- Missing Authorization header
- Invalid API key format
- Key not found in database
- Key has been deactivated

#### 403 Forbidden
```json
{
  "error": "forbidden",
  "message": "You can only view information about your own API key",
  "timestamp": "2023-12-01T10:00:00Z"
}
```

**Causes:**
- Attempting to access another user's key information
- Insufficient permissions for requested operation

### Error Handling Implementation

```python
class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass

class AuthorizationError(Exception):
    """Raised when authorization fails."""
    pass

def handle_auth_error(response):
    """Handle authentication and authorization errors."""
    if response.status_code == 401:
        error_data = response.json()
        if "Invalid API key format" in error_data.get("message", ""):
            raise AuthenticationError("API key must start with 'mel_'")
        elif "Invalid API key" in error_data.get("message", ""):
            raise AuthenticationError("API key not found or invalid")
        elif "deactivated" in error_data.get("message", ""):
            raise AuthenticationError("API key has been deactivated")
        else:
            raise AuthenticationError("Authentication failed")
    
    elif response.status_code == 403:
        raise AuthorizationError("Access denied for requested resource")
```

## Testing Authentication

### Test Key Validity
```python
def test_api_key(api_key, base_url):
    """Test if an API key is valid."""
    try:
        response = requests.get(
            f"{base_url}/health",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        return response.status_code == 200
    except:
        return False

# Usage
if test_api_key("mel_your_key", "http://your-tailscale-ip:8000"):
    print("API key is valid")
else:
    print("API key is invalid")
```

### Test Key Permissions
```python
def test_key_permissions(api_key, key_id, base_url):
    """Test key permissions by accessing key info."""
    try:
        response = requests.get(
            f"{base_url}/auth/keys/{key_id}",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        
        if response.status_code == 200:
            return "full_access"
        elif response.status_code == 403:
            return "limited_access"
        else:
            return "no_access"
    except:
        return "error"
```

## Troubleshooting

### Common Issues

1. **"Invalid API key format"**
   - Ensure key starts with `mel_`
   - Check for extra spaces or characters
   - Verify key length (should be ~44 characters)

2. **"API key not found"**
   - Key may have been deactivated
   - Check key spelling
   - Verify you're using the correct server

3. **"Access denied"**
   - Trying to access another user's resources
   - Key may have limited permissions

### Debug Commands

```bash
# Test basic authentication
curl -H "Authorization: Bearer mel_your_key" \
     http://your-tailscale-ip:8000/health

# Check key information
curl -H "Authorization: Bearer mel_your_key" \
     http://your-tailscale-ip:8000/auth/keys/mel_your_key_id

# Test with invalid key (should return 401)
curl -H "Authorization: Bearer invalid_key" \
     http://your-tailscale-ip:8000/health
```

## Security Considerations

### Network Security
- API requires Tailscale network for additional security layer
- CORS restricted to localhost and Tailscale origins
- No public internet access to API endpoints

### Key Security
- Keys are hashed using bcrypt with salt
- Raw keys are never stored in database
- Keys cannot be retrieved after creation

### Best Practices
1. **Never commit keys to version control**
2. **Use environment variables for key storage**
3. **Rotate keys regularly**
4. **Monitor key usage for anomalies**
5. **Deactivate unused keys immediately**
6. **Use different keys for different environments**

This authentication guide provides comprehensive coverage of API key management, security implementation, and best practices for the Melanie AI API.