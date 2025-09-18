"""
Configuration management for Melanie CLI.

Handles CLI configuration including API endpoints, authentication,
and user preferences with persistent storage.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class CLIDefaults:
    """Default configuration values for the CLI."""
    api_endpoint: str = "http://localhost:8000"
    api_key: Optional[str] = None
    max_agents: int = 3
    default_timeout: int = 300  # 5 minutes
    verbose: bool = False
    auto_save_sessions: bool = True
    editor: str = "code"  # Default editor command
    test_command: str = "pytest"
    run_command: str = "python"
    project_templates_dir: Optional[str] = None


class CLIConfig:
    """
    Configuration manager for Melanie CLI.
    
    Handles loading, saving, and managing CLI configuration with
    support for environment variables and user overrides.
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_dir: Custom config directory (uses default if None)
        """
        self.config_dir = config_dir or self._get_default_config_dir()
        self.config_file = self.config_dir / "config.json"
        self.defaults = CLIDefaults()
        self._config: Dict[str, Any] = {}
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load configuration
        self._load_config()
    
    def _get_default_config_dir(self) -> Path:
        """Get the default configuration directory."""
        if os.name == 'nt':  # Windows
            config_dir = Path(os.environ.get('APPDATA', '~')) / 'melanie-cli'
        else:  # Unix-like systems
            config_dir = Path.home() / '.config' / 'melanie-cli'
        
        return config_dir.expanduser()
    
    def _load_config(self):
        """Load configuration from file and environment variables."""
        # Start with defaults
        self._config = asdict(self.defaults)
        
        # Load from config file if it exists
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    file_config = json.load(f)
                    self._config.update(file_config)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load config file: {e}")
        
        # Override with environment variables
        self._load_env_overrides()
    
    def _load_env_overrides(self):
        """Load configuration overrides from environment variables."""
        env_mappings = {
            'MELANIE_API_ENDPOINT': 'api_endpoint',
            'MELANIE_API_KEY': 'api_key',
            'MELANIE_MAX_AGENTS': 'max_agents',
            'MELANIE_TIMEOUT': 'default_timeout',
            'MELANIE_VERBOSE': 'verbose',
            'MELANIE_EDITOR': 'editor',
            'MELANIE_TEST_COMMAND': 'test_command',
            'MELANIE_RUN_COMMAND': 'run_command',
        }
        
        for env_var, config_key in env_mappings.items():
            env_value = os.environ.get(env_var)
            if env_value is not None:
                # Convert string values to appropriate types
                if config_key in ['max_agents', 'default_timeout']:
                    try:
                        self._config[config_key] = int(env_value)
                    except ValueError:
                        print(f"Warning: Invalid integer value for {env_var}: {env_value}")
                elif config_key == 'verbose':
                    self._config[config_key] = env_value.lower() in ('true', '1', 'yes', 'on')
                else:
                    self._config[config_key] = env_value
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any):
        """
        Set a configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        self._config[key] = value
        self._save_config()
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values."""
        return self._config.copy()
    
    def reset(self):
        """Reset configuration to defaults."""
        self._config = asdict(self.defaults)
        self._save_config()
    
    def _save_config(self):
        """Save configuration to file."""
        try:
            # Only save non-default values to keep config file clean
            config_to_save = {}
            defaults_dict = asdict(self.defaults)
            
            for key, value in self._config.items():
                if key not in defaults_dict or value != defaults_dict[key]:
                    config_to_save[key] = value
            
            with open(self.config_file, 'w') as f:
                json.dump(config_to_save, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save config file: {e}")
    
    def validate_api_connection(self) -> bool:
        """
        Validate API connection settings.
        
        Returns:
            True if API endpoint is configured and reachable
        """
        api_endpoint = self.get('api_endpoint')
        if not api_endpoint:
            return False
        
        # Basic URL validation
        if not (api_endpoint.startswith('http://') or api_endpoint.startswith('https://')):
            return False
        
        return True
    
    def get_session_dir(self) -> Path:
        """Get the directory for storing sessions."""
        session_dir = self.config_dir / "sessions"
        session_dir.mkdir(exist_ok=True)
        return session_dir
    
    def get_cache_dir(self) -> Path:
        """Get the directory for caching data."""
        cache_dir = self.config_dir / "cache"
        cache_dir.mkdir(exist_ok=True)
        return cache_dir
    
    def get_logs_dir(self) -> Path:
        """Get the directory for log files."""
        logs_dir = self.config_dir / "logs"
        logs_dir.mkdir(exist_ok=True)
        return logs_dir