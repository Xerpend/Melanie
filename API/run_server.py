#!/usr/bin/env python3
"""
Melanie AI Server Startup Script

This script provides a convenient way to start the Melanie AI API server
with proper environment configuration and validation.
"""

import os
import sys
from pathlib import Path

# Add the API directory to Python path
api_dir = Path(__file__).parent
sys.path.insert(0, str(api_dir))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(api_dir / ".env")

# Import and run the server
from server import main

if __name__ == "__main__":
    main()