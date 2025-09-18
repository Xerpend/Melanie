"""
Base model interface and validation system for Melanie AI API

This module implements:
- BaseModel abstract class with common interface for AI models
- Request validation with Pydantic models
- Input sanitization and file type validation
- Error handling structures for proper API responses
"""

import re
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class ModelType(str, Enum):
    """Supported AI model types."""
    MELANIE_3 = "Melanie-3"
    MELANIE_3_LIGHT = "Melanie-3-light"
    MELANIE_3_CODE = "Melanie-3-code"


class MessageRole(str, Enum):
    """Chat message roles."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ToolType(str, Enum):
    """Available tool types."""
    FUNCTION = "function"


class ChatMessage(BaseModel):
    """Chat message model with validation."""
    role: MessageRole
    content: str = Field(..., min_length=1, max_length=100000)
    name: Optional[str] = Field(None, max_length=100)
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        """Sanitize and validate message content."""
        if not v or not v.strip():
            raise ValueError("Message content cannot be empty")
        
        # Basic sanitization - remove null bytes and control characters
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', v)
        
        # Limit consecutive whitespace
        sanitized = re.sub(r'\s{10,}', ' ' * 10, sanitized)
        
        return sanitized.strip()
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate optional name field."""
        if v is not None:
            # Only allow alphanumeric, underscore, hyphen
            if not re.match(r'^[a-zA-Z0-9_-]+$', v):
                raise ValueError("Name must contain only alphanumeric characters, underscores, and hyphens")
        return v


class ToolFunction(BaseModel):
    """Tool function definition."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    parameters: Optional[Dict[str, Any]] = None
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate function name."""
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', v):
            raise ValueError("Function name must start with letter and contain only alphanumeric, underscore, hyphen")
        return v


class Tool(BaseModel):
    """Tool definition model."""
    type: ToolType = ToolType.FUNCTION
    function: ToolFunction


class ToolCall(BaseModel):
    """Tool call in assistant response."""
    id: str = Field(..., min_length=1, max_length=100)
    type: ToolType = ToolType.FUNCTION
    function: Dict[str, Any]


class ChatCompletionRequest(BaseModel):
    """Chat completion request model with comprehensive validation."""
    model: ModelType
    messages: List[ChatMessage] = Field(..., min_length=1, max_length=100)
    tools: Optional[List[Tool]] = Field(None, max_length=20)
    web_search: bool = Field(False)
    max_tokens: Optional[int] = Field(None, ge=1, le=100000)
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(1.0, ge=0.0, le=1.0)
    stream: bool = Field(False)
    
    @field_validator('messages')
    @classmethod
    def validate_messages(cls, v):
        """Validate message sequence."""
        if not v:
            raise ValueError("At least one message is required")
        
        # Check for reasonable conversation flow
        roles = [msg.role for msg in v]
        
        # First message should typically be user or system
        if roles[0] not in [MessageRole.USER, MessageRole.SYSTEM]:
            raise ValueError("First message should be from user or system")
        
        return v
    
    @field_validator('tools')
    @classmethod
    def validate_tools(cls, v):
        """Validate tools list."""
        if v is not None:
            # Check for duplicate tool names
            names = [tool.function.name for tool in v]
            if len(names) != len(set(names)):
                raise ValueError("Duplicate tool names are not allowed")
        return v


class Usage(BaseModel):
    """Token usage information."""
    prompt_tokens: int = Field(..., ge=0)
    completion_tokens: int = Field(..., ge=0)
    total_tokens: int = Field(..., ge=0)
    
    @field_validator('total_tokens')
    @classmethod
    def validate_total(cls, v, info):
        """Ensure total equals sum of prompt and completion tokens."""
        if info.data and 'prompt_tokens' in info.data and 'completion_tokens' in info.data:
            expected_total = info.data['prompt_tokens'] + info.data['completion_tokens']
            if v != expected_total:
                raise ValueError("Total tokens must equal prompt_tokens + completion_tokens")
        return v


class Choice(BaseModel):
    """Chat completion choice."""
    index: int = Field(..., ge=0)
    message: Dict[str, Any]
    finish_reason: Optional[str] = None


class ChatCompletionResponse(BaseModel):
    """Chat completion response model."""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice] = Field(..., min_length=1)
    usage: Usage
    research_plan: Optional[Dict[str, Any]] = None  # Custom field for deep research


class FileType(str, Enum):
    """Supported file types."""
    TEXT = "text/plain"
    MARKDOWN = "text/markdown"
    PDF = "application/pdf"
    IMAGE_JPEG = "image/jpeg"
    IMAGE_PNG = "image/png"
    IMAGE_WEBP = "image/webp"
    JSON = "application/json"


class FileUploadRequest(BaseModel):
    """File upload validation."""
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str
    size: int = Field(..., ge=1, le=50_000_000)  # Max 50MB
    
    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v):
        """Validate filename for security."""
        # Remove path traversal attempts
        filename = v.replace('..', '').replace('/', '').replace('\\', '')
        
        # Check for valid characters
        if not re.match(r'^[a-zA-Z0-9._-]+$', filename):
            raise ValueError("Filename contains invalid characters")
        
        # Must have extension
        if '.' not in filename:
            raise ValueError("Filename must have an extension")
        
        return filename
    
    @field_validator('content_type')
    @classmethod
    def validate_content_type(cls, v):
        """Validate file content type."""
        allowed_types = [ft.value for ft in FileType]
        if v not in allowed_types:
            raise ValueError(f"Unsupported file type. Allowed: {', '.join(allowed_types)}")
        return v


class FileInfo(BaseModel):
    """File information model."""
    id: str
    filename: str
    content_type: str
    size: int
    uploaded_at: datetime
    processed: bool = False
    rag_ingested: bool = False
    content_hash: Optional[str] = None  # SHA-256 hash for duplicate detection


class APIError(BaseModel):
    """Standard API error response."""
    error: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    details: Optional[Dict[str, Any]] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ValidationError(BaseModel):
    """Validation error details."""
    field: str
    message: str
    invalid_value: Optional[Any] = None


class DetailedAPIError(APIError):
    """API error with validation details."""
    validation_errors: Optional[List[ValidationError]] = None


# Abstract base class for AI models
class BaseAIModel(ABC):
    """
    Abstract base class for AI model implementations.
    
    Provides common interface for all AI models in the system.
    """
    
    def __init__(self, model_name: str, api_key: str, **kwargs):
        """
        Initialize base model.
        
        Args:
            model_name: Name of the model
            api_key: API key for the model service
            **kwargs: Additional model-specific configuration
        """
        self.model_name = model_name
        self.api_key = api_key
        self.config = kwargs
        self._validate_config()
    
    def _validate_config(self):
        """Validate model configuration."""
        if not self.model_name:
            raise ValueError("Model name is required")
        if not self.api_key:
            raise ValueError("API key is required")
    
    @abstractmethod
    async def generate(
        self, 
        messages: List[ChatMessage], 
        tools: Optional[List[Tool]] = None,
        **kwargs
    ) -> ChatCompletionResponse:
        """
        Generate chat completion.
        
        Args:
            messages: List of chat messages
            tools: Optional list of available tools
            **kwargs: Additional generation parameters
            
        Returns:
            ChatCompletionResponse: Generated response
        """
        pass
    
    @abstractmethod
    async def validate_request(self, request: ChatCompletionRequest) -> bool:
        """
        Validate if request is compatible with this model.
        
        Args:
            request: Chat completion request
            
        Returns:
            bool: True if request is valid for this model
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """
        Get list of model capabilities.
        
        Returns:
            List[str]: List of capability names
        """
        pass
    
    @abstractmethod
    def get_max_tokens(self) -> int:
        """
        Get maximum token limit for this model.
        
        Returns:
            int: Maximum token limit
        """
        pass
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get model information.
        
        Returns:
            Dict: Model information including name, capabilities, limits
        """
        return {
            "name": self.model_name,
            "capabilities": self.get_capabilities(),
            "max_tokens": self.get_max_tokens(),
            "config": self.config
        }


class InputSanitizer:
    """Input sanitization utilities."""
    
    @staticmethod
    def sanitize_text(text: str, max_length: int = 100000) -> str:
        """
        Sanitize text input.
        
        Args:
            text: Input text to sanitize
            max_length: Maximum allowed length
            
        Returns:
            str: Sanitized text
        """
        if not isinstance(text, str):
            raise ValueError("Input must be a string")
        
        # Remove null bytes and control characters
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        # Normalize whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized)
        
        return sanitized.strip()
    
    @staticmethod
    def validate_file_extension(filename: str) -> bool:
        """
        Validate file extension against allowed types.
        
        Args:
            filename: Name of the file
            
        Returns:
            bool: True if extension is allowed
        """
        allowed_extensions = {
            '.txt', '.md', '.pdf', '.jpg', '.jpeg', '.png', '.webp', '.json'
        }
        
        extension = filename.lower().split('.')[-1] if '.' in filename else ''
        return f'.{extension}' in allowed_extensions
    
    @staticmethod
    def validate_content_size(content: bytes, max_size: int = 50_000_000) -> bool:
        """
        Validate content size.
        
        Args:
            content: File content as bytes
            max_size: Maximum allowed size in bytes
            
        Returns:
            bool: True if size is within limits
        """
        return len(content) <= max_size


class RequestValidator:
    """Request validation utilities."""
    
    @staticmethod
    def validate_chat_request(request: Dict[str, Any]) -> ChatCompletionRequest:
        """
        Validate and parse chat completion request.
        
        Args:
            request: Raw request dictionary
            
        Returns:
            ChatCompletionRequest: Validated request object
            
        Raises:
            ValueError: If validation fails
        """
        try:
            return ChatCompletionRequest(**request)
        except Exception as e:
            raise ValueError(f"Invalid request format: {str(e)}")
    
    @staticmethod
    def validate_file_upload(
        filename: str, 
        content_type: str, 
        size: int
    ) -> FileUploadRequest:
        """
        Validate file upload request.
        
        Args:
            filename: Name of the file
            content_type: MIME type of the file
            size: Size of the file in bytes
            
        Returns:
            FileUploadRequest: Validated file upload request
            
        Raises:
            ValueError: If validation fails
        """
        try:
            return FileUploadRequest(
                filename=filename,
                content_type=content_type,
                size=size
            )
        except Exception as e:
            raise ValueError(f"Invalid file upload: {str(e)}")