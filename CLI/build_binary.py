#!/usr/bin/env python3
"""
Cross-platform binary builder for Melanie CLI
Builds standalone executables for Windows, macOS, and Linux
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a command and return the result"""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result.stdout

def install_dependencies():
    """Install build dependencies"""
    print("Installing build dependencies...")
    run_command([sys.executable, "-m", "pip", "install", "pyinstaller", "setuptools"])

def build_binary(target_os=None):
    """Build binary for specified OS or current OS"""
    if target_os is None:
        target_os = platform.system().lower()
    
    print(f"Building binary for {target_os}...")
    
    # Create dist directory
    dist_dir = Path("dist")
    dist_dir.mkdir(exist_ok=True)
    
    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "melanie-cli",
        "--add-data", "theme.py:.",
        "--add-data", "config.py:.",
        "--hidden-import", "rich",
        "--hidden-import", "typer",
        "--hidden-import", "httpx",
        "--hidden-import", "asyncio",
        "main.py"
    ]
    
    # Add OS-specific options
    if target_os == "windows":
        cmd.extend(["--console"])
    elif target_os == "darwin":  # macOS
        cmd.extend(["--console"])
    elif target_os == "linux":
        cmd.extend(["--console"])
    
    # Run PyInstaller
    run_command(cmd, cwd=Path(__file__).parent)
    
    # Rename binary with OS suffix
    binary_name = "melanie-cli"
    if target_os == "windows":
        binary_name += ".exe"
    
    source_path = dist_dir / binary_name
    target_path = dist_dir / f"melanie-cli-{target_os}-{platform.machine().lower()}"
    
    if target_os == "windows":
        target_path = target_path.with_suffix(".exe")
    
    if source_path.exists():
        shutil.move(str(source_path), str(target_path))
        print(f"Binary created: {target_path}")
    else:
        print(f"Error: Binary not found at {source_path}")
        sys.exit(1)

def create_installer_scripts():
    """Create installer scripts for different platforms"""
    
    # Windows installer script
    windows_installer = """@echo off
echo Installing Melanie CLI...

REM Create installation directory
if not exist "%PROGRAMFILES%\\Melanie" mkdir "%PROGRAMFILES%\\Melanie"

REM Copy binary
copy "melanie-cli-windows-*.exe" "%PROGRAMFILES%\\Melanie\\melanie-cli.exe"

REM Add to PATH
setx PATH "%PATH%;%PROGRAMFILES%\\Melanie" /M

echo Melanie CLI installed successfully!
echo You can now use 'melanie-cli' from any command prompt.
pause
"""
    
    # macOS/Linux installer script
    unix_installer = """#!/bin/bash
echo "Installing Melanie CLI..."

# Determine OS
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m | tr '[:upper:]' '[:lower:]')

# Find binary
BINARY="melanie-cli-${OS}-${ARCH}"
if [ ! -f "$BINARY" ]; then
    echo "Error: Binary $BINARY not found"
    exit 1
fi

# Install to /usr/local/bin
sudo cp "$BINARY" /usr/local/bin/melanie-cli
sudo chmod +x /usr/local/bin/melanie-cli

echo "Melanie CLI installed successfully!"
echo "You can now use 'melanie-cli' from any terminal."
"""
    
    # Write installer scripts
    with open("dist/install-windows.bat", "w") as f:
        f.write(windows_installer)
    
    with open("dist/install-unix.sh", "w") as f:
        f.write(unix_installer)
    
    # Make Unix installer executable
    os.chmod("dist/install-unix.sh", 0o755)
    
    print("Installer scripts created in dist/")

def create_package_info():
    """Create package information files"""
    
    readme_content = """# Melanie CLI Binary Distribution

## Installation

### Windows
1. Download `melanie-cli-windows-*.exe`
2. Run `install-windows.bat` as Administrator
3. Use `melanie-cli` from any command prompt

### macOS
1. Download `melanie-cli-darwin-*`
2. Run `chmod +x install-unix.sh && ./install-unix.sh`
3. Use `melanie-cli` from any terminal

### Linux
1. Download `melanie-cli-linux-*`
2. Run `chmod +x install-unix.sh && ./install-unix.sh`
3. Use `melanie-cli` from any terminal

## Manual Installation

You can also manually copy the binary to any directory in your PATH.

## Usage

```bash
melanie-cli --help
```

## Requirements

- No additional dependencies required
- Standalone executable
- Requires API server running on Tailscale network

## Support

For issues and documentation, visit: https://github.com/your-org/melanie-ai
"""
    
    with open("dist/README.md", "w") as f:
        f.write(readme_content)
    
    print("Package documentation created")

def main():
    """Main build function"""
    print("Melanie CLI Binary Builder")
    print("=" * 30)
    
    # Install dependencies
    install_dependencies()
    
    # Build for current platform
    current_os = platform.system().lower()
    build_binary(current_os)
    
    # Create installer scripts
    create_installer_scripts()
    
    # Create package info
    create_package_info()
    
    print("\nBuild completed successfully!")
    print(f"Binary and installers available in: {Path('dist').absolute()}")

if __name__ == "__main__":
    main()