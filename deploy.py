#!/usr/bin/env python3
"""
Comprehensive deployment script for Melanie AI Ecosystem
Handles building, packaging, and deployment of all components
"""

import os
import sys
import subprocess
import platform
import shutil
import json
from pathlib import Path
from datetime import datetime

class MelanieDeployer:
    def __init__(self):
        self.root_dir = Path(__file__).parent
        self.deploy_dir = self.root_dir / "deploy-package"
        self.platform = platform.system().lower()
        self.arch = platform.machine().lower()
        
    def run_command(self, cmd, cwd=None, shell=False):
        """Run a command and return the result"""
        if isinstance(cmd, str):
            cmd_str = cmd
        else:
            cmd_str = ' '.join(cmd)
            
        print(f"Running: {cmd_str}")
        
        try:
            result = subprocess.run(
                cmd, 
                cwd=cwd or self.root_dir, 
                shell=shell,
                capture_output=True, 
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"Error running command: {cmd_str}")
            print(f"Exit code: {e.returncode}")
            print(f"Error output: {e.stderr}")
            raise
    
    def check_prerequisites(self):
        """Check if all required tools are installed"""
        print("Checking prerequisites...")
        
        required_tools = {
            'python': ['python', '--version'],
            'node': ['node', '--version'],
            'npm': ['npm', '--version'],
            'cargo': ['cargo', '--version'],
            'docker': ['docker', '--version']
        }
        
        missing_tools = []
        
        for tool, cmd in required_tools.items():
            try:
                self.run_command(cmd)
                print(f"✓ {tool} found")
            except (subprocess.CalledProcessError, FileNotFoundError):
                print(f"✗ {tool} not found")
                missing_tools.append(tool)
        
        if missing_tools:
            print(f"Missing required tools: {', '.join(missing_tools)}")
            print("Please install missing tools and try again.")
            sys.exit(1)
        
        print("All prerequisites satisfied")
    
    def clean_previous_builds(self):
        """Clean previous build artifacts"""
        print("Cleaning previous builds...")
        
        clean_paths = [
            self.deploy_dir,
            "API/dist",
            "WEB/.next",
            "WEB/deploy",
            "CLI/dist",
            "CLI/build",
            "Email/dist-installers",
            "RAG/target"
        ]
        
        for path in clean_paths:
            full_path = self.root_dir / path
            if full_path.exists():
                shutil.rmtree(full_path)
                print(f"Cleaned: {path}")
        
        print("Cleanup completed")
    
    def build_api_server(self):
        """Build API server Docker image"""
        print("Building API server...")
        
        api_dir = self.root_dir / "API"
        
        # Build Docker image
        self.run_command([
            'docker', 'build', 
            '-t', 'melanie-api:latest',
            '-f', 'Dockerfile',
            '.'
        ], cwd=api_dir)
        
        # Save Docker image
        self.run_command([
            'docker', 'save', 
            '-o', str(self.deploy_dir / 'melanie-api.tar'),
            'melanie-api:latest'
        ])
        
        print("API server build completed")
    
    def build_web_interface(self):
        """Build web interface"""
        print("Building web interface...")
        
        web_dir = self.root_dir / "WEB"
        
        # Install dependencies and build
        self.run_command(['npm', 'ci'], cwd=web_dir)
        self.run_command(['npm', 'run', 'build'], cwd=web_dir)
        
        # Build Docker image
        self.run_command([
            'docker', 'build',
            '-t', 'melanie-web:latest',
            '-f', 'Dockerfile',
            '.'
        ], cwd=web_dir)
        
        # Save Docker image
        self.run_command([
            'docker', 'save',
            '-o', str(self.deploy_dir / 'melanie-web.tar'),
            'melanie-web:latest'
        ])
        
        # Run production build script
        build_script = web_dir / "scripts" / "build-production.js"
        if build_script.exists():
            self.run_command(['node', str(build_script)], cwd=web_dir)
            
            # Copy deployment package
            web_deploy = web_dir / "deploy"
            if web_deploy.exists():
                shutil.copytree(web_deploy, self.deploy_dir / "web-standalone")
        
        print("Web interface build completed")
    
    def build_cli_binary(self):
        """Build CLI binary"""
        print("Building CLI binary...")
        
        cli_dir = self.root_dir / "CLI"
        
        # Run binary build script
        build_script = cli_dir / "build_binary.py"
        if build_script.exists():
            self.run_command([sys.executable, str(build_script)], cwd=cli_dir)
            
            # Copy binaries to deploy directory
            cli_dist = cli_dir / "dist"
            if cli_dist.exists():
                cli_deploy = self.deploy_dir / "cli-binaries"
                cli_deploy.mkdir(exist_ok=True)
                
                for file in cli_dist.iterdir():
                    if file.is_file():
                        shutil.copy2(file, cli_deploy)
        
        print("CLI binary build completed")
    
    def build_email_client(self):
        """Build email client installers"""
        print("Building email client...")
        
        email_dir = self.root_dir / "Email"
        
        # Install dependencies
        self.run_command(['npm', 'ci'], cwd=email_dir)
        
        # Run installer build script
        build_script = email_dir / "scripts" / "build-installers.js"
        if build_script.exists():
            try:
                self.run_command(['node', str(build_script)], cwd=email_dir)
                
                # Copy installers to deploy directory
                email_dist = email_dir / "dist-installers"
                if email_dist.exists():
                    email_deploy = self.deploy_dir / "email-installers"
                    shutil.copytree(email_dist, email_deploy)
            except subprocess.CalledProcessError:
                print("Email client build failed (platform-specific tools may be missing)")
                print("Continuing with other components...")
        
        print("Email client build completed")
    
    def build_rag_engine(self):
        """Build RAG engine"""
        print("Building RAG engine...")
        
        rag_dir = self.root_dir / "RAG"
        
        # Build Rust project
        self.run_command(['cargo', 'build', '--release'], cwd=rag_dir)
        
        # Build Docker image
        self.run_command([
            'docker', 'build',
            '-t', 'melanie-rag:latest',
            '-f', 'Dockerfile',
            '.'
        ], cwd=rag_dir)
        
        # Save Docker image
        self.run_command([
            'docker', 'save',
            '-o', str(self.deploy_dir / 'melanie-rag.tar'),
            'melanie-rag:latest'
        ])
        
        print("RAG engine build completed")
    
    def create_docker_compose(self):
        """Create production Docker Compose configuration"""
        print("Creating Docker Compose configuration...")
        
        # Copy main docker-compose.yml
        main_compose = self.root_dir / "docker-compose.yml"
        if main_compose.exists():
            shutil.copy2(main_compose, self.deploy_dir / "docker-compose.yml")
        
        # Create production override
        prod_compose = {
            'version': '3.8',
            'services': {
                'melanie-api': {
                    'restart': 'always',
                    'logging': {
                        'driver': 'json-file',
                        'options': {
                            'max-size': '10m',
                            'max-file': '3'
                        }
                    }
                },
                'melanie-web': {
                    'restart': 'always',
                    'logging': {
                        'driver': 'json-file',
                        'options': {
                            'max-size': '10m',
                            'max-file': '3'
                        }
                    }
                },
                'melanie-rag': {
                    'restart': 'always',
                    'logging': {
                        'driver': 'json-file',
                        'options': {
                            'max-size': '10m',
                            'max-file': '3'
                        }
                    }
                }
            }
        }
        
        with open(self.deploy_dir / "docker-compose.prod.yml", 'w') as f:
            import yaml
            yaml.dump(prod_compose, f, default_flow_style=False)
        
        print("Docker Compose configuration created")
    
    def create_deployment_scripts(self):
        """Create deployment and management scripts"""
        print("Creating deployment scripts...")
        
        # Docker deployment script
        docker_deploy = """#!/bin/bash
# Docker deployment script for Melanie AI Ecosystem

set -e

echo "Melanie AI Ecosystem - Docker Deployment"
echo "========================================"

# Load Docker images
echo "Loading Docker images..."
docker load -i melanie-api.tar
docker load -i melanie-web.tar
docker load -i melanie-rag.tar

# Create necessary directories
mkdir -p data/file_storage
mkdir -p data/rag_data
mkdir -p data/logs

# Set permissions
chmod 755 data/file_storage
chmod 755 data/rag_data
chmod 755 data/logs

# Start services
echo "Starting services..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

echo "Deployment completed!"
echo "Services will be available at:"
echo "  - API Server: http://localhost:8000"
echo "  - Web Interface: http://localhost:3000"
echo ""
echo "To check status: docker-compose ps"
echo "To view logs: docker-compose logs -f"
echo "To stop: docker-compose down"
"""
        
        with open(self.deploy_dir / "deploy-docker.sh", 'w') as f:
            f.write(docker_deploy)
        os.chmod(self.deploy_dir / "deploy-docker.sh", 0o755)
        
        # Standalone deployment script
        standalone_deploy = """#!/bin/bash
# Standalone deployment script for Melanie AI Ecosystem

set -e

echo "Melanie AI Ecosystem - Standalone Deployment"
echo "============================================"

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required but not installed."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js is required but not installed."; exit 1; }

# Deploy API server
echo "Setting up API server..."
cd api-standalone
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create systemd service (optional)
if command -v systemctl >/dev/null 2>&1; then
    echo "Creating systemd service..."
    sudo tee /etc/systemd/system/melanie-api.service > /dev/null <<EOF
[Unit]
Description=Melanie API Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
ExecStart=$(pwd)/venv/bin/python server.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    sudo systemctl enable melanie-api
    sudo systemctl start melanie-api
    echo "API server service created and started"
else
    echo "To start API server manually: cd api-standalone && source venv/bin/activate && python server.py"
fi

# Deploy web interface
echo "Setting up web interface..."
cd ../web-standalone
npm ci --only=production

if command -v systemctl >/dev/null 2>&1; then
    echo "Creating web interface service..."
    sudo tee /etc/systemd/system/melanie-web.service > /dev/null <<EOF
[Unit]
Description=Melanie Web Interface
After=network.target melanie-api.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/npm start
Restart=always
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    sudo systemctl enable melanie-web
    sudo systemctl start melanie-web
    echo "Web interface service created and started"
else
    echo "To start web interface manually: cd web-standalone && npm start"
fi

echo "Deployment completed!"
echo "Services will be available at:"
echo "  - API Server: http://localhost:8000"
echo "  - Web Interface: http://localhost:3000"
"""
        
        with open(self.deploy_dir / "deploy-standalone.sh", 'w') as f:
            f.write(standalone_deploy)
        os.chmod(self.deploy_dir / "deploy-standalone.sh", 0o755)
        
        print("Deployment scripts created")
    
    def create_documentation(self):
        """Create deployment documentation"""
        print("Creating deployment documentation...")
        
        readme_content = f"""# Melanie AI Ecosystem - Deployment Package

Generated on: {datetime.now().isoformat()}
Platform: {self.platform} ({self.arch})

## Contents

This deployment package contains:

- **Docker Images**: Pre-built containers for all services
- **Standalone Packages**: Direct deployment without Docker
- **CLI Binaries**: Cross-platform command-line tools
- **Email Client Installers**: Desktop application installers
- **Documentation**: Setup and configuration guides

## Quick Start

### Docker Deployment (Recommended)

1. Ensure Docker and Docker Compose are installed
2. Run the deployment script:
   ```bash
   ./deploy-docker.sh
   ```
3. Access the services:
   - Web Interface: http://localhost:3000
   - API Server: http://localhost:8000

### Standalone Deployment

1. Run the standalone deployment script:
   ```bash
   ./deploy-standalone.sh
   ```
2. Follow the on-screen instructions

## Components

### API Server
- **Docker Image**: melanie-api.tar
- **Standalone**: api-standalone/
- **Port**: 8000
- **Requirements**: Python 3.11+, Tailscale network

### Web Interface
- **Docker Image**: melanie-web.tar
- **Standalone**: web-standalone/
- **Port**: 3000
- **Requirements**: Node.js 18+

### RAG Engine
- **Docker Image**: melanie-rag.tar
- **Requirements**: Rust runtime

### CLI Tools
- **Location**: cli-binaries/
- **Platforms**: Windows, macOS, Linux
- **Installation**: Run appropriate installer script

### Email Client
- **Location**: email-installers/
- **Formats**: MSI (Windows), DMG (macOS), DEB (Linux)
- **Installation**: Run platform-specific installer

## Configuration

### Environment Variables

Create `.env` files with the following variables:

```bash
# API Keys
XAI_API_KEY=your_xai_key_here
OPENAI_API_KEY=your_openai_key_here
PERPLEXITY_API_KEY=your_perplexity_key_here

# Server Configuration
API_HOST=0.0.0.0
API_PORT=8000
WEB_PORT=3000

# Security
SECRET_KEY=your_secret_key_here
ALLOWED_ORIGINS=http://localhost:3000,https://your-domain.com
```

### Tailscale Setup

1. Install Tailscale on your server
2. Connect to your Tailscale network
3. The API server will automatically detect and bind to Tailscale IP

## Security Considerations

- **Network**: Requires Tailscale for secure access
- **API Keys**: Store securely in environment files
- **HTTPS**: Use reverse proxy (nginx/Apache) for HTTPS
- **Firewall**: Configure appropriate firewall rules

## Monitoring

### Health Checks
- API: `curl http://localhost:8000/health`
- Web: `curl http://localhost:3000`

### Logs
- Docker: `docker-compose logs -f`
- Standalone: Check systemd logs with `journalctl -u melanie-api -f`

## Troubleshooting

### Common Issues

1. **Tailscale not detected**
   - Ensure Tailscale is running and connected
   - Check network interfaces with `ip addr` or `ifconfig`

2. **Port conflicts**
   - Change ports in docker-compose.yml or environment files
   - Ensure ports 3000 and 8000 are available

3. **Permission errors**
   - Check file permissions in data directories
   - Ensure Docker has access to mounted volumes

### Support

For issues and documentation:
- GitHub: https://github.com/your-org/melanie-ai
- Documentation: See docs/ directory
- Logs: Check application logs for detailed error messages

## Updating

To update the deployment:
1. Stop services: `docker-compose down`
2. Load new images: `docker load -i new-image.tar`
3. Start services: `docker-compose up -d`

## Backup

Important directories to backup:
- `data/file_storage/` - Uploaded files
- `data/rag_data/` - RAG database
- `.env` files - Configuration
- `docker-compose.yml` - Service configuration
"""
        
        with open(self.deploy_dir / "README.md", 'w') as f:
            f.write(readme_content)
        
        # Create system requirements document
        requirements_doc = """# System Requirements

## Minimum Requirements

### Docker Deployment
- **OS**: Linux, macOS, or Windows with WSL2
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 10GB free space
- **Docker**: 20.10+ with Docker Compose
- **Network**: Tailscale installed and connected

### Standalone Deployment
- **OS**: Ubuntu 18.04+, macOS 10.15+, Windows 10+
- **RAM**: 2GB minimum, 4GB recommended
- **Storage**: 5GB free space
- **Python**: 3.11+
- **Node.js**: 18+
- **Network**: Tailscale installed and connected

## Recommended Specifications

### Production Server
- **CPU**: 4+ cores
- **RAM**: 16GB+
- **Storage**: 50GB+ SSD
- **Network**: Gigabit connection
- **OS**: Ubuntu 22.04 LTS or similar

### Development Environment
- **CPU**: 2+ cores
- **RAM**: 8GB+
- **Storage**: 20GB+ available
- **Network**: Stable internet connection

## Network Requirements

### Ports
- **3000**: Web interface (HTTP)
- **8000**: API server (HTTP)
- **8001**: RAG engine (internal)

### External Services
- **XAI API**: For Grok models
- **OpenAI API**: For GPT models
- **Perplexity API**: For search capabilities
- **Tailscale**: For secure networking

## Security Requirements

- **Tailscale**: Required for network access
- **HTTPS**: Recommended for production
- **Firewall**: Configure appropriate rules
- **API Keys**: Secure storage required
"""
        
        with open(self.deploy_dir / "REQUIREMENTS.md", 'w') as f:
            f.write(requirements_doc)
        
        print("Documentation created")
    
    def create_deployment_manifest(self):
        """Create deployment manifest with build information"""
        print("Creating deployment manifest...")
        
        manifest = {
            "name": "Melanie AI Ecosystem",
            "version": "1.0.0",
            "build_date": datetime.now().isoformat(),
            "platform": self.platform,
            "architecture": self.arch,
            "components": {
                "api_server": {
                    "type": "docker",
                    "image": "melanie-api:latest",
                    "port": 8000
                },
                "web_interface": {
                    "type": "docker",
                    "image": "melanie-web:latest",
                    "port": 3000
                },
                "rag_engine": {
                    "type": "docker",
                    "image": "melanie-rag:latest",
                    "port": 8001
                },
                "cli_tools": {
                    "type": "binary",
                    "platforms": ["windows", "macos", "linux"]
                },
                "email_client": {
                    "type": "installer",
                    "formats": ["msi", "dmg", "deb"]
                }
            },
            "requirements": {
                "docker": "20.10+",
                "docker_compose": "1.29+",
                "python": "3.11+",
                "node": "18+",
                "tailscale": "required"
            }
        }
        
        with open(self.deploy_dir / "manifest.json", 'w') as f:
            json.dump(manifest, f, indent=2)
        
        print("Deployment manifest created")
    
    def run_deployment(self):
        """Run the complete deployment process"""
        print("Starting Melanie AI Ecosystem deployment build...")
        print("=" * 50)
        
        try:
            # Preparation
            self.check_prerequisites()
            self.clean_previous_builds()
            
            # Create deployment directory
            self.deploy_dir.mkdir(exist_ok=True)
            
            # Build components
            self.build_api_server()
            self.build_web_interface()
            self.build_cli_binary()
            self.build_email_client()
            self.build_rag_engine()
            
            # Create deployment artifacts
            self.create_docker_compose()
            self.create_deployment_scripts()
            self.create_documentation()
            self.create_deployment_manifest()
            
            print("\n" + "=" * 50)
            print("Deployment build completed successfully!")
            print(f"Deployment package available at: {self.deploy_dir.absolute()}")
            print("\nNext steps:")
            print("1. Copy the deployment package to your target server")
            print("2. Run ./deploy-docker.sh for Docker deployment")
            print("3. Or run ./deploy-standalone.sh for standalone deployment")
            
        except Exception as e:
            print(f"\nDeployment build failed: {e}")
            sys.exit(1)

def main():
    deployer = MelanieDeployer()
    deployer.run_deployment()

if __name__ == "__main__":
    main()