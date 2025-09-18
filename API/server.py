"""
Melanie AI FastAPI Server with Tailscale Integration

This module implements the core FastAPI server for the Melanie AI ecosystem
with Tailscale network detection and security features.
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import List, Optional

import psutil
import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import authentication system
from auth import (
    api_key_manager, 
    api_key_auth, 
    APIKey, 
    CreateKeyResponse, 
    KeyInfoResponse,
    create_demo_key
)
from datetime import datetime
from fastapi import status

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TailscaleDetector:
    """Handles Tailscale network detection and IP resolution."""
    
    @staticmethod
    def get_tailscale_ip() -> Optional[str]:
        """
        Detect Tailscale IP address by looking for tailscale0 interface.
        
        Returns:
            str: Tailscale IP address if found, None otherwise
        """
        try:
            # Get all network interfaces
            interfaces = psutil.net_if_addrs()
            
            # Look for tailscale0 interface
            if 'tailscale0' in interfaces:
                for addr in interfaces['tailscale0']:
                    if addr.family == 2:  # AF_INET (IPv4)
                        logger.info(f"Found Tailscale IP: {addr.address}")
                        return addr.address
            
            # Alternative: Look for interfaces with Tailscale-like IPs (100.x.x.x range)
            for interface_name, addresses in interfaces.items():
                for addr in addresses:
                    if addr.family == 2 and addr.address.startswith('100.'):
                        logger.info(f"Found potential Tailscale IP on {interface_name}: {addr.address}")
                        return addr.address
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting Tailscale network: {e}")
            return None
    
    @staticmethod
    def is_tailscale_available() -> bool:
        """Check if Tailscale is available and running."""
        return TailscaleDetector.get_tailscale_ip() is not None


class ServerConfig:
    """Server configuration management with strict Tailscale-only enforcement."""
    
    def __init__(self):
        self.tailscale_ip = TailscaleDetector.get_tailscale_ip()
        self.port = int(os.getenv("API_PORT", "8000"))
        self.dev_mode = os.getenv("MELANIE_DEV_MODE", "false").lower() == "true"
        
        # SECURITY: Strict Tailscale-only binding - NO localhost fallback
        if not self.tailscale_ip:
            if self.dev_mode:
                # Development mode: simulate Tailscale IP but still enforce security model
                self.tailscale_ip = "100.64.0.1"  # Simulated Tailscale IP
                logger.warning("🔧 DEVELOPMENT MODE: Using simulated Tailscale IP")
                logger.warning("🔧 In production, this would be your actual Tailscale IP")
                logger.warning("🔧 Security model still enforced - no localhost access")
            else:
                logger.error("SECURITY ENFORCEMENT: No Tailscale IP detected")
                logger.error("This server REQUIRES Tailscale network access for security")
                logger.error("Please install and configure Tailscale before starting the server")
                logger.error("For development: export MELANIE_DEV_MODE=true")
                sys.exit(1)
        
        self.host = self.tailscale_ip  # ONLY bind to Tailscale IP (real or simulated)
        
    def get_cors_origins(self) -> List[str]:
        """Get allowed CORS origins - TAILSCALE ONLY, no localhost."""
        if not self.tailscale_ip:
            return []  # No origins allowed without Tailscale
        
        # SECURITY: Only allow Tailscale IP origins - NO localhost/127.0.0.1
        origins = [
            f"http://{self.tailscale_ip}:3000",
            f"http://{self.tailscale_ip}:8000",
            f"https://{self.tailscale_ip}:3000",
            f"https://{self.tailscale_ip}:8000",
        ]
        
        logger.info(f"CORS restricted to Tailscale-only origins: {origins}")
        return origins


# Global server configuration
server_config = ServerConfig()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager with STRICT Tailscale-only enforcement.
    
    SECURITY POLICY:
    - Server ONLY runs on Tailscale network
    - NO localhost/127.0.0.1 access allowed
    - Fails immediately if Tailscale not available
    """
    # Startup
    logger.info("🔒 Starting Melanie AI API Server with STRICT Tailscale-only security...")
    
    # CRITICAL SECURITY CHECK: Tailscale MUST be available
    tailscale_ip = TailscaleDetector.get_tailscale_ip()
    if not tailscale_ip:
        logger.error("🚨 SECURITY ENFORCEMENT FAILURE: Tailscale network not detected")
        logger.error("🚨 This server REQUIRES Tailscale for network-level security")
        logger.error("🚨 NO localhost or public internet access is permitted")
        logger.error("🚨 Please install Tailscale and join your tailnet before starting")
        logger.error("🚨 Visit: https://tailscale.com/download")
        sys.exit(1)
    
    logger.info(f"🔒 SECURITY: Tailscale network detected - IP: {tailscale_ip}")
    logger.info(f"🔒 SECURITY: Server binding EXCLUSIVELY to Tailscale IP: {server_config.host}:{server_config.port}")
    logger.info(f"🔒 SECURITY: NO localhost (127.0.0.1) access permitted")
    logger.info(f"🔒 SECURITY: Access only via: http://{tailscale_ip}:{server_config.port}")
    
    # Create a demo API key for testing
    demo_key = create_demo_key()
    logger.info(f"🔑 Demo API key created: {demo_key}")
    logger.info(f"🔑 Use this key in Authorization header: Bearer {demo_key}")
    logger.info(f"🌐 API Documentation: http://{tailscale_ip}:{server_config.port}/docs")
    
    logger.info("✅ Server startup complete with Tailscale-only security enforced")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Melanie AI API Server...")
    logger.info("✅ Cleanup complete. Server stopped.")


# Create FastAPI application
app = FastAPI(
    title="Melanie AI API",
    description="Unified AI platform with multi-model integration and advanced orchestration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=server_config.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include MCP router if available (will be added after MCP imports)

# Configure enhanced error handling and logging middleware
try:
    from middleware import (
        ErrorHandlingMiddleware,
        LoggingMiddleware,
        InputValidationMiddleware,
        SecurityHeadersMiddleware
    )
    
    # Add middleware in reverse order (last added = first executed)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(InputValidationMiddleware, sanitize_inputs=True)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(ErrorHandlingMiddleware)
    
    logger.info("Enhanced middleware configured successfully")
    
except ImportError as e:
    logger.warning(f"Could not import enhanced middleware: {e}")
    logger.warning("Running with basic error handling only")


# Health check models
class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    message: str
    tailscale_ip: Optional[str]
    server_info: dict


# Basic endpoints
@app.get("/")
async def root():
    """Root endpoint with basic server information."""
    return {
        "message": "Melanie AI API Server",
        "version": "1.0.0",
        "status": "running",
        "tailscale_ip": server_config.tailscale_ip
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for monitoring and validation.
    
    Returns:
        HealthResponse: Server health status and configuration
    """
    return HealthResponse(
        status="healthy",
        message="Melanie AI API Server is running",
        tailscale_ip=server_config.tailscale_ip,
        server_info={
            "host": server_config.host,
            "port": server_config.port,
            "tailscale_available": TailscaleDetector.is_tailscale_available(),
            "cors_origins": server_config.get_cors_origins()
        }
    )


@app.get("/health/detailed")
async def detailed_health_check():
    """
    Comprehensive health check endpoint with detailed component status.
    
    Returns:
        SystemHealth: Detailed system health information
    """
    try:
        from health_monitor import health_monitor
        return await health_monitor.get_system_health()
    except ImportError:
        logger.warning("Health monitor not available, falling back to basic health check")
        return {
            "status": "degraded",
            "message": "Detailed health monitoring not available",
            "timestamp": datetime.utcnow().isoformat(),
            "components": [],
            "system_info": {},
            "performance_metrics": {},
            "uptime_seconds": 0
        }


@app.get("/health/component/{component_name}")
async def component_health_check(component_name: str):
    """
    Health check for a specific system component.
    
    Args:
        component_name: Name of the component to check
        
    Returns:
        ComponentHealth: Health status of the specified component
    """
    try:
        from health_monitor import health_monitor
        
        component_health = await health_monitor.get_component_health(component_name)
        if component_health:
            return component_health
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Component '{component_name}' not found. Available components: {health_monitor.get_available_components()}"
            )
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health monitoring system not available"
        )


@app.get("/health/errors")
async def error_statistics():
    """
    Get error statistics and monitoring information.
    
    Returns:
        dict: Error statistics and fallback information
    """
    try:
        from middleware import ErrorHandler, fallback_manager
        
        error_stats = ErrorHandler.get_error_stats()
        fallback_stats = fallback_manager.get_fallback_stats()
        
        return {
            "error_statistics": error_stats,
            "fallback_statistics": fallback_stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except ImportError:
        return {
            "error": "Error monitoring not available",
            "timestamp": datetime.utcnow().isoformat()
        }


@app.get("/health/performance")
async def performance_metrics():
    """
    Get performance metrics and system statistics.
    
    Returns:
        dict: Performance metrics and system resource usage
    """
    try:
        import psutil
        
        # CPU and memory metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('.')
        
        # Network statistics
        network = psutil.net_io_counters()
        
        # Process information
        process = psutil.Process()
        process_memory = process.memory_info()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "cpu": {
                "percent": cpu_percent,
                "count": psutil.cpu_count()
            },
            "memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "percent": memory.percent
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent": round((disk.used / disk.total) * 100, 1)
            },
            "network": {
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv
            } if network else None,
            "process": {
                "memory_mb": round(process_memory.rss / (1024**2), 2),
                "cpu_percent": process.cpu_percent(),
                "threads": process.num_threads(),
                "connections": len(process.connections())
            }
        }
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        return {
            "error": f"Failed to get performance metrics: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }


@app.get("/tailscale/status")
async def tailscale_status():
    """
    Tailscale network status endpoint.
    
    Returns:
        dict: Tailscale network information
    """
    tailscale_ip = TailscaleDetector.get_tailscale_ip()
    
    return {
        "tailscale_available": tailscale_ip is not None,
        "tailscale_ip": tailscale_ip,
        "network_interfaces": {
            name: [
                {"address": addr.address, "family": addr.family}
                for addr in addresses
                if addr.family == 2  # IPv4 only
            ]
            for name, addresses in psutil.net_if_addrs().items()
            if any(addr.family == 2 for addr in addresses)
        }
    }


# Authentication endpoints
@app.post("/auth/keys", response_model=CreateKeyResponse)
async def create_api_key():
    """
    Create a new API key with mel_ prefix.
    
    Returns:
        CreateKeyResponse: New API key information
    """
    raw_key, api_key = api_key_manager.create_api_key()
    
    return CreateKeyResponse(
        api_key=raw_key,
        key_id=api_key.key_id,
        message="API key created successfully. Store this key securely - it cannot be retrieved again.",
        rate_limit=api_key.rate_limit
    )


@app.get("/auth/keys/{key_id}", response_model=KeyInfoResponse)
async def get_key_info(key_id: str, current_key: APIKey = Depends(api_key_auth)):
    """
    Get information about an API key.
    
    Args:
        key_id: API key identifier
        current_key: Current authenticated API key
        
    Returns:
        KeyInfoResponse: API key information
    """
    # Users can only view their own key info
    if current_key.key_id != key_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view information about your own API key."
        )
    
    api_key = api_key_manager.get_key_info(key_id)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found."
        )
    
    return KeyInfoResponse(
        key_id=api_key.key_id,
        created_at=api_key.created_at,
        last_used=api_key.last_used,
        is_active=api_key.is_active,
        rate_limit=api_key.rate_limit
    )


@app.delete("/auth/keys/{key_id}")
async def deactivate_key(key_id: str, current_key: APIKey = Depends(api_key_auth)):
    """
    Deactivate an API key.
    
    Args:
        key_id: API key identifier to deactivate
        current_key: Current authenticated API key
        
    Returns:
        dict: Deactivation confirmation
    """
    # Users can only deactivate their own keys
    if current_key.key_id != key_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only deactivate your own API key."
        )
    
    success = api_key_manager.deactivate_key(key_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found."
        )
    
    return {
        "message": f"API key {key_id} has been deactivated.",
        "key_id": key_id,
        "deactivated_at": datetime.utcnow().isoformat()
    }


# Import additional dependencies for chat completions
import uuid
from typing import Dict, Any, Optional
from fastapi import Request

# Import model classes and orchestration
try:
    from models import (
        ChatCompletionRequest, 
        ChatCompletionResponse, 
        ChatMessage,
        MessageRole,
        ModelType,
        APIError,
        RequestValidator
    )
    from tools import ToolManager, ToolType
    from research_orchestrator import DeepResearchOrchestrator
    
    # Import AI models
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'AI'))
    from melanie_three_model import MelanieThree
    from melanie_three_light_model import MelanieThreeLight
    from melanie_three_code_model import MelanieThreeCode
    from rag_integration_client import RagIntegrationClient
    
    MODELS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import model dependencies: {e}")
    MODELS_AVAILABLE = False
    
    # Create placeholder classes
    class ChatCompletionRequest:
        pass
    class ChatCompletionResponse:
        pass
    class ToolManager:
        pass
    class DeepResearchOrchestrator:
        pass
    class RagIntegrationClient:
        pass

# Import MCP integration
try:
    from mcp_endpoints import mcp_router
    from mcp_config import get_mcp_config_manager
    from mcp_integration import get_mcp_manager
    
    MCP_AVAILABLE = True
    logger.info("MCP integration loaded successfully")
    
    # Include MCP router
    app.include_router(mcp_router)
    logger.info("MCP endpoints registered successfully")
    
except ImportError as e:
    logger.warning(f"Could not import MCP dependencies: {e}")
    MCP_AVAILABLE = False


# Global instances for model management
model_instances: Dict[str, Any] = {}
tool_manager: Optional[Any] = None
research_orchestrator: Optional[Any] = None
rag_client: Optional[Any] = None


async def get_model_instance(model_type: str):
    """Get or create model instance."""
    global model_instances
    
    if not MODELS_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI models not available"
        )
    
    if model_type not in model_instances:
        try:
            if model_type == "Melanie-3":
                model_instances[model_type] = MelanieThree()
            elif model_type == "Melanie-3-light":
                model_instances[model_type] = MelanieThreeLight()
            elif model_type == "Melanie-3-code":
                model_instances[model_type] = MelanieThreeCode()
            else:
                raise ValueError(f"Unknown model type: {model_type}")
        except Exception as e:
            logger.error(f"Failed to initialize model {model_type}: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Model {model_type} initialization failed"
            )
    
    return model_instances[model_type]


async def get_tool_manager():
    """Get or create tool manager instance."""
    global tool_manager
    
    if tool_manager is None:
        tool_manager = ToolManager()
    
    return tool_manager


async def get_research_orchestrator():
    """Get or create research orchestrator instance."""
    global research_orchestrator
    
    if research_orchestrator is None:
        research_orchestrator = DeepResearchOrchestrator()
    
    return research_orchestrator


async def get_rag_client():
    """Get or create RAG client instance."""
    global rag_client
    
    if rag_client is None:
        try:
            rag_client = RagIntegrationClient()
        except Exception as e:
            logger.warning(f"RAG client initialization failed: {e}")
            rag_client = None
    
    return rag_client


async def inject_rag_context(messages: List[ChatMessage], model_type: str) -> List[ChatMessage]:
    """
    Inject RAG context for all requests.
    
    Args:
        messages: Original chat messages
        model_type: Model type for context mode selection
        
    Returns:
        List[ChatMessage]: Messages with RAG context injected
    """
    try:
        rag_client = await get_rag_client()
        
        if not rag_client:
            logger.debug("RAG client not available, proceeding without context")
            return messages
        
        # Extract query from the last user message
        user_messages = [msg for msg in messages if msg.role == MessageRole.USER]
        if not user_messages:
            return messages
        
        query = user_messages[-1].content
        
        # Determine context mode based on model and query complexity
        context_mode = "research" if len(query) > 100 else "general"
        
        # Get context chunks
        context_chunks = await rag_client.get_context(query, mode=context_mode)
        
        if not context_chunks:
            logger.debug("No relevant context found")
            return messages
        
        # Create context content
        context_content = "## Relevant Context\n\n"
        for i, chunk in enumerate(context_chunks[:10], 1):  # Limit to top 10 chunks
            context_content += f"### Context {i}\n{chunk['content']}\n\n"
        
        # Inject context before the last user message
        enhanced_messages = messages[:-1]  # All messages except the last
        
        # Add context as system message
        context_message = ChatMessage(
            role=MessageRole.SYSTEM,
            content=f"Use the following context to enhance your response:\n\n{context_content}"
        )
        enhanced_messages.append(context_message)
        
        # Add the original last message
        enhanced_messages.append(messages[-1])
        
        logger.info(f"Injected {len(context_chunks)} context chunks for query")
        return enhanced_messages
        
    except Exception as e:
        logger.error(f"RAG context injection failed: {e}")
        # Return original messages if context injection fails
        return messages


# Chat completions endpoint
@app.post("/chat/completions")
async def chat_completions(
    request: Dict[str, Any],
    current_key: APIKey = Depends(api_key_auth)
):
    """
    Create a chat completion using the specified model.
    
    Implements requirements 2.1 and 2.2:
    - Accept JSON with 'model', 'messages', optional 'tools', and 'web_search' parameters
    - Return responses in standard OpenAI format with custom fields like 'research_plan'
    
    Args:
        request: Chat completion request
        current_key: Authenticated API key
        
    Returns:
        ChatCompletionResponse: Generated response with optional research plan
    """
    try:
        if not MODELS_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI models not available"
            )
        
        # Validate request
        try:
            validated_request = RequestValidator.validate_chat_request(request)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        
        # Get model instance
        model = await get_model_instance(validated_request.model)
        
        # Inject RAG context for all requests
        enhanced_messages = await inject_rag_context(validated_request.messages, validated_request.model)
        
        # Check if this is a deep research request
        is_research_request = (
            validated_request.web_search and 
            len(validated_request.messages) > 0 and
            len(validated_request.messages[-1].content) > 50 and
            any(keyword in validated_request.messages[-1].content.lower() 
                for keyword in ["research", "analyze", "investigate", "comprehensive", "detailed"])
        )
        
        research_plan = None
        
        if is_research_request:
            # Handle deep research orchestration
            try:
                orchestrator = await get_research_orchestrator()
                
                # Generate research plan
                query = validated_request.messages[-1].content
                plan = await orchestrator.generate_research_plan(query)
                
                # Convert plan to dict for response
                research_plan = {
                    "id": plan.id,
                    "title": plan.title,
                    "description": plan.description,
                    "subtasks": [
                        {
                            "id": subtask.id,
                            "title": subtask.title,
                            "description": subtask.description,
                            "estimated_duration": subtask.estimated_duration,
                            "tools_required": subtask.tools_required
                        }
                        for subtask in plan.subtasks
                    ],
                    "estimated_agents": plan.estimated_agents,
                    "estimated_duration": plan.estimated_duration
                }
                
                logger.info(f"Generated research plan for query: {query[:100]}...")
                
            except Exception as e:
                logger.error(f"Research plan generation failed: {e}")
                # Continue with regular chat completion if research planning fails
        
        # Handle tool calling with automatic selection
        available_tools = None
        if validated_request.tools or validated_request.web_search:
            try:
                tool_manager = await get_tool_manager()
                available_tools = tool_manager.get_available_tools(validated_request.model, validated_request.web_search)
                
                # Convert tools to the format expected by the model
                if available_tools:
                    tool_schemas = []
                    for tool_type in available_tools:
                        tool = tool_manager.tools.get(tool_type)
                        if tool:
                            tool_schemas.append(tool.get_schema())
                    
                    # Update request with available tools
                    if tool_schemas:
                        validated_request.tools = tool_schemas
                
            except Exception as e:
                logger.error(f"Tool setup failed: {e}")
                # Continue without tools if setup fails
        
        # Generate response using the model
        try:
            response = await model.generate(
                messages=enhanced_messages,
                tools=validated_request.tools,
                max_tokens=validated_request.max_tokens,
                temperature=validated_request.temperature,
                top_p=validated_request.top_p,
                stream=validated_request.stream
            )
            
            # Add research plan to response if generated
            if research_plan:
                response.research_plan = research_plan
            
            logger.info(f"Generated chat completion using {validated_request.model}")
            return response
            
        except Exception as e:
            logger.error(f"Model generation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Model generation failed: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


# Import file management system
try:
    from file_manager import file_manager, FileProcessingResult
    from fastapi import File, UploadFile, Query
    from fastapi.responses import Response
    FILES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import file management dependencies: {e}")
    FILES_AVAILABLE = False


# Files API endpoints
@app.post("/files")
async def upload_file(
    file: UploadFile = File(...),
    current_key: APIKey = Depends(api_key_auth)
):
    """
    Upload a file for processing.
    
    Implements requirements 2.3 and 2.4:
    - Provide /files endpoints for POST uploads
    - Auto-process TXT/MD files via RAG ingestion
    - Store PDF/image metadata for multimodal processing
    
    Args:
        file: File to upload
        current_key: Authenticated API key
        
    Returns:
        dict: Upload result with file information
    """
    try:
        if not FILES_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="File management system not available"
            )
        
        # Upload and process file
        file_id, file_info = await file_manager.upload_file(file)
        
        # Prepare response
        response_data = {
            "id": file_id,
            "filename": file_info.filename,
            "content_type": file_info.content_type,
            "size": file_info.size,
            "uploaded_at": file_info.uploaded_at.isoformat(),
            "processed": file_info.processed,
            "rag_ingested": file_info.rag_ingested,
            "message": "File uploaded successfully"
        }
        
        # Add processing status
        if file_info.rag_ingested:
            response_data["processing_status"] = "Auto-processed through RAG system"
        elif file_info.processed:
            response_data["processing_status"] = "Metadata extracted for multimodal processing"
        else:
            response_data["processing_status"] = "File stored, no automatic processing applied"
        
        logger.info(f"File uploaded successfully: {file_id} by key {current_key.key_id}")
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}"
        )


@app.get("/files/{file_id}")
async def get_file(
    file_id: str,
    download: bool = Query(False, description="Download file content"),
    current_key: APIKey = Depends(api_key_auth)
):
    """
    Get file information or download file content.
    
    Implements requirement 2.3:
    - Provide /files endpoints for GET retrieval
    
    Args:
        file_id: File identifier
        download: Whether to download file content
        current_key: Authenticated API key
        
    Returns:
        File information or file content
    """
    try:
        if not FILES_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="File management system not available"
            )
        
        # Get file information
        file_info = file_manager.get_file_info(file_id)
        if not file_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        if download:
            # Download file content
            content = file_manager.get_file_content(file_id)
            if content is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File content not found"
                )
            
            # Return file content with appropriate headers
            return Response(
                content=content,
                media_type=file_info.content_type,
                headers={
                    "Content-Disposition": f"attachment; filename={file_info.filename}",
                    "Content-Length": str(len(content))
                }
            )
        else:
            # Return file information
            return {
                "id": file_info.id,
                "filename": file_info.filename,
                "content_type": file_info.content_type,
                "size": file_info.size,
                "uploaded_at": file_info.uploaded_at.isoformat(),
                "processed": file_info.processed,
                "rag_ingested": file_info.rag_ingested
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File retrieval failed for {file_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File retrieval failed: {str(e)}"
        )


@app.delete("/files/{file_id}")
async def delete_file(
    file_id: str,
    current_key: APIKey = Depends(api_key_auth)
):
    """
    Delete a file and its associated data.
    
    Implements requirement 2.3:
    - Provide /files endpoints for DELETE operations
    
    Args:
        file_id: File identifier
        current_key: Authenticated API key
        
    Returns:
        dict: Deletion confirmation
    """
    try:
        if not FILES_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="File management system not available"
            )
        
        # Check if file exists
        file_info = file_manager.get_file_info(file_id)
        if not file_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Delete file
        success = file_manager.delete_file(file_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete file"
            )
        
        logger.info(f"File deleted successfully: {file_id} by key {current_key.key_id}")
        return {
            "message": f"File {file_id} deleted successfully",
            "file_id": file_id,
            "filename": file_info.filename,
            "deleted_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File deletion failed for {file_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File deletion failed: {str(e)}"
        )


@app.get("/files")
async def list_files(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of files to return"),
    offset: int = Query(0, ge=0, description="Number of files to skip"),
    current_key: APIKey = Depends(api_key_auth)
):
    """
    List uploaded files with pagination.
    
    Args:
        limit: Maximum number of files to return
        offset: Number of files to skip
        current_key: Authenticated API key
        
    Returns:
        dict: List of files with pagination info
    """
    try:
        if not FILES_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="File management system not available"
            )
        
        # Get files list
        files = file_manager.list_files(limit=limit, offset=offset)
        
        # Convert to response format
        files_data = []
        for file_info in files:
            files_data.append({
                "id": file_info.id,
                "filename": file_info.filename,
                "content_type": file_info.content_type,
                "size": file_info.size,
                "uploaded_at": file_info.uploaded_at.isoformat(),
                "processed": file_info.processed,
                "rag_ingested": file_info.rag_ingested
            })
        
        # Get storage statistics
        stats = file_manager.get_storage_stats()
        
        return {
            "files": files_data,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total_files": stats["total_files"],
                "has_more": offset + limit < stats["total_files"]
            },
            "storage_stats": {
                "total_files": stats["total_files"],
                "total_size_mb": stats["total_size_mb"],
                "processed_files": stats["processed_files"],
                "rag_ingested_files": stats["rag_ingested_files"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File listing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File listing failed: {str(e)}"
        )


# Protected endpoint example
@app.get("/protected")
async def protected_endpoint(current_key: APIKey = Depends(api_key_auth)):
    """
    Example protected endpoint that requires authentication.
    
    Args:
        current_key: Authenticated API key
        
    Returns:
        dict: Protected resource information
    """
    return {
        "message": "This is a protected endpoint",
        "authenticated_key": current_key.key_id,
        "last_used": current_key.last_used.isoformat() if current_key.last_used else None,
        "rate_limit": current_key.rate_limit
    }


def main():
    """Main entry point for running the server."""
    # Validate Tailscale before starting
    if not TailscaleDetector.is_tailscale_available():
        logger.error("Tailscale network not detected!")
        logger.error("This server requires Tailscale for network security.")
        logger.error("Please install and start Tailscale, then try again.")
        sys.exit(1)
    
    # Run the server
    uvicorn.run(
        "server:app",
        host=server_config.host,
        port=server_config.port,
        reload=False,  # Disable reload in production
        log_level="info",
        access_log=True
    )


if __name__ == "__main__":
    main()