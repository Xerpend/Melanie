#!/usr/bin/env python3
"""
Build script for the Melanie RAG Python module using PyO3.

This script helps build the Rust extension module for Python.
"""

import subprocess
import sys
import os
from pathlib import Path


def check_requirements():
    """Check if required tools are available."""
    print("🔍 Checking requirements...")
    
    # Check if we're in the right directory
    if not Path("Cargo.toml").exists():
        print("❌ Error: Cargo.toml not found. Please run this script from the RAG directory.")
        return False
    
    # Check if Rust is installed
    try:
        result = subprocess.run(["cargo", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Rust: {result.stdout.strip()}")
        else:
            print("❌ Error: Cargo not found. Please install Rust: https://rustup.rs/")
            return False
    except FileNotFoundError:
        print("❌ Error: Cargo not found. Please install Rust: https://rustup.rs/")
        return False
    
    # Check if maturin is installed
    try:
        result = subprocess.run(["maturin", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Maturin: {result.stdout.strip()}")
        else:
            print("⚠️  Maturin not found. Installing...")
            install_maturin()
    except FileNotFoundError:
        print("⚠️  Maturin not found. Installing...")
        install_maturin()
    
    return True


def install_maturin():
    """Install maturin for building Python extensions."""
    print("📦 Installing maturin...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "maturin"], check=True)
        print("✅ Maturin installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing maturin: {e}")
        sys.exit(1)


def build_module(development=True):
    """Build the Python module."""
    print("🔨 Building Python module...")
    
    try:
        if development:
            # Development build (installs in current environment)
            print("📝 Building in development mode...")
            subprocess.run(["maturin", "develop", "--release"], check=True)
            print("✅ Development build completed")
        else:
            # Production build (creates wheel)
            print("📦 Building wheel...")
            subprocess.run(["maturin", "build", "--release"], check=True)
            print("✅ Wheel build completed")
            
            # List the created wheel
            target_dir = Path("target/wheels")
            if target_dir.exists():
                wheels = list(target_dir.glob("*.whl"))
                if wheels:
                    print(f"📦 Created wheel: {wheels[-1]}")
                    print(f"   Install with: pip install {wheels[-1]}")
    
    except subprocess.CalledProcessError as e:
        print(f"❌ Error building module: {e}")
        sys.exit(1)


def test_import():
    """Test if the module can be imported."""
    print("🧪 Testing module import...")
    
    try:
        import melanie_rag
        print("✅ Module imported successfully")
        print(f"   Version: {melanie_rag.get_version()}")
        print(f"   Default token limit: {melanie_rag.DEFAULT_TOKEN_LIMIT}")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def main():
    """Main build process."""
    print("🚀 Melanie RAG Python Module Builder")
    print("=" * 40)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Parse command line arguments
    development = "--release" not in sys.argv
    
    # Build the module
    build_module(development=development)
    
    # Test import
    if test_import():
        print("\n🎉 Build completed successfully!")
        print("\n📋 Next steps:")
        print("   1. Run tests: python -m pytest ../AI/test_rag_pyo3_integration.py")
        print("   2. Use in Python: import melanie_rag")
    else:
        print("\n❌ Build completed but module import failed")
        print("   Try rebuilding or check for errors above")
        sys.exit(1)


if __name__ == "__main__":
    main()