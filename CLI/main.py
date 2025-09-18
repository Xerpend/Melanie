#!/usr/bin/env python3
"""
Melanie CLI - Main entry point for the terminal-based AI coding assistant.

This module provides the main CLI interface for interacting with Melanie's
coding capabilities through a rich terminal interface.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

try:
    # Try relative imports first (when installed as package)
    from .cli_app import MelanieCLI
    from .theme import DarkBlueTheme
    from .session import SessionManager
    from .config import CLIConfig
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    
    from cli_app import MelanieCLI
    from theme import DarkBlueTheme
    from session import SessionManager
    from config import CLIConfig


app = typer.Typer(
    name="melanie-cli",
    help="Melanie AI Terminal Coder - Intelligent coding assistant with agent coordination",
    add_completion=False,
    rich_markup_mode="rich"
)

# Initialize console with dark blue theme
console = Console(theme=DarkBlueTheme())


@app.command()
def code(
    request: str = typer.Argument(..., help="Coding task description"),
    project_dir: Optional[Path] = typer.Option(
        None, "--project", "-p", help="Project directory (default: current)"
    ),
    agents: Optional[int] = typer.Option(
        None, "--agents", "-a", help="Number of agents (1-3, auto-determined if not specified)"
    ),
    parallel: Optional[bool] = typer.Option(
        None, "--parallel", help="Force parallel execution (auto-determined if not specified)"
    ),
    session_name: Optional[str] = typer.Option(
        None, "--session", "-s", help="Session name for persistence"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    )
):
    """
    Execute a coding task with AI assistance.
    
    Examples:
        melanie-cli code "Create a REST API for user management"
        melanie-cli code "Add unit tests for the auth module" --project ./my-app
        melanie-cli code "Refactor database layer" --agents 2 --parallel
    """
    asyncio.run(_handle_code_request(
        request, project_dir, agents, parallel, session_name, verbose
    ))


@app.command()
def session(
    action: str = typer.Argument(..., help="Session action: list, load, delete"),
    name: Optional[str] = typer.Argument(None, help="Session name")
):
    """
    Manage CLI sessions.
    
    Examples:
        melanie-cli session list
        melanie-cli session load my-project
        melanie-cli session delete old-session
    """
    asyncio.run(_handle_session_command(action, name))


@app.command()
def config(
    action: str = typer.Argument(..., help="Config action: show, set, reset"),
    key: Optional[str] = typer.Argument(None, help="Configuration key"),
    value: Optional[str] = typer.Argument(None, help="Configuration value")
):
    """
    Manage CLI configuration.
    
    Examples:
        melanie-cli config show
        melanie-cli config set api_endpoint http://localhost:8000
        melanie-cli config reset
    """
    asyncio.run(_handle_config_command(action, key, value))


@app.command()
def version():
    """Show version information."""
    try:
        from . import __version__
    except ImportError:
        __version__ = "1.0.0"
    
    version_text = Text(f"Melanie CLI v{__version__}", style="bold #007BFF")
    panel = Panel(
        version_text,
        title="[bold #001F3F]Version Info[/bold #001F3F]",
        border_style="#007BFF"
    )
    console.print(panel)


async def _handle_code_request(
    request: str,
    project_dir: Optional[Path],
    agents: Optional[int],
    parallel: Optional[bool],
    session_name: Optional[str],
    verbose: bool
):
    """Handle coding request with proper error handling."""
    try:
        # Initialize CLI application
        cli_app = MelanieCLI(console=console, verbose=verbose)
        
        # Set project directory
        if project_dir:
            project_dir = project_dir.resolve()
        else:
            project_dir = Path.cwd()
        
        # Execute coding request
        await cli_app.handle_code_request(
            request=request,
            project_dir=project_dir,
            agents=agents,
            parallel=parallel,
            session_name=session_name
        )
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if verbose:
            console.print_exception()
        sys.exit(1)


async def _handle_session_command(action: str, name: Optional[str]):
    """Handle session management commands."""
    try:
        session_manager = SessionManager()
        
        if action == "list":
            sessions = await session_manager.list_sessions()
            if not sessions:
                console.print("[yellow]No sessions found[/yellow]")
                return
            
            console.print("[bold #001F3F]Available Sessions:[/bold #001F3F]")
            for session in sessions:
                console.print(f"  • {session}")
        
        elif action == "load":
            if not name:
                console.print("[red]Session name required for load action[/red]")
                sys.exit(1)
            
            session_data = await session_manager.load_session(name)
            if session_data:
                console.print(f"[green]Loaded session: {name}[/green]")
            else:
                console.print(f"[red]Session not found: {name}[/red]")
                sys.exit(1)
        
        elif action == "delete":
            if not name:
                console.print("[red]Session name required for delete action[/red]")
                sys.exit(1)
            
            success = await session_manager.delete_session(name)
            if success:
                console.print(f"[green]Deleted session: {name}[/green]")
            else:
                console.print(f"[red]Session not found: {name}[/red]")
                sys.exit(1)
        
        else:
            console.print(f"[red]Unknown session action: {action}[/red]")
            sys.exit(1)
    
    except Exception as e:
        console.print(f"[red]Session error: {e}[/red]")
        sys.exit(1)


async def _handle_config_command(action: str, key: Optional[str], value: Optional[str]):
    """Handle configuration commands."""
    try:
        config = CLIConfig()
        
        if action == "show":
            config_data = config.get_all()
            console.print("[bold #001F3F]Current Configuration:[/bold #001F3F]")
            for k, v in config_data.items():
                console.print(f"  {k}: {v}")
        
        elif action == "set":
            if not key or value is None:
                console.print("[red]Key and value required for set action[/red]")
                sys.exit(1)
            
            config.set(key, value)
            console.print(f"[green]Set {key} = {value}[/green]")
        
        elif action == "reset":
            config.reset()
            console.print("[green]Configuration reset to defaults[/green]")
        
        else:
            console.print(f"[red]Unknown config action: {action}[/red]")
            sys.exit(1)
    
    except Exception as e:
        console.print(f"[red]Config error: {e}[/red]")
        sys.exit(1)


def main():
    """Main entry point for the CLI application."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()