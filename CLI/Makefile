# Melanie CLI Makefile
# Cross-platform build automation

.PHONY: help install clean build test lint format dev-install package verify

# Default target
help:
	@echo "Melanie CLI Build System"
	@echo ""
	@echo "Available targets:"
	@echo "  install     - Install dependencies"
	@echo "  dev-install - Install development dependencies"
	@echo "  clean       - Clean build artifacts"
	@echo "  build       - Build executable for current platform"
	@echo "  test        - Run tests"
	@echo "  lint        - Run linting"
	@echo "  format      - Format code"
	@echo "  package     - Create distribution package"
	@echo "  verify      - Verify built executable"
	@echo "  all         - Run full build pipeline"

# Install production dependencies
install:
	@echo "📦 Installing dependencies..."
	pip install -r requirements.txt

# Install development dependencies
dev-install: install
	@echo "🔧 Installing development dependencies..."
	pip install pytest pytest-asyncio black isort mypy

# Clean build artifacts
clean:
	@echo "🧹 Cleaning build artifacts..."
	python build.py --no-clean
	rm -rf build/ dist/ *.spec
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete

# Build executable
build:
	@echo "🔨 Building executable..."
	python build.py

# Run tests
test:
	@echo "🧪 Running tests..."
	python -m pytest tests/ -v

# Run code generation workflow tests
test-code-generation:
	@echo "🧪 Running code generation workflow tests..."
	python -m pytest tests/test_code_generation_workflow.py -v

# Run integration workflow tests
test-integration:
	@echo "🧪 Running integration workflow tests..."
	python -m pytest tests/test_integration_workflow.py -v

# Run all tests with coverage
test-coverage:
	@echo "🧪 Running all tests with coverage..."
	python -m pytest tests/ -v --cov=. --cov-report=term-missing --cov-report=html

# Run linting
lint:
	@echo "🔍 Running linting..."
	python -m mypy . --ignore-missing-imports
	python -m isort --check-only .
	python -m black --check .

# Format code
format:
	@echo "✨ Formatting code..."
	python -m isort .
	python -m black .

# Create distribution package
package: build
	@echo "📦 Creating distribution package..."
	# Package is created as part of build process

# Verify executable
verify:
	@echo "✅ Verifying executable..."
	python build.py --verify-only

# Full build pipeline
all: clean dev-install lint test build verify
	@echo "✨ Full build pipeline completed!"

# Platform-specific builds (for CI/CD)
build-macos:
	@echo "🍎 Building for macOS..."
	python build.py

build-linux:
	@echo "🐧 Building for Linux..."
	python build.py

build-windows:
	@echo "🪟 Building for Windows..."
	python build.py

# Development targets
dev: dev-install
	@echo "🚀 Development environment ready!"

run-dev:
	@echo "🏃 Running CLI in development mode..."
	python main.py

# Install CLI globally (development)
install-dev:
	@echo "🔗 Installing CLI for development..."
	pip install -e .

# Uninstall CLI
uninstall:
	@echo "🗑️  Uninstalling CLI..."
	pip uninstall melanie-cli -y