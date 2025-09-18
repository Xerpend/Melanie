"""
Melanie AI API Package

This package contains the FastAPI server implementation for the Melanie AI ecosystem,
including Tailscale integration, CORS configuration, and basic endpoints.
"""

from .server import app, TailscaleDetector, ServerConfig

__version__ = "1.0.0"
__all__ = ["app", "TailscaleDetector", "ServerConfig"]