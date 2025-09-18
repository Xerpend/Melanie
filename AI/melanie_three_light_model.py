"""
Melanie-3-light (Grok 3 mini) model wrapper implementing BaseAIModel interface.

This module provides:
- MelanieThreeLight class implementing BaseAIModel interface with lightweight operations focus
- Agent coordination capabilities for multi-agent workflows
- Concurrent request handling with semaphore-based concurrency control
- Error handling and fallback mechanisms
- Comprehensive logging and monitoring
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import threading

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
        APIError,
        MessageRole
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


@dataclass
class AgentTask:
    """Represents a task for agent coordination."""
    id: str
    messages: List[ChatMessage]
    tools: Optional[List[Tool]] = None
    priority: int = 0
    timeout: float = 300.0  # 5 minutes default
    retry_count: int = 0
    max_retries: int = 2
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class AgentResult:
    """Result from agent task execution."""
    task_id: str
    success: bool
    response: Optional[ChatCompletionResponse] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    retry_count: int = 0


class MelanieThreeLightError(Exception):
    """Custom exception for MelanieThreeLight model errors."""
    pass


class MelanieThreeLightTimeoutError(MelanieThreeLightError):
    """Timeout error for MelanieThreeLight model."""
    def __init__(self, timeout: float):
        self.timeout = timeout
        super().__init__(f"Request timed out after {timeout} seconds")


class MelanieThreeLightRateLimitError(MelanieThreeLightError):
    """Rate limit error for MelanieThreeLight model."""
    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        message = "Rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after} seconds"
        super().__init__(message)


class AgentCoordinator:
    """
    Coordinates multiple agent tasks with concurrency control and load balancing.
    """
    
    def __init__(self, max_concurrent_agents: int = 5, max_queue_size: int = 100):
        """
        Initialize agent coordinator.
        
        Args:
            max_concurrent_agents: Maximum number of concurrent agent tasks
            max_queue_size: Maximum size of task queue
        """
        self.max_concurrent_agents = max_concurrent_agents
        self.max_queue_size = max_queue_size
        self.semaphore = asyncio.Semaphore(max_concurrent_agents)
        self.task_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.completed_tasks: Dict[str, AgentResult] = {}
        self.task_counter = 0
        self._lock = asyncio.Lock()
        self._shutdown = False
    
    async def submit_task(self, task: AgentTask) -> str:
        """
        Submit a task for agent execution.
        
        Args:
            task: AgentTask to execute
            
        Returns:
            str: Task ID for tracking
            
        Raises:
            MelanieThreeLightError: If queue is full or coordinator is shutdown
        """
        if self._shutdown:
            raise MelanieThreeLightError("Agent coordinator is shutdown")
        
        try:
            await self.task_queue.put(task)
            logger.info(f"Task {task.id} submitted to queue")
            return task.id
        except asyncio.QueueFull:
            raise MelanieThreeLightError("Agent task queue is full")
    
    async def get_result(self, task_id: str, timeout: Optional[float] = None) -> AgentResult:
        """
        Get result for a specific task.
        
        Args:
            task_id: ID of the task
            timeout: Optional timeout for waiting
            
        Returns:
            AgentResult: Result of the task execution
            
        Raises:
            MelanieThreeLightError: If task not found or timeout
        """
        start_time = time.time()
        
        while True:
            async with self._lock:
                if task_id in self.completed_tasks:
                    return self.completed_tasks[task_id]
            
            if timeout and (time.time() - start_time) > timeout:
                raise MelanieThreeLightError(f"Timeout waiting for task {task_id}")
            
            await asyncio.sleep(0.1)  # Small delay to prevent busy waiting
    
    async def get_all_results(self, task_ids: List[str], timeout: Optional[float] = None) -> List[AgentResult]:
        """
        Get results for multiple tasks.
        
        Args:
            task_ids: List of task IDs
            timeout: Optional timeout for waiting
            
        Returns:
            List[AgentResult]: Results for all tasks
        """
        results = []
        for task_id in task_ids:
            result = await self.get_result(task_id, timeout)
            results.append(result)
        return results
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running task.
        
        Args:
            task_id: ID of the task to cancel
            
        Returns:
            bool: True if task was cancelled
        """
        async with self._lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                task.cancel()
                del self.active_tasks[task_id]
                
                # Add cancelled result
                self.completed_tasks[task_id] = AgentResult(
                    task_id=task_id,
                    success=False,
                    error="Task cancelled",
                    execution_time=0.0
                )
                return True
        return False
    
    async def shutdown(self, timeout: float = 30.0):
        """
        Shutdown the coordinator and wait for active tasks.
        
        Args:
            timeout: Maximum time to wait for tasks to complete
        """
        self._shutdown = True
        
        # Cancel all active tasks
        async with self._lock:
            for task_id, task in self.active_tasks.items():
                task.cancel()
        
        # Wait for tasks to complete or timeout
        start_time = time.time()
        while self.active_tasks and (time.time() - start_time) < timeout:
            await asyncio.sleep(0.1)
        
        logger.info("Agent coordinator shutdown complete")


class MelanieThreeLight(BaseAIModel):
    """
    Melanie-3-light (Grok 3 mini) model wrapper implementing BaseAIModel interface.
    
    Focuses on lightweight operations and agent coordination capabilities for
    multi-agent workflows with concurrent request handling.
    """
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize MelanieThreeLight model.
        
        Args:
            api_key: xAI API key (defaults to XAI_API_KEY env var)
            **kwargs: Additional configuration options
        """
        api_key = api_key or os.getenv("XAI_API_KEY")
        if not api_key:
            raise ValueError("XAI_API_KEY environment variable or api_key parameter is required")
        
        super().__init__(
            model_name="grok-3-mini",
            api_key=api_key,
            **kwargs
        )
        
        # Configuration
        self.base_url = kwargs.get("base_url", "https://api.x.ai/v1")
        self.timeout = kwargs.get("timeout", 300)  # 5 minutes for lightweight operations
        self.max_retries = kwargs.get("max_retries", 3)
        self.retry_delay = kwargs.get("retry_delay", 1.0)
        
        # Agent coordination settings
        self.max_concurrent_requests = kwargs.get("max_concurrent_requests", 10)
        self.agent_coordinator = AgentCoordinator(
            max_concurrent_agents=kwargs.get("max_concurrent_agents", 5),
            max_queue_size=kwargs.get("max_queue_size", 100)
        )
        
        # Concurrency control
        self.request_semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        self.active_requests: Set[str] = set()
        self._request_lock = asyncio.Lock()
        
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
        await self.agent_coordinator.shutdown()
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
        payload: Dict[str, Any],
        request_id: str
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic and concurrency control.
        
        Args:
            endpoint: API endpoint path
            payload: Request payload
            request_id: Unique request identifier
            
        Returns:
            Response data
            
        Raises:
            MelanieThreeLightError: On API or network errors
        """
        async with self.request_semaphore:
            async with self._request_lock:
                self.active_requests.add(request_id)
            
            try:
                last_exception = None
                
                for attempt in range(self.max_retries + 1):
                    try:
                        logger.info(f"Making request {request_id} to {endpoint} (attempt {attempt + 1})")
                        
                        response = await self.client.post(endpoint, json=payload)
                        
                        # Handle rate limiting
                        if response.status_code == 429:
                            retry_after = int(response.headers.get("Retry-After", 30))
                            if attempt < self.max_retries:
                                logger.warning(f"Rate limited for request {request_id}, waiting {retry_after} seconds")
                                await asyncio.sleep(retry_after)
                                continue
                            else:
                                raise MelanieThreeLightRateLimitError(retry_after)
                        
                        # Handle other HTTP errors
                        if response.status_code >= 400:
                            error_data = response.json() if response.content else {}
                            error_message = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                            raise MelanieThreeLightError(f"API error: {error_message}")
                        
                        # Success
                        return response.json()
                        
                    except httpx.TimeoutException as e:
                        last_exception = MelanieThreeLightTimeoutError(self.timeout)
                        if attempt < self.max_retries:
                            delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                            logger.warning(f"Request {request_id} timed out, retrying in {delay} seconds")
                            await asyncio.sleep(delay)
                            continue
                            
                    except httpx.RequestError as e:
                        last_exception = MelanieThreeLightError(f"Network error: {str(e)}")
                        if attempt < self.max_retries:
                            delay = self.retry_delay * (2 ** attempt)
                            logger.warning(f"Network error for request {request_id}, retrying in {delay} seconds")
                            await asyncio.sleep(delay)
                            continue
                            
                    except Exception as e:
                        last_exception = MelanieThreeLightError(f"Unexpected error: {str(e)}")
                        break
                
                # All retries exhausted
                raise last_exception or MelanieThreeLightError("Request failed after all retries")
                
            finally:
                async with self._request_lock:
                    self.active_requests.discard(request_id)
    
    async def generate(
        self, 
        messages: List[ChatMessage], 
        tools: Optional[List[Tool]] = None,
        **kwargs
    ) -> ChatCompletionResponse:
        """
        Generate chat completion using Grok-3-mini with lightweight operations focus.
        
        Args:
            messages: List of chat messages
            tools: Optional list of available tools
            **kwargs: Additional generation parameters
            
        Returns:
            ChatCompletionResponse: Generated response in OpenAI format
            
        Raises:
            MelanieThreeLightError: On generation errors
        """
        try:
            # Generate unique request ID
            request_id = f"chatcmpl-light-{int(time.time())}-{hash(str(messages)) % 10000}"
            
            # Format request payload
            payload = {
                "model": self.model_name,
                "messages": self._format_messages_for_xai(messages),
                "max_tokens": kwargs.get("max_tokens", 4000),  # Smaller default for lightweight ops
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
                payload,
                request_id
            )
            
            # Convert to OpenAI format
            return self._create_openai_response(response_data, request_id)
            
        except Exception as e:
            logger.error(f"Generation failed: {str(e)}")
            if isinstance(e, MelanieThreeLightError):
                raise
            else:
                raise MelanieThreeLightError(f"Generation failed: {str(e)}")
    
    async def generate_agent_task(self, task: AgentTask) -> AgentResult:
        """
        Execute a single agent task.
        
        Args:
            task: AgentTask to execute
            
        Returns:
            AgentResult: Result of task execution
        """
        start_time = time.time()
        
        try:
            # Execute the task with timeout
            response = await asyncio.wait_for(
                self.generate(task.messages, task.tools),
                timeout=task.timeout
            )
            
            execution_time = time.time() - start_time
            
            return AgentResult(
                task_id=task.id,
                success=True,
                response=response,
                execution_time=execution_time,
                retry_count=task.retry_count
            )
            
        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            error_msg = f"Task {task.id} timed out after {task.timeout} seconds"
            logger.error(error_msg)
            
            return AgentResult(
                task_id=task.id,
                success=False,
                error=error_msg,
                execution_time=execution_time,
                retry_count=task.retry_count
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Task {task.id} failed: {str(e)}"
            logger.error(error_msg)
            
            return AgentResult(
                task_id=task.id,
                success=False,
                error=error_msg,
                execution_time=execution_time,
                retry_count=task.retry_count
            )
    
    async def coordinate_agents(self, tasks: List[AgentTask]) -> List[AgentResult]:
        """
        Coordinate multiple agent tasks with concurrent execution.
        
        Args:
            tasks: List of AgentTask objects to execute
            
        Returns:
            List[AgentResult]: Results from all tasks
        """
        if not tasks:
            return []
        
        # Submit all tasks to coordinator
        task_ids = []
        for task in tasks:
            task_id = await self.agent_coordinator.submit_task(task)
            task_ids.append(task_id)
        
        # Process tasks concurrently
        async def process_task_queue():
            while not self.agent_coordinator._shutdown:
                task = None
                try:
                    task = await asyncio.wait_for(
                        self.agent_coordinator.task_queue.get(), 
                        timeout=1.0
                    )
                    
                    # Execute task
                    result = await self.generate_agent_task(task)
                    
                    # Store result
                    async with self.agent_coordinator._lock:
                        self.agent_coordinator.completed_tasks[task.id] = result
                    
                    # Mark task as done
                    self.agent_coordinator.task_queue.task_done()
                    
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error processing task queue: {str(e)}")
                    
                    # If we have a task, create a failed result for it
                    if task is not None:
                        failed_result = AgentResult(
                            task_id=task.id,
                            success=False,
                            error=f"Task processing failed: {str(e)}",
                            execution_time=0.0,
                            retry_count=0
                        )
                        
                        # Store the failed result
                        async with self.agent_coordinator._lock:
                            self.agent_coordinator.completed_tasks[task.id] = failed_result
                        
                        # Mark task as done
                        self.agent_coordinator.task_queue.task_done()
        
        # Start task processing
        processor_task = asyncio.create_task(process_task_queue())
        
        try:
            # Wait for all results
            results = await self.agent_coordinator.get_all_results(
                task_ids, 
                timeout=max(task.timeout for task in tasks) + 30
            )
            return results
            
        finally:
            processor_task.cancel()
            try:
                await processor_task
            except asyncio.CancelledError:
                pass
    
    async def validate_request(self, request: ChatCompletionRequest) -> bool:
        """
        Validate if request is compatible with Grok-3-mini.
        
        Args:
            request: Chat completion request
            
        Returns:
            bool: True if request is valid for this model
        """
        try:
            # Check model compatibility
            model_name = getattr(request.model, 'value', request.model)
            if model_name != "Melanie-3-light":
                return False
            
            # Check message count and content (lighter limits for mini model)
            if not request.messages or len(request.messages) > 50:
                return False
            
            # Check token limits (smaller for lightweight operations)
            total_chars = sum(len(msg.content) for msg in request.messages)
            if total_chars > 100000:  # Smaller character limit
                return False
            
            # Check tool compatibility
            if request.tools and len(request.tools) > 10:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Request validation failed: {str(e)}")
            return False
    
    def get_capabilities(self) -> List[str]:
        """
        Get list of Grok-3-mini capabilities focused on lightweight operations.
        
        Returns:
            List[str]: List of capability names
        """
        return [
            "chat_completion",
            "tool_calling",
            "function_calling",
            "agent_coordination",
            "concurrent_processing",
            "lightweight_operations",
            "quick_responses",
            "multi_agent_workflows",
            "task_orchestration",
            "basic_reasoning",
            "code_assistance",
            "general_knowledge"
        ]
    
    def get_max_tokens(self) -> int:
        """
        Get maximum token limit for Grok-3-mini.
        
        Returns:
            int: Maximum token limit
        """
        return 32768  # 32k tokens for Grok-3-mini (smaller than Grok-4)
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get comprehensive model information.
        
        Returns:
            Dict: Model information including capabilities and limits
        """
        info = super().get_model_info()
        info.update({
            "provider": "xAI",
            "version": "grok-3-mini",
            "context_window": self.get_max_tokens(),
            "supports_streaming": True,
            "supports_tools": True,
            "supports_vision": False,  # Grok-3-mini is text-only
            "supports_agent_coordination": True,
            "max_concurrent_requests": self.max_concurrent_requests,
            "max_concurrent_agents": self.agent_coordinator.max_concurrent_agents,
            "pricing_per_1k_tokens": {
                "input": 0.005,  # Example pricing (lower than Grok-4)
                "output": 0.025
            },
            "optimized_for": [
                "lightweight_operations",
                "agent_coordination",
                "concurrent_processing",
                "quick_responses"
            ]
        })
        return info
    
    async def get_active_request_count(self) -> int:
        """Get number of currently active requests."""
        async with self._request_lock:
            return len(self.active_requests)
    
    async def get_agent_coordinator_status(self) -> Dict[str, Any]:
        """Get status of the agent coordinator."""
        async with self.agent_coordinator._lock:
            return {
                "active_tasks": len(self.agent_coordinator.active_tasks),
                "completed_tasks": len(self.agent_coordinator.completed_tasks),
                "queue_size": self.agent_coordinator.task_queue.qsize(),
                "max_concurrent_agents": self.agent_coordinator.max_concurrent_agents,
                "shutdown": self.agent_coordinator._shutdown
            }


# Convenience function for backward compatibility
async def ask_grok_light_async(
    prompt: str, 
    system_prompt: str = "You are Melanie, a helpful AI assistant focused on efficient, lightweight responses.",
    **kwargs
) -> str:
    """
    Async version of ask_grok_light function for backward compatibility.
    
    Args:
        prompt: User prompt/question
        system_prompt: System prompt to set context
        **kwargs: Additional parameters
        
    Returns:
        str: Response content from Grok-3-mini
    """
    async with MelanieThreeLight() as model:
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
            async with MelanieThreeLight() as model:
                messages = [
                    ChatMessage(role=MessageRole.SYSTEM, content="You are Melanie, a helpful AI assistant."),
                    ChatMessage(role=MessageRole.USER, content="What is 2 + 2? Keep it brief.")
                ]
                
                response = await model.generate(messages)
                print(f"Response: {response.choices[0].message['content']}")
                print(f"Usage: {response.usage}")
                
        except Exception as e:
            print(f"Test failed: {str(e)}")
    
    async def test_agent_coordination():
        """Test agent coordination functionality."""
        try:
            async with MelanieThreeLight() as model:
                # Create multiple tasks
                tasks = []
                for i in range(3):
                    task = AgentTask(
                        id=f"task_{i}",
                        messages=[
                            ChatMessage(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
                            ChatMessage(role=MessageRole.USER, content=f"Count to {i+1}")
                        ],
                        timeout=30.0
                    )
                    tasks.append(task)
                
                # Execute tasks concurrently
                results = await model.coordinate_agents(tasks)
                
                print(f"Executed {len(results)} tasks:")
                for result in results:
                    if result.success:
                        content = result.response.choices[0].message["content"]
                        print(f"Task {result.task_id}: {content[:50]}...")
                    else:
                        print(f"Task {result.task_id} failed: {result.error}")
                
        except Exception as e:
            print(f"Agent coordination test failed: {str(e)}")
    
    # Run tests
    asyncio.run(test_basic_generation())
    asyncio.run(test_agent_coordination())