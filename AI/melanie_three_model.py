"""
Melanie-3 (Grok 4) model wrapper implementing BaseAIModel interface.

This module provides:
- MelanieThree class implementing BaseAIModel interface
- xAI API integration with async HTTP client
- Request/response formatting for OpenAI compatibility
- Timeout handling and retry logic with exponential backoff
- Comprehensive error handling and logging
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import httpx
from pydantic import ValidationError

# Import from API models - adjust path as needed
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'API'))

try:
    from models import (
        BaseAIModel, 
        ChatMessage, 
        ChatCompletionRequest, 
        ChatCompletionResponse,
        Tool,
        Choice,
        Usage,
        APIError
    )
except ImportError:
    # Fallback for testing - create minimal stubs
    from abc import ABC, abstractmethod
    from typing import List, Optional, Dict, Any
    from pydantic import BaseModel
    from enum import Enum
    
    class MessageRole(str, Enum):
        USER = "user"
        ASSISTANT = "assistant"
        SYSTEM = "system"
    
    class ChatMessage(BaseModel):
        role: MessageRole
        content: str
        name: Optional[str] = None
    
    class Usage(BaseModel):
        prompt_tokens: int
        completion_tokens: int
        total_tokens: int
    
    class Choice(BaseModel):
        index: int
        message: Dict[str, Any]
        finish_reason: Optional[str] = None
    
    class ChatCompletionResponse(BaseModel):
        id: str
        object: str = "chat.completion"
        created: int
        model: str
        choices: List[Choice]
        usage: Usage
        research_plan: Optional[Dict[str, Any]] = None
    
    class ToolFunction(BaseModel):
        name: str
        description: Optional[str] = None
        parameters: Optional[Dict[str, Any]] = None
    
    class Tool(BaseModel):
        function: ToolFunction
    
    class ChatCompletionRequest(BaseModel):
        model: str
        messages: List[ChatMessage]
        tools: Optional[List[Tool]] = None
    
    class BaseAIModel(ABC):
        def __init__(self, model_name: str, api_key: str, **kwargs):
            self.model_name = model_name
            self.api_key = api_key
            self.config = kwargs
        
        @abstractmethod
        async def generate(self, messages: List[ChatMessage], tools: Optional[List[Tool]] = None, **kwargs) -> ChatCompletionResponse:
            pass
        
        @abstractmethod
        async def validate_request(self, request: ChatCompletionRequest) -> bool:
            pass
        
        @abstractmethod
        def get_capabilities(self) -> List[str]:
            pass
        
        @abstractmethod
        def get_max_tokens(self) -> int:
            pass
        
        def get_model_info(self) -> Dict[str, Any]:
            return {
                "name": self.model_name,
                "capabilities": self.get_capabilities(),
                "max_tokens": self.get_max_tokens(),
                "config": self.config
            }
    
    class APIError(Exception):
        pass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MelanieThreeError(Exception):
    """Custom exception for MelanieThree model errors."""
    pass


class MelanieThreeTimeoutError(MelanieThreeError):
    """Timeout error for MelanieThree model."""
    def __init__(self, timeout: float):
        self.timeout = timeout
        super().__init__(f"Request timed out after {timeout} seconds")


class MelanieThreeRateLimitError(MelanieThreeError):
    """Rate limit error for MelanieThree model."""
    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        message = "Rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after} seconds"
        super().__init__(message)


class MelanieThree(BaseAIModel):
    """
    Melanie-3 (Grok 4) model wrapper implementing BaseAIModel interface.
    
    Provides async HTTP client integration with xAI API, OpenAI-compatible
    request/response formatting, and comprehensive error handling.
    """
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize MelanieThree model.
        
        Args:
            api_key: xAI API key (defaults to XAI_API_KEY env var)
            **kwargs: Additional configuration options
        """
        api_key = api_key or os.getenv("XAI_API_KEY")
        if not api_key:
            raise ValueError("XAI_API_KEY environment variable or api_key parameter is required")
        
        super().__init__(
            model_name="grok-4",
            api_key=api_key,
            **kwargs
        )
        
        # Configuration
        self.base_url = kwargs.get("base_url", "https://api.x.ai/v1")
        self.timeout = kwargs.get("timeout", 3600)  # 1 hour for reasoning models
        self.max_retries = kwargs.get("max_retries", 3)
        self.retry_delay = kwargs.get("retry_delay", 1.0)
        
        # HTTP client configuration
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
    
    def _format_messages_for_xai(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        """
        Format messages for xAI API.
        
        Args:
            messages: List of ChatMessage objects
            
        Returns:
            List of formatted message dictionaries
        """
        formatted_messages = []
        
        for message in messages:
            formatted_message = {
                "role": message.role.value,
                "content": message.content
            }
            
            # Add name if provided
            if message.name:
                formatted_message["name"] = message.name
            
            formatted_messages.append(formatted_message)
        
        return formatted_messages
    
    def _format_tools_for_xai(self, tools: Optional[List[Tool]]) -> Optional[List[Dict[str, Any]]]:
        """
        Format tools for xAI API.
        
        Args:
            tools: List of Tool objects
            
        Returns:
            List of formatted tool dictionaries or None
        """
        if not tools:
            return None
        
        formatted_tools = []
        
        for tool in tools:
            # Handle both enum and string types for tool.type
            tool_type = getattr(tool, 'type', None)
            if hasattr(tool_type, 'value'):
                type_value = tool_type.value
            else:
                type_value = "function"  # Default fallback
            
            formatted_tool = {
                "type": type_value,
                "function": {
                    "name": tool.function.name,
                    "description": tool.function.description or "",
                    "parameters": tool.function.parameters or {}
                }
            }
            formatted_tools.append(formatted_tool)
        
        return formatted_tools
    
    def _create_openai_response(
        self, 
        xai_response: Dict[str, Any], 
        request_id: str
    ) -> ChatCompletionResponse:
        """
        Convert xAI response to OpenAI-compatible format.
        
        Args:
            xai_response: Raw response from xAI API
            request_id: Unique request identifier
            
        Returns:
            ChatCompletionResponse object
        """
        # Extract choice data
        choices_data = []
        if "choices" in xai_response and xai_response["choices"]:
            for i, choice in enumerate(xai_response["choices"]):
                choice_data = Choice(
                    index=i,
                    message=choice.get("message", {}),
                    finish_reason=choice.get("finish_reason")
                )
                choices_data.append(choice_data)
        else:
            # Fallback for simple response format
            choice_data = Choice(
                index=0,
                message={
                    "role": "assistant",
                    "content": str(xai_response)
                },
                finish_reason="stop"
            )
            choices_data.append(choice_data)
        
        # Extract usage data
        usage_data = xai_response.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0)
        )
        
        return ChatCompletionResponse(
            id=xai_response.get("id", request_id),
            object="chat.completion",
            created=xai_response.get("created", int(time.time())),
            model=self.model_name,
            choices=choices_data,
            usage=usage
        )
    
    async def _make_request_with_retry(
        self, 
        endpoint: str, 
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic.
        
        Args:
            endpoint: API endpoint path
            payload: Request payload
            
        Returns:
            Response data
            
        Raises:
            MelanieThreeError: On API or network errors
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Making request to {endpoint} (attempt {attempt + 1})")
                
                response = await self.client.post(endpoint, json=payload)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    if attempt < self.max_retries:
                        logger.warning(f"Rate limited, waiting {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        raise MelanieThreeRateLimitError(retry_after)
                
                # Handle other HTTP errors
                if response.status_code >= 400:
                    error_data = response.json() if response.content else {}
                    error_message = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                    raise MelanieThreeError(f"API error: {error_message}")
                
                # Success
                return response.json()
                
            except httpx.TimeoutException as e:
                last_exception = MelanieThreeTimeoutError(self.timeout)
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Request timed out, retrying in {delay} seconds")
                    await asyncio.sleep(delay)
                    continue
                    
            except httpx.RequestError as e:
                last_exception = MelanieThreeError(f"Network error: {str(e)}")
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Network error, retrying in {delay} seconds")
                    await asyncio.sleep(delay)
                    continue
                    
            except Exception as e:
                last_exception = MelanieThreeError(f"Unexpected error: {str(e)}")
                break
        
        # All retries exhausted
        raise last_exception or MelanieThreeError("Request failed after all retries")
    
    async def generate(
        self, 
        messages: List[ChatMessage], 
        tools: Optional[List[Tool]] = None,
        **kwargs
    ) -> ChatCompletionResponse:
        """
        Generate chat completion using Grok-4.
        
        Args:
            messages: List of chat messages
            tools: Optional list of available tools
            **kwargs: Additional generation parameters
            
        Returns:
            ChatCompletionResponse: Generated response in OpenAI format
            
        Raises:
            MelanieThreeError: On generation errors
        """
        try:
            # Format request payload
            payload = {
                "model": self.model_name,
                "messages": self._format_messages_for_xai(messages),
                "max_tokens": kwargs.get("max_tokens"),
                "temperature": kwargs.get("temperature", 0.7),
                "top_p": kwargs.get("top_p", 1.0),
                "stream": kwargs.get("stream", False)
            }
            
            # Add tools if provided
            if tools:
                payload["tools"] = self._format_tools_for_xai(tools)
                payload["tool_choice"] = kwargs.get("tool_choice", "auto")
            
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}
            
            # Make request
            response_data = await self._make_request_with_retry(
                "/chat/completions", 
                payload
            )
            
            # Generate unique request ID
            request_id = f"chatcmpl-{int(time.time())}-{hash(str(payload)) % 10000}"
            
            # Convert to OpenAI format
            return self._create_openai_response(response_data, request_id)
            
        except Exception as e:
            logger.error(f"Generation failed: {str(e)}")
            if isinstance(e, MelanieThreeError):
                raise
            else:
                raise MelanieThreeError(f"Generation failed: {str(e)}")
    
    async def validate_request(self, request: ChatCompletionRequest) -> bool:
        """
        Validate if request is compatible with Grok-4.
        
        Args:
            request: Chat completion request
            
        Returns:
            bool: True if request is valid for this model
        """
        try:
            # Check model compatibility
            model_name = getattr(request.model, 'value', request.model)
            if model_name != "Melanie-3":
                return False
            
            # Check message count and content
            if not request.messages or len(request.messages) > 100:
                return False
            
            # Check token limits
            total_chars = sum(len(msg.content) for msg in request.messages)
            if total_chars > 500000:  # Rough character limit
                return False
            
            # Check tool compatibility
            if request.tools and len(request.tools) > 20:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Request validation failed: {str(e)}")
            return False
    
    def get_capabilities(self) -> List[str]:
        """
        Get list of Grok-4 capabilities.
        
        Returns:
            List[str]: List of capability names
        """
        return [
            "chat_completion",
            "tool_calling",
            "function_calling",
            "reasoning",
            "code_generation",
            "analysis",
            "creative_writing",
            "math",
            "science",
            "general_knowledge"
        ]
    
    def get_max_tokens(self) -> int:
        """
        Get maximum token limit for Grok-4.
        
        Returns:
            int: Maximum token limit
        """
        return 131072  # 128k tokens for Grok-4
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get comprehensive model information.
        
        Returns:
            Dict: Model information including capabilities and limits
        """
        info = super().get_model_info()
        info.update({
            "provider": "xAI",
            "version": "grok-4",
            "context_window": self.get_max_tokens(),
            "supports_streaming": True,
            "supports_tools": True,
            "supports_vision": False,  # Grok-4 is text-only
            "pricing_per_1k_tokens": {
                "input": 0.015,  # Example pricing
                "output": 0.075
            }
        })
        return info


# Convenience function for backward compatibility
async def ask_grok_async(
    prompt: str, 
    system_prompt: str = "You are Melanie, a helpful AI assistant.",
    **kwargs
) -> str:
    """
    Async version of ask_grok function for backward compatibility.
    
    Args:
        prompt: User prompt/question
        system_prompt: System prompt to set context
        **kwargs: Additional parameters
        
    Returns:
        str: Response content from Grok-4
    """
    async with MelanieThree() as model:
        # Use the MessageRole enum if available, otherwise use strings
        try:
            from models import MessageRole
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=MessageRole.USER, content=prompt)
            ]
        except ImportError:
            # Fallback to the local MessageRole
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=MessageRole.USER, content=prompt)
            ]
        
        response = await model.generate(messages, **kwargs)
        return response.choices[0].message["content"]


# Example usage and testing
if __name__ == "__main__":
    async def test_basic_generation():
        """Test basic generation functionality."""
        try:
            async with MelanieThree() as model:
                messages = [
                    ChatMessage(role=MessageRole.SYSTEM, content="You are Melanie, a PhD-level mathematician."),
                    ChatMessage(role=MessageRole.USER, content="What is 2 + 2?")
                ]
                
                response = await model.generate(messages)
                print(f"Response: {response.choices[0].message['content']}")
                print(f"Usage: {response.usage}")
                
        except Exception as e:
            print(f"Test failed: {str(e)}")
    
    # Run test
    asyncio.run(test_basic_generation())