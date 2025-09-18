"""
Melanie-3-code (Grok Code Fast) model wrapper implementing BaseAIModel interface.

This module provides:
- MelanieThreeCode class implementing BaseAIModel interface for coding tasks
- Code generation with comments and testing emphasis
- Code quality validation and PEP8 compliance checking
- Iterative debugging and testing capabilities
- Specialized coding, debugging, and analysis tasks
"""

import asyncio
import json
import logging
import os
import time
import ast
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

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
class CodeQualityResult:
    """Result from code quality validation."""
    is_valid: bool
    syntax_errors: List[str]
    pep8_violations: List[str]
    complexity_issues: List[str]
    test_coverage: float
    suggestions: List[str]


@dataclass
class DebugResult:
    """Result from debugging iteration."""
    iteration: int
    original_code: str
    fixed_code: str
    errors_found: List[str]
    fixes_applied: List[str]
    test_results: Dict[str, Any]
    success: bool


class MelanieThreeCodeError(Exception):
    """Custom exception for MelanieThreeCode model errors."""
    pass


class MelanieThreeCodeTimeoutError(MelanieThreeCodeError):
    """Timeout error for MelanieThreeCode model."""
    def __init__(self, timeout: float):
        self.timeout = timeout
        super().__init__(f"Request timed out after {timeout} seconds")


class MelanieThreeCodeRateLimitError(MelanieThreeCodeError):
    """Rate limit error for MelanieThreeCode model."""
    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        message = "Rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after} seconds"
        super().__init__(message)


class CodeQualityValidator:
    """
    Validates code quality including syntax, PEP8 compliance, and complexity.
    """
    
    def __init__(self):
        """Initialize code quality validator."""
        self.max_complexity = 10
        self.max_line_length = 88  # Black's default
    
    def validate_syntax(self, code: str) -> List[str]:
        """
        Validate Python syntax.
        
        Args:
            code: Python code to validate
            
        Returns:
            List of syntax error messages
        """
        errors = []
        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
        except Exception as e:
            errors.append(f"Parse error: {str(e)}")
        
        return errors
    
    def check_pep8_compliance(self, code: str) -> List[str]:
        """
        Check PEP8 compliance using basic rules.
        
        Args:
            code: Python code to check
            
        Returns:
            List of PEP8 violation messages
        """
        violations = []
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Check line length
            if len(line) > self.max_line_length:
                violations.append(f"Line {i}: Line too long ({len(line)} > {self.max_line_length})")
            
            # Check trailing whitespace
            if line.endswith(' ') or line.endswith('\t'):
                violations.append(f"Line {i}: Trailing whitespace")
            
            # Check indentation (basic check for tabs)
            if '\t' in line:
                violations.append(f"Line {i}: Use spaces instead of tabs")
            
            # Check for multiple statements on one line
            if ';' in line and not line.strip().startswith('#'):
                violations.append(f"Line {i}: Multiple statements on one line")
        
        return violations
    
    def analyze_complexity(self, code: str) -> List[str]:
        """
        Analyze code complexity.
        
        Args:
            code: Python code to analyze
            
        Returns:
            List of complexity issue messages
        """
        issues = []
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Count complexity indicators within this function only
                    complexity = 1  # Base complexity
                    
                    # Walk only the direct children of this function
                    for child in node.body:
                        complexity += self._count_complexity_in_node(child)
                    
                    if complexity > self.max_complexity:
                        issues.append(
                            f"Function '{node.name}' has high complexity ({complexity} > {self.max_complexity})"
                        )
        
        except Exception as e:
            issues.append(f"Complexity analysis failed: {str(e)}")
        
        return issues
    
    def _count_complexity_in_node(self, node) -> int:
        """
        Recursively count complexity in a node.
        
        Args:
            node: AST node to analyze
            
        Returns:
            Complexity count for this node
        """
        complexity = 0
        
        if isinstance(node, (ast.If, ast.While, ast.For, ast.Try, ast.With)):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            complexity += len(node.values) - 1
        elif isinstance(node, (ast.And, ast.Or)):
            complexity += 1
        
        # Recursively count in child nodes
        for child in ast.iter_child_nodes(node):
            complexity += self._count_complexity_in_node(child)
        
        return complexity
    
    def estimate_test_coverage(self, code: str) -> float:
        """
        Estimate test coverage based on code structure.
        
        Args:
            code: Python code to analyze
            
        Returns:
            Estimated test coverage percentage
        """
        try:
            tree = ast.parse(code)
            
            total_functions = 0
            test_functions = 0
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    total_functions += 1
                    if node.name.startswith('test_') or 'test' in node.name.lower():
                        test_functions += 1
            
            if total_functions == 0:
                return 0.0
            
            # Basic heuristic: if we have test functions, estimate coverage
            if test_functions > 0:
                return min(100.0, (test_functions / total_functions) * 100)
            else:
                return 0.0
        
        except Exception:
            return 0.0
    
    def generate_suggestions(self, code: str, violations: List[str]) -> List[str]:
        """
        Generate improvement suggestions based on violations.
        
        Args:
            code: Python code
            violations: List of violations found
            
        Returns:
            List of improvement suggestions
        """
        suggestions = []
        
        if any("Line too long" in v for v in violations):
            suggestions.append("Consider breaking long lines using parentheses or backslashes")
        
        if any("Trailing whitespace" in v for v in violations):
            suggestions.append("Remove trailing whitespace from lines")
        
        if any("Use spaces instead of tabs" in v for v in violations):
            suggestions.append("Configure your editor to use 4 spaces for indentation")
        
        if any("high complexity" in v for v in violations):
            suggestions.append("Consider breaking complex functions into smaller, more focused functions")
        
        # Check for missing docstrings
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    if not ast.get_docstring(node):
                        suggestions.append(f"Add docstring to {node.__class__.__name__.lower()} '{node.name}'")
                        break
        except Exception:
            pass
        
        return suggestions
    
    def validate_code_quality(self, code: str) -> CodeQualityResult:
        """
        Perform comprehensive code quality validation.
        
        Args:
            code: Python code to validate
            
        Returns:
            CodeQualityResult with validation results
        """
        syntax_errors = self.validate_syntax(code)
        pep8_violations = self.check_pep8_compliance(code)
        complexity_issues = self.analyze_complexity(code)
        test_coverage = self.estimate_test_coverage(code)
        
        all_violations = syntax_errors + pep8_violations + complexity_issues
        suggestions = self.generate_suggestions(code, all_violations)
        
        is_valid = len(syntax_errors) == 0 and len(pep8_violations) <= 5 and len(complexity_issues) == 0
        
        return CodeQualityResult(
            is_valid=is_valid,
            syntax_errors=syntax_errors,
            pep8_violations=pep8_violations,
            complexity_issues=complexity_issues,
            test_coverage=test_coverage,
            suggestions=suggestions
        )


class MelanieThreeCode(BaseAIModel):
    """
    Melanie-3-code (Grok Code Fast) model wrapper implementing BaseAIModel interface.
    
    Specialized for coding tasks with emphasis on code generation with comments,
    testing, code quality validation, PEP8 compliance, and iterative debugging.
    """
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize MelanieThreeCode model.
        
        Args:
            api_key: xAI API key (defaults to XAI_API_KEY env var)
            **kwargs: Additional configuration options
        """
        api_key = api_key or os.getenv("XAI_API_KEY")
        if not api_key:
            raise ValueError("XAI_API_KEY environment variable or api_key parameter is required")
        
        super().__init__(
            model_name="grok-code-fast",
            api_key=api_key,
            **kwargs
        )
        
        # Configuration
        self.base_url = kwargs.get("base_url", "https://api.x.ai/v1")
        self.timeout = kwargs.get("timeout", 1800)  # 30 minutes for coding tasks
        self.max_retries = kwargs.get("max_retries", 3)
        self.retry_delay = kwargs.get("retry_delay", 1.0)
        
        # Code quality settings
        self.enable_quality_validation = kwargs.get("enable_quality_validation", True)
        self.max_debug_iterations = kwargs.get("max_debug_iterations", 3)
        self.require_tests = kwargs.get("require_tests", True)
        self.min_test_coverage = kwargs.get("min_test_coverage", 70.0)
        
        # Initialize code quality validator
        self.quality_validator = CodeQualityValidator()
        
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
    
    def _create_coding_system_prompt(self) -> str:
        """
        Create system prompt optimized for coding tasks.
        
        Returns:
            System prompt string
        """
        return """You are Melanie, an expert software engineer and code reviewer specializing in Python development.

Your coding guidelines:
1. Always write clean, readable, and well-documented code
2. Include comprehensive docstrings for all functions and classes
3. Follow PEP8 style guidelines strictly
4. Write unit tests for all functions when requested
5. Add inline comments for complex logic
6. Use type hints for function parameters and return values
7. Handle errors gracefully with appropriate exception handling
8. Optimize for readability and maintainability over cleverness
9. Include examples in docstrings when helpful
10. Consider edge cases and input validation

When generating code:
- Start with a brief explanation of the approach
- Provide the complete, runnable code
- Include comprehensive tests if requested
- Explain any complex algorithms or design decisions
- Suggest improvements or alternative approaches when relevant

Focus on producing production-ready code that follows best practices."""
    
    def _format_messages_for_xai(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        """
        Format messages for xAI API with coding-specific enhancements.
        
        Args:
            messages: List of ChatMessage objects
            
        Returns:
            List of formatted message dictionaries
        """
        formatted_messages = []
        
        # Add coding-specific system prompt if not present
        has_system_prompt = any(msg.role == MessageRole.SYSTEM for msg in messages)
        if not has_system_prompt:
            formatted_messages.append({
                "role": "system",
                "content": self._create_coding_system_prompt()
            })
        
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
        Format tools for xAI API (limited to multimodal only for Melanie-3-code).
        
        Args:
            tools: List of Tool objects
            
        Returns:
            List of formatted tool dictionaries or None
        """
        if not tools:
            return None
        
        # Filter to only allow multimodal tools for Melanie-3-code (per requirement 3.2)
        allowed_tools = ["multimodal"]
        filtered_tools = [
            tool for tool in tools 
            if tool.function.name in allowed_tools
        ]
        
        if not filtered_tools:
            return None
        
        formatted_tools = []
        
        for tool in filtered_tools:
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
        request_id: str,
        quality_result: Optional[CodeQualityResult] = None
    ) -> ChatCompletionResponse:
        """
        Convert xAI response to OpenAI-compatible format with code quality metadata.
        
        Args:
            xai_response: Raw response from xAI API
            request_id: Unique request identifier
            quality_result: Optional code quality validation result
            
        Returns:
            ChatCompletionResponse object
        """
        # Extract choice data
        choices_data = []
        if "choices" in xai_response and xai_response["choices"]:
            for i, choice in enumerate(xai_response["choices"]):
                message = choice.get("message", {})
                
                # Add code quality metadata if available
                if quality_result and message.get("role") == "assistant":
                    if "metadata" not in message:
                        message["metadata"] = {}
                    
                    message["metadata"]["code_quality"] = {
                        "is_valid": quality_result.is_valid,
                        "syntax_errors": quality_result.syntax_errors,
                        "pep8_violations": len(quality_result.pep8_violations),
                        "complexity_issues": len(quality_result.complexity_issues),
                        "test_coverage": quality_result.test_coverage,
                        "suggestions": quality_result.suggestions
                    }
                
                choice_data = Choice(
                    index=i,
                    message=message,
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
            MelanieThreeCodeError: On API or network errors
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Making coding request to {endpoint} (attempt {attempt + 1})")
                
                response = await self.client.post(endpoint, json=payload)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    if attempt < self.max_retries:
                        logger.warning(f"Rate limited, waiting {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        raise MelanieThreeCodeRateLimitError(retry_after)
                
                # Handle other HTTP errors
                if response.status_code >= 400:
                    error_data = response.json() if response.content else {}
                    error_message = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                    raise MelanieThreeCodeError(f"API error: {error_message}")
                
                # Success
                return response.json()
                
            except httpx.TimeoutException as e:
                last_exception = MelanieThreeCodeTimeoutError(self.timeout)
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Request timed out, retrying in {delay} seconds")
                    await asyncio.sleep(delay)
                    continue
                    
            except httpx.RequestError as e:
                last_exception = MelanieThreeCodeError(f"Network error: {str(e)}")
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Network error, retrying in {delay} seconds")
                    await asyncio.sleep(delay)
                    continue
                    
            except Exception as e:
                last_exception = MelanieThreeCodeError(f"Unexpected error: {str(e)}")
                break
        
        # All retries exhausted
        raise last_exception or MelanieThreeCodeError("Request failed after all retries")
    
    def _extract_code_from_response(self, content: str) -> List[str]:
        """
        Extract Python code blocks from response content.
        
        Args:
            content: Response content that may contain code blocks
            
        Returns:
            List of extracted code strings
        """
        code_blocks = []
        lines = content.split('\n')
        in_code_block = False
        current_code = []
        
        for line in lines:
            if line.strip().startswith('```python') or line.strip().startswith('```py'):
                in_code_block = True
                current_code = []
            elif line.strip() == '```' and in_code_block:
                in_code_block = False
                if current_code:
                    code_blocks.append('\n'.join(current_code))
                current_code = []
            elif in_code_block:
                current_code.append(line)
        
        # If no code blocks found, try to detect inline code
        if not code_blocks:
            # Simple heuristic: if content looks like Python code
            if any(keyword in content for keyword in ['def ', 'class ', 'import ', 'from ']):
                code_blocks.append(content)
        
        return code_blocks
    
    async def validate_generated_code(self, content: str) -> Tuple[List[str], CodeQualityResult]:
        """
        Validate generated code for quality and compliance.
        
        Args:
            content: Generated content that may contain code
            
        Returns:
            Tuple of (code_blocks, quality_result)
        """
        code_blocks = self._extract_code_from_response(content)
        
        if not code_blocks:
            return [], CodeQualityResult(
                is_valid=True,
                syntax_errors=[],
                pep8_violations=[],
                complexity_issues=[],
                test_coverage=0.0,
                suggestions=[]
            )
        
        # Validate the first (main) code block
        main_code = code_blocks[0]
        quality_result = self.quality_validator.validate_code_quality(main_code)
        
        return code_blocks, quality_result
    
    async def iterative_debug_code(
        self, 
        original_code: str, 
        errors: List[str]
    ) -> DebugResult:
        """
        Perform iterative debugging on code with errors.
        
        Args:
            original_code: Original code with errors
            errors: List of error messages
            
        Returns:
            DebugResult with debugging information
        """
        debug_prompt = f"""
The following Python code has errors that need to be fixed:

```python
{original_code}
```

Errors found:
{chr(10).join(f"- {error}" for error in errors)}

Please provide the corrected code with:
1. All syntax errors fixed
2. PEP8 compliance improvements
3. Reduced complexity where possible
4. Added comments explaining the fixes
5. Improved error handling if needed

Return only the corrected Python code in a code block.
"""
        
        try:
            messages = [
                ChatMessage(role=MessageRole.USER, content=debug_prompt)
            ]
            
            response = await self.generate(messages, enable_quality_check=False)
            fixed_content = response.choices[0].message["content"]
            
            # Extract fixed code
            fixed_code_blocks = self._extract_code_from_response(fixed_content)
            fixed_code = fixed_code_blocks[0] if fixed_code_blocks else original_code
            
            # Validate fixed code
            quality_result = self.quality_validator.validate_code_quality(fixed_code)
            
            return DebugResult(
                iteration=1,
                original_code=original_code,
                fixed_code=fixed_code,
                errors_found=errors,
                fixes_applied=["Syntax fixes", "PEP8 improvements", "Complexity reduction"],
                test_results={"quality_score": quality_result.is_valid},
                success=quality_result.is_valid
            )
            
        except Exception as e:
            logger.error(f"Debug iteration failed: {str(e)}")
            return DebugResult(
                iteration=1,
                original_code=original_code,
                fixed_code=original_code,
                errors_found=errors,
                fixes_applied=[],
                test_results={"error": str(e)},
                success=False
            )
    
    async def generate(
        self, 
        messages: List[ChatMessage], 
        tools: Optional[List[Tool]] = None,
        enable_quality_check: bool = None,
        **kwargs
    ) -> ChatCompletionResponse:
        """
        Generate chat completion using Grok Code Fast with code quality validation.
        
        Args:
            messages: List of chat messages
            tools: Optional list of available tools (limited to multimodal)
            enable_quality_check: Whether to perform code quality validation
            **kwargs: Additional generation parameters
            
        Returns:
            ChatCompletionResponse: Generated response in OpenAI format
            
        Raises:
            MelanieThreeCodeError: On generation errors
        """
        if enable_quality_check is None:
            enable_quality_check = self.enable_quality_validation
        
        try:
            # Format request payload
            payload = {
                "model": self.model_name,
                "messages": self._format_messages_for_xai(messages),
                "max_tokens": kwargs.get("max_tokens", 8000),  # Larger for code generation
                "temperature": kwargs.get("temperature", 0.3),  # Lower for more consistent code
                "top_p": kwargs.get("top_p", 0.9),
                "stream": kwargs.get("stream", False)
            }
            
            # Add tools if provided (filtered to multimodal only)
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
            request_id = f"chatcmpl-code-{int(time.time())}-{hash(str(payload)) % 10000}"
            
            # Validate code quality if enabled
            quality_result = None
            if enable_quality_check and "choices" in response_data:
                content = response_data["choices"][0]["message"]["content"]
                code_blocks, quality_result = await self.validate_generated_code(content)
                
                # If code has issues and iterative debugging is enabled, try to fix
                if (quality_result and not quality_result.is_valid and 
                    code_blocks and self.max_debug_iterations > 0):
                    
                    all_errors = (quality_result.syntax_errors + 
                                quality_result.pep8_violations + 
                                quality_result.complexity_issues)
                    
                    if all_errors:
                        logger.info("Code quality issues found, attempting to debug...")
                        debug_result = await self.iterative_debug_code(code_blocks[0], all_errors)
                        
                        if debug_result.success:
                            # Update response with fixed code
                            response_data["choices"][0]["message"]["content"] = f"""
Here's the improved code:

```python
{debug_result.fixed_code}
```

Fixes applied:
{chr(10).join(f"- {fix}" for fix in debug_result.fixes_applied)}
"""
                            # Re-validate the fixed code
                            _, quality_result = await self.validate_generated_code(
                                response_data["choices"][0]["message"]["content"]
                            )
            
            # Convert to OpenAI format
            return self._create_openai_response(response_data, request_id, quality_result)
            
        except Exception as e:
            logger.error(f"Code generation failed: {str(e)}")
            if isinstance(e, MelanieThreeCodeError):
                raise
            else:
                raise MelanieThreeCodeError(f"Code generation failed: {str(e)}")
    
    async def validate_request(self, request: ChatCompletionRequest) -> bool:
        """
        Validate if request is compatible with Grok Code Fast.
        
        Args:
            request: Chat completion request
            
        Returns:
            bool: True if request is valid for this model
        """
        try:
            # Check model compatibility
            model_name = getattr(request.model, 'value', request.model)
            if model_name != "Melanie-3-code":
                return False
            
            # Check message count and content
            if not request.messages or len(request.messages) > 50:
                return False
            
            # Check token limits
            total_chars = sum(len(getattr(msg, 'content', '')) for msg in request.messages)
            if total_chars > 200000:  # Reasonable limit for code tasks
                return False
            
            # Check tool compatibility (only multimodal allowed)
            if request.tools:
                allowed_tools = {"multimodal"}
                for tool in request.tools:
                    tool_name = getattr(tool.function, 'name', None)
                    if tool_name not in allowed_tools:
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Request validation failed: {str(e)}")
            return False
    
    def get_capabilities(self) -> List[str]:
        """
        Get list of Grok Code Fast capabilities.
        
        Returns:
            List[str]: List of capability names
        """
        return [
            "code_generation",
            "code_review",
            "debugging",
            "testing",
            "pep8_compliance",
            "code_quality_validation",
            "iterative_debugging",
            "syntax_checking",
            "complexity_analysis",
            "documentation_generation",
            "refactoring",
            "error_handling",
            "type_hinting",
            "unit_testing",
            "multimodal_tool_access"  # Limited tool access per requirement 3.2
        ]
    
    def get_max_tokens(self) -> int:
        """
        Get maximum token limit for Grok Code Fast.
        
        Returns:
            int: Maximum token limit
        """
        return 65536  # 64k tokens for code generation tasks
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get comprehensive model information.
        
        Returns:
            Dict: Model information including capabilities and limits
        """
        info = super().get_model_info()
        info.update({
            "provider": "xAI",
            "version": "grok-code-fast",
            "context_window": self.get_max_tokens(),
            "supports_streaming": True,
            "supports_tools": True,
            "allowed_tools": ["multimodal"],  # Per requirement 3.2
            "supports_vision": False,  # Code-focused model
            "code_quality_features": {
                "syntax_validation": True,
                "pep8_checking": True,
                "complexity_analysis": True,
                "iterative_debugging": True,
                "test_coverage_estimation": True
            },
            "pricing_per_1k_tokens": {
                "input": 0.01,  # Example pricing for code model
                "output": 0.05
            },
            "optimized_for": [
                "code_generation",
                "debugging",
                "code_quality",
                "testing",
                "documentation"
            ]
        })
        return info


# Convenience function for backward compatibility
async def ask_grok_code_async(
    prompt: str, 
    system_prompt: Optional[str] = None,
    enable_quality_check: bool = True,
    **kwargs
) -> str:
    """
    Async version of ask_grok_code function with quality validation.
    
    Args:
        prompt: User prompt/question
        system_prompt: Optional system prompt (uses coding-specific default if None)
        enable_quality_check: Whether to perform code quality validation
        **kwargs: Additional parameters
        
    Returns:
        str: Response content from Grok Code Fast
    """
    async with MelanieThreeCode() as model:
        messages = []
        
        if system_prompt:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))
        
        messages.append(ChatMessage(role=MessageRole.USER, content=prompt))
        
        response = await model.generate(
            messages, 
            enable_quality_check=enable_quality_check,
            **kwargs
        )
        return response.choices[0].message["content"]


# Example usage and testing
if __name__ == "__main__":
    async def test_code_generation():
        """Test code generation functionality."""
        try:
            async with MelanieThreeCode() as model:
                messages = [
                    ChatMessage(
                        role=MessageRole.USER, 
                        content="Write a Python function to calculate the factorial of a number with proper error handling and tests."
                    )
                ]
                
                response = await model.generate(messages)
                print(f"Generated code:\n{response.choices[0].message['content']}")
                
                # Check if quality metadata is included
                metadata = response.choices[0].message.get("metadata", {})
                if "code_quality" in metadata:
                    quality = metadata["code_quality"]
                    print(f"\nCode Quality Report:")
                    print(f"Valid: {quality['is_valid']}")
                    print(f"Syntax Errors: {len(quality['syntax_errors'])}")
                    print(f"PEP8 Violations: {quality['pep8_violations']}")
                    print(f"Test Coverage: {quality['test_coverage']}%")
                
        except Exception as e:
            print(f"Test failed: {str(e)}")
    
    # Run test
    asyncio.run(test_code_generation())