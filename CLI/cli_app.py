"""
Main CLI Application class for Melanie Terminal Coder.

Handles the core CLI functionality including agent coordination,
progress tracking, and user interaction.
"""

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text
from rich.live import Live

try:
    from .session import SessionManager
    from .config import CLIConfig
    from .api_client import APIClient
    from .agent_coordinator import AgentCoordinator
    from .plan_generator import PlanGenerator
    from .result_compiler import ResultCompiler
except ImportError:
    from session import SessionManager
    from config import CLIConfig
    from api_client import APIClient
    from agent_coordinator import AgentCoordinator
    from plan_generator import PlanGenerator
    from result_compiler import ResultCompiler


class MelanieCLI:
    """
    Main CLI application for Melanie Terminal Coder.
    
    Provides the primary interface for coding tasks with AI assistance,
    including plan generation, agent coordination, and result compilation.
    """
    
    def __init__(self, console: Optional[Console] = None, verbose: bool = False):
        """
        Initialize the CLI application.
        
        Args:
            console: Rich console instance (creates new if None)
            verbose: Enable verbose output
        """
        self.console = console or Console()
        self.verbose = verbose
        self.config = CLIConfig()
        self.session_manager = SessionManager()
        self.api_client = APIClient(self.config.get("api_endpoint"))
        self.plan_generator = PlanGenerator(self.api_client)
        self.agent_coordinator = AgentCoordinator(self.api_client, self.console)
        self.result_compiler = ResultCompiler(self.console)
        
        # Current session state
        self.current_session: Optional[Dict[str, Any]] = None
        self.current_project_dir: Optional[Path] = None
    
    async def handle_code_request(
        self,
        request: str,
        project_dir: Path,
        agents: Optional[int] = None,
        parallel: Optional[bool] = None,
        session_name: Optional[str] = None
    ):
        """
        Handle a coding request from start to finish.
        
        Args:
            request: The coding task description
            project_dir: Project directory path
            agents: Number of agents to use (auto-determined if None)
            parallel: Force parallel execution (auto-determined if None)
            session_name: Session name for persistence
        """
        try:
            # Initialize session
            await self._initialize_session(session_name, project_dir)
            
            # Display welcome message
            self._display_welcome(request, project_dir)
            
            # Generate execution plan
            self.console.print("\n[info]Analyzing request and generating execution plan...[/info]")
            
            with self.console.status("[spinner]Generating plan..."):
                plan = await self.plan_generator.generate_plan(
                    request=request,
                    project_dir=project_dir,
                    suggested_agents=agents,
                    force_parallel=parallel
                )
            
            # Display plan to user
            self._display_plan(plan)
            
            # Get user confirmation
            if not self._confirm_plan():
                self.console.print("[warning]Plan cancelled by user[/warning]")
                return
            
            # Execute plan with progress tracking
            results = await self._execute_plan_with_progress(plan)
            
            # Compile and display results
            compiled_results = await self.result_compiler.compile_results(results)
            self._display_results(compiled_results)
            
            # Handle user actions
            await self._handle_user_actions(compiled_results)
            
        except KeyboardInterrupt:
            self.console.print("\n[warning]Operation cancelled by user[/warning]")
            await self._save_session_state()
        except Exception as e:
            self.console.print(f"[error]Execution failed: {e}[/error]")
            if self.verbose:
                self.console.print_exception()
            raise
    
    async def _initialize_session(self, session_name: Optional[str], project_dir: Path):
        """Initialize or load a session."""
        self.current_project_dir = project_dir
        
        if session_name:
            # Try to load existing session
            session_data = await self.session_manager.load_session(session_name)
            if session_data:
                self.current_session = session_data
                self.console.print(f"[success]Loaded session: {session_name}[/success]")
            else:
                # Create new session
                self.current_session = await self.session_manager.create_session(
                    session_name, project_dir
                )
                self.console.print(f"[success]Created new session: {session_name}[/success]")
        else:
            # Create temporary session
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_name = f"temp_{timestamp}"
            self.current_session = await self.session_manager.create_session(
                temp_name, project_dir
            )
    
    def _display_welcome(self, request: str, project_dir: Path):
        """Display welcome message and request summary."""
        welcome_text = Text()
        welcome_text.append("Melanie Terminal Coder\n", style="bold #001F3F")
        welcome_text.append(f"Request: {request}\n", style="#F0F4F8")
        welcome_text.append(f"Project: {project_dir}", style="#6C757D")
        
        panel = Panel(
            welcome_text,
            title="[bold #007BFF]Coding Assistant[/bold #007BFF]",
            border_style="#007BFF",
            padding=(1, 2)
        )
        self.console.print(panel)
    
    def _display_plan(self, plan: Dict[str, Any]):
        """Display the execution plan to the user."""
        # Plan summary
        summary_text = Text()
        summary_text.append(f"Tasks: {len(plan['tasks'])}\n", style="#F0F4F8")
        summary_text.append(f"Agents: {plan['agent_count']}\n", style="#F0F4F8")
        summary_text.append(f"Execution: {'Parallel' if plan['parallel'] else 'Sequential'}\n", style="#F0F4F8")
        summary_text.append(f"Estimated time: {plan['estimated_duration']} minutes", style="#6C757D")
        
        summary_panel = Panel(
            summary_text,
            title="[bold #001F3F]Execution Plan[/bold #001F3F]",
            border_style="#007BFF"
        )
        self.console.print(summary_panel)
        
        # Task breakdown
        if self.verbose or len(plan['tasks']) <= 5:
            task_table = Table(title="Task Breakdown", border_style="#007BFF")
            task_table.add_column("Task", style="#F0F4F8")
            task_table.add_column("Agent", style="#007BFF")
            task_table.add_column("Dependencies", style="#6C757D")
            
            for i, task in enumerate(plan['tasks']):
                task_table.add_row(
                    task['description'][:50] + ("..." if len(task['description']) > 50 else ""),
                    f"Agent {task['agent_id']}",
                    ", ".join(task.get('dependencies', []))
                )
            
            self.console.print(task_table)
    
    def _confirm_plan(self) -> bool:
        """Get user confirmation for the execution plan."""
        return Confirm.ask(
            "[prompt]Proceed with this execution plan?[/prompt]",
            default=True,
            console=self.console
        )
    
    async def _execute_plan_with_progress(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute the plan with progress tracking."""
        # Create progress display
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        )
        
        with progress:
            # Add main progress task
            main_task = progress.add_task(
                "Executing coding plan...", 
                total=len(plan['tasks'])
            )
            
            # Execute tasks
            if plan['parallel']:
                results = await self.agent_coordinator.execute_parallel(
                    plan['tasks'], progress, main_task
                )
            else:
                results = await self.agent_coordinator.execute_sequential(
                    plan['tasks'], progress, main_task
                )
            
            progress.update(main_task, completed=len(plan['tasks']))
        
        return results
    
    def _display_results(self, results: Dict[str, Any]):
        """Display the compiled results."""
        # Results summary
        summary_text = Text()
        summary_text.append(f"Tasks completed: {results['completed_tasks']}\n", style="#28A745")
        summary_text.append(f"Tasks failed: {results['failed_tasks']}\n", style="#DC3545")
        summary_text.append(f"Files created: {len(results['created_files'])}\n", style="#F0F4F8")
        summary_text.append(f"Files modified: {len(results['modified_files'])}\n", style="#F0F4F8")
        summary_text.append(f"Tests passed: {results['tests_passed']}/{results['total_tests']}", style="#28A745")
        
        summary_panel = Panel(
            summary_text,
            title="[bold #001F3F]Results Summary[/bold #001F3F]",
            border_style="#007BFF"
        )
        self.console.print(summary_panel)
        
        # Show created/modified files
        if results['created_files'] or results['modified_files']:
            file_table = Table(title="File Changes", border_style="#007BFF")
            file_table.add_column("File", style="#F0F4F8")
            file_table.add_column("Action", style="#007BFF")
            file_table.add_column("Lines", style="#6C757D")
            
            for file_info in results['created_files']:
                file_table.add_row(
                    file_info['path'],
                    "[success]Created[/success]",
                    str(file_info['lines'])
                )
            
            for file_info in results['modified_files']:
                file_table.add_row(
                    file_info['path'],
                    "[warning]Modified[/warning]",
                    f"+{file_info['added_lines']}/-{file_info['removed_lines']}"
                )
            
            self.console.print(file_table)
        
        # Show any errors or warnings
        if results.get('errors'):
            self.console.print("\n[error]Errors encountered:[/error]")
            for error in results['errors']:
                self.console.print(f"  • {error}", style="error")
        
        if results.get('warnings'):
            self.console.print("\n[warning]Warnings:[/warning]")
            for warning in results['warnings']:
                self.console.print(f"  • {warning}", style="warning")
    
    async def _handle_user_actions(self, results: Dict[str, Any]):
        """Handle post-execution user actions."""
        while True:
            # Show available actions with context
            self._display_action_menu(results)
            
            action = Prompt.ask(
                "\n[prompt]Next action[/prompt]",
                choices=["edit", "run", "test", "save", "report", "rag", "exit"],
                default="exit",
                console=self.console
            )
            
            if action == "edit":
                await self._handle_edit_action(results)
            elif action == "run":
                await self._handle_run_action(results)
            elif action == "test":
                await self._handle_test_action(results)
            elif action == "save":
                await self._handle_save_action(results)
            elif action == "report":
                await self._handle_report_action(results)
            elif action == "rag":
                await self._handle_rag_action(results)
            elif action == "exit":
                break
    
    async def _handle_edit_action(self, results: Dict[str, Any]):
        """Handle edit action - allow user to modify generated code."""
        self.console.print("[info]Opening files for editing...[/info]")
        # Implementation would integrate with user's preferred editor
        # For now, just show the files that can be edited
        if results['created_files'] or results['modified_files']:
            self.console.print("Files available for editing:")
            for file_info in results['created_files'] + results['modified_files']:
                self.console.print(f"  • {file_info['path']}")
    
    async def _handle_run_action(self, results: Dict[str, Any]):
        """Handle run action - execute the generated code."""
        self.console.print("[info]Running generated code...[/info]")
        # Implementation would execute the main entry point
        # This is a placeholder for the actual execution logic
        
    async def _handle_test_action(self, results: Dict[str, Any]):
        """Handle test action - run tests on generated code."""
        self.console.print("[info]Running tests...[/info]")
        
        if not self.current_project_dir:
            self.console.print("[error]No project directory available[/error]")
            return
        
        try:
            # Use the test executor to run tests
            from .test_executor import TestExecutor
            test_executor = TestExecutor(self.console)
            
            # Run tests in the current project directory
            test_report = await test_executor.execute_tests(
                project_path=self.current_project_dir,
                timeout=120
            )
            
            # Display summary
            if test_report.success:
                self.console.print(f"[success]✅ All tests passed! Coverage: {test_report.coverage.total_coverage:.1f}%[/success]")
            else:
                self.console.print(f"[error]❌ Tests failed. {test_report.failed_tests} failed, {test_report.passed_tests} passed[/error]")
                
                # Show failed tests
                if test_report.failed_tests > 0:
                    failed_test_names = [tc.name for tc in test_report.test_cases if tc.status == 'failed']
                    self.console.print(f"[error]Failed tests: {', '.join(failed_test_names)}[/error]")
        
        except ImportError:
            self.console.print("[error]Test executor not available[/error]")
        except Exception as e:
            self.console.print(f"[error]Test execution failed: {e}[/error]")
        
    async def _handle_save_action(self, results: Dict[str, Any]):
        """Handle save action - save session and results."""
        await self._save_session_state()
        self.console.print("[success]Session saved[/success]")
    
    def _display_action_menu(self, results: Dict[str, Any]):
        """Display available actions with context."""
        actions_text = Text()
        actions_text.append("Available Actions:\n", style="bold #001F3F")
        
        # Edit action
        if results.get('files', {}).get('created') or results.get('files', {}).get('modified'):
            actions_text.append("  📝 edit   - Open generated files for editing\n", style="#F0F4F8")
        else:
            actions_text.append("  📝 edit   - No files to edit\n", style="#6C757D")
        
        # Run action
        if self._has_executable_code(results):
            actions_text.append("  ▶️  run    - Execute the generated code\n", style="#F0F4F8")
        else:
            actions_text.append("  ▶️  run    - No executable code found\n", style="#6C757D")
        
        # Test action
        actions_text.append("  🧪 test   - Run tests and check coverage\n", style="#F0F4F8")
        
        # Save action
        actions_text.append("  💾 save   - Save session and results\n", style="#F0F4F8")
        
        # Report action
        actions_text.append("  📊 report - Generate detailed summary report\n", style="#F0F4F8")
        
        # RAG action
        actions_text.append("  🧠 rag    - Add results to RAG context\n", style="#F0F4F8")
        
        # Exit action
        actions_text.append("  🚪 exit   - Exit the CLI\n", style="#F0F4F8")
        
        panel = Panel(
            actions_text,
            title="[bold #007BFF]What would you like to do?[/bold #007BFF]",
            border_style="#007BFF"
        )
        self.console.print(panel)
    
    def _has_executable_code(self, results: Dict[str, Any]) -> bool:
        """Check if results contain executable code."""
        # Look for main.py, app.py, or other common entry points
        created_files = results.get('files', {}).get('created', [])
        modified_files = results.get('files', {}).get('modified', [])
        
        all_files = [f['path'] for f in created_files + modified_files]
        
        executable_patterns = ['main.py', 'app.py', 'run.py', '__main__.py', 'server.py', 'manage.py']
        return any(any(pattern in file_path for pattern in executable_patterns) for file_path in all_files)
    
    async def _handle_report_action(self, results: Dict[str, Any]):
        """Handle report generation action."""
        self.console.print("[info]Generating detailed summary report...[/info]")
        
        try:
            # Generate markdown report
            report_md = await self.result_compiler.generate_summary_report(results)
            
            # Save report to file
            if self.current_project_dir:
                report_file = self.current_project_dir / "melanie_execution_report.md"
                with open(report_file, 'w', encoding='utf-8') as f:
                    f.write(report_md)
                
                self.console.print(f"[success]Report saved to: {report_file}[/success]")
                
                # Ask if user wants to view the report
                if Confirm.ask("View the report now?", default=True, console=self.console):
                    self.console.print("\n" + "="*80)
                    self.console.print(report_md)
                    self.console.print("="*80 + "\n")
            else:
                # Just display the report
                self.console.print("\n" + "="*80)
                self.console.print(report_md)
                self.console.print("="*80 + "\n")
        
        except Exception as e:
            self.console.print(f"[error]Failed to generate report: {e}[/error]")
    
    async def _handle_rag_action(self, results: Dict[str, Any]):
        """Handle RAG integration action."""
        self.console.print("[info]Integrating results with RAG system...[/info]")
        
        try:
            # Generate summary for RAG ingestion
            rag_content = await self._prepare_rag_content(results)
            
            # Upload to RAG system via API
            response = await self.api_client.upload_file(
                file_path=f"session_{self.current_session['id']}_results.md",
                content=rag_content.encode('utf-8')
            )
            
            if response.success:
                self.console.print("[success]Results added to RAG context successfully[/success]")
                
                # Update session with RAG integration info
                if self.current_session:
                    self.current_session['context']['rag_integrated'] = True
                    self.current_session['context']['rag_file_id'] = response.data.get('file_id')
                    await self.session_manager.save_session(self.current_session)
            else:
                self.console.print(f"[error]Failed to integrate with RAG: {response.error}[/error]")
        
        except Exception as e:
            self.console.print(f"[error]RAG integration failed: {e}[/error]")
    
    async def _prepare_rag_content(self, results: Dict[str, Any]) -> str:
        """Prepare content for RAG ingestion."""
        content_lines = [
            f"# Melanie CLI Execution Results",
            f"Session: {self.current_session['name'] if self.current_session else 'Unknown'}",
            f"Project: {self.current_project_dir}",
            f"Timestamp: {datetime.now().isoformat()}",
            "",
            "## Summary",
            f"- Tasks completed: {results['summary']['completed_tasks']}",
            f"- Success rate: {results['summary']['success_rate']:.1%}",
            f"- Quality score: {results['summary']['quality_score']:.1f}/100",
            "",
            "## Files Created/Modified"
        ]
        
        # Add file information
        for file_info in results['files']['created']:
            content_lines.append(f"- Created: {file_info['path']} ({file_info['lines']} lines)")
        
        for file_info in results['files']['modified']:
            content_lines.append(f"- Modified: {file_info['path']} (+{file_info['added_lines']}/-{file_info['removed_lines']} lines)")
        
        # Add task details
        if results.get('tasks'):
            content_lines.extend([
                "",
                "## Task Details"
            ])
            for task in results['tasks']:
                content_lines.extend([
                    f"### {task.get('description', 'Unknown task')}",
                    f"- Agent: {task.get('agent_id', 'Unknown')}",
                    f"- Status: {task.get('status', 'Unknown')}",
                    f"- Duration: {task.get('execution_time', 0.0):.2f}s",
                    f"- Summary: {task.get('output_summary', 'No summary')}",
                    ""
                ])
        
        # Add recommendations
        if results.get('recommendations'):
            content_lines.extend([
                "## Recommendations"
            ])
            for rec in results['recommendations']:
                content_lines.extend([
                    f"- **{rec['type'].title()}** ({rec['priority']}): {rec['message']}",
                    f"  Action: {rec['action']}",
                    ""
                ])
        
        return "\n".join(content_lines)
    
    async def _save_session_state(self):
        """Save current session state."""
        if self.current_session:
            await self.session_manager.save_session(self.current_session)