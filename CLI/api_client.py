"""
API Client for Melanie CLI.

Handles communication with the Melanie API server including
authentication, request formatting, and error handling.
"""

import asyncio
import aiohttp
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json


@dataclass
class APIResponse:
    """Response from the Melanie API."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    status_code: Optional[int] = None


class APIClient:
    """
    Client for communicating with the Melanie API server.
    
    Provides async methods for all API endpoints with proper
    authentication, error handling, and response parsing.
    """
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Initialize API client.
        
        Args:
            base_url: Base URL of the Melanie API server
            api_key: API key for authentication (loaded from config if None)
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Load API key from environment if not provided
        if not self.api_key:
            import os
            self.api_key = os.getenv('MELANIE_API_KEY')
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def _ensure_session(self):
        """Ensure aiohttp session is created."""
        if not self.session:
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes
            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=timeout
            )
    
    async def close(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> APIResponse:
        """
        Make an HTTP request to the API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters
            
        Returns:
            APIResponse object
        """
        await self._ensure_session()
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.request(
                method=method,
                url=url,
                json=data,
                params=params
            ) as response:
                
                # Parse response
                try:
                    response_data = await response.json()
                except aiohttp.ContentTypeError:
                    response_data = {"message": await response.text()}
                
                if response.status >= 200 and response.status < 300:
                    return APIResponse(
                        success=True,
                        data=response_data,
                        status_code=response.status
                    )
                else:
                    error_msg = response_data.get('message', f'HTTP {response.status}')
                    return APIResponse(
                        success=False,
                        error=error_msg,
                        status_code=response.status
                    )
        
        except aiohttp.ClientError as e:
            return APIResponse(
                success=False,
                error=f"Connection error: {str(e)}"
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
    
    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        web_search: bool = False,
        **kwargs
    ) -> APIResponse:
        """
        Send a chat completion request.
        
        Args:
            model: Model name (Melanie-3, Melanie-3-light, Melanie-3-code)
            messages: List of chat messages
            tools: Optional list of tools to use
            web_search: Enable web search capabilities
            **kwargs: Additional parameters
            
        Returns:
            APIResponse with chat completion data
        """
        data = {
            "model": model,
            "messages": messages,
            "web_search": web_search,
            **kwargs
        }
        
        if tools:
            data["tools"] = tools
        
        return await self._make_request("POST", "/chat/completions", data)
    
    async def generate_plan(
        self,
        request: str,
        project_dir: str,
        suggested_agents: Optional[int] = None,
        force_parallel: Optional[bool] = None
    ) -> APIResponse:
        """
        Generate an execution plan for a coding request.
        
        Args:
            request: Coding task description
            project_dir: Project directory path
            suggested_agents: Suggested number of agents
            force_parallel: Force parallel execution
            
        Returns:
            APIResponse with execution plan
        """
        # Use Melanie-3-light for plan generation
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a coding task planner. Analyze the user's request and generate "
                    "a detailed execution plan with tasks, dependencies, and agent assignments. "
                    "Consider the project structure and complexity to determine optimal execution strategy."
                )
            },
            {
                "role": "user", 
                "content": f"Project directory: {project_dir}\n\nCoding request: {request}"
            }
        ]
        
        # Add planning constraints
        if suggested_agents:
            messages[0]["content"] += f"\n\nUse exactly {suggested_agents} agents."
        if force_parallel is not None:
            execution_type = "parallel" if force_parallel else "sequential"
            messages[0]["content"] += f"\n\nUse {execution_type} execution."
        
        return await self.chat_completion(
            model="Melanie-3-light",
            messages=messages
        )
    
    async def execute_agent_task(
        self,
        task_description: str,
        agent_id: str,
        project_context: Dict[str, Any],
        dependencies: Optional[List[Dict[str, Any]]] = None
    ) -> APIResponse:
        """
        Execute a single agent task.
        
        Args:
            task_description: Description of the task to execute
            agent_id: Unique identifier for the agent
            project_context: Project context and file information
            dependencies: List of dependency task results
            
        Returns:
            APIResponse with agent execution results
        """
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are Agent {agent_id}, a specialized coding assistant. "
                    "Execute the given task with high quality code generation, "
                    "comprehensive testing, and proper documentation. "
                    "Focus on iterative development and debugging."
                )
            },
            {
                "role": "user",
                "content": f"Task: {task_description}\n\nProject context: {json.dumps(project_context, indent=2)}"
            }
        ]
        
        if dependencies:
            messages[1]["content"] += f"\n\nDependency results: {json.dumps(dependencies, indent=2)}"
        
        # Use Melanie-3-code for actual coding tasks
        return await self.chat_completion(
            model="Melanie-3-code",
            messages=messages,
            tools=[
                {"type": "function", "function": {"name": "coder"}},
                {"type": "function", "function": {"name": "multimodal"}}
            ]
        )
    
    async def upload_file(self, file_path: str, content: bytes) -> APIResponse:
        """
        Upload a file to the API server.
        
        Args:
            file_path: Path/name of the file
            content: File content as bytes
            
        Returns:
            APIResponse with file upload result
        """
        # This would be implemented when the files API is available
        # For now, return a placeholder response
        return APIResponse(
            success=True,
            data={"file_id": "placeholder", "filename": file_path}
        )
    
    async def health_check(self) -> APIResponse:
        """
        Check API server health.
        
        Returns:
            APIResponse with health status
        """
        return await self._make_request("GET", "/health")
    
    async def get_models(self) -> APIResponse:
        """
        Get available models.
        
        Returns:
            APIResponse with available models list
        """
        return await self._make_request("GET", "/models")