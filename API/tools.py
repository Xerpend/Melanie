"""
Core tool system for Melanie AI ecosystem.

This module provides:
- ToolManager class with tool registry and orchestration
- Individual tool classes (coder, multimodal, search)
- Concurrency limits and semaphore management
- Tool access matrix based on model capabilities
- Query diversity validation using cosine similarity
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Import model classes
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'AI'))

try:
    from melanie_three_model import MelanieThree
    from melanie_three_light_model import MelanieThreeLight
    from melanie_three_code_model import MelanieThreeCode
    from melanie_multimodal_model import MelanieMultimodal
except ImportError as e:
    logging.warning(f"Could not import AI models: {e}")
    # Create placeholder classes for testing
    class MelanieThree:
        pass
    class MelanieThreeLight:
        pass
    class MelanieThreeCode:
        pass
    class MelanieMultimodal:
        pass

try:
    from models import ChatMessage, ChatCompletionResponse, Tool, MessageRole
except ImportError:
    # Fallback for testing
    from pydantic import BaseModel
    from enum import Enum
    from typing import List, Optional, Dict, Any
    
    class MessageRole(str, Enum):
        USER = "user"
        ASSISTANT = "assistant"
        SYSTEM = "system"
    
    class ChatMessage(BaseModel):
        role: MessageRole
        content: str
        name: Optional[str] = None
    
    class ChatCompletionResponse(BaseModel):
        id: str
        object: str = "chat.completion"
        created: int
        model: str
        choices: List[Dict]
        usage: Dict[str, int]
    
    class ToolFunction(BaseModel):
        name: str
        description: Optional[str] = None
        parameters: Optional[Dict[str, Any]] = None
    
    class Tool(BaseModel):
        function: ToolFunction

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ToolType(str, Enum):
    """Available tool types in the system."""
    CODER = "coder"
    MULTIMODAL = "multimodal"
    LIGHT_SEARCH = "light-search"
    MEDIUM_SEARCH = "medium-search"
    AGENT = "agent"


@dataclass
class ToolCall:
    """Represents a tool call request."""
    id: str
    tool_type: ToolType
    function_name: str
    arguments: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ToolResult:
    """Result from tool execution."""
    call_id: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Optional[Dict[str, Any]] = None


class ToolError(Exception):
    """Base exception for tool-related errors."""
    pass


class ToolTimeoutError(ToolError):
    """Tool execution timeout error."""
    pass


class ToolConcurrencyError(ToolError):
    """Tool concurrency limit exceeded error."""
    pass


class BaseTool(ABC):
    """
    Abstract base class for all tools in the system.
    """
    
    def __init__(self, name: str, **kwargs):
        """
        Initialize base tool.
        
        Args:
            name: Tool name
            **kwargs: Additional configuration
        """
        self.name = name
        self.config = kwargs
        self.timeout = kwargs.get("timeout", 300.0)  # 5 minutes default
        self.max_concurrent = kwargs.get("max_concurrent", 1)
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        self.active_calls: Set[str] = set()
        self._lock = asyncio.Lock()
    
    @abstractmethod
    async def execute(self, call: ToolCall) -> ToolResult:
        """
        Execute the tool with given parameters.
        
        Args:
            call: ToolCall with execution parameters
            
        Returns:
            ToolResult: Execution result
        """
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """
        Get tool schema for function calling.
        
        Returns:
            Dict: Tool schema in OpenAI function format
        """
        pass
    
    async def execute_with_concurrency_control(self, call: ToolCall) -> ToolResult:
        """
        Execute tool with concurrency control and timeout.
        
        Args:
            call: ToolCall to execute
            
        Returns:
            ToolResult: Execution result
        """
        async with self.semaphore:
            async with self._lock:
                self.active_calls.add(call.id)
            
            try:
                start_time = time.time()
                
                # Execute with timeout
                result = await asyncio.wait_for(
                    self.execute(call),
                    timeout=self.timeout
                )
                
                execution_time = time.time() - start_time
                result.execution_time = execution_time
                
                return result
                
            except asyncio.TimeoutError:
                execution_time = time.time() - start_time
                return ToolResult(
                    call_id=call.id,
                    success=False,
                    error=f"Tool execution timed out after {self.timeout} seconds",
                    execution_time=execution_time
                )
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"Tool {self.name} execution failed: {str(e)}")
                return ToolResult(
                    call_id=call.id,
                    success=False,
                    error=str(e),
                    execution_time=execution_time
                )
            finally:
                async with self._lock:
                    self.active_calls.discard(call.id)
    
    async def get_active_call_count(self) -> int:
        """Get number of currently active calls."""
        async with self._lock:
            return len(self.active_calls)


class CoderTool(BaseTool):
    """
    Tool for code generation and analysis using Melanie-3-code.
    """
    
    def __init__(self, **kwargs):
        """Initialize coder tool."""
        super().__init__("coder", **kwargs)
        self.model = None  # Will be initialized when needed
    
    async def _get_model(self):
        """Get or initialize the coding model."""
        if self.model is None:
            try:
                self.model = MelanieThreeCode()
            except Exception as e:
                logger.error(f"Failed to initialize MelanieThreeCode: {e}")
                raise ToolError(f"Coder tool initialization failed: {e}")
        return self.model
    
    async def execute(self, call: ToolCall) -> ToolResult:
        """
        Execute code generation or analysis.
        
        Args:
            call: ToolCall with coding parameters
            
        Returns:
            ToolResult: Code generation result
        """
        try:
            model = await self._get_model()
            
            # Extract parameters
            prompt = call.arguments.get("prompt", "")
            task_type = call.arguments.get("task_type", "generate")
            language = call.arguments.get("language", "python")
            include_tests = call.arguments.get("include_tests", True)
            
            # Create coding prompt
            if task_type == "generate":
                system_prompt = f"Generate {language} code with comprehensive comments and documentation."
                if include_tests:
                    system_prompt += " Include unit tests for the generated code."
            elif task_type == "review":
                system_prompt = f"Review and analyze the provided {language} code for quality, bugs, and improvements."
            elif task_type == "debug":
                system_prompt = f"Debug and fix issues in the provided {language} code."
            else:
                system_prompt = f"Assist with {language} coding task."
            
            # Create messages
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=MessageRole.USER, content=prompt)
            ]
            
            # Generate response
            response = await model.generate(messages)
            
            # Extract result
            result_content = response.choices[0].message["content"]
            
            return ToolResult(
                call_id=call.id,
                success=True,
                result={
                    "content": result_content,
                    "task_type": task_type,
                    "language": language,
                    "model_used": model.model_name
                },
                metadata={
                    "usage": response.usage.dict() if hasattr(response.usage, 'dict') else response.usage,
                    "finish_reason": response.choices[0].finish_reason
                }
            )
            
        except Exception as e:
            logger.error(f"Coder tool execution failed: {str(e)}")
            return ToolResult(
                call_id=call.id,
                success=False,
                error=str(e)
            )
    
    def get_schema(self) -> Dict[str, Any]:
        """Get coder tool schema."""
        return {
            "type": "function",
            "function": {
                "name": "coder",
                "description": "Generate, review, or debug code using AI assistance",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "The coding task or question"
                        },
                        "task_type": {
                            "type": "string",
                            "enum": ["generate", "review", "debug", "explain"],
                            "description": "Type of coding task to perform"
                        },
                        "language": {
                            "type": "string",
                            "description": "Programming language (default: python)"
                        },
                        "include_tests": {
                            "type": "boolean",
                            "description": "Whether to include unit tests (default: true)"
                        }
                    },
                    "required": ["prompt"]
                }
            }
        }


class MultimodalTool(BaseTool):
    """
    Tool for image and document processing using multimodal AI.
    """
    
    def __init__(self, **kwargs):
        """Initialize multimodal tool."""
        super().__init__("multimodal", **kwargs)
        self.model = None  # Will be initialized when needed
    
    async def _get_model(self):
        """Get or initialize the multimodal model."""
        if self.model is None:
            try:
                self.model = MelanieMultimodal()
            except Exception as e:
                logger.error(f"Failed to initialize MelanieMultimodal: {e}")
                raise ToolError(f"Multimodal tool initialization failed: {e}")
        return self.model
    
    async def execute(self, call: ToolCall) -> ToolResult:
        """
        Execute multimodal processing.
        
        Args:
            call: ToolCall with multimodal parameters
            
        Returns:
            ToolResult: Processing result
        """
        try:
            model = await self._get_model()
            
            # Extract parameters
            prompt = call.arguments.get("prompt", "Analyze this content")
            content_type = call.arguments.get("content_type", "image")
            file_path = call.arguments.get("file_path")
            
            if not file_path:
                return ToolResult(
                    call_id=call.id,
                    success=False,
                    error="file_path parameter is required"
                )
            
            # Process based on content type
            if content_type == "image":
                result = await model.analyze_image(file_path, prompt)
                return ToolResult(
                    call_id=call.id,
                    success=True,
                    result={
                        "description": result.description,
                        "objects_detected": result.objects_detected,
                        "text_extracted": result.text_extracted,
                        "metadata": result.metadata,
                        "confidence_score": result.confidence_score
                    }
                )
            elif content_type == "document":
                result = await model.extract_document_content(file_path, prompt)
                return ToolResult(
                    call_id=call.id,
                    success=True,
                    result={
                        "text_content": result.text_content,
                        "page_count": result.page_count,
                        "images_extracted": result.images_extracted,
                        "metadata": result.metadata,
                        "structure_analysis": result.structure_analysis
                    }
                )
            else:
                return ToolResult(
                    call_id=call.id,
                    success=False,
                    error=f"Unsupported content type: {content_type}"
                )
                
        except Exception as e:
            logger.error(f"Multimodal tool execution failed: {str(e)}")
            return ToolResult(
                call_id=call.id,
                success=False,
                error=str(e)
            )
    
    def get_schema(self) -> Dict[str, Any]:
        """Get multimodal tool schema."""
        return {
            "type": "function",
            "function": {
                "name": "multimodal",
                "description": "Analyze images or extract content from documents",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Analysis prompt or question about the content"
                        },
                        "content_type": {
                            "type": "string",
                            "enum": ["image", "document"],
                            "description": "Type of content to process"
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file to process"
                        }
                    },
                    "required": ["file_path"]
                }
            }
        }


class LightSearchTool(BaseTool):
    """
    Tool for quick web searches using Perplexity sonar model.
    """
    
    def __init__(self, **kwargs):
        """Initialize light search tool."""
        super().__init__("light-search", max_concurrent=2, **kwargs)
        self.api_key = os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            logger.warning("PERPLEXITY_API_KEY not found, light search will not work")
    
    async def execute(self, call: ToolCall) -> ToolResult:
        """
        Execute light web search.
        
        Args:
            call: ToolCall with search parameters
            
        Returns:
            ToolResult: Search result
        """
        try:
            if not self.api_key:
                return ToolResult(
                    call_id=call.id,
                    success=False,
                    error="PERPLEXITY_API_KEY not configured"
                )
            
            # Import here to avoid circular imports
            import httpx
            
            query = call.arguments.get("query", "")
            if not query:
                return ToolResult(
                    call_id=call.id,
                    success=False,
                    error="query parameter is required"
                )
            
            # Make search request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    json={
                        "model": "sonar",
                        "messages": [
                            {"role": "user", "content": query}
                        ]
                    },
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    return ToolResult(
                        call_id=call.id,
                        success=False,
                        error=f"Search API error: {response.status_code}"
                    )
                
                result_data = response.json()
                
                return ToolResult(
                    call_id=call.id,
                    success=True,
                    result={
                        "query": query,
                        "answer": result_data["choices"][0]["message"]["content"],
                        "model": "sonar",
                        "search_type": "light"
                    },
                    metadata={
                        "usage": result_data.get("usage", {}),
                        "citations": result_data.get("citations", [])
                    }
                )
                
        except Exception as e:
            logger.error(f"Light search tool execution failed: {str(e)}")
            return ToolResult(
                call_id=call.id,
                success=False,
                error=str(e)
            )
    
    def get_schema(self) -> Dict[str, Any]:
        """Get light search tool schema."""
        return {
            "type": "function",
            "function": {
                "name": "light-search",
                "description": "Perform quick web search for current information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query or question"
                        }
                    },
                    "required": ["query"]
                }
            }
        }


class MediumSearchTool(BaseTool):
    """
    Tool for detailed web searches using Perplexity sonar-reasoning model.
    """
    
    def __init__(self, **kwargs):
        """Initialize medium search tool."""
        super().__init__("medium-search", max_concurrent=2, **kwargs)
        self.api_key = os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            logger.warning("PERPLEXITY_API_KEY not found, medium search will not work")
    
    async def execute(self, call: ToolCall) -> ToolResult:
        """
        Execute detailed web search.
        
        Args:
            call: ToolCall with search parameters
            
        Returns:
            ToolResult: Search result
        """
        try:
            if not self.api_key:
                return ToolResult(
                    call_id=call.id,
                    success=False,
                    error="PERPLEXITY_API_KEY not configured"
                )
            
            # Import here to avoid circular imports
            import httpx
            
            query = call.arguments.get("query", "")
            if not query:
                return ToolResult(
                    call_id=call.id,
                    success=False,
                    error="query parameter is required"
                )
            
            # Make search request with longer timeout for reasoning model
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    json={
                        "model": "sonar-reasoning",
                        "messages": [
                            {"role": "user", "content": query}
                        ]
                    },
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    timeout=120.0  # Longer timeout for reasoning
                )
                
                if response.status_code != 200:
                    return ToolResult(
                        call_id=call.id,
                        success=False,
                        error=f"Search API error: {response.status_code}"
                    )
                
                result_data = response.json()
                
                return ToolResult(
                    call_id=call.id,
                    success=True,
                    result={
                        "query": query,
                        "answer": result_data["choices"][0]["message"]["content"],
                        "model": "sonar-reasoning",
                        "search_type": "medium"
                    },
                    metadata={
                        "usage": result_data.get("usage", {}),
                        "citations": result_data.get("citations", [])
                    }
                )
                
        except Exception as e:
            logger.error(f"Medium search tool execution failed: {str(e)}")
            return ToolResult(
                call_id=call.id,
                success=False,
                error=str(e)
            )
    
    def get_schema(self) -> Dict[str, Any]:
        """Get medium search tool schema."""
        return {
            "type": "function",
            "function": {
                "name": "medium-search",
                "description": "Perform detailed web search with reasoning and analysis",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query or question requiring detailed analysis"
                        }
                    },
                    "required": ["query"]
                }
            }
        }


class QueryDiversityValidator:
    """
    Validates query diversity using cosine similarity to prevent redundant tool calls.
    Implements requirement 3.5: diversity enforcement with 0.8 threshold.
    """
    
    def __init__(self, similarity_threshold: float = 0.8):
        """
        Initialize diversity validator.
        
        Args:
            similarity_threshold: Cosine similarity threshold (per requirement 3.5: 0.8 threshold)
        """
        self.similarity_threshold = similarity_threshold
        # Use both word-level and character-level features for better similarity detection
        self.word_vectorizer = TfidfVectorizer(
            analyzer='word',
            ngram_range=(1, 2),
            max_features=500,
            lowercase=True,
            stop_words='english'
        )
        self.char_vectorizer = TfidfVectorizer(
            analyzer='char_wb', 
            ngram_range=(2, 4), 
            max_features=500,
            lowercase=True
        )
    
    def validate_diversity(self, queries: List[str]) -> bool:
        """
        Validate that queries are sufficiently diverse using cosine similarity.
        Per requirement 3.5: enforce diversity with 0.8 threshold.
        
        Args:
            queries: List of query strings to validate
            
        Returns:
            bool: True if queries are diverse enough (all similarities < 0.8)
        """
        if len(queries) <= 1:
            return True
        
        # Filter out empty queries
        non_empty_queries = [q.strip() for q in queries if q.strip()]
        if len(non_empty_queries) <= 1:
            return True
        
        try:
            # Use combined word and character-level similarity
            word_similarities = self._calculate_word_similarity(non_empty_queries)
            char_similarities = self._calculate_char_similarity(non_empty_queries)
            
            # Check if any pair exceeds threshold using maximum of both similarities
            for i in range(len(non_empty_queries)):
                for j in range(i + 1, len(non_empty_queries)):
                    word_sim = word_similarities[i][j] if word_similarities is not None else 0.0
                    char_sim = char_similarities[i][j] if char_similarities is not None else 0.0
                    max_similarity = max(word_sim, char_sim)
                    
                    if max_similarity > self.similarity_threshold:
                        logger.warning(
                            f"Queries too similar (similarity: {max_similarity:.3f}, threshold: {self.similarity_threshold}): "
                            f"'{non_empty_queries[i][:50]}...' and '{non_empty_queries[j][:50]}...'"
                        )
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Diversity validation failed: {str(e)}")
            # If validation fails, allow the queries to proceed
            return True
    
    def _calculate_word_similarity(self, queries: List[str]) -> Optional[np.ndarray]:
        """Calculate word-level TF-IDF cosine similarity."""
        try:
            word_matrix = self.word_vectorizer.fit_transform(queries)
            return cosine_similarity(word_matrix)
        except Exception as e:
            logger.debug(f"Word similarity calculation failed: {e}")
            return None
    
    def _calculate_char_similarity(self, queries: List[str]) -> Optional[np.ndarray]:
        """Calculate character-level TF-IDF cosine similarity."""
        try:
            char_matrix = self.char_vectorizer.fit_transform(queries)
            return cosine_similarity(char_matrix)
        except Exception as e:
            logger.debug(f"Character similarity calculation failed: {e}")
            return None
    
    def break_similar_queries(self, queries: List[str]) -> List[str]:
        """
        Break similar queries into more diverse sub-queries.
        Per requirement 3.5: implement query breaking for unique sub-queries.
        
        Args:
            queries: List of potentially similar queries
            
        Returns:
            List[str]: Modified queries with better diversity
        """
        if self.validate_diversity(queries):
            return queries
        
        # Strategy: add unique perspectives and focus areas to make queries more diverse
        modified_queries = []
        perspectives = [
            "technical implementation details",
            "recent developments and trends", 
            "practical applications and use cases",
            "theoretical foundations and principles",
            "performance and optimization aspects",
            "security and best practices",
            "comparison with alternatives",
            "future implications and roadmap"
        ]
        
        for i, query in enumerate(queries):
            if i == 0:
                # Keep first query unchanged
                modified_queries.append(query)
            else:
                # Add unique perspective to subsequent queries
                perspective = perspectives[i % len(perspectives)]
                modified_query = f"Focusing on {perspective}: {query}"
                modified_queries.append(modified_query)
        
        # Validate that modified queries are now diverse
        if not self.validate_diversity(modified_queries):
            logger.warning("Query breaking did not achieve sufficient diversity")
            # Fallback: add more distinctive prefixes
            for i in range(1, len(modified_queries)):
                modified_queries[i] = f"[Query {i+1} - {perspectives[i % len(perspectives)]}] {queries[i]}"
        
        return modified_queries


class ToolManager:
    """
    Central manager for all tools in the system with orchestration capabilities.
    """
    
    def __init__(self, **kwargs):
        """
        Initialize tool manager.
        
        Args:
            **kwargs: Configuration options
        """
        self.config = kwargs
        
        # Initialize tools
        self.tools: Dict[ToolType, BaseTool] = {
            ToolType.CODER: CoderTool(**kwargs.get("coder", {})),
            ToolType.MULTIMODAL: MultimodalTool(**kwargs.get("multimodal", {})),
            ToolType.LIGHT_SEARCH: LightSearchTool(**kwargs.get("light_search", {})),
            ToolType.MEDIUM_SEARCH: MediumSearchTool(**kwargs.get("medium_search", {}))
        }
        
        # Tool access matrix based on model capabilities (per requirements 3.1, 3.2)
        self.model_tool_access = {
            "Melanie-3": {ToolType.CODER, ToolType.MULTIMODAL},  # + search when web_search=True
            "Melanie-3-light": {ToolType.CODER, ToolType.MULTIMODAL},  # + search when web_search=True
            "Melanie-3-code": {ToolType.MULTIMODAL}  # Only multimodal + search when web_search=True
        }
        
        # Query diversity validator
        self.diversity_validator = QueryDiversityValidator()
        
        # Execution tracking
        self.active_executions: Dict[str, asyncio.Task] = {}
        self._execution_lock = asyncio.Lock()
    
    def get_available_tools(self, model: str, web_search: bool = False) -> Set[ToolType]:
        """
        Get available tools for a specific model.
        
        Args:
            model: Model name
            web_search: Whether web search is enabled
            
        Returns:
            Set[ToolType]: Available tool types
        """
        base_tools = self.model_tool_access.get(model, set())
        
        # Add search tools if web_search is enabled (per requirement 3.4)
        if web_search:
            base_tools = base_tools.union({ToolType.LIGHT_SEARCH, ToolType.MEDIUM_SEARCH})
        
        return base_tools
    
    def get_tool_schemas(self, model: str, web_search: bool = False) -> List[Dict[str, Any]]:
        """
        Get tool schemas for available tools.
        
        Args:
            model: Model name
            web_search: Whether web search is enabled
            
        Returns:
            List[Dict]: Tool schemas in OpenAI function format
        """
        available_tools = self.get_available_tools(model, web_search)
        schemas = []
        
        for tool_type in available_tools:
            if tool_type in self.tools:
                schema = self.tools[tool_type].get_schema()
                schemas.append(schema)
        
        return schemas
    
    async def validate_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> bool:
        """
        Validate tool calls for diversity and availability.
        
        Args:
            tool_calls: List of tool call dictionaries
            
        Returns:
            bool: True if tool calls are valid
        """
        if len(tool_calls) <= 1:
            return True
        
        # Extract queries for diversity validation (per requirement 3.5)
        queries = []
        for call in tool_calls:
            function_args = call.get("function", {}).get("arguments", {})
            if isinstance(function_args, str):
                try:
                    function_args = json.loads(function_args)
                except json.JSONDecodeError:
                    continue
            
            # Extract query-like parameters
            query = (
                function_args.get("query") or 
                function_args.get("prompt") or 
                str(function_args)
            )
            queries.append(query)
        
        # Validate diversity
        return self.diversity_validator.validate_diversity(queries)
    
    async def execute_tool_calls(
        self, 
        tool_calls: List[Dict[str, Any]], 
        model: str, 
        web_search: bool = False
    ) -> List[ToolResult]:
        """
        Execute multiple tool calls with concurrency control.
        
        Args:
            tool_calls: List of tool call dictionaries
            model: Model name for access control
            web_search: Whether web search is enabled
            
        Returns:
            List[ToolResult]: Results from all tool executions
        """
        if not tool_calls:
            return []
        
        # Validate tool calls
        if not await self.validate_tool_calls(tool_calls):
            # Break similar queries if validation fails
            queries = []
            for call in tool_calls:
                function_args = call.get("function", {}).get("arguments", {})
                if isinstance(function_args, str):
                    try:
                        function_args = json.loads(function_args)
                    except json.JSONDecodeError:
                        continue
                query = (
                    function_args.get("query") or 
                    function_args.get("prompt") or 
                    str(function_args)
                )
                queries.append(query)
            
            # Modify queries for better diversity
            modified_queries = self.diversity_validator.break_similar_queries(queries)
            
            # Update tool calls with modified queries
            for i, (call, modified_query) in enumerate(zip(tool_calls, modified_queries)):
                function_args = call.get("function", {}).get("arguments", {})
                if isinstance(function_args, str):
                    try:
                        function_args = json.loads(function_args)
                    except json.JSONDecodeError:
                        continue
                
                if "query" in function_args:
                    function_args["query"] = modified_query
                elif "prompt" in function_args:
                    function_args["prompt"] = modified_query
                
                call["function"]["arguments"] = function_args
        
        # Get available tools for model
        available_tools = self.get_available_tools(model, web_search)
        
        # Create tool call objects
        tool_call_objects = []
        for call in tool_calls:
            function_name = call.get("function", {}).get("name", "")
            
            # Map function name to tool type
            tool_type = None
            for tt in ToolType:
                if tt.value == function_name:
                    tool_type = tt
                    break
            
            if tool_type is None or tool_type not in available_tools:
                logger.warning(f"Tool {function_name} not available for model {model}")
                continue
            
            # Parse arguments
            function_args = call.get("function", {}).get("arguments", {})
            if isinstance(function_args, str):
                try:
                    function_args = json.loads(function_args)
                except json.JSONDecodeError:
                    function_args = {}
            
            tool_call_obj = ToolCall(
                id=call.get("id", f"call_{int(time.time())}_{len(tool_call_objects)}"),
                tool_type=tool_type,
                function_name=function_name,
                arguments=function_args
            )
            tool_call_objects.append(tool_call_obj)
        
        # Execute tool calls concurrently
        tasks = []
        for call_obj in tool_call_objects:
            if call_obj.tool_type in self.tools:
                tool = self.tools[call_obj.tool_type]
                task = asyncio.create_task(
                    tool.execute_with_concurrency_control(call_obj)
                )
                tasks.append(task)
        
        # Wait for all tasks to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Convert exceptions to error results
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    call_obj = tool_call_objects[i]
                    error_result = ToolResult(
                        call_id=call_obj.id,
                        success=False,
                        error=str(result)
                    )
                    final_results.append(error_result)
                else:
                    final_results.append(result)
            
            return final_results
        
        return []
    
    async def get_tool_status(self) -> Dict[str, Any]:
        """
        Get status of all tools including active calls and availability.
        
        Returns:
            Dict: Tool status information
        """
        status = {
            "tools": {},
            "total_active_calls": 0
        }
        
        for tool_type, tool in self.tools.items():
            active_calls = await tool.get_active_call_count()
            status["tools"][tool_type.value] = {
                "name": tool.name,
                "max_concurrent": tool.max_concurrent,
                "active_calls": active_calls,
                "timeout": tool.timeout,
                "available": True  # Could add health checks here
            }
            status["total_active_calls"] += active_calls
        
        return status
    
    async def shutdown(self):
        """Shutdown all tools and cleanup resources."""
        logger.info("Shutting down tool manager...")
        
        # Cancel active executions
        async with self._execution_lock:
            for task in self.active_executions.values():
                task.cancel()
        
        # Cleanup tools if they have cleanup methods
        for tool in self.tools.values():
            if hasattr(tool, 'cleanup'):
                try:
                    await tool.cleanup()
                except Exception as e:
                    logger.error(f"Error cleaning up tool {tool.name}: {e}")
        
        logger.info("Tool manager shutdown complete")


# Example usage and testing
if __name__ == "__main__":
    async def test_tool_manager():
        """Test basic tool manager functionality."""
        try:
            # Initialize tool manager
            manager = ToolManager()
            
            # Test tool availability
            available_tools = manager.get_available_tools("Melanie-3", web_search=True)
            print(f"Available tools for Melanie-3 with web search: {available_tools}")
            
            # Test tool schemas
            schemas = manager.get_tool_schemas("Melanie-3", web_search=True)
            print(f"Tool schemas: {len(schemas)} tools available")
            
            # Test tool status
            status = await manager.get_tool_status()
            print(f"Tool status: {status}")
            
            # Test diversity validation
            similar_queries = [
                "What is machine learning?",
                "Explain machine learning concepts",
                "Tell me about ML algorithms"
            ]
            
            is_diverse = manager.diversity_validator.validate_diversity(similar_queries)
            print(f"Query diversity validation: {is_diverse}")
            
            if not is_diverse:
                modified = manager.diversity_validator.break_similar_queries(similar_queries)
                print(f"Modified queries: {modified}")
            
            await manager.shutdown()
            
        except Exception as e:
            print(f"Test failed: {str(e)}")
    
    # Run test
    asyncio.run(test_tool_manager())