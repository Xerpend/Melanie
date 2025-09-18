"""
Dark Blue Theme for Melanie CLI.

Provides consistent color scheme across all CLI interfaces matching
the overall Melanie ecosystem design.
"""

from rich.theme import Theme
from rich.style import Style


class DarkBlueTheme(Theme):
    """
    Dark blue theme for Rich console output.
    
    Colors:
    - Primary: #001F3F (Dark Navy Blue)
    - Accent: #007BFF (Bright Blue)
    - Text: #F0F4F8 (Light Gray)
    - Success: #28A745 (Green)
    - Warning: #FFC107 (Yellow)
    - Error: #DC3545 (Red)
    """
    
    def __init__(self):
        styles = {
            # Base styles
            "info": "bold #007BFF",
            "success": "bold #28A745",
            "warning": "bold #FFC107", 
            "error": "bold #DC3545",
            "muted": "#6C757D",
            
            # Primary theme colors
            "primary": "bold #001F3F",
            "accent": "#007BFF",
            "text": "#F0F4F8",
            
            # Headers and titles
            "header": "bold #001F3F on #F0F4F8",
            "title": "bold #007BFF",
            "subtitle": "#007BFF",
            
            # Progress and status
            "progress.bar": "#007BFF",
            "progress.percentage": "#F0F4F8",
            "progress.data.speed": "#007BFF",
            "progress.description": "#F0F4F8",
            "progress.elapsed": "#6C757D",
            "progress.remaining": "#6C757D",
            
            # Status indicators
            "status.running": "bold #007BFF",
            "status.success": "bold #28A745",
            "status.failed": "bold #DC3545",
            "status.pending": "bold #FFC107",
            "status.cancelled": "bold #6C757D",
            
            # Agent-specific styles
            "agent.id": "bold #007BFF",
            "agent.task": "#F0F4F8",
            "agent.output": "#E9ECEF",
            "agent.error": "#DC3545",
            
            # Code-related styles
            "code.keyword": "bold #007BFF",
            "code.string": "#28A745",
            "code.number": "#FFC107",
            "code.comment": "#6C757D",
            "code.function": "#007BFF",
            "code.class": "bold #001F3F",
            
            # File and path styles
            "path": "#007BFF",
            "filename": "bold #F0F4F8",
            "extension": "#6C757D",
            
            # Panel and border styles
            "panel.border": "#007BFF",
            "panel.title": "bold #001F3F",
            
            # Table styles
            "table.header": "bold #001F3F on #F0F4F8",
            "table.row": "#F0F4F8",
            "table.row.alternate": "#E9ECEF",
            
            # Prompt styles
            "prompt": "bold #007BFF",
            "prompt.choices": "#F0F4F8",
            "prompt.default": "#6C757D",
            
            # Log levels
            "log.debug": "#6C757D",
            "log.info": "#007BFF", 
            "log.warning": "#FFC107",
            "log.error": "bold #DC3545",
            "log.critical": "bold white on #DC3545",
            
            # Syntax highlighting for code blocks
            "syntax.keyword": "bold #007BFF",
            "syntax.string": "#28A745",
            "syntax.number": "#FFC107",
            "syntax.comment": "italic #6C757D",
            "syntax.function": "#007BFF",
            "syntax.class": "bold #001F3F",
            "syntax.variable": "#F0F4F8",
            "syntax.operator": "#007BFF",
            
            # Special UI elements
            "spinner": "#007BFF",
            "rule": "#007BFF",
            "tree.line": "#007BFF",
            
            # Interactive elements
            "button": "bold #F0F4F8 on #007BFF",
            "button.hover": "bold #F0F4F8 on #001F3F",
            "link": "underline #007BFF",
            "link.hover": "underline bold #007BFF",
        }
        
        super().__init__(styles)


# Predefined style objects for common use cases
STYLES = {
    "primary": Style(color="#001F3F", bold=True),
    "accent": Style(color="#007BFF"),
    "success": Style(color="#28A745", bold=True),
    "warning": Style(color="#FFC107", bold=True),
    "error": Style(color="#DC3545", bold=True),
    "muted": Style(color="#6C757D"),
    "text": Style(color="#F0F4F8"),
    
    # Agent status styles
    "agent_running": Style(color="#007BFF", bold=True),
    "agent_success": Style(color="#28A745", bold=True),
    "agent_failed": Style(color="#DC3545", bold=True),
    
    # Code generation styles
    "code_generated": Style(color="#28A745"),
    "code_testing": Style(color="#FFC107"),
    "code_error": Style(color="#DC3545"),
    
    # Progress styles
    "progress_active": Style(color="#007BFF"),
    "progress_complete": Style(color="#28A745"),
}


def get_theme() -> DarkBlueTheme:
    """Get the default dark blue theme instance."""
    return DarkBlueTheme()


def get_style(name: str) -> Style:
    """Get a predefined style by name."""
    return STYLES.get(name, Style())


# Color constants for direct use
class Colors:
    """Color constants matching the theme."""
    PRIMARY = "#001F3F"
    ACCENT = "#007BFF" 
    SUCCESS = "#28A745"
    WARNING = "#FFC107"
    ERROR = "#DC3545"
    MUTED = "#6C757D"
    TEXT = "#F0F4F8"
    BACKGROUND = "#000000"