"""
Comprehensive error handling middleware and logging system for Melanie AI API

This module implements:
- Enhanced error handling middleware with specific error types
- Structured logging with JSON format
- Exception handling and graceful error responses
- Input validation middleware
- Fallback manager for graceful degradation
- Health monitoring and error tracking
"""

import asyncio
import json
import logging
import logging.handlers
import os
import sys
import time
import traceback
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union
from pathlib import Path

from fastapi import HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from models import (
    APIError, 
    DetailedAPIError, 
    ValidationError as CustomValidationError,
    InputSanitizer,
    RequestValidator
)

# Configure structured logging
class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging."""
    
    def format(self, record):
        """Format log record as structured JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                log_data[key] = value
        
        return json.dumps(log_data)

def setup_logging():
    """Setup comprehensive logging configuration."""
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler with structured format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(console_handler)
    
    # File handler for all logs
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "melanie_api.log",
        maxBytes=10_000_000,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(file_handler)
    
    # Error-specific file handler
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "melanie_errors.log",
        maxBytes=5_000_000,  # 5MB
        backupCount=10
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(error_handler)
    
    return logging.getLogger(__name__)

# Initialize logging
logger = setup_logging()


class ErrorHandler:
    """Centralized error handling with proper logging and response formatting."""
    
    # Error tracking for monitoring
    _error_counts = {}
    _last_reset = time.time()
    
    @classmethod
    def _track_error(cls, error_type: str):
        """Track error occurrences for monitoring."""
        current_time = time.time()
        
        # Reset counters every hour
        if current_time - cls._last_reset > 3600:
            cls._error_counts = {}
            cls._last_reset = current_time
        
        cls._error_counts[error_type] = cls._error_counts.get(error_type, 0) + 1
    
    @classmethod
    def get_error_stats(cls) -> Dict[str, Any]:
        """Get error statistics for monitoring."""
        return {
            "error_counts": cls._error_counts.copy(),
            "last_reset": cls._last_reset,
            "total_errors": sum(cls._error_counts.values())
        }
    
    @staticmethod
    def handle_validation_error(exc: RequestValidationError) -> DetailedAPIError:
        """
        Handle Pydantic validation errors.
        
        Args:
            exc: RequestValidationError from FastAPI/Pydantic
            
        Returns:
            DetailedAPIError: Formatted error response
        """
        ErrorHandler._track_error("validation_error")
        
        validation_errors = []
        error_id = str(uuid.uuid4())
        
        for error in exc.errors():
            field_path = " -> ".join(str(loc) for loc in error["loc"])
            validation_errors.append(
                CustomValidationError(
                    field=field_path,
                    message=error["msg"],
                    invalid_value=error.get("input")
                )
            )
        
        logger.warning(
            "Validation error occurred",
            extra={
                "error_id": error_id,
                "error_type": "validation_error",
                "field_count": len(validation_errors),
                "fields": [ve.field for ve in validation_errors]
            }
        )
        
        return DetailedAPIError(
            error="validation_error",
            message="Request validation failed",
            details={
                "error_id": error_id,
                "error_count": len(validation_errors)
            },
            validation_errors=validation_errors
        )
    
    @staticmethod
    def handle_http_exception(exc: HTTPException) -> APIError:
        """
        Handle FastAPI HTTP exceptions.
        
        Args:
            exc: HTTPException from FastAPI
            
        Returns:
            APIError: Formatted error response
        """
        ErrorHandler._track_error("http_error")
        error_id = str(uuid.uuid4())
        
        logger.warning(
            "HTTP exception occurred",
            extra={
                "error_id": error_id,
                "error_type": "http_error",
                "status_code": exc.status_code,
                "detail": str(exc.detail)
            }
        )
        
        return APIError(
            error="http_error",
            message=str(exc.detail),
            details={
                "error_id": error_id,
                "status_code": exc.status_code,
                "headers": exc.headers
            }
        )
    
    @staticmethod
    def handle_generic_exception(exc: Exception) -> APIError:
        """
        Handle generic exceptions with proper logging.
        
        Args:
            exc: Generic exception
            
        Returns:
            APIError: Formatted error response
        """
        ErrorHandler._track_error("internal_error")
        error_id = str(uuid.uuid4())
        
        logger.error(
            "Unhandled exception occurred",
            extra={
                "error_id": error_id,
                "error_type": "internal_error",
                "exception_type": type(exc).__name__,
                "exception_message": str(exc)
            },
            exc_info=True
        )
        
        return APIError(
            error="internal_error",
            message="An internal server error occurred",
            details={
                "error_id": error_id,
                "type": type(exc).__name__
            }
        )
    
    @staticmethod
    def handle_model_error(exc: Exception, model_name: str) -> APIError:
        """
        Handle AI model-specific errors.
        
        Args:
            exc: Exception from AI model
            model_name: Name of the model that failed
            
        Returns:
            APIError: Formatted error response
        """
        error_id = str(uuid.uuid4())
        exc_str = str(exc).lower()
        
        # Determine specific error type
        if "timeout" in exc_str or "timed out" in exc_str:
            error_type = "model_timeout"
            message = f"Model {model_name} request timed out"
        elif "rate limit" in exc_str or "429" in exc_str:
            error_type = "model_rate_limit"
            message = f"Model {model_name} rate limit exceeded"
        elif "api key" in exc_str or "unauthorized" in exc_str or "401" in exc_str:
            error_type = "model_auth_error"
            message = f"Authentication failed for model {model_name}"
        elif "quota" in exc_str or "billing" in exc_str:
            error_type = "model_quota_error"
            message = f"Model {model_name} quota exceeded"
        elif "service unavailable" in exc_str or "503" in exc_str:
            error_type = "model_unavailable"
            message = f"Model {model_name} service unavailable"
        elif "bad request" in exc_str or "400" in exc_str:
            error_type = "model_bad_request"
            message = f"Invalid request to model {model_name}"
        else:
            error_type = "model_error"
            message = f"Model {model_name} encountered an error"
        
        ErrorHandler._track_error(error_type)
        
        logger.error(
            "Model error occurred",
            extra={
                "error_id": error_id,
                "error_type": error_type,
                "model_name": model_name,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc)
            }
        )
        
        return APIError(
            error=error_type,
            message=message,
            details={
                "error_id": error_id,
                "model": model_name,
                "original_error": str(exc)
            }
        )
    
    @staticmethod
    def handle_file_error(exc: Exception, operation: str, file_id: Optional[str] = None) -> APIError:
        """
        Handle file operation errors.
        
        Args:
            exc: Exception from file operation
            operation: Type of file operation (upload, process, etc.)
            file_id: Optional file identifier
            
        Returns:
            APIError: Formatted error response
        """
        error_id = str(uuid.uuid4())
        exc_str = str(exc).lower()
        
        # Determine specific file error type
        if "not found" in exc_str or "no such file" in exc_str:
            error_type = "file_not_found"
            message = f"File not found during {operation}"
        elif "permission" in exc_str or "access denied" in exc_str:
            error_type = "file_permission_error"
            message = f"Permission denied during file {operation}"
        elif "disk" in exc_str or "space" in exc_str:
            error_type = "file_storage_error"
            message = f"Storage error during file {operation}"
        elif "size" in exc_str or "too large" in exc_str:
            error_type = "file_size_error"
            message = f"File size error during {operation}"
        elif "format" in exc_str or "invalid" in exc_str:
            error_type = "file_format_error"
            message = f"Invalid file format during {operation}"
        else:
            error_type = "file_error"
            message = f"File {operation} failed"
        
        ErrorHandler._track_error(error_type)
        
        logger.error(
            "File operation error occurred",
            extra={
                "error_id": error_id,
                "error_type": error_type,
                "operation": operation,
                "file_id": file_id,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc)
            }
        )
        
        return APIError(
            error=error_type,
            message=message,
            details={
                "error_id": error_id,
                "operation": operation,
                "file_id": file_id,
                "error": str(exc)
            }
        )
    
    @staticmethod
    def handle_rag_error(exc: Exception, operation: str) -> APIError:
        """
        Handle RAG system errors.
        
        Args:
            exc: Exception from RAG system
            operation: Type of RAG operation
            
        Returns:
            APIError: Formatted error response
        """
        error_id = str(uuid.uuid4())
        ErrorHandler._track_error("rag_error")
        
        logger.error(
            "RAG system error occurred",
            extra={
                "error_id": error_id,
                "error_type": "rag_error",
                "operation": operation,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc)
            }
        )
        
        return APIError(
            error="rag_error",
            message=f"RAG system {operation} failed",
            details={
                "error_id": error_id,
                "operation": operation,
                "error": str(exc)
            }
        )
    
    @staticmethod
    def handle_tool_error(exc: Exception, tool_name: str, operation: str) -> APIError:
        """
        Handle tool execution errors.
        
        Args:
            exc: Exception from tool execution
            tool_name: Name of the tool that failed
            operation: Type of tool operation
            
        Returns:
            APIError: Formatted error response
        """
        error_id = str(uuid.uuid4())
        ErrorHandler._track_error("tool_error")
        
        logger.error(
            "Tool execution error occurred",
            extra={
                "error_id": error_id,
                "error_type": "tool_error",
                "tool_name": tool_name,
                "operation": operation,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc)
            }
        )
        
        return APIError(
            error="tool_error",
            message=f"Tool {tool_name} {operation} failed",
            details={
                "error_id": error_id,
                "tool": tool_name,
                "operation": operation,
                "error": str(exc)
            }
        )
    
    @staticmethod
    def handle_auth_error(exc: Exception, operation: str) -> APIError:
        """
        Handle authentication errors.
        
        Args:
            exc: Exception from authentication
            operation: Type of auth operation
            
        Returns:
            APIError: Formatted error response
        """
        error_id = str(uuid.uuid4())
        ErrorHandler._track_error("auth_error")
        
        logger.warning(
            "Authentication error occurred",
            extra={
                "error_id": error_id,
                "error_type": "auth_error",
                "operation": operation,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc)
            }
        )
        
        return APIError(
            error="auth_error",
            message=f"Authentication {operation} failed",
            details={
                "error_id": error_id,
                "operation": operation,
                "error": str(exc)
            }
        )


class FallbackManager:
    """Manages graceful degradation and fallback mechanisms."""
    
    def __init__(self):
        self.fallback_stats = {}
        self.circuit_breakers = {}
    
    async def execute_with_fallback(
        self, 
        primary_func: Callable, 
        fallback_func: Optional[Callable] = None,
        operation_name: str = "unknown",
        *args, 
        **kwargs
    ) -> Any:
        """
        Execute function with fallback mechanism.
        
        Args:
            primary_func: Primary function to execute
            fallback_func: Fallback function if primary fails
            operation_name: Name of the operation for logging
            *args: Arguments for the functions
            **kwargs: Keyword arguments for the functions
            
        Returns:
            Result from primary or fallback function
        """
        operation_id = str(uuid.uuid4())
        
        try:
            # Check circuit breaker
            if self._is_circuit_open(operation_name):
                logger.warning(
                    "Circuit breaker open, using fallback",
                    extra={
                        "operation_id": operation_id,
                        "operation_name": operation_name,
                        "reason": "circuit_breaker_open"
                    }
                )
                if fallback_func:
                    return await self._execute_fallback(fallback_func, operation_name, operation_id, *args, **kwargs)
                else:
                    raise Exception(f"Circuit breaker open for {operation_name} and no fallback available")
            
            # Execute primary function
            logger.debug(
                "Executing primary function",
                extra={
                    "operation_id": operation_id,
                    "operation_name": operation_name,
                    "function": primary_func.__name__ if hasattr(primary_func, '__name__') else str(primary_func)
                }
            )
            
            result = await primary_func(*args, **kwargs) if asyncio.iscoroutinefunction(primary_func) else primary_func(*args, **kwargs)
            
            # Record success
            self._record_success(operation_name)
            
            logger.debug(
                "Primary function executed successfully",
                extra={
                    "operation_id": operation_id,
                    "operation_name": operation_name
                }
            )
            
            return result
            
        except Exception as e:
            # Record failure
            self._record_failure(operation_name)
            
            logger.warning(
                "Primary function failed, attempting fallback",
                extra={
                    "operation_id": operation_id,
                    "operation_name": operation_name,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            
            if fallback_func:
                return await self._execute_fallback(fallback_func, operation_name, operation_id, *args, **kwargs)
            else:
                logger.error(
                    "No fallback available for failed operation",
                    extra={
                        "operation_id": operation_id,
                        "operation_name": operation_name,
                        "error": str(e)
                    }
                )
                raise e
    
    async def _execute_fallback(
        self, 
        fallback_func: Callable, 
        operation_name: str, 
        operation_id: str,
        *args, 
        **kwargs
    ) -> Any:
        """Execute fallback function with error handling."""
        try:
            logger.info(
                "Executing fallback function",
                extra={
                    "operation_id": operation_id,
                    "operation_name": operation_name,
                    "fallback_function": fallback_func.__name__ if hasattr(fallback_func, '__name__') else str(fallback_func)
                }
            )
            
            result = await fallback_func(*args, **kwargs) if asyncio.iscoroutinefunction(fallback_func) else fallback_func(*args, **kwargs)
            
            # Track fallback usage
            self._track_fallback_usage(operation_name)
            
            logger.info(
                "Fallback function executed successfully",
                extra={
                    "operation_id": operation_id,
                    "operation_name": operation_name
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Fallback function also failed",
                extra={
                    "operation_id": operation_id,
                    "operation_name": operation_name,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise Exception(f"Both primary and fallback functions failed for {operation_name}: {str(e)}")
    
    def _is_circuit_open(self, operation_name: str) -> bool:
        """Check if circuit breaker is open for an operation."""
        if operation_name not in self.circuit_breakers:
            return False
        
        breaker = self.circuit_breakers[operation_name]
        current_time = time.time()
        
        # Reset circuit breaker after timeout
        if current_time - breaker.get('last_failure', 0) > breaker.get('timeout', 300):  # 5 minutes
            breaker['failures'] = 0
            breaker['is_open'] = False
        
        return breaker.get('is_open', False)
    
    def _record_success(self, operation_name: str):
        """Record successful operation."""
        if operation_name in self.circuit_breakers:
            self.circuit_breakers[operation_name]['failures'] = 0
            self.circuit_breakers[operation_name]['is_open'] = False
    
    def _record_failure(self, operation_name: str):
        """Record failed operation and update circuit breaker."""
        if operation_name not in self.circuit_breakers:
            self.circuit_breakers[operation_name] = {
                'failures': 0,
                'is_open': False,
                'threshold': 5,  # Open after 5 failures
                'timeout': 300   # 5 minutes
            }
        
        breaker = self.circuit_breakers[operation_name]
        breaker['failures'] += 1
        breaker['last_failure'] = time.time()
        
        if breaker['failures'] >= breaker['threshold']:
            breaker['is_open'] = True
            logger.warning(
                "Circuit breaker opened",
                extra={
                    "operation_name": operation_name,
                    "failure_count": breaker['failures'],
                    "threshold": breaker['threshold']
                }
            )
    
    def _track_fallback_usage(self, operation_name: str):
        """Track fallback usage for monitoring."""
        if operation_name not in self.fallback_stats:
            self.fallback_stats[operation_name] = {
                'count': 0,
                'last_used': None
            }
        
        self.fallback_stats[operation_name]['count'] += 1
        self.fallback_stats[operation_name]['last_used'] = time.time()
    
    def get_fallback_stats(self) -> Dict[str, Any]:
        """Get fallback usage statistics."""
        return {
            "fallback_usage": self.fallback_stats.copy(),
            "circuit_breakers": {
                name: {
                    "failures": breaker.get('failures', 0),
                    "is_open": breaker.get('is_open', False),
                    "last_failure": breaker.get('last_failure')
                }
                for name, breaker in self.circuit_breakers.items()
            }
        }
    
    async def model_with_fallback(self, model_name: str, messages: List[Dict], **kwargs) -> Dict:
        """Execute model request with fallback to lighter model."""
        async def primary_model():
            # Import here to avoid circular imports
            from server import get_model_instance
            model = await get_model_instance(model_name)
            return await model.generate(messages, **kwargs)
        
        async def fallback_model():
            # Fallback to Melanie-3-light for basic responses
            from server import get_model_instance
            fallback_model = await get_model_instance("Melanie-3-light")
            return await fallback_model.generate(messages, **kwargs)
        
        return await self.execute_with_fallback(
            primary_model,
            fallback_model if model_name != "Melanie-3-light" else None,
            f"model_{model_name}",
            **kwargs
        )
    
    async def rag_with_fallback(self, query: str, mode: str = "general") -> List[Dict]:
        """Execute RAG query with fallback to empty context."""
        async def primary_rag():
            from server import get_rag_client
            rag_client = await get_rag_client()
            if not rag_client:
                raise Exception("RAG client not available")
            return await rag_client.get_context(query, mode=mode)
        
        def fallback_rag():
            logger.warning("RAG failed, proceeding without context")
            return []
        
        return await self.execute_with_fallback(
            primary_rag,
            fallback_rag,
            "rag_retrieval"
        )
    
    async def tool_with_fallback(self, tool_name: str, tool_func: Callable, *args, **kwargs) -> Any:
        """Execute tool with fallback mechanism."""
        def fallback_tool():
            logger.warning(f"Tool {tool_name} failed, returning empty result")
            return {"error": f"Tool {tool_name} unavailable", "result": None}
        
        return await self.execute_with_fallback(
            tool_func,
            fallback_tool,
            f"tool_{tool_name}",
            *args,
            **kwargs
        )

# Global fallback manager instance
fallback_manager = FallbackManager()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Log requests and responses with timing information.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response: HTTP response
        """
        start_time = time.time()
        
        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )
        
        # Log request body for non-GET requests (truncated for security)
        if request.method != "GET":
            try:
                body = await request.body()
                if body:
                    body_str = body.decode('utf-8')[:500]  # Truncate for logging
                    if len(body) > 500:
                        body_str += "... (truncated)"
                    logger.debug(f"Request body: {body_str}")
            except Exception as e:
                logger.debug(f"Could not log request body: {e}")
        
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log response
        logger.info(
            f"Response: {response.status_code} "
            f"({process_time:.3f}s) "
            f"for {request.method} {request.url.path}"
        )
        
        # Add timing header
        response.headers["X-Process-Time"] = str(process_time)
        
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for centralized error handling."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Handle exceptions and return properly formatted error responses.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response: HTTP response (success or error)
        """
        try:
            response = await call_next(request)
            return response
            
        except RequestValidationError as exc:
            error_response = ErrorHandler.handle_validation_error(exc)
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=error_response.model_dump()
            )
            
        except HTTPException as exc:
            error_response = ErrorHandler.handle_http_exception(exc)
            return JSONResponse(
                status_code=exc.status_code,
                content=error_response.model_dump()
            )
            
        except Exception as exc:
            error_response = ErrorHandler.handle_generic_exception(exc)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=error_response.model_dump()
            )


class InputValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for input sanitization and validation."""
    
    def __init__(self, app, sanitize_inputs: bool = True):
        """
        Initialize input validation middleware.
        
        Args:
            app: FastAPI application
            sanitize_inputs: Whether to sanitize text inputs
        """
        super().__init__(app)
        self.sanitize_inputs = sanitize_inputs
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Validate and sanitize inputs before processing.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response: HTTP response
        """
        # Skip validation for certain endpoints
        skip_paths = ["/docs", "/redoc", "/openapi.json", "/health"]
        if any(request.url.path.startswith(path) for path in skip_paths):
            return await call_next(request)
        
        # Validate content type for POST/PUT requests
        if request.method in ["POST", "PUT"]:
            content_type = request.headers.get("content-type", "")
            
            if content_type.startswith("application/json"):
                try:
                    body = await request.body()
                    if body:
                        # Validate JSON structure
                        json_data = json.loads(body.decode('utf-8'))
                        
                        # Sanitize text fields if enabled
                        if self.sanitize_inputs:
                            sanitized_data = self._sanitize_json_data(json_data)
                            
                            # Replace request body with sanitized data
                            sanitized_body = json.dumps(sanitized_data).encode('utf-8')
                            request._body = sanitized_body
                            
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in request to {request.url.path}")
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content=APIError(
                            error="invalid_json",
                            message="Request body contains invalid JSON"
                        ).model_dump()
                    )
                except Exception as e:
                    logger.error(f"Error processing request body: {e}")
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content=APIError(
                            error="request_processing_error",
                            message="Error processing request body"
                        ).model_dump()
                    )
        
        return await call_next(request)
    
    def _sanitize_json_data(self, data: Any) -> Any:
        """
        Recursively sanitize JSON data.
        
        Args:
            data: JSON data to sanitize
            
        Returns:
            Any: Sanitized data
        """
        if isinstance(data, dict):
            return {key: self._sanitize_json_data(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_json_data(item) for item in data]
        elif isinstance(data, str):
            try:
                return InputSanitizer.sanitize_text(data)
            except ValueError:
                # If sanitization fails, return original (will be caught by validation)
                return data
        else:
            return data


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Add security headers to responses.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response: HTTP response with security headers
        """
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Add custom headers
        response.headers["X-API-Version"] = "1.0.0"
        response.headers["X-Powered-By"] = "Melanie-AI"
        
        return response


# Utility functions for error handling
def create_error_response(
    error_type: str, 
    message: str, 
    status_code: int = 500,
    details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """
    Create standardized error response.
    
    Args:
        error_type: Type of error
        message: Error message
        status_code: HTTP status code
        details: Additional error details
        
    Returns:
        JSONResponse: Formatted error response
    """
    error = APIError(
        error=error_type,
        message=message,
        details=details
    )
    
    return JSONResponse(
        status_code=status_code,
        content=error.model_dump()
    )


def log_model_interaction(
    model_name: str,
    request_data: Dict[str, Any],
    response_data: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    duration: Optional[float] = None
):
    """
    Log AI model interactions for monitoring and debugging.
    
    Args:
        model_name: Name of the AI model
        request_data: Request data (sanitized)
        response_data: Response data (optional)
        error: Error message if request failed
        duration: Request duration in seconds
    """
    log_data = {
        "model": model_name,
        "timestamp": time.time(),
        "duration": duration,
        "success": error is None
    }
    
    if error:
        log_data["error"] = error
        logger.error(f"Model interaction failed: {json.dumps(log_data)}")
    else:
        # Log successful interactions at debug level to avoid spam
        logger.debug(f"Model interaction: {json.dumps(log_data)}")


def validate_request_size(request: Request, max_size: int = 10_000_000) -> bool:
    """
    Validate request size to prevent DoS attacks.
    
    Args:
        request: HTTP request
        max_size: Maximum allowed request size in bytes
        
    Returns:
        bool: True if request size is acceptable
    """
    content_length = request.headers.get("content-length")
    
    if content_length:
        try:
            size = int(content_length)
            return size <= max_size
        except ValueError:
            return False
    
    return True  # Allow requests without content-length header