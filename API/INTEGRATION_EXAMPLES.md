# Integration Examples

## Overview

This guide provides comprehensive integration examples for the Melanie AI API across different programming languages, frameworks, and use cases. Each example includes error handling, best practices, and real-world scenarios.

## Table of Contents

1. [Python Integration](#python-integration)
2. [JavaScript/Node.js Integration](#javascriptnodejs-integration)
3. [Web Frontend Integration](#web-frontend-integration)
4. [CLI Integration](#cli-integration)
5. [Mobile Integration](#mobile-integration)
6. [Framework-Specific Examples](#framework-specific-examples)
7. [Advanced Use Cases](#advanced-use-cases)

## Python Integration

### Basic Python Client

```python
import asyncio
import aiohttp
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class MelanieConfig:
    """Configuration for Melanie AI client."""
    api_key: str
    base_url: str
    timeout: int = 60
    max_retries: int = 3

class MelanieAIClient:
    """Async Python client for Melanie AI API."""
    
    def __init__(self, config: MelanieConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "MelanieAI-Python/1.0.0"
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            headers=self.headers
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        url = f"{self.config.base_url}{endpoint}"
        
        for attempt in range(self.config.max_retries + 1):
            try:
                async with self.session.request(method, url, json=data, **kwargs) as response:
                    response_data = await response.json()
                    
                    if response.status == 200:
                        return response_data
                    elif response.status == 429:
                        # Rate limit handling
                        retry_after = int(response.headers.get('Retry-After', 60))
                        if attempt < self.config.max_retries:
                            print(f"Rate limited. Retrying in {retry_after}s...")
                            await asyncio.sleep(retry_after)
                            continue
                    elif response.status >= 500:
                        # Server error handling
                        if attempt < self.config.max_retries:
                            wait_time = (2 ** attempt) + (time.time() % 1)
                            print(f"Server error. Retrying in {wait_time:.2f}s...")
                            await asyncio.sleep(wait_time)
                            continue
                    
                    # Handle other errors
                    error_msg = response_data.get('message', f'HTTP {response.status}')
                    raise Exception(f"API Error: {error_msg}")
                    
            except aiohttp.ClientError as e:
                if attempt < self.config.max_retries:
                    wait_time = (2 ** attempt) + (time.time() % 1)
                    await asyncio.sleep(wait_time)
                    continue
                raise Exception(f"Network error: {e}")
        
        raise Exception("Max retries exceeded")
    
    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """Create a chat completion."""
        data = {
            "model": model,
            "messages": messages,
            **kwargs
        }
        
        return await self._make_request("POST", "/chat/completions", data)
    
    async def upload_file(self, file_path: str) -> Dict[str, Any]:
        """Upload a file for processing."""
        data = aiohttp.FormData()
        data.add_field('file', open(file_path, 'rb'))
        
        # Remove Content-Type header for multipart
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        
        async with self.session.post(
            f"{self.config.base_url}/files",
            data=data,
            headers=headers
        ) as response:
            return await response.json()
    
    async def get_file_info(self, file_id: str) -> Dict[str, Any]:
        """Get file information."""
        return await self._make_request("GET", f"/files/{file_id}")
    
    async def delete_file(self, file_id: str) -> Dict[str, Any]:
        """Delete a file."""
        return await self._make_request("DELETE", f"/files/{file_id}")
    
    async def query_documentation(
        self, 
        technology: str, 
        topic: str, 
        version: Optional[str] = None
    ) -> Dict[str, Any]:
        """Query MCP documentation."""
        data = {
            "technology": technology,
            "topic": topic
        }
        if version:
            data["version"] = version
        
        return await self._make_request("POST", "/mcp/documentation", data)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check API health."""
        return await self._make_request("GET", "/health")

# Usage Examples
async def basic_chat_example():
    """Basic chat completion example."""
    config = MelanieConfig(
        api_key="mel_your_api_key_here",
        base_url="http://your-tailscale-ip:8000"
    )
    
    async with MelanieAIClient(config) as client:
        response = await client.chat_completion(
            model="Melanie-3",
            messages=[
                {"role": "user", "content": "Explain quantum computing in simple terms"}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        print("Response:", response['choices'][0]['message']['content'])
        print("Tokens used:", response['usage']['total_tokens'])

async def coding_assistant_example():
    """Coding assistant example."""
    config = MelanieConfig(
        api_key="mel_your_api_key_here",
        base_url="http://your-tailscale-ip:8000"
    )
    
    async with MelanieAIClient(config) as client:
        response = await client.chat_completion(
            model="Melanie-3-code",
            messages=[
                {
                    "role": "user", 
                    "content": "Write a Python function to implement binary search with error handling"
                }
            ],
            temperature=0.3  # Lower temperature for more deterministic code
        )
        
        code = response['choices'][0]['message']['content']
        print("Generated code:")
        print(code)

async def research_example():
    """Deep research example."""
    config = MelanieConfig(
        api_key="mel_your_api_key_here",
        base_url="http://your-tailscale-ip:8000"
    )
    
    async with MelanieAIClient(config) as client:
        response = await client.chat_completion(
            model="Melanie-3",
            messages=[
                {
                    "role": "user",
                    "content": "Research the latest developments in renewable energy storage technologies and their economic impact"
                }
            ],
            web_search=True
        )
        
        print("Research response:", response['choices'][0]['message']['content'])
        
        if 'research_plan' in response:
            plan = response['research_plan']
            print(f"\nResearch Plan: {plan['title']}")
            print(f"Estimated agents: {plan['estimated_agents']}")
            print(f"Estimated duration: {plan['estimated_duration']} seconds")

async def file_processing_example():
    """File upload and processing example."""
    config = MelanieConfig(
        api_key="mel_your_api_key_here",
        base_url="http://your-tailscale-ip:8000"
    )
    
    async with MelanieAIClient(config) as client:
        # Upload file
        upload_result = await client.upload_file("document.pdf")
        file_id = upload_result['id']
        
        print(f"File uploaded: {file_id}")
        print(f"Processing status: {upload_result['processing_status']}")
        
        # Get file info
        file_info = await client.get_file_info(file_id)
        print(f"File processed: {file_info['processed']}")
        print(f"RAG ingested: {file_info['rag_ingested']}")
        
        # Use file context in chat
        response = await client.chat_completion(
            model="Melanie-3",
            messages=[
                {
                    "role": "user",
                    "content": "Summarize the key points from the uploaded document"
                }
            ]
        )
        
        print("Document summary:", response['choices'][0]['message']['content'])

# Run examples
if __name__ == "__main__":
    asyncio.run(basic_chat_example())
    asyncio.run(coding_assistant_example())
    asyncio.run(research_example())
    asyncio.run(file_processing_example())
```

### Django Integration

```python
# settings.py
MELANIE_AI_CONFIG = {
    'API_KEY': os.getenv('MELANIE_API_KEY'),
    'BASE_URL': os.getenv('MELANIE_BASE_URL', 'http://your-tailscale-ip:8000'),
    'TIMEOUT': 60,
    'MAX_RETRIES': 3
}

# services/melanie_service.py
from django.conf import settings
import aiohttp
import asyncio
from asgiref.sync import sync_to_async

class MelanieDjangoService:
    """Django service for Melanie AI integration."""
    
    def __init__(self):
        self.config = settings.MELANIE_AI_CONFIG
        self.headers = {
            "Authorization": f"Bearer {self.config['API_KEY']}",
            "Content-Type": "application/json"
        }
    
    async def generate_response(self, user_message: str, model: str = "Melanie-3"):
        """Generate AI response for user message."""
        async with aiohttp.ClientSession() as session:
            data = {
                "model": model,
                "messages": [
                    {"role": "user", "content": user_message}
                ]
            }
            
            async with session.post(
                f"{self.config['BASE_URL']}/chat/completions",
                json=data,
                headers=self.headers
            ) as response:
                result = await response.json()
                return result['choices'][0]['message']['content']

# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import asyncio

@csrf_exempt
@require_http_methods(["POST"])
def chat_endpoint(request):
    """Django view for chat completions."""
    try:
        data = json.loads(request.body)
        user_message = data.get('message')
        model = data.get('model', 'Melanie-3')
        
        if not user_message:
            return JsonResponse({'error': 'Message is required'}, status=400)
        
        # Run async function in sync context
        service = MelanieDjangoService()
        response = asyncio.run(service.generate_response(user_message, model))
        
        return JsonResponse({
            'response': response,
            'model': model
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('api/chat/', views.chat_endpoint, name='chat'),
]
```

### FastAPI Integration

```python
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import aiohttp
import asyncio
from typing import Optional, List

app = FastAPI(title="Melanie AI Integration")

class ChatRequest(BaseModel):
    message: str
    model: str = "Melanie-3"
    web_search: bool = False

class ChatResponse(BaseModel):
    response: str
    model: str
    tokens_used: int

class MelanieFastAPIService:
    """FastAPI service for Melanie AI integration."""
    
    def __init__(self):
        self.api_key = "mel_your_api_key_here"
        self.base_url = "http://your-tailscale-ip:8000"
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def get_session(self):
        """Get or create aiohttp session."""
        if not self.session:
            self.session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
        return self.session
    
    async def close_session(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Create chat completion."""
        session = await self.get_session()
        
        data = {
            "model": request.model,
            "messages": [
                {"role": "user", "content": request.message}
            ],
            "web_search": request.web_search
        }
        
        async with session.post(f"{self.base_url}/chat/completions", json=data) as response:
            if response.status != 200:
                error_data = await response.json()
                raise HTTPException(
                    status_code=response.status,
                    detail=error_data.get('message', 'API request failed')
                )
            
            result = await response.json()
            
            return ChatResponse(
                response=result['choices'][0]['message']['content'],
                model=result['model'],
                tokens_used=result['usage']['total_tokens']
            )

# Global service instance
melanie_service = MelanieFastAPIService()

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    print("Starting Melanie AI integration service...")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    await melanie_service.close_session()

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Chat completion endpoint."""
    try:
        return await melanie_service.chat_completion(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        session = await melanie_service.get_session()
        async with session.get(f"{melanie_service.base_url}/health") as response:
            if response.status == 200:
                return {"status": "healthy", "melanie_api": "connected"}
            else:
                return {"status": "degraded", "melanie_api": "disconnected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

## JavaScript/Node.js Integration

### Node.js Client

```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

class MelanieAIClient {
    constructor(config) {
        this.apiKey = config.apiKey;
        this.baseUrl = config.baseUrl;
        this.timeout = config.timeout || 60000;
        this.maxRetries = config.maxRetries || 3;
        
        this.client = axios.create({
            baseURL: this.baseUrl,
            timeout: this.timeout,
            headers: {
                'Authorization': `Bearer ${this.apiKey}`,
                'Content-Type': 'application/json',
                'User-Agent': 'MelanieAI-Node/1.0.0'
            }
        });
        
        // Add response interceptor for error handling
        this.client.interceptors.response.use(
            response => response,
            error => this.handleError(error)
        );
    }
    
    async handleError(error) {
        if (error.response) {
            const { status, data } = error.response;
            
            if (status === 429) {
                // Rate limit handling
                const retryAfter = parseInt(error.response.headers['retry-after'] || '60');
                throw new RateLimitError(data.message, retryAfter, data.details);
            } else if (status >= 500) {
                // Server error
                throw new ServerError(data.message, status, data.details);
            } else {
                // Client error
                throw new APIError(data.message, status, data.error, data.details);
            }
        } else if (error.request) {
            throw new NetworkError('Network request failed');
        } else {
            throw new Error(`Request setup error: ${error.message}`);
        }
    }
    
    async retryWithBackoff(fn, maxRetries = this.maxRetries) {
        let lastError;
        
        for (let attempt = 0; attempt <= maxRetries; attempt++) {
            try {
                return await fn();
            } catch (error) {
                lastError = error;
                
                if (error instanceof RateLimitError && attempt < maxRetries) {
                    console.log(`Rate limited. Retrying in ${error.retryAfter}s...`);
                    await this.sleep(error.retryAfter * 1000);
                    continue;
                } else if (error instanceof ServerError && attempt < maxRetries) {
                    const delay = Math.min(1000 * Math.pow(2, attempt), 60000);
                    console.log(`Server error. Retrying in ${delay}ms...`);
                    await this.sleep(delay);
                    continue;
                } else {
                    break;
                }
            }
        }
        
        throw lastError;
    }
    
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    async chatCompletion(model, messages, options = {}) {
        const requestFn = () => this.client.post('/chat/completions', {
            model,
            messages,
            ...options
        });
        
        const response = await this.retryWithBackoff(requestFn);
        return response.data;
    }
    
    async uploadFile(filePath) {
        const form = new FormData();
        form.append('file', fs.createReadStream(filePath));
        
        const requestFn = () => this.client.post('/files', form, {
            headers: {
                ...form.getHeaders(),
                'Authorization': `Bearer ${this.apiKey}`
            }
        });
        
        const response = await this.retryWithBackoff(requestFn);
        return response.data;
    }
    
    async getFileInfo(fileId) {
        const response = await this.client.get(`/files/${fileId}`);
        return response.data;
    }
    
    async deleteFile(fileId) {
        const response = await this.client.delete(`/files/${fileId}`);
        return response.data;
    }
    
    async queryDocumentation(technology, topic, version = null) {
        const data = { technology, topic };
        if (version) data.version = version;
        
        const response = await this.client.post('/mcp/documentation', data);
        return response.data;
    }
    
    async healthCheck() {
        const response = await this.client.get('/health');
        return response.data;
    }
}

// Custom error classes
class APIError extends Error {
    constructor(message, statusCode, errorCode, details = {}) {
        super(message);
        this.name = 'APIError';
        this.statusCode = statusCode;
        this.errorCode = errorCode;
        this.details = details;
    }
}

class RateLimitError extends APIError {
    constructor(message, retryAfter, details = {}) {
        super(message, 429, 'rate_limit_exceeded', details);
        this.name = 'RateLimitError';
        this.retryAfter = retryAfter;
    }
}

class ServerError extends APIError {
    constructor(message, statusCode, details = {}) {
        super(message, statusCode, 'server_error', details);
        this.name = 'ServerError';
    }
}

class NetworkError extends Error {
    constructor(message) {
        super(message);
        this.name = 'NetworkError';
    }
}

// Usage examples
async function basicChatExample() {
    const client = new MelanieAIClient({
        apiKey: 'mel_your_api_key_here',
        baseUrl: 'http://your-tailscale-ip:8000'
    });
    
    try {
        const response = await client.chatCompletion('Melanie-3', [
            { role: 'user', content: 'Explain machine learning in simple terms' }
        ], {
            max_tokens: 500,
            temperature: 0.7
        });
        
        console.log('Response:', response.choices[0].message.content);
        console.log('Tokens used:', response.usage.total_tokens);
    } catch (error) {
        console.error('Error:', error.message);
    }
}

async function codingAssistantExample() {
    const client = new MelanieAIClient({
        apiKey: 'mel_your_api_key_here',
        baseUrl: 'http://your-tailscale-ip:8000'
    });
    
    try {
        const response = await client.chatCompletion('Melanie-3-code', [
            {
                role: 'user',
                content: 'Write a JavaScript function to debounce API calls'
            }
        ], {
            temperature: 0.3
        });
        
        console.log('Generated code:');
        console.log(response.choices[0].message.content);
    } catch (error) {
        console.error('Error:', error.message);
    }
}

async function fileProcessingExample() {
    const client = new MelanieAIClient({
        apiKey: 'mel_your_api_key_here',
        baseUrl: 'http://your-tailscale-ip:8000'
    });
    
    try {
        // Upload file
        const uploadResult = await client.uploadFile('./document.pdf');
        console.log('File uploaded:', uploadResult.id);
        
        // Get file info
        const fileInfo = await client.getFileInfo(uploadResult.id);
        console.log('File processed:', fileInfo.processed);
        
        // Use file context in chat
        const response = await client.chatCompletion('Melanie-3', [
            {
                role: 'user',
                content: 'Analyze the uploaded document and provide key insights'
            }
        ]);
        
        console.log('Analysis:', response.choices[0].message.content);
    } catch (error) {
        console.error('Error:', error.message);
    }
}

module.exports = {
    MelanieAIClient,
    APIError,
    RateLimitError,
    ServerError,
    NetworkError
};

// Run examples if this file is executed directly
if (require.main === module) {
    basicChatExample();
    codingAssistantExample();
    fileProcessingExample();
}
```

### Express.js Integration

```javascript
const express = require('express');
const { MelanieAIClient } = require('./melanie-client');
const multer = require('multer');
const path = require('path');

const app = express();
const upload = multer({ dest: 'uploads/' });

// Initialize Melanie client
const melanie = new MelanieAIClient({
    apiKey: process.env.MELANIE_API_KEY,
    baseUrl: process.env.MELANIE_BASE_URL || 'http://your-tailscale-ip:8000'
});

app.use(express.json());

// Chat endpoint
app.post('/api/chat', async (req, res) => {
    try {
        const { message, model = 'Melanie-3', web_search = false } = req.body;
        
        if (!message) {
            return res.status(400).json({ error: 'Message is required' });
        }
        
        const response = await melanie.chatCompletion(model, [
            { role: 'user', content: message }
        ], { web_search });
        
        res.json({
            response: response.choices[0].message.content,
            model: response.model,
            tokens_used: response.usage.total_tokens,
            research_plan: response.research_plan
        });
        
    } catch (error) {
        console.error('Chat error:', error);
        res.status(error.statusCode || 500).json({
            error: error.message,
            type: error.name
        });
    }
});

// File upload endpoint
app.post('/api/upload', upload.single('file'), async (req, res) => {
    try {
        if (!req.file) {
            return res.status(400).json({ error: 'No file uploaded' });
        }
        
        const result = await melanie.uploadFile(req.file.path);
        
        res.json({
            file_id: result.id,
            filename: result.filename,
            processed: result.processed,
            rag_ingested: result.rag_ingested
        });
        
    } catch (error) {
        console.error('Upload error:', error);
        res.status(error.statusCode || 500).json({
            error: error.message,
            type: error.name
        });
    }
});

// Health check endpoint
app.get('/api/health', async (req, res) => {
    try {
        const health = await melanie.healthCheck();
        res.json({
            status: 'healthy',
            melanie_api: health.status,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(503).json({
            status: 'unhealthy',
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// Error handling middleware
app.use((error, req, res, next) => {
    console.error('Unhandled error:', error);
    res.status(500).json({
        error: 'Internal server error',
        message: error.message
    });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
```

## Web Frontend Integration

### React Integration

```jsx
import React, { useState, useCallback, useRef, useEffect } from 'react';
import axios from 'axios';

// Custom hook for Melanie AI integration
const useMelanieAI = (apiKey, baseUrl) => {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const abortControllerRef = useRef(null);
    
    const client = axios.create({
        baseURL: baseUrl,
        headers: {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json'
        }
    });
    
    const chatCompletion = useCallback(async (model, messages, options = {}) => {
        setLoading(true);
        setError(null);
        
        // Cancel previous request if still pending
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        
        abortControllerRef.current = new AbortController();
        
        try {
            const response = await client.post('/chat/completions', {
                model,
                messages,
                ...options
            }, {
                signal: abortControllerRef.current.signal
            });
            
            return response.data;
        } catch (err) {
            if (err.name !== 'AbortError') {
                setError(err.response?.data?.message || err.message);
                throw err;
            }
        } finally {
            setLoading(false);
        }
    }, [client]);
    
    const uploadFile = useCallback(async (file) => {
        setLoading(true);
        setError(null);
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await client.post('/files', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            });
            
            return response.data;
        } catch (err) {
            setError(err.response?.data?.message || err.message);
            throw err;
        } finally {
            setLoading(false);
        }
    }, [client]);
    
    useEffect(() => {
        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
        };
    }, []);
    
    return {
        chatCompletion,
        uploadFile,
        loading,
        error
    };
};

// Chat component
const ChatInterface = ({ apiKey, baseUrl }) => {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [model, setModel] = useState('Melanie-3');
    const [webSearch, setWebSearch] = useState(false);
    
    const { chatCompletion, uploadFile, loading, error } = useMelanieAI(apiKey, baseUrl);
    
    const handleSendMessage = async () => {
        if (!input.trim()) return;
        
        const userMessage = { role: 'user', content: input };
        const newMessages = [...messages, userMessage];
        setMessages(newMessages);
        setInput('');
        
        try {
            const response = await chatCompletion(model, newMessages, {
                web_search: webSearch,
                max_tokens: 1000
            });
            
            const assistantMessage = {
                role: 'assistant',
                content: response.choices[0].message.content,
                tokens_used: response.usage.total_tokens,
                research_plan: response.research_plan
            };
            
            setMessages([...newMessages, assistantMessage]);
        } catch (err) {
            console.error('Chat error:', err);
        }
    };
    
    const handleFileUpload = async (event) => {
        const file = event.target.files[0];
        if (!file) return;
        
        try {
            const result = await uploadFile(file);
            
            const fileMessage = {
                role: 'system',
                content: `File uploaded: ${result.filename} (${result.processing_status})`
            };
            
            setMessages(prev => [...prev, fileMessage]);
        } catch (err) {
            console.error('Upload error:', err);
        }
    };
    
    return (
        <div className="chat-interface">
            <div className="chat-header">
                <select 
                    value={model} 
                    onChange={(e) => setModel(e.target.value)}
                    className="model-selector"
                >
                    <option value="Melanie-3">Melanie-3 (General)</option>
                    <option value="Melanie-3-light">Melanie-3-light (Fast)</option>
                    <option value="Melanie-3-code">Melanie-3-code (Coding)</option>
                </select>
                
                <label className="web-search-toggle">
                    <input
                        type="checkbox"
                        checked={webSearch}
                        onChange={(e) => setWebSearch(e.target.checked)}
                    />
                    Web Search
                </label>
            </div>
            
            <div className="messages">
                {messages.map((message, index) => (
                    <div key={index} className={`message ${message.role}`}>
                        <div className="message-content">
                            {message.content}
                        </div>
                        {message.tokens_used && (
                            <div className="message-meta">
                                Tokens: {message.tokens_used}
                            </div>
                        )}
                        {message.research_plan && (
                            <div className="research-plan">
                                <h4>Research Plan: {message.research_plan.title}</h4>
                                <p>Agents: {message.research_plan.estimated_agents}</p>
                                <p>Duration: {message.research_plan.estimated_duration}s</p>
                            </div>
                        )}
                    </div>
                ))}
            </div>
            
            {error && (
                <div className="error-message">
                    Error: {error}
                </div>
            )}
            
            <div className="input-area">
                <input
                    type="file"
                    onChange={handleFileUpload}
                    accept=".txt,.md,.pdf,.jpg,.jpeg,.png"
                    className="file-input"
                />
                
                <div className="message-input">
                    <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyPress={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                handleSendMessage();
                            }
                        }}
                        placeholder="Type your message..."
                        disabled={loading}
                    />
                    <button 
                        onClick={handleSendMessage}
                        disabled={loading || !input.trim()}
                    >
                        {loading ? 'Sending...' : 'Send'}
                    </button>
                </div>
            </div>
        </div>
    );
};

// Main App component
const App = () => {
    const apiKey = process.env.REACT_APP_MELANIE_API_KEY;
    const baseUrl = process.env.REACT_APP_MELANIE_BASE_URL || 'http://your-tailscale-ip:8000';
    
    if (!apiKey) {
        return (
            <div className="error">
                Please set REACT_APP_MELANIE_API_KEY environment variable
            </div>
        );
    }
    
    return (
        <div className="app">
            <h1>Melanie AI Chat</h1>
            <ChatInterface apiKey={apiKey} baseUrl={baseUrl} />
        </div>
    );
};

export default App;
```

### Vue.js Integration

```vue
<template>
  <div class="melanie-chat">
    <div class="chat-header">
      <select v-model="selectedModel" class="model-selector">
        <option value="Melanie-3">Melanie-3 (General)</option>
        <option value="Melanie-3-light">Melanie-3-light (Fast)</option>
        <option value="Melanie-3-code">Melanie-3-code (Coding)</option>
      </select>
      
      <label class="web-search-toggle">
        <input type="checkbox" v-model="webSearch" />
        Web Search
      </label>
    </div>
    
    <div class="messages" ref="messagesContainer">
      <div 
        v-for="(message, index) in messages" 
        :key="index" 
        :class="['message', message.role]"
      >
        <div class="message-content" v-html="formatMessage(message.content)"></div>
        <div v-if="message.tokens_used" class="message-meta">
          Tokens: {{ message.tokens_used }}
        </div>
        <div v-if="message.research_plan" class="research-plan">
          <h4>Research Plan: {{ message.research_plan.title }}</h4>
          <p>Agents: {{ message.research_plan.estimated_agents }}</p>
          <p>Duration: {{ message.research_plan.estimated_duration }}s</p>
        </div>
      </div>
    </div>
    
    <div v-if="error" class="error-message">
      Error: {{ error }}
    </div>
    
    <div class="input-area">
      <input
        type="file"
        @change="handleFileUpload"
        accept=".txt,.md,.pdf,.jpg,.jpeg,.png"
        class="file-input"
      />
      
      <div class="message-input">
        <textarea
          v-model="input"
          @keypress.enter.exact.prevent="sendMessage"
          placeholder="Type your message..."
          :disabled="loading"
        ></textarea>
        <button 
          @click="sendMessage"
          :disabled="loading || !input.trim()"
        >
          {{ loading ? 'Sending...' : 'Send' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'MelanieChat',
  props: {
    apiKey: {
      type: String,
      required: true
    },
    baseUrl: {
      type: String,
      default: 'http://your-tailscale-ip:8000'
    }
  },
  data() {
    return {
      messages: [],
      input: '',
      selectedModel: 'Melanie-3',
      webSearch: false,
      loading: false,
      error: null,
      client: null
    };
  },
  created() {
    this.client = axios.create({
      baseURL: this.baseUrl,
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json'
      }
    });
  },
  methods: {
    async sendMessage() {
      if (!this.input.trim()) return;
      
      const userMessage = { role: 'user', content: this.input };
      this.messages.push(userMessage);
      const currentInput = this.input;
      this.input = '';
      this.loading = true;
      this.error = null;
      
      try {
        const response = await this.client.post('/chat/completions', {
          model: this.selectedModel,
          messages: this.messages,
          web_search: this.webSearch,
          max_tokens: 1000
        });
        
        const assistantMessage = {
          role: 'assistant',
          content: response.data.choices[0].message.content,
          tokens_used: response.data.usage.total_tokens,
          research_plan: response.data.research_plan
        };
        
        this.messages.push(assistantMessage);
        this.scrollToBottom();
        
      } catch (err) {
        this.error = err.response?.data?.message || err.message;
        console.error('Chat error:', err);
      } finally {
        this.loading = false;
      }
    },
    
    async handleFileUpload(event) {
      const file = event.target.files[0];
      if (!file) return;
      
      const formData = new FormData();
      formData.append('file', file);
      
      this.loading = true;
      this.error = null;
      
      try {
        const response = await this.client.post('/files', formData, {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        });
        
        const fileMessage = {
          role: 'system',
          content: `File uploaded: ${response.data.filename} (${response.data.processing_status})`
        };
        
        this.messages.push(fileMessage);
        this.scrollToBottom();
        
      } catch (err) {
        this.error = err.response?.data?.message || err.message;
        console.error('Upload error:', err);
      } finally {
        this.loading = false;
      }
    },
    
    formatMessage(content) {
      // Basic markdown-like formatting
      return content
        .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>');
    },
    
    scrollToBottom() {
      this.$nextTick(() => {
        const container = this.$refs.messagesContainer;
        container.scrollTop = container.scrollHeight;
      });
    }
  }
};
</script>

<style scoped>
.melanie-chat {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  font-family: Arial, sans-serif;
}

.chat-header {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  align-items: center;
}

.model-selector {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.web-search-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
}

.messages {
  height: 400px;
  overflow-y: auto;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.message {
  margin-bottom: 16px;
  padding: 12px;
  border-radius: 8px;
}

.message.user {
  background-color: #e3f2fd;
  margin-left: 20%;
}

.message.assistant {
  background-color: #f5f5f5;
  margin-right: 20%;
}

.message.system {
  background-color: #fff3e0;
  font-style: italic;
}

.message-content {
  margin-bottom: 8px;
}

.message-meta {
  font-size: 12px;
  color: #666;
}

.research-plan {
  margin-top: 12px;
  padding: 12px;
  background-color: #e8f5e8;
  border-radius: 4px;
}

.research-plan h4 {
  margin: 0 0 8px 0;
  color: #2e7d32;
}

.research-plan p {
  margin: 4px 0;
  font-size: 14px;
}

.error-message {
  background-color: #ffebee;
  color: #c62828;
  padding: 12px;
  border-radius: 4px;
  margin-bottom: 16px;
}

.input-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.file-input {
  padding: 8px;
}

.message-input {
  display: flex;
  gap: 12px;
}

.message-input textarea {
  flex: 1;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  resize: vertical;
  min-height: 60px;
}

.message-input button {
  padding: 12px 24px;
  background-color: #1976d2;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.message-input button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.message-input button:hover:not(:disabled) {
  background-color: #1565c0;
}
</style>
```

This comprehensive integration guide provides examples for multiple programming languages and frameworks, demonstrating how to integrate with the Melanie AI API effectively. Each example includes proper error handling, retry logic, and best practices for production use.