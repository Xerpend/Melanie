"""
Authentication system for Melanie AI API

This module implements:
- API key generation with mel_ prefix
- bcrypt hashing for secure key storage
- Authentication middleware for request validation
- Basic rate limiting (100 req/min per key)
"""

import asyncio
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import bcrypt
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel


class APIKey(BaseModel):
    """API key model for storage and validation."""
    key_id: str
    key_hash: str
    created_at: datetime
    last_used: Optional[datetime] = None
    is_active: bool = True
    rate_limit: int = 100  # requests per minute


class RateLimiter:
    """Simple in-memory rate limiter for API keys."""
    
    def __init__(self):
        # Store request timestamps for each key
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, key_id: str, limit: int = 100) -> Tuple[bool, int]:
        """
        Check if request is allowed under rate limit.
        
        Args:
            key_id: API key identifier
            limit: Requests per minute limit
            
        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        async with self._lock:
            now = time.time()
            minute_ago = now - 60
            
            # Clean old requests (older than 1 minute)
            self._requests[key_id] = [
                req_time for req_time in self._requests[key_id]
                if req_time > minute_ago
            ]
            
            current_count = len(self._requests[key_id])
            
            if current_count >= limit:
                return False, 0
            
            # Add current request
            self._requests[key_id].append(now)
            remaining = limit - (current_count + 1)
            
            return True, remaining


class APIKeyManager:
    """Manages API key generation, storage, and validation."""
    
    def __init__(self):
        # In-memory storage for demo (in production, use database)
        self._keys: Dict[str, APIKey] = {}
        self.rate_limiter = RateLimiter()
    
    def generate_key(self) -> Tuple[str, str]:
        """
        Generate a new API key with mel_ prefix.
        
        Returns:
            Tuple of (raw_key, key_id) where raw_key should be given to user
        """
        # Generate random key with mel_ prefix
        random_part = secrets.token_urlsafe(32)
        raw_key = f"mel_{random_part}"
        
        # Create key ID (first 8 chars after prefix for identification)
        key_id = f"mel_{random_part[:8]}"
        
        return raw_key, key_id
    
    def hash_key(self, raw_key: str) -> str:
        """Hash API key using bcrypt."""
        key_bytes = raw_key.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(key_bytes, salt)
        return hashed.decode('utf-8')
    
    def verify_key(self, raw_key: str, key_hash: str) -> bool:
        """Verify raw key against stored hash."""
        key_bytes = raw_key.encode('utf-8')
        hash_bytes = key_hash.encode('utf-8')
        return bcrypt.checkpw(key_bytes, hash_bytes)
    
    def create_api_key(self) -> Tuple[str, APIKey]:
        """
        Create and store a new API key.
        
        Returns:
            Tuple of (raw_key, api_key_object)
        """
        raw_key, key_id = self.generate_key()
        key_hash = self.hash_key(raw_key)
        
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            created_at=datetime.utcnow(),
            is_active=True,
            rate_limit=100
        )
        
        self._keys[key_id] = api_key
        return raw_key, api_key
    
    async def validate_key(self, raw_key: str) -> Optional[APIKey]:
        """
        Validate API key and check rate limits.
        
        Args:
            raw_key: Raw API key from request
            
        Returns:
            APIKey object if valid, None if invalid
        """
        if not raw_key or not raw_key.startswith('mel_'):
            return None
        
        # Extract key ID for lookup
        try:
            key_id = f"mel_{raw_key[4:12]}"  # mel_ + first 8 chars
        except IndexError:
            return None
        
        # Check if key exists
        if key_id not in self._keys:
            return None
        
        api_key = self._keys[key_id]
        
        # Check if key is active
        if not api_key.is_active:
            return None
        
        # Verify key hash
        if not self.verify_key(raw_key, api_key.key_hash):
            return None
        
        # Check rate limit
        allowed, remaining = await self.rate_limiter.is_allowed(
            key_id, api_key.rate_limit
        )
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Maximum 100 requests per minute.",
                headers={"Retry-After": "60"}
            )
        
        # Update last used timestamp
        api_key.last_used = datetime.utcnow()
        
        return api_key
    
    def get_key_info(self, key_id: str) -> Optional[APIKey]:
        """Get API key information by key ID."""
        return self._keys.get(key_id)
    
    def list_keys(self) -> Dict[str, APIKey]:
        """List all API keys (for admin purposes)."""
        return self._keys.copy()
    
    def deactivate_key(self, key_id: str) -> bool:
        """Deactivate an API key."""
        if key_id in self._keys:
            self._keys[key_id].is_active = False
            return True
        return False


class APIKeyAuth(HTTPBearer):
    """FastAPI authentication dependency for API keys."""
    
    def __init__(self, key_manager: APIKeyManager):
        super().__init__(auto_error=False)
        self.key_manager = key_manager
    
    async def __call__(self, request: Request) -> Optional[APIKey]:
        """
        Authenticate request using API key.
        
        Args:
            request: FastAPI request object
            
        Returns:
            APIKey object if authenticated, raises HTTPException if not
        """
        # Try to get credentials from Authorization header
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API key. Include 'Authorization: Bearer mel_your_key' header.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Validate the API key
        api_key = await self.key_manager.validate_key(credentials.credentials)
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key. Ensure your key starts with 'mel_' and is active.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return api_key


# Global instances
api_key_manager = APIKeyManager()
api_key_auth = APIKeyAuth(api_key_manager)


# Response models for API endpoints
class CreateKeyResponse(BaseModel):
    """Response model for API key creation."""
    api_key: str
    key_id: str
    message: str
    rate_limit: int


class KeyInfoResponse(BaseModel):
    """Response model for API key information."""
    key_id: str
    created_at: datetime
    last_used: Optional[datetime]
    is_active: bool
    rate_limit: int


def create_demo_key() -> str:
    """Create a demo API key for testing purposes."""
    raw_key, api_key = api_key_manager.create_api_key()
    return raw_key