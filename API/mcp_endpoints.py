"""
MCP API Endpoints for Melanie AI

This module provides REST API endpoints for accessing MCP (Model Context Protocol)
integrations, allowing clients to query current documentation, security guidelines,
performance recommendations, and version information.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field

from auth import APIKey, api_key_auth
from mcp_integration import (
    MCPIntegrationManager, 
    MCPResult, 
    MCPToolType,
    get_mcp_manager
)
from mcp_config import get_mcp_config_manager, MCPConfigManager

logger = logging.getLogger(__name__)

# Create router for MCP endpoints
mcp_router = APIRouter(prefix="/mcp", tags=["MCP Integration"])


# Request/Response Models
class DocumentationQueryRequest(BaseModel):
    """Request model for documentation queries."""
    technology: str = Field(..., description="Technology name (e.g., fastapi, rust, python)")
    topic: str = Field(..., description="Specific topic or feature")
    version: Optional[str] = Field(None, description="Optional version specification")


class SecurityQueryRequest(BaseModel):
    """Request model for security guideline queries."""
    technology: str = Field(..., description="Technology or framework name")
    category: str = Field(default="general", description="Security category (auth, crypto, web, etc.)")


class PerformanceQueryRequest(BaseModel):
    """Request model for performance recommendation queries."""
    technology: str = Field(..., description="Technology name")
    use_case: str = Field(..., description="Specific use case or scenario")


class VersionCheckRequest(BaseModel):
    """Request model for version checking."""
    packages: List[str] = Field(..., description="List of package names to check")


class VulnerabilityCheckRequest(BaseModel):
    """Request model for vulnerability checking."""
    dependencies: List[Dict[str, str]] = Field(
        ..., 
        description="List of dependencies with name and version",
        example=[{"name": "fastapi", "version": "0.104.1"}]
    )


class IssueTrackerQueryRequest(BaseModel):
    """Request model for issue tracker queries."""
    technology: str = Field(..., description="Technology name")
    issue_type: str = Field(..., description="Type of issue (bug, feature, documentation)")
    keywords: List[str] = Field(..., description="Keywords to search for")


class BestPracticesQueryRequest(BaseModel):
    """Request model for best practices queries."""
    technology: str = Field(..., description="Technology name")
    domain: str = Field(..., description="Domain or area (architecture, security, performance)")


class MCPResultResponse(BaseModel):
    """Response model for MCP query results."""
    query_id: str
    tool_type: str
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    source: Optional[str] = None
    timestamp: datetime
    cached: bool = False


class MCPQueryHistoryResponse(BaseModel):
    """Response model for MCP query history."""
    queries: List[Dict[str, Any]]
    total_count: int
    cache_stats: Dict[str, Any]


class MCPConfigResponse(BaseModel):
    """Response model for MCP configuration."""
    servers: Dict[str, Dict[str, Any]]
    enabled_servers: List[str]
    disabled_servers: List[str]
    global_timeout: int
    cache_ttl: int


# Documentation Endpoints
@mcp_router.post("/documentation", response_model=MCPResultResponse)
async def query_documentation(
    request: DocumentationQueryRequest,
    current_key: APIKey = Depends(api_key_auth),
    mcp_manager: MCPIntegrationManager = Depends(get_mcp_manager)
):
    """
    Query current technical documentation for a specific technology and topic.
    
    Implements Requirement 12.1: Access current official documentation
    """
    try:
        result = await mcp_manager.query_documentation(
            technology=request.technology,
            topic=request.topic,
            version=request.version
        )
        
        return MCPResultResponse(
            query_id=result.query_id,
            tool_type=result.tool_type.value,
            success=result.success,
            data=result.data,
            error=result.error,
            source=result.source,
            timestamp=result.timestamp
        )
        
    except Exception as e:
        logger.error(f"Documentation query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Documentation query failed: {str(e)}"
        )


@mcp_router.get("/documentation/{technology}/{topic}")
async def get_documentation(
    technology: str,
    topic: str,
    version: Optional[str] = Query(None),
    current_key: APIKey = Depends(api_key_auth),
    mcp_manager: MCPIntegrationManager = Depends(get_mcp_manager)
):
    """
    Get documentation via GET request for easier integration.
    
    Alternative endpoint for documentation queries using path parameters.
    """
    try:
        result = await mcp_manager.query_documentation(
            technology=technology,
            topic=topic,
            version=version
        )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.error or "Documentation not found"
            )
        
        return result.data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Documentation retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Documentation retrieval failed: {str(e)}"
        )


# Security Endpoints
@mcp_router.post("/security/guidelines", response_model=MCPResultResponse)
async def query_security_guidelines(
    request: SecurityQueryRequest,
    current_key: APIKey = Depends(api_key_auth),
    mcp_manager: MCPIntegrationManager = Depends(get_mcp_manager)
):
    """
    Query current security guidelines for a technology.
    
    Implements Requirement 12.2: Query current security guidelines and vulnerability databases
    """
    try:
        result = await mcp_manager.query_security_guidelines(
            technology=request.technology,
            category=request.category
        )
        
        return MCPResultResponse(
            query_id=result.query_id,
            tool_type=result.tool_type.value,
            success=result.success,
            data=result.data,
            error=result.error,
            source=result.source,
            timestamp=result.timestamp
        )
        
    except Exception as e:
        logger.error(f"Security guidelines query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Security guidelines query failed: {str(e)}"
        )


@mcp_router.post("/security/vulnerabilities", response_model=MCPResultResponse)
async def check_vulnerabilities(
    request: VulnerabilityCheckRequest,
    current_key: APIKey = Depends(api_key_auth),
    mcp_manager: MCPIntegrationManager = Depends(get_mcp_manager)
):
    """
    Check for known vulnerabilities in project dependencies.
    
    Implements Requirement 12.2: Query vulnerability databases
    """
    try:
        result = await mcp_manager.check_vulnerabilities(request.dependencies)
        
        return MCPResultResponse(
            query_id=result.query_id,
            tool_type=result.tool_type.value,
            success=result.success,
            data=result.data,
            error=result.error,
            source=result.source,
            timestamp=result.timestamp
        )
        
    except Exception as e:
        logger.error(f"Vulnerability check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vulnerability check failed: {str(e)}"
        )


# Performance Endpoints
@mcp_router.post("/performance/recommendations", response_model=MCPResultResponse)
async def get_performance_recommendations(
    request: PerformanceQueryRequest,
    current_key: APIKey = Depends(api_key_auth),
    mcp_manager: MCPIntegrationManager = Depends(get_mcp_manager)
):
    """
    Get current performance recommendations and benchmarks.
    
    Implements Requirement 12.3: Retrieve latest performance recommendations and benchmarks
    """
    try:
        result = await mcp_manager.get_performance_recommendations(
            technology=request.technology,
            use_case=request.use_case
        )
        
        return MCPResultResponse(
            query_id=result.query_id,
            tool_type=result.tool_type.value,
            success=result.success,
            data=result.data,
            error=result.error,
            source=result.source,
            timestamp=result.timestamp
        )
        
    except Exception as e:
        logger.error(f"Performance recommendations query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Performance recommendations query failed: {str(e)}"
        )


# Version and Compatibility Endpoints
@mcp_router.post("/versions/check", response_model=MCPResultResponse)
async def check_versions(
    request: VersionCheckRequest,
    current_key: APIKey = Depends(api_key_auth),
    mcp_manager: MCPIntegrationManager = Depends(get_mcp_manager)
):
    """
    Check current release information and compatibility matrices.
    
    Implements Requirement 12.4: Check current release information and compatibility matrices
    """
    try:
        result = await mcp_manager.check_versions_and_compatibility(request.packages)
        
        return MCPResultResponse(
            query_id=result.query_id,
            tool_type=result.tool_type.value,
            success=result.success,
            data=result.data,
            error=result.error,
            source=result.source,
            timestamp=result.timestamp
        )
        
    except Exception as e:
        logger.error(f"Version check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Version check failed: {str(e)}"
        )


# API Documentation Endpoints
@mcp_router.get("/api-docs/{api_name}")
async def get_api_documentation(
    api_name: str,
    endpoint: Optional[str] = Query(None),
    current_key: APIKey = Depends(api_key_auth),
    mcp_manager: MCPIntegrationManager = Depends(get_mcp_manager)
):
    """
    Access current API documentation and framework updates.
    
    Implements Requirement 12.5: Access current API documentation and framework updates
    """
    try:
        result = await mcp_manager.get_api_documentation(api_name, endpoint)
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.error or "API documentation not found"
            )
        
        return result.data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API documentation query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"API documentation query failed: {str(e)}"
        )


# Issue Tracker Endpoints
@mcp_router.post("/issues/search", response_model=MCPResultResponse)
async def search_issue_trackers(
    request: IssueTrackerQueryRequest,
    current_key: APIKey = Depends(api_key_auth),
    mcp_manager: MCPIntegrationManager = Depends(get_mcp_manager)
):
    """
    Consult current issue trackers, forums, and knowledge bases.
    
    Implements Requirement 12.6: Consult current issue trackers, forums, and knowledge bases
    """
    try:
        result = await mcp_manager.consult_issue_trackers(
            technology=request.technology,
            issue_type=request.issue_type,
            keywords=request.keywords
        )
        
        return MCPResultResponse(
            query_id=result.query_id,
            tool_type=result.tool_type.value,
            success=result.success,
            data=result.data,
            error=result.error,
            source=result.source,
            timestamp=result.timestamp
        )
        
    except Exception as e:
        logger.error(f"Issue tracker search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Issue tracker search failed: {str(e)}"
        )


# Best Practices Endpoints
@mcp_router.post("/best-practices", response_model=MCPResultResponse)
async def get_best_practices(
    request: BestPracticesQueryRequest,
    current_key: APIKey = Depends(api_key_auth),
    mcp_manager: MCPIntegrationManager = Depends(get_mcp_manager)
):
    """
    Reference current best practices and design patterns.
    
    Implements Requirement 12.7: Reference current best practices and design patterns
    """
    try:
        result = await mcp_manager.get_best_practices(
            technology=request.technology,
            domain=request.domain
        )
        
        return MCPResultResponse(
            query_id=result.query_id,
            tool_type=result.tool_type.value,
            success=result.success,
            data=result.data,
            error=result.error,
            source=result.source,
            timestamp=result.timestamp
        )
        
    except Exception as e:
        logger.error(f"Best practices query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Best practices query failed: {str(e)}"
        )


# Management Endpoints
@mcp_router.get("/history", response_model=MCPQueryHistoryResponse)
async def get_query_history(
    limit: int = Query(50, ge=1, le=200),
    current_key: APIKey = Depends(api_key_auth),
    mcp_manager: MCPIntegrationManager = Depends(get_mcp_manager)
):
    """Get recent MCP query history and cache statistics."""
    try:
        history = mcp_manager.get_query_history(limit)
        cache_stats = mcp_manager.get_cache_stats()
        
        return MCPQueryHistoryResponse(
            queries=[
                {
                    "query_id": q.query_id,
                    "tool_type": q.tool_type.value,
                    "query": q.query,
                    "context": q.context,
                    "timestamp": q.timestamp.isoformat(),
                    "priority": q.priority
                }
                for q in history
            ],
            total_count=len(history),
            cache_stats=cache_stats
        )
        
    except Exception as e:
        logger.error(f"Failed to get query history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get query history: {str(e)}"
        )


@mcp_router.get("/config", response_model=MCPConfigResponse)
async def get_mcp_configuration(
    current_key: APIKey = Depends(api_key_auth),
    config_manager: MCPConfigManager = Depends(get_mcp_config_manager)
):
    """Get current MCP configuration and server status."""
    try:
        config = config_manager.load_config()
        enabled_servers = [name for name, server in config.servers.items() if not server.disabled]
        disabled_servers = [name for name, server in config.servers.items() if server.disabled]
        
        return MCPConfigResponse(
            servers={
                name: {
                    "command": server.command,
                    "args": server.args,
                    "disabled": server.disabled,
                    "auto_approve": server.auto_approve,
                    "timeout": server.timeout
                }
                for name, server in config.servers.items()
            },
            enabled_servers=enabled_servers,
            disabled_servers=disabled_servers,
            global_timeout=config.global_timeout,
            cache_ttl=config.cache_ttl
        )
        
    except Exception as e:
        logger.error(f"Failed to get MCP configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get MCP configuration: {str(e)}"
        )


@mcp_router.post("/cache/clear")
async def clear_mcp_cache(
    current_key: APIKey = Depends(api_key_auth),
    mcp_manager: MCPIntegrationManager = Depends(get_mcp_manager)
):
    """Clear MCP cache."""
    try:
        mcp_manager.clear_cache()
        
        return {
            "message": "MCP cache cleared successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to clear MCP cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear MCP cache: {str(e)}"
        )


@mcp_router.get("/health")
async def mcp_health_check(
    current_key: APIKey = Depends(api_key_auth),
    config_manager: MCPConfigManager = Depends(get_mcp_config_manager),
    mcp_manager: MCPIntegrationManager = Depends(get_mcp_manager)
):
    """Health check for MCP integration system."""
    try:
        config = config_manager.load_config()
        enabled_servers = config_manager.get_enabled_servers()
        cache_stats = mcp_manager.get_cache_stats()
        
        # Validate configuration
        config_issues = config_manager.validate_config()
        
        health_status = {
            "status": "healthy" if not config_issues else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "servers": {
                "total": len(config.servers),
                "enabled": len(enabled_servers),
                "disabled": len(config.servers) - len(enabled_servers)
            },
            "cache": cache_stats,
            "configuration": {
                "valid": len(config_issues) == 0,
                "issues": config_issues
            }
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"MCP health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }