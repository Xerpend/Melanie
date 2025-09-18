# Melanie Email - Desktop Application Makefile

.PHONY: help install dev build clean test lint format deps icons

# Default target
help:
	@echo "Melanie Email - Desktop Application"
	@echo ""
	@echo "Available commands:"
	@echo "  install     Install all dependencies"
	@echo "  dev         Start development server"
	@echo "  build       Build application for current platform"
	@echo "  build-all   Build for all platforms (requires setup)"
	@echo "  clean       Clean build artifacts"
	@echo "  test        Run tests"
	@echo "  lint        Run linter"
	@echo "  format      Format code"
	@echo "  deps        Check and update dependencies"
	@echo "  icons       Generate application icons"

# Install dependencies
install:
	@echo "Installing frontend dependencies..."
	npm install
	@echo "Installing Rust dependencies..."
	cd src-tauri && cargo fetch
	@echo "Dependencies installed successfully!"

# Development server
dev:
	@echo "Starting development server..."
	npm run tauri:dev

# Build for current platform
build:
	@echo "Building for current platform..."
	npm run build
	npm run tauri:build

# Build for all platforms (requires cross-compilation setup)
build-all:
	@echo "Building for all platforms..."
	@echo "Note: This requires proper cross-compilation setup"
	npm run build
	# Windows
	@if command -v cargo >/dev/null 2>&1; then \
		echo "Building for Windows..."; \
		rustup target add x86_64-pc-windows-msvc; \
		npm run tauri:build -- --target x86_64-pc-windows-msvc; \
	fi
	# macOS
	@if [[ "$$(uname)" == "Darwin" ]]; then \
		echo "Building for macOS..."; \
		npm run tauri:build -- --target x86_64-apple-darwin; \
		npm run tauri:build -- --target aarch64-apple-darwin; \
	fi
	# Linux
	@if [[ "$$(uname)" == "Linux" ]]; then \
		echo "Building for Linux..."; \
		npm run tauri:build -- --target x86_64-unknown-linux-gnu; \
	fi

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf dist/
	rm -rf src-tauri/target/
	rm -rf node_modules/
	@echo "Clean completed!"

# Run tests
test:
	@echo "Running frontend tests..."
	npm test
	@echo "Running Rust tests..."
	cd src-tauri && cargo test

# Lint code
lint:
	@echo "Linting frontend code..."
	npm run lint
	@echo "Linting Rust code..."
	cd src-tauri && cargo clippy -- -D warnings

# Format code
format:
	@echo "Formatting frontend code..."
	npm run lint:fix
	@echo "Formatting Rust code..."
	cd src-tauri && cargo fmt

# Check and update dependencies
deps:
	@echo "Checking frontend dependencies..."
	npm audit
	npm outdated
	@echo "Checking Rust dependencies..."
	cd src-tauri && cargo audit

# Generate application icons (placeholder - requires actual icon source)
icons:
	@echo "Generating application icons..."
	@echo "Note: This requires a source icon file and appropriate tools"
	@echo "Please ensure you have:"
	@echo "  - Source icon (1024x1024 PNG or SVG)"
	@echo "  - iconutil (macOS)"
	@echo "  - ImageMagick or similar for resizing"
	@echo "Run this manually with proper icon generation tools"

# Platform-specific builds
build-windows:
	npm run build
	npm run tauri:build -- --target x86_64-pc-windows-msvc

build-macos:
	npm run build
	npm run tauri:build -- --target x86_64-apple-darwin
	npm run tauri:build -- --target aarch64-apple-darwin

build-linux:
	npm run build
	npm run tauri:build -- --target x86_64-unknown-linux-gnu

# Development utilities
setup-dev:
	@echo "Setting up development environment..."
	@echo "Installing Rust targets..."
	rustup target add x86_64-pc-windows-msvc
	rustup target add x86_64-apple-darwin
	rustup target add aarch64-apple-darwin
	rustup target add x86_64-unknown-linux-gnu
	@echo "Installing additional tools..."
	cargo install cargo-audit
	@echo "Development environment setup complete!"