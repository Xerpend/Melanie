# Melanie AI Ecosystem - Deployment Makefile

.PHONY: help build deploy clean test docker-build docker-deploy standalone-deploy

# Default target
help:
	@echo "Melanie AI Ecosystem - Deployment Commands"
	@echo "=========================================="
	@echo ""
	@echo "Available targets:"
	@echo "  build           - Build all components"
	@echo "  deploy          - Full deployment build"
	@echo "  docker-build    - Build Docker images only"
	@echo "  docker-deploy   - Deploy using Docker"
	@echo "  standalone      - Deploy standalone packages"
	@echo "  cli-binary      - Build CLI binary only"
	@echo "  web-build       - Build web interface only"
	@echo "  email-installer - Build email client installer"
	@echo "  test            - Run all tests"
	@echo "  clean           - Clean build artifacts"
	@echo "  help            - Show this help message"

# Full deployment build
build deploy:
	@echo "Starting full deployment build..."
	python3 deploy.py

# Docker-specific builds
docker-build:
	@echo "Building Docker images..."
	docker build -t melanie-api:latest ./API
	docker build -t melanie-web:latest ./WEB
	docker build -t melanie-rag:latest ./RAG

docker-deploy: docker-build
	@echo "Deploying with Docker Compose..."
	docker-compose up -d

# Standalone deployment
standalone-deploy:
	@echo "Building standalone packages..."
	cd WEB && node scripts/build-production.js
	cd CLI && python3 build_binary.py

# Individual component builds
cli-binary:
	@echo "Building CLI binary..."
	cd CLI && python3 build_binary.py

web-build:
	@echo "Building web interface..."
	cd WEB && npm ci && npm run build
	cd WEB && node scripts/build-production.js

email-installer:
	@echo "Building email client installer..."
	cd Email && npm ci
	cd Email && node scripts/build-installers.js

api-server:
	@echo "Building API server..."
	docker build -t melanie-api:latest ./API

rag-engine:
	@echo "Building RAG engine..."
	cd RAG && cargo build --release
	docker build -t melanie-rag:latest ./RAG

# Testing
test:
	@echo "Running tests..."
	cd API && python -m pytest test_*.py
	cd WEB && npm test -- --run
	cd CLI && python -m pytest tests/
	cd Email && npm test

test-api:
	@echo "Testing API server..."
	cd API && python -m pytest test_*.py -v

test-web:
	@echo "Testing web interface..."
	cd WEB && npm test -- --run --coverage

test-cli:
	@echo "Testing CLI..."
	cd CLI && python -m pytest tests/ -v

test-email:
	@echo "Testing email client..."
	cd Email && npm test

# Development helpers
dev-api:
	@echo "Starting API server in development mode..."
	cd API && python server.py

dev-web:
	@echo "Starting web interface in development mode..."
	cd WEB && npm run dev

dev-cli:
	@echo "Running CLI in development mode..."
	cd CLI && python main.py

# Cleanup
clean:
	@echo "Cleaning build artifacts..."
	rm -rf deploy-package/
	rm -rf API/dist/
	rm -rf WEB/.next/
	rm -rf WEB/deploy/
	rm -rf CLI/dist/
	rm -rf CLI/build/
	rm -rf Email/dist-installers/
	rm -rf RAG/target/
	docker system prune -f
	@echo "Cleanup completed"

# Installation helpers
install-deps:
	@echo "Installing dependencies..."
	cd API && pip install -r requirements.txt
	cd WEB && npm ci
	cd CLI && pip install -r requirements.txt
	cd Email && npm ci
	cd RAG && cargo build

# Production deployment helpers
prod-deploy: build
	@echo "Deploying to production..."
	@echo "Please copy deploy-package/ to your production server"
	@echo "Then run: ./deploy-docker.sh or ./deploy-standalone.sh"

# Quick development setup
dev-setup: install-deps
	@echo "Setting up development environment..."
	cp API/.env.example API/.env
	cp WEB/.env.example WEB/.env.local
	@echo "Please edit .env files with your API keys"
	@echo "Then run: make dev-api (in one terminal) and make dev-web (in another)"

# Health checks
health-check:
	@echo "Checking service health..."
	curl -f http://localhost:8000/health || echo "API server not responding"
	curl -f http://localhost:3000 || echo "Web interface not responding"

# Logs
logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f melanie-api

logs-web:
	docker-compose logs -f melanie-web

# Service management
start:
	docker-compose up -d

stop:
	docker-compose down

restart: stop start

# Backup
backup:
	@echo "Creating backup..."
	mkdir -p backups/$(shell date +%Y%m%d_%H%M%S)
	cp -r file_storage/ backups/$(shell date +%Y%m%d_%H%M%S)/
	cp -r rag_data/ backups/$(shell date +%Y%m%d_%H%M%S)/
	cp docker-compose.yml backups/$(shell date +%Y%m%d_%H%M%S)/
	cp .env backups/$(shell date +%Y%m%d_%H%M%S)/ 2>/dev/null || true
	@echo "Backup created in backups/"

# Update
update:
	@echo "Updating deployment..."
	git pull
	make build
	make restart

# Deployment verification
verify:
	@echo "Verifying deployment..."
	python3 verify-deployment.py

# Full deployment pipeline
deploy-full: clean build verify
	@echo "Full deployment pipeline completed"

# Quick deployment for development
deploy-dev: dev-setup
	@echo "Development deployment ready"
	@echo "Run 'make dev-api' and 'make dev-web' in separate terminals"