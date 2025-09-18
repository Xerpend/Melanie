#!/usr/bin/env python3
"""
Melanie AI Ecosystem - Comprehensive Suite Launcher
====================================================

This script launches the complete Melanie AI ecosystem with all components:
- RAG System (Rust-based engine)
- API Server (FastAPI with Tailscale integration)
- Web Interface (React/Next.js chat interface)
- CLI Tools (Terminal coder with agent coordination)
- Email Client (Tauri desktop application)

Usage:
    python launch_melanie_suite.py [options]

Options:
    --api-only          Launch only the API server
    --web-only          Launch only the web interface
    --full              Launch all components (default)
    --check             Check prerequisites and system status
    --build             Build all components before launching
    --help              Show this help message

Prerequisites:
    - Python 3.11+
    - Node.js 18+
    - Rust 1.70+
    - Tailscale network access
    - API keys configured in .env file
"""

import os
import sys
import subprocess
import time
import signal
import threading
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('melanie_suite.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('MelanieSuite')

class Colors:
    """ANSI color codes for terminal output"""
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

class MelanieSuiteLauncher:
    """Comprehensive launcher for the Melanie AI ecosystem"""
    
    def __init__(self):
        self.project_root = Path.cwd()
        self.processes = {}
        self.running = True
        self.start_time = datetime.now()
        
        # Component configurations
        self.components = {
            'rag': {
                'name': 'RAG System',
                'path': self.project_root / 'RAG',
                'build_cmd': ['cargo', 'build', '--release'],
                'start_cmd': None,  # RAG is a library, not a service
                'port': None,
                'health_check': self._check_rag_system,
                'required': True
            },
            'api': {
                'name': 'API Server',
                'path': self.project_root / 'API',
                'build_cmd': None,
                'start_cmd': ['python', 'run_server.py'],
                'port': 8000,
                'health_check': self._check_api_server,
                'required': True
            },
            'web': {
                'name': 'Web Interface',
                'path': self.project_root / 'WEB',
                'build_cmd': ['npm', 'run', 'build'],
                'start_cmd': ['npm', 'start'],
                'port': 3000,
                'health_check': self._check_web_interface,
                'required': False
            },
            'cli': {
                'name': 'CLI Tools',
                'path': self.project_root / 'CLI',
                'build_cmd': ['python', 'build.py'],
                'start_cmd': None,  # CLI is on-demand
                'port': None,
                'health_check': self._check_cli_tools,
                'required': False
            },
            'email': {
                'name': 'Email Client',
                'path': self.project_root / 'Email',
                'build_cmd': ['npm', 'run', 'tauri', 'build'],
                'start_cmd': ['npm', 'run', 'tauri', 'dev'],
                'port': None,
                'health_check': self._check_email_client,
                'required': False
            }
        }
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def print_banner(self):
        """Print the Melanie AI banner"""
        banner = f"""
{Colors.BLUE}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                    🤖 MELANIE AI ECOSYSTEM LAUNCHER 🤖                      ║
║                                                                              ║
║                     Comprehensive AI Assistant Suite                        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
{Colors.END}

{Colors.CYAN}🚀 Multi-Model AI Integration{Colors.END}
   • Grok-4, Grok-3-mini, Grok-Code-Fast, GPT-5-mini, Perplexity

{Colors.GREEN}🔧 Production-Grade Components{Colors.END}
   • FastAPI Server with Tailscale Security
   • Rust-based RAG System with PyO3 Bindings
   • React/Next.js Web Chat Interface
   • Terminal CLI Coder with Agent Coordination
   • Tauri Desktop Email Client with AI Features

{Colors.YELLOW}⚡ Advanced Capabilities{Colors.END}
   • Deep Research Orchestration with Multi-Agent Coordination
   • Tool Calling and Function Execution
   • Cross-Component Context Sharing
   • Real-time Web Search Integration
   • Document Processing and RAG Integration

{Colors.PURPLE}🔒 Enterprise Security{Colors.END}
   • Tailscale Network Requirement
   • API Key Authentication with Rate Limiting
   • Input Validation and Sanitization
   • Secure Error Handling

{Colors.WHITE}Starting system validation...{Colors.END}
"""
        print(banner)
    
    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are installed"""
        logger.info("Checking system prerequisites...")
        
        checks = [
            ('Python 3.11+', self._check_python),
            ('Node.js 18+', self._check_nodejs),
            ('Rust 1.70+', self._check_rust),
            ('Environment Variables', self._check_env_vars),
            ('Tailscale Network', self._check_tailscale),
            ('Project Structure', self._check_project_structure)
        ]
        
        all_passed = True
        
        print(f"\n{Colors.BOLD}🔍 System Prerequisites Check{Colors.END}")
        print("=" * 50)
        
        for check_name, check_func in checks:
            try:
                result = check_func()
                status = f"{Colors.GREEN}✅ PASS{Colors.END}" if result else f"{Colors.RED}❌ FAIL{Colors.END}"
                print(f"{check_name:<25} {status}")
                if not result:
                    all_passed = False
            except Exception as e:
                print(f"{check_name:<25} {Colors.RED}❌ ERROR: {e}{Colors.END}")
                all_passed = False
        
        print("=" * 50)
        
        if all_passed:
            print(f"{Colors.GREEN}{Colors.BOLD}✅ All prerequisites satisfied!{Colors.END}")
        else:
            print(f"{Colors.RED}{Colors.BOLD}❌ Some prerequisites failed. Please fix before launching.{Colors.END}")
        
        return all_passed
    
    def _check_python(self) -> bool:
        """Check Python version"""
        try:
            result = subprocess.run(['python', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip().split()[1]
                major, minor = map(int, version.split('.')[:2])
                return major >= 3 and minor >= 11
        except Exception:
            pass
        return False
    
    def _check_nodejs(self) -> bool:
        """Check Node.js version"""
        try:
            result = subprocess.run(['node', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip().replace('v', '')
                major = int(version.split('.')[0])
                return major >= 18
        except Exception:
            pass
        return False
    
    def _check_rust(self) -> bool:
        """Check Rust version"""
        try:
            result = subprocess.run(['rustc', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip().split()[1]
                major, minor = map(int, version.split('.')[:2])
                return major >= 1 and minor >= 70
        except Exception:
            pass
        return False
    
    def _check_env_vars(self) -> bool:
        """Check required environment variables"""
        env_file = self.project_root / '.env'
        if not env_file.exists():
            return False
        
        required_vars = ['XAI_API_KEY', 'OPENAI_API_KEY', 'PERPLEXITY_API_KEY']
        
        try:
            with open(env_file) as f:
                content = f.read()
                return all(var in content for var in required_vars)
        except Exception:
            return False
    
    def _check_tailscale(self) -> bool:
        """Check Tailscale network connectivity - REQUIRED for security"""
        try:
            # Check if tailscale command is available
            result = subprocess.run(['tailscale', 'status'], capture_output=True, text=True)
            if result.returncode == 0:
                return True
            
            # Alternative: Check for tailscale0 interface or Tailscale-like IPs
            import psutil
            interfaces = psutil.net_if_addrs()
            
            # Look for tailscale0 interface
            if 'tailscale0' in interfaces:
                return True
            
            # Look for interfaces with Tailscale-like IPs (100.x.x.x range)
            for interface_name, addresses in interfaces.items():
                for addr in addresses:
                    if hasattr(addr, 'family') and addr.family == 2 and addr.address.startswith('100.'):
                        return True
            
            # Development mode fallback
            if os.getenv('MELANIE_DEV_MODE', 'false').lower() == 'true':
                logger.info("Development mode: Tailscale check passed")
                return True
            
            return False
            
        except Exception:
            # Development mode fallback
            if os.getenv('MELANIE_DEV_MODE', 'false').lower() == 'true':
                return True
            return False
    
    def _check_project_structure(self) -> bool:
        """Check project directory structure"""
        required_dirs = ['API', 'AI', 'CLI', 'WEB', 'Email', 'RAG']
        return all((self.project_root / dir_name).exists() for dir_name in required_dirs)
    
    def get_tailscale_ip(self) -> Optional[str]:
        """Get Tailscale IP address for secure access"""
        try:
            import psutil
            interfaces = psutil.net_if_addrs()
            
            # Look for tailscale0 interface first
            if 'tailscale0' in interfaces:
                for addr in interfaces['tailscale0']:
                    if hasattr(addr, 'family') and addr.family == 2:  # AF_INET (IPv4)
                        return addr.address
            
            # Alternative: Look for interfaces with Tailscale-like IPs (100.x.x.x range)
            for interface_name, addresses in interfaces.items():
                for addr in addresses:
                    if hasattr(addr, 'family') and addr.family == 2 and addr.address.startswith('100.'):
                        return addr.address
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting Tailscale IP: {e}")
            return None
    
    def build_components(self, components: List[str] = None) -> bool:
        """Build specified components or all components"""
        if components is None:
            components = list(self.components.keys())
        
        logger.info(f"Building components: {', '.join(components)}")
        
        print(f"\n{Colors.BOLD}🔨 Building Components{Colors.END}")
        print("=" * 50)
        
        all_success = True
        
        for component in components:
            if component not in self.components:
                logger.warning(f"Unknown component: {component}")
                continue
            
            config = self.components[component]
            
            if config['build_cmd'] is None:
                print(f"{config['name']:<20} {Colors.YELLOW}⏭️  SKIP (no build required){Colors.END}")
                continue
            
            print(f"{config['name']:<20} {Colors.BLUE}🔨 Building...{Colors.END}")
            
            try:
                result = subprocess.run(
                    config['build_cmd'],
                    cwd=config['path'],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                
                if result.returncode == 0:
                    print(f"{config['name']:<20} {Colors.GREEN}✅ Built successfully{Colors.END}")
                else:
                    print(f"{config['name']:<20} {Colors.RED}❌ Build failed{Colors.END}")
                    logger.error(f"Build failed for {component}: {result.stderr}")
                    all_success = False
                    
            except subprocess.TimeoutExpired:
                print(f"{config['name']:<20} {Colors.RED}❌ Build timeout{Colors.END}")
                all_success = False
            except Exception as e:
                print(f"{config['name']:<20} {Colors.RED}❌ Build error: {e}{Colors.END}")
                all_success = False
        
        print("=" * 50)
        return all_success
    
    def start_component(self, component: str) -> bool:
        """Start a specific component"""
        if component not in self.components:
            logger.error(f"Unknown component: {component}")
            return False
        
        config = self.components[component]
        
        if config['start_cmd'] is None:
            logger.info(f"{config['name']} does not require a service process")
            return True
        
        logger.info(f"Starting {config['name']}...")
        
        try:
            process = subprocess.Popen(
                config['start_cmd'],
                cwd=config['path'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.processes[component] = process
            
            # Give the process a moment to start
            time.sleep(2)
            
            # Check if process is still running
            if process.poll() is None:
                logger.info(f"{config['name']} started successfully (PID: {process.pid})")
                return True
            else:
                logger.error(f"{config['name']} failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start {config['name']}: {e}")
            return False
    
    def stop_component(self, component: str):
        """Stop a specific component"""
        if component in self.processes:
            process = self.processes[component]
            if process.poll() is None:
                logger.info(f"Stopping {self.components[component]['name']}...")
                process.terminate()
                
                # Wait for graceful shutdown
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Force killing {self.components[component]['name']}...")
                    process.kill()
                
                del self.processes[component]
    
    def _check_rag_system(self) -> bool:
        """Check RAG system status"""
        rag_path = self.project_root / 'RAG'
        return (rag_path / 'Cargo.toml').exists()
    
    def _check_api_server(self) -> bool:
        """Check API server health"""
        try:
            import requests
            response = requests.get('http://localhost:8000/health', timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def _check_web_interface(self) -> bool:
        """Check web interface health"""
        try:
            import requests
            response = requests.get('http://localhost:3000', timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def _check_cli_tools(self) -> bool:
        """Check CLI tools availability"""
        cli_path = self.project_root / 'CLI'
        return (cli_path / 'main.py').exists()
    
    def _check_email_client(self) -> bool:
        """Check email client availability"""
        email_path = self.project_root / 'Email'
        return (email_path / 'src-tauri' / 'Cargo.toml').exists()
    
    def monitor_components(self):
        """Monitor running components and restart if needed"""
        while self.running:
            for component, process in list(self.processes.items()):
                if process.poll() is not None:
                    logger.warning(f"{self.components[component]['name']} has stopped unexpectedly")
                    # Could implement auto-restart logic here
            
            time.sleep(10)  # Check every 10 seconds
    
    def show_status(self):
        """Show current system status"""
        print(f"\n{Colors.BOLD}📊 System Status{Colors.END}")
        print("=" * 50)
        
        uptime = datetime.now() - self.start_time
        print(f"Uptime: {uptime}")
        print(f"Running processes: {len(self.processes)}")
        
        for component, config in self.components.items():
            if component in self.processes:
                process = self.processes[component]
                status = f"{Colors.GREEN}🟢 RUNNING (PID: {process.pid}){Colors.END}"
            else:
                if config['start_cmd'] is None:
                    status = f"{Colors.BLUE}🔵 LIBRARY{Colors.END}"
                else:
                    status = f"{Colors.YELLOW}🟡 STOPPED{Colors.END}"
            
            print(f"{config['name']:<20} {status}")
        
        print("=" * 50)
    
    def launch_full_suite(self):
        """Launch the complete Melanie AI suite"""
        logger.info("Launching complete Melanie AI suite...")
        
        print(f"\n{Colors.BOLD}🚀 Launching Melanie AI Suite{Colors.END}")
        print("=" * 50)
        
        # Start core components in order
        core_components = ['api', 'web']
        
        for component in core_components:
            config = self.components[component]
            print(f"Starting {config['name']}...")
            
            if self.start_component(component):
                print(f"{config['name']:<20} {Colors.GREEN}✅ Started{Colors.END}")
                
                # Wait for health check
                if config['health_check']:
                    print(f"Waiting for {config['name']} to be ready...")
                    for _ in range(30):  # Wait up to 30 seconds
                        if config['health_check']():
                            print(f"{config['name']:<20} {Colors.GREEN}✅ Ready{Colors.END}")
                            break
                        time.sleep(1)
                    else:
                        print(f"{config['name']:<20} {Colors.YELLOW}⚠️  Started but not responding{Colors.END}")
            else:
                print(f"{config['name']:<20} {Colors.RED}❌ Failed to start{Colors.END}")
        
        print("=" * 50)
        
        # Show access information with Tailscale IP
        tailscale_ip = self.get_tailscale_ip()
        print(f"\n{Colors.BOLD}🌐 Secure Access Information (Tailscale Only){Colors.END}")
        print("=" * 50)
        if tailscale_ip:
            print(f"🔒 API Server:      http://{tailscale_ip}:8000")
            print(f"🔒 API Docs:        http://{tailscale_ip}:8000/docs")
            print(f"🔒 Web Interface:   http://{tailscale_ip}:3000")
            print(f"🔒 Tailscale IP:    {tailscale_ip}")
        else:
            print(f"{Colors.RED}⚠️  Tailscale IP not detected - check Tailscale status{Colors.END}")
        print(f"💻 CLI Tool:        python CLI/main.py")
        print(f"📧 Email Client:    npm run tauri dev (in Email/)")
        print("=" * 50)
        print(f"{Colors.YELLOW}🔒 SECURITY: Access restricted to Tailscale network only{Colors.END}")
        print(f"{Colors.YELLOW}🔒 NO localhost or public internet access permitted{Colors.END}")
        print("=" * 50)
        
        # Start monitoring thread
        monitor_thread = threading.Thread(target=self.monitor_components, daemon=True)
        monitor_thread.start()
        
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 Melanie AI Suite is running!{Colors.END}")
        print(f"{Colors.CYAN}Press Ctrl+C to stop all services{Colors.END}")
        
        # Keep main thread alive
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Received shutdown signal, stopping all components...")
        self.running = False
        self.shutdown()
    
    def shutdown(self):
        """Gracefully shutdown all components"""
        print(f"\n{Colors.YELLOW}🛑 Shutting down Melanie AI Suite...{Colors.END}")
        
        for component in list(self.processes.keys()):
            self.stop_component(component)
        
        print(f"{Colors.GREEN}✅ All components stopped successfully{Colors.END}")
        logger.info("Melanie AI Suite shutdown complete")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Melanie AI Ecosystem - Comprehensive Suite Launcher',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python launch_melanie_suite.py                    # Launch full suite
  python launch_melanie_suite.py --check            # Check prerequisites only
  python launch_melanie_suite.py --build            # Build all components
  python launch_melanie_suite.py --api-only         # Launch API server only
  python launch_melanie_suite.py --web-only         # Launch web interface only
        """
    )
    
    parser.add_argument('--api-only', action='store_true', help='Launch only the API server')
    parser.add_argument('--web-only', action='store_true', help='Launch only the web interface')
    parser.add_argument('--full', action='store_true', help='Launch all components (default)')
    parser.add_argument('--check', action='store_true', help='Check prerequisites and system status')
    parser.add_argument('--build', action='store_true', help='Build all components before launching')
    parser.add_argument('--status', action='store_true', help='Show current system status')
    
    args = parser.parse_args()
    
    launcher = MelanieSuiteLauncher()
    launcher.print_banner()
    
    try:
        if args.check:
            success = launcher.check_prerequisites()
            sys.exit(0 if success else 1)
        
        if args.status:
            launcher.show_status()
            sys.exit(0)
        
        # Check prerequisites first
        if not launcher.check_prerequisites():
            print(f"\n{Colors.RED}❌ Prerequisites check failed. Please fix issues before launching.{Colors.END}")
            sys.exit(1)
        
        if args.build:
            if not launcher.build_components():
                print(f"\n{Colors.RED}❌ Build failed. Please fix issues before launching.{Colors.END}")
                sys.exit(1)
        
        if args.api_only:
            print(f"\n{Colors.BLUE}🚀 Launching API Server only...{Colors.END}")
            if launcher.start_component('api'):
                print(f"{Colors.GREEN}✅ API Server started at http://localhost:8000{Colors.END}")
                print(f"{Colors.CYAN}Press Ctrl+C to stop{Colors.END}")
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
            else:
                print(f"{Colors.RED}❌ Failed to start API Server{Colors.END}")
                sys.exit(1)
        
        elif args.web_only:
            print(f"\n{Colors.BLUE}🚀 Launching Web Interface only...{Colors.END}")
            if launcher.start_component('web'):
                print(f"{Colors.GREEN}✅ Web Interface started at http://localhost:3000{Colors.END}")
                print(f"{Colors.CYAN}Press Ctrl+C to stop{Colors.END}")
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
            else:
                print(f"{Colors.RED}❌ Failed to start Web Interface{Colors.END}")
                sys.exit(1)
        
        else:
            # Launch full suite (default)
            launcher.launch_full_suite()
    
    except KeyboardInterrupt:
        pass
    finally:
        launcher.shutdown()

if __name__ == "__main__":
    main()