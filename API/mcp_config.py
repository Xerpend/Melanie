"""
MCP Configuration Management for Melanie AI

This module handles configuration and setup for MCP (Model Context Protocol) integrations,
including tool registration, authentication, and connection management.
"""

import json
import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    name: str
    command: str
    args: List[str]
    env: Dict[str, str]
    disabled: bool = False
    auto_approve: List[str] = None
    timeout: int = 30
    retry_attempts: int = 3
    
    def __post_init__(self):
        if self.auto_approve is None:
            self.auto_approve = []


@dataclass
class MCPIntegrationConfig:
    """Main configuration for MCP integrations."""
    servers: Dict[str, MCPServerConfig]
    global_timeout: int = 60
    cache_ttl: int = 3600
    enable_logging: bool = True
    log_level: str = "INFO"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPIntegrationConfig':
        """Create configuration from dictionary."""
        servers = {}
        
        if "mcpServers" in data:
            for name, server_data in data["mcpServers"].items():
                servers[name] = MCPServerConfig(
                    name=name,
                    command=server_data.get("command", ""),
                    args=server_data.get("args", []),
                    env=server_data.get("env", {}),
                    disabled=server_data.get("disabled", False),
                    auto_approve=server_data.get("autoApprove", []),
                    timeout=server_data.get("timeout", 30),
                    retry_attempts=server_data.get("retry_attempts", 3)
                )
        
        return cls(
            servers=servers,
            global_timeout=data.get("global_timeout", 60),
            cache_ttl=data.get("cache_ttl", 3600),
            enable_logging=data.get("enable_logging", True),
            log_level=data.get("log_level", "INFO")
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "mcpServers": {
                name: {
                    "command": server.command,
                    "args": server.args,
                    "env": server.env,
                    "disabled": server.disabled,
                    "autoApprove": server.auto_approve,
                    "timeout": server.timeout,
                    "retry_attempts": server.retry_attempts
                }
                for name, server in self.servers.items()
            },
            "global_timeout": self.global_timeout,
            "cache_ttl": self.cache_ttl,
            "enable_logging": self.enable_logging,
            "log_level": self.log_level
        }


class MCPConfigManager:
    """Manages MCP configuration loading and validation."""
    
    def __init__(self):
        self.workspace_config_path = Path(".kiro/settings/mcp.json")
        self.user_config_path = Path.home() / ".kiro/settings/mcp.json"
        self.config: Optional[MCPIntegrationConfig] = None
    
    def load_config(self) -> MCPIntegrationConfig:
        """
        Load MCP configuration from workspace and user config files.
        
        Workspace config takes precedence over user config for conflicting servers.
        """
        user_config = {}
        workspace_config = {}
        
        # Load user-level config
        if self.user_config_path.exists():
            try:
                with open(self.user_config_path, 'r') as f:
                    user_config = json.load(f)
                logger.info(f"Loaded user MCP config from {self.user_config_path}")
            except Exception as e:
                logger.warning(f"Failed to load user MCP config: {e}")
        
        # Load workspace-level config
        if self.workspace_config_path.exists():
            try:
                with open(self.workspace_config_path, 'r') as f:
                    workspace_config = json.load(f)
                logger.info(f"Loaded workspace MCP config from {self.workspace_config_path}")
            except Exception as e:
                logger.warning(f"Failed to load workspace MCP config: {e}")
        
        # Merge configurations (workspace takes precedence)
        merged_config = self._merge_configs(user_config, workspace_config)
        
        # Add default MCP servers if none configured
        if not merged_config.get("mcpServers"):
            merged_config = self._add_default_servers(merged_config)
        
        self.config = MCPIntegrationConfig.from_dict(merged_config)
        return self.config
    
    def _merge_configs(self, user_config: Dict, workspace_config: Dict) -> Dict:
        """Merge user and workspace configurations."""
        merged = user_config.copy()
        
        # Merge MCP servers (workspace takes precedence)
        if "mcpServers" in workspace_config:
            if "mcpServers" not in merged:
                merged["mcpServers"] = {}
            merged["mcpServers"].update(workspace_config["mcpServers"])
        
        # Override global settings with workspace values
        for key in ["global_timeout", "cache_ttl", "enable_logging", "log_level"]:
            if key in workspace_config:
                merged[key] = workspace_config[key]
        
        return merged
    
    def _add_default_servers(self, config: Dict) -> Dict:
        """Add default MCP servers for Melanie AI development."""
        default_servers = {
            "context7": {
                "command": "uvx",
                "args": ["context7-mcp-server@latest"],
                "env": {
                    "FASTMCP_LOG_LEVEL": "ERROR"
                },
                "disabled": False,
                "autoApprove": [
                    "resolve_library_id",
                    "get_library_docs"
                ]
            },
            "web-search": {
                "command": "uvx", 
                "args": ["mcp-server-web-search@latest"],
                "env": {
                    "FASTMCP_LOG_LEVEL": "ERROR"
                },
                "disabled": False,
                "autoApprove": [
                    "web_search"
                ]
            },
            "fetch": {
                "command": "uvx",
                "args": ["mcp-server-fetch@latest"],
                "env": {
                    "FASTMCP_LOG_LEVEL": "ERROR"
                },
                "disabled": False,
                "autoApprove": [
                    "fetch_url",
                    "fetch_html"
                ]
            },
            "github": {
                "command": "uvx",
                "args": ["mcp-server-github@latest"],
                "env": {
                    "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", ""),
                    "FASTMCP_LOG_LEVEL": "ERROR"
                },
                "disabled": not bool(os.getenv("GITHUB_TOKEN")),
                "autoApprove": [
                    "search_repositories",
                    "get_repository",
                    "get_issues"
                ]
            },
            "memory": {
                "command": "uvx",
                "args": ["mcp-server-memory@latest"],
                "env": {
                    "FASTMCP_LOG_LEVEL": "ERROR"
                },
                "disabled": False,
                "autoApprove": [
                    "create_entities",
                    "search_nodes",
                    "read_graph"
                ]
            }
        }
        
        if "mcpServers" not in config:
            config["mcpServers"] = {}
        
        # Only add servers that aren't already configured
        for name, server_config in default_servers.items():
            if name not in config["mcpServers"]:
                config["mcpServers"][name] = server_config
                logger.info(f"Added default MCP server: {name}")
        
        return config
    
    def save_workspace_config(self, config: MCPIntegrationConfig) -> None:
        """Save configuration to workspace config file."""
        try:
            # Ensure directory exists
            self.workspace_config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save configuration
            with open(self.workspace_config_path, 'w') as f:
                json.dump(config.to_dict(), f, indent=2)
            
            logger.info(f"Saved workspace MCP config to {self.workspace_config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save workspace MCP config: {e}")
            raise
    
    def get_enabled_servers(self) -> Dict[str, MCPServerConfig]:
        """Get all enabled MCP servers."""
        if not self.config:
            self.load_config()
        
        return {
            name: server 
            for name, server in self.config.servers.items() 
            if not server.disabled
        }
    
    def is_server_enabled(self, server_name: str) -> bool:
        """Check if a specific MCP server is enabled."""
        if not self.config:
            self.load_config()
        
        server = self.config.servers.get(server_name)
        return server is not None and not server.disabled
    
    def get_server_config(self, server_name: str) -> Optional[MCPServerConfig]:
        """Get configuration for a specific server."""
        if not self.config:
            self.load_config()
        
        return self.config.servers.get(server_name)
    
    def add_server(self, name: str, config: MCPServerConfig) -> None:
        """Add a new MCP server configuration."""
        if not self.config:
            self.load_config()
        
        self.config.servers[name] = config
        logger.info(f"Added MCP server configuration: {name}")
    
    def remove_server(self, name: str) -> bool:
        """Remove an MCP server configuration."""
        if not self.config:
            self.load_config()
        
        if name in self.config.servers:
            del self.config.servers[name]
            logger.info(f"Removed MCP server configuration: {name}")
            return True
        
        return False
    
    def enable_server(self, name: str) -> bool:
        """Enable an MCP server."""
        if not self.config:
            self.load_config()
        
        server = self.config.servers.get(name)
        if server:
            server.disabled = False
            logger.info(f"Enabled MCP server: {name}")
            return True
        
        return False
    
    def disable_server(self, name: str) -> bool:
        """Disable an MCP server."""
        if not self.config:
            self.load_config()
        
        server = self.config.servers.get(name)
        if server:
            server.disabled = True
            logger.info(f"Disabled MCP server: {name}")
            return True
        
        return False
    
    def validate_config(self) -> List[str]:
        """Validate MCP configuration and return any issues."""
        if not self.config:
            self.load_config()
        
        issues = []
        
        for name, server in self.config.servers.items():
            if not server.command:
                issues.append(f"Server '{name}' has no command specified")
            
            if server.timeout <= 0:
                issues.append(f"Server '{name}' has invalid timeout: {server.timeout}")
            
            if server.retry_attempts < 0:
                issues.append(f"Server '{name}' has invalid retry attempts: {server.retry_attempts}")
        
        return issues


# Global config manager instance
config_manager = MCPConfigManager()


def get_mcp_config() -> MCPIntegrationConfig:
    """Get the current MCP configuration."""
    return config_manager.load_config()


def get_mcp_config_manager() -> MCPConfigManager:
    """Get the MCP configuration manager."""
    return config_manager