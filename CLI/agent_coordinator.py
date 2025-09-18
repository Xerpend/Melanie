"""
Agent Coordinator for Melanie CLI.

Manages the execution of multiple AI agents for coding tasks,
handling both parallel and sequential execution with progress tracking.
"""

import asyncio
import signal
import threading
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import json
from enum import Enum

from rich.console import Console
from rich.progress import Progress, TaskID, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.table import Table
from rich.prompt import Confirm

try:
    from .api_client import APIClient, APIResponse
    from .code_generator import CodeGenerator
    from .test_executor import TestExecutor
except ImportError:
    from api_client import APIClient, APIResponse
    from code_generator import CodeGenerator
    from test_executor import TestExecutor


class ExecutionState(Enum):
    """Execution state for agent coordination."""
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentStatus(Enum):
    """Status for individual agents."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentCoordinator:
    """
    Coordinates multiple AI agents for coding task execution.
    
    Handles agent spawning, task distribution, progress tracking,
    and result compilation with support for both parallel and
    sequential execution strategies with graceful pause/resume.
    """
    
    def __init__(self, api_client: APIClient, console: Console):
        """
        Initialize agent coordinator.
        
        Args:
            api_client: API client for communication with Melanie server
            console: Rich console for output
        """
        self.api_client = api_client
        self.console = console
        self.active_agents: Dict[str, Dict[str, Any]] = {}
        self.completed_tasks: List[Dict[str, Any]] = []
        self.failed_tasks: List[Dict[str, Any]] = []
        
        # Code generation and testing components
        self.code_generator = CodeGenerator(api_client, console)
        self.test_executor = TestExecutor(console)
        
        # Execution control
        self.execution_state = ExecutionState.RUNNING
        self.pause_event = asyncio.Event()
        self.pause_event.set()  # Start unpaused
        self.cancel_event = asyncio.Event()
        
        # Real-time output tracking
        self.agent_outputs: Dict[str, List[str]] = {}
        self.output_callbacks: List[Callable[[str, str], None]] = []
        
        # Progress tracking
        self.progress_table = Table(show_header=True, header_style="bold blue")
        self.progress_table.add_column("Agent ID", style="cyan")
        self.progress_table.add_column("Status", style="green")
        self.progress_table.add_column("Task", style="white")
        self.progress_table.add_column("Progress", style="blue")
        self.progress_table.add_column("Output", style="dim")
        
        # Signal handling for graceful interruption
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful interruption."""
        def signal_handler(signum, frame):
            """Handle interrupt signals."""
            if self.execution_state == ExecutionState.RUNNING:
                self.console.print("\n[warning]Received interrupt signal. Pausing execution...[/warning]")
                self.pause_execution()
            elif self.execution_state == ExecutionState.PAUSED:
                self.console.print("\n[warning]Received second interrupt. Cancelling execution...[/warning]")
                self.cancel_execution()
        
        # Set up signal handlers (Unix-like systems)
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except AttributeError:
            # Windows doesn't have SIGTERM
            signal.signal(signal.SIGINT, signal_handler)
    
    def pause_execution(self):
        """Pause the execution of all agents."""
        if self.execution_state == ExecutionState.RUNNING:
            self.execution_state = ExecutionState.PAUSED
            self.pause_event.clear()
            self.console.print("[warning]Execution paused. Press 'r' to resume, 'c' to cancel, or 's' to show status.[/warning]")
            
            # Start interactive prompt in separate thread
            threading.Thread(target=self._handle_pause_input, daemon=True).start()
    
    def resume_execution(self):
        """Resume the execution of all agents."""
        if self.execution_state == ExecutionState.PAUSED:
            self.execution_state = ExecutionState.RUNNING
            self.pause_event.set()
            self.console.print("[success]Execution resumed.[/success]")
    
    def cancel_execution(self):
        """Cancel the execution of all agents."""
        self.execution_state = ExecutionState.CANCELLED
        self.cancel_event.set()
        self.pause_event.set()  # Unblock any waiting tasks
        self.console.print("[error]Execution cancelled.[/error]")
    
    def _handle_pause_input(self):
        """Handle user input during pause state."""
        while self.execution_state == ExecutionState.PAUSED:
            try:
                # Check if we're in a testing environment
                import sys
                if hasattr(sys, '_called_from_test') or 'pytest' in sys.modules:
                    # In test mode, don't try to read from stdin
                    break
                
                choice = input().lower().strip()
                if choice == 'r':
                    self.resume_execution()
                    break
                elif choice == 'c':
                    self.cancel_execution()
                    break
                elif choice == 's':
                    self._show_status()
                else:
                    print("Press 'r' to resume, 'c' to cancel, or 's' to show status.")
            except (EOFError, KeyboardInterrupt, OSError):
                # Handle test environment or other input errors
                self.cancel_execution()
                break
    
    def _show_status(self):
        """Show current status of all agents."""
        self.console.print("\n[info]Current Agent Status:[/info]")
        
        if not self.active_agents:
            self.console.print("[muted]No active agents[/muted]")
            return
        
        status_table = Table(show_header=True, header_style="bold blue")
        status_table.add_column("Agent ID", style="cyan")
        status_table.add_column("Status", style="green")
        status_table.add_column("Task", style="white")
        status_table.add_column("Last Output", style="dim")
        
        for agent_id, agent_info in self.active_agents.items():
            last_output = ""
            if agent_id in self.agent_outputs and self.agent_outputs[agent_id]:
                last_output = self.agent_outputs[agent_id][-1][:50] + "..."
            
            status_table.add_row(
                agent_id,
                agent_info.get('status', 'unknown'),
                agent_info.get('description', 'N/A')[:30] + "...",
                last_output
            )
        
        self.console.print(status_table)
        self.console.print("\nPress 'r' to resume, 'c' to cancel, or 's' to show status again.")
    
    def add_output_callback(self, callback: Callable[[str, str], None]):
        """Add a callback for real-time output updates."""
        self.output_callbacks.append(callback)
    
    def _emit_output(self, agent_id: str, output: str):
        """Emit output from an agent to all callbacks."""
        if agent_id not in self.agent_outputs:
            self.agent_outputs[agent_id] = []
        
        self.agent_outputs[agent_id].append(output)
        
        # Call all registered callbacks
        for callback in self.output_callbacks:
            try:
                callback(agent_id, output)
            except Exception as e:
                self.console.print(f"[error]Output callback error: {e}[/error]")
    
    async def execute_parallel(
        self,
        tasks: List[Dict[str, Any]],
        progress: Progress,
        main_task: TaskID
    ) -> List[Dict[str, Any]]:
        """
        Execute tasks in parallel using multiple agents with pause/resume support.
        
        Args:
            tasks: List of task definitions
            progress: Rich progress instance
            main_task: Main progress task ID
            
        Returns:
            List of agent execution results
        """
        self.console.print("[info]Starting parallel agent execution...[/info]")
        
        # Group tasks by dependencies to determine execution phases
        phases = self._group_tasks_by_dependencies(tasks)
        all_results = []
        
        try:
            for phase_num, phase_tasks in enumerate(phases):
                # Check for cancellation
                if self.execution_state == ExecutionState.CANCELLED:
                    self.console.print("[warning]Execution cancelled by user[/warning]")
                    break
                
                # Wait for pause to be lifted
                await self.pause_event.wait()
                
                self.console.print(f"[info]Executing phase {phase_num + 1} with {len(phase_tasks)} tasks[/info]")
                
                # Create agent tasks for this phase
                agent_tasks = []
                for task in phase_tasks:
                    agent_task = progress.add_task(
                        f"Agent {task['agent_id']}: {task['description'][:30]}...",
                        total=100
                    )
                    
                    # Register agent as active
                    self.active_agents[task['agent_id']] = {
                        'status': AgentStatus.PENDING.value,
                        'description': task['description'],
                        'progress_task': agent_task
                    }
                    
                    # Start agent execution
                    coroutine = self._execute_single_agent(
                        task, agent_task, progress, all_results
                    )
                    agent_tasks.append(coroutine)
                
                # Wait for all agents in this phase to complete
                phase_results = await asyncio.gather(*agent_tasks, return_exceptions=True)
                
                # Process results and handle exceptions
                for i, result in enumerate(phase_results):
                    agent_id = phase_tasks[i]['agent_id']
                    
                    if isinstance(result, Exception):
                        self.console.print(f"[error]Agent {agent_id} failed: {result}[/error]")
                        self.failed_tasks.append({
                            **phase_tasks[i],
                            'error': str(result),
                            'completed_at': datetime.now().isoformat()
                        })
                        self.active_agents[agent_id]['status'] = AgentStatus.FAILED.value
                    else:
                        all_results.append(result)
                        self.completed_tasks.append(result)
                        self.active_agents[agent_id]['status'] = AgentStatus.COMPLETED.value
                    
                    # Remove from active agents
                    if agent_id in self.active_agents:
                        del self.active_agents[agent_id]
                
                # Update main progress
                progress.update(main_task, advance=len(phase_tasks))
                
                # Check for cancellation after each phase
                if self.execution_state == ExecutionState.CANCELLED:
                    break
        
        except asyncio.CancelledError:
            self.console.print("[warning]Execution was cancelled[/warning]")
            self.execution_state = ExecutionState.CANCELLED
        except Exception as e:
            self.console.print(f"[error]Unexpected error during parallel execution: {e}[/error]")
            self.execution_state = ExecutionState.FAILED
        
        # Update final state
        if self.execution_state == ExecutionState.RUNNING:
            self.execution_state = ExecutionState.COMPLETED
        
        return all_results
    
    async def execute_sequential(
        self,
        tasks: List[Dict[str, Any]],
        progress: Progress,
        main_task: TaskID
    ) -> List[Dict[str, Any]]:
        """
        Execute tasks sequentially using agents with pause/resume support.
        
        Args:
            tasks: List of task definitions
            progress: Rich progress instance
            main_task: Main progress task ID
            
        Returns:
            List of agent execution results
        """
        self.console.print("[info]Starting sequential agent execution...[/info]")
        
        results = []
        
        try:
            for i, task in enumerate(tasks):
                # Check for cancellation
                if self.execution_state == ExecutionState.CANCELLED:
                    self.console.print("[warning]Execution cancelled by user[/warning]")
                    break
                
                # Wait for pause to be lifted
                await self.pause_event.wait()
                
                self.console.print(f"[info]Executing task {i + 1}/{len(tasks)}: {task['description'][:50]}[/info]")
                
                # Create progress task for this agent
                agent_task = progress.add_task(
                    f"Agent {task['agent_id']}: {task['description'][:30]}...",
                    total=100
                )
                
                # Register agent as active
                agent_id = task['agent_id']
                self.active_agents[agent_id] = {
                    'status': AgentStatus.PENDING.value,
                    'description': task['description'],
                    'progress_task': agent_task
                }
                
                try:
                    # Execute single agent
                    result = await self._execute_single_agent(
                        task, agent_task, progress, results
                    )
                    results.append(result)
                    self.completed_tasks.append(result)
                    self.active_agents[agent_id]['status'] = AgentStatus.COMPLETED.value
                    
                except Exception as e:
                    self.console.print(f"[error]Agent {agent_id} failed: {e}[/error]")
                    self.failed_tasks.append({
                        **task,
                        'error': str(e),
                        'completed_at': datetime.now().isoformat()
                    })
                    self.active_agents[agent_id]['status'] = AgentStatus.FAILED.value
                    
                    # Ask user if they want to continue after failure (only if not paused/cancelled)
                    if self.execution_state == ExecutionState.RUNNING:
                        if not Confirm.ask(f"Task failed. Continue with remaining tasks?", default=True):
                            break
                
                # Remove from active agents
                if agent_id in self.active_agents:
                    del self.active_agents[agent_id]
                
                # Update main progress
                progress.update(main_task, advance=1)
                
                # Check for cancellation after each task
                if self.execution_state == ExecutionState.CANCELLED:
                    break
        
        except asyncio.CancelledError:
            self.console.print("[warning]Execution was cancelled[/warning]")
            self.execution_state = ExecutionState.CANCELLED
        except Exception as e:
            self.console.print(f"[error]Unexpected error during sequential execution: {e}[/error]")
            self.execution_state = ExecutionState.FAILED
        
        # Update final state
        if self.execution_state == ExecutionState.RUNNING:
            self.execution_state = ExecutionState.COMPLETED
        
        return results
    
    async def _execute_single_agent(
        self,
        task: Dict[str, Any],
        agent_task: TaskID,
        progress: Progress,
        previous_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute a single agent task with pause/resume and real-time output support.
        
        Args:
            task: Task definition
            agent_task: Agent progress task ID
            progress: Rich progress instance
            previous_results: Results from previous tasks
            
        Returns:
            Agent execution result
        """
        agent_id = task['agent_id']
        start_time = datetime.now()
        
        try:
            # Update agent status
            if agent_id in self.active_agents:
                self.active_agents[agent_id]['status'] = AgentStatus.RUNNING.value
            
            # Update progress
            progress.update(agent_task, description=f"Agent {agent_id}: Initializing...")
            self._emit_output(agent_id, "Initializing agent...")
            
            # Wait for pause to be lifted
            await self.pause_event.wait()
            
            # Check for cancellation
            if self.execution_state == ExecutionState.CANCELLED:
                raise asyncio.CancelledError("Execution cancelled by user")
            
            # Prepare project context
            self._emit_output(agent_id, "Preparing project context...")
            project_context = await self._prepare_project_context(task)
            progress.update(agent_task, advance=10)
            
            # Wait for pause to be lifted and check cancellation
            await self.pause_event.wait()
            if self.execution_state == ExecutionState.CANCELLED:
                raise asyncio.CancelledError("Execution cancelled by user")
            
            # Prepare dependencies
            self._emit_output(agent_id, "Preparing dependencies...")
            dependencies = self._prepare_dependencies(task, previous_results)
            progress.update(agent_task, advance=10)
            
            # Wait for pause to be lifted and check cancellation
            await self.pause_event.wait()
            if self.execution_state == ExecutionState.CANCELLED:
                raise asyncio.CancelledError("Execution cancelled by user")
            
            # Update progress
            progress.update(agent_task, description=f"Agent {agent_id}: Executing task...")
            self._emit_output(agent_id, f"Executing task: {task['description'][:50]}...")
            
            # Check for cancellation before API call
            if self.execution_state == ExecutionState.CANCELLED:
                raise asyncio.CancelledError("Execution cancelled by user")
            
            # Check if this is a coding task that needs the enhanced workflow
            if self._is_coding_task(task):
                self._emit_output(agent_id, "Starting enhanced code generation workflow...")
                result = await self._execute_coding_task_with_workflow(
                    task, agent_id, project_context, dependencies, progress, agent_task, start_time
                )
            else:
                # Execute the task via API with Melanie-3-code (legacy workflow)
                response = await self.api_client.execute_agent_task(
                    task_description=task['description'],
                    agent_id=agent_id,
                    project_context=project_context,
                    dependencies=dependencies
                )
                
                progress.update(agent_task, advance=60)
                
                if not response.success:
                    error_msg = f"API error: {response.error}"
                    self._emit_output(agent_id, f"ERROR: {error_msg}")
                    raise Exception(error_msg)
                
                # Process response and emit output
                self._emit_output(agent_id, "Processing response...")
                result = self._process_agent_response(task, response.data, start_time)
            
            # Emit completion output
            if result.get('output'):
                self._emit_output(agent_id, f"Generated output: {result['output'][:100]}...")
            
            if result.get('tool_calls'):
                self._emit_output(agent_id, f"Executed {len(result['tool_calls'])} tool calls")
            
            # Update progress
            progress.update(agent_task, advance=20, description=f"Agent {agent_id}: Completed")
            self._emit_output(agent_id, f"Task completed successfully in {result['execution_time']:.2f}s")
            
            return result
            
        except asyncio.CancelledError:
            progress.update(agent_task, description=f"Agent {agent_id}: Cancelled")
            self._emit_output(agent_id, "Task cancelled by user")
            if agent_id in self.active_agents:
                self.active_agents[agent_id]['status'] = AgentStatus.CANCELLED.value
            raise
        except Exception as e:
            progress.update(agent_task, description=f"Agent {agent_id}: Failed")
            self._emit_output(agent_id, f"Task failed: {str(e)}")
            if agent_id in self.active_agents:
                self.active_agents[agent_id]['status'] = AgentStatus.FAILED.value
            raise e
    
    def _group_tasks_by_dependencies(self, tasks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Group tasks into execution phases based on dependencies.
        
        Args:
            tasks: List of task definitions
            
        Returns:
            List of task phases (each phase can execute in parallel)
        """
        phases = []
        remaining_tasks = tasks.copy()
        completed_task_ids = set()
        
        while remaining_tasks:
            # Find tasks with no unmet dependencies
            ready_tasks = []
            for task in remaining_tasks:
                dependencies = task.get('dependencies', [])
                if all(dep in completed_task_ids for dep in dependencies):
                    ready_tasks.append(task)
            
            if not ready_tasks:
                # Circular dependency or invalid dependency - take first task
                ready_tasks = [remaining_tasks[0]]
                self.console.print("[warning]Circular dependency detected, forcing execution[/warning]")
            
            # Add ready tasks to current phase
            phases.append(ready_tasks)
            
            # Remove ready tasks from remaining and mark as completed
            for task in ready_tasks:
                remaining_tasks.remove(task)
                completed_task_ids.add(task.get('id', task['agent_id']))
        
        return phases
    
    async def _prepare_project_context(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare project context for agent execution.
        
        Args:
            task: Task definition
            
        Returns:
            Project context dictionary
        """
        # This would analyze the project directory and prepare context
        # For now, return basic context
        return {
            'project_dir': task.get('project_dir', '.'),
            'task_type': task.get('type', 'general'),
            'files': [],  # Would be populated with relevant files
            'dependencies': task.get('dependencies', []),
            'constraints': task.get('constraints', {})
        }
    
    def _prepare_dependencies(
        self,
        task: Dict[str, Any],
        previous_results: List[Dict[str, Any]]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Prepare dependency results for agent execution.
        
        Args:
            task: Task definition
            previous_results: Results from previous tasks
            
        Returns:
            List of relevant dependency results
        """
        task_dependencies = task.get('dependencies', [])
        if not task_dependencies:
            return None
        
        # Find results for dependencies
        dependency_results = []
        for result in previous_results:
            if result.get('task_id') in task_dependencies:
                dependency_results.append({
                    'task_id': result['task_id'],
                    'output': result.get('output'),
                    'files_created': result.get('files_created', []),
                    'files_modified': result.get('files_modified', [])
                })
        
        return dependency_results if dependency_results else None
    
    def _process_agent_response(
        self,
        task: Dict[str, Any],
        response_data: Dict[str, Any],
        start_time: datetime
    ) -> Dict[str, Any]:
        """
        Process agent response into standardized result format.
        
        Args:
            task: Original task definition
            response_data: Response data from API
            start_time: Task start time
            
        Returns:
            Processed result dictionary
        """
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        # Extract relevant information from response
        choices = response_data.get('choices', [])
        if choices:
            message = choices[0].get('message', {})
            content = message.get('content', '')
            tool_calls = message.get('tool_calls', [])
        else:
            content = ''
            tool_calls = []
        
        return {
            'task_id': task.get('id', task['agent_id']),
            'agent_id': task['agent_id'],
            'description': task['description'],
            'status': 'completed',
            'output': content,
            'tool_calls': tool_calls,
            'files_created': [],  # Would be extracted from tool calls
            'files_modified': [],  # Would be extracted from tool calls
            'tests_run': [],  # Would be extracted from tool calls
            'execution_time': execution_time,
            'started_at': start_time.isoformat(),
            'completed_at': end_time.isoformat()
        }
    
    def create_live_display(self) -> Live:
        """
        Create a live display for real-time progress and output tracking.
        
        Returns:
            Rich Live display object
        """
        # Create progress display
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console
        )
        
        # Create output table
        output_table = Table(show_header=True, header_style="bold blue")
        output_table.add_column("Agent", style="cyan", width=12)
        output_table.add_column("Status", style="green", width=12)
        output_table.add_column("Latest Output", style="white")
        
        # Create layout
        from rich.layout import Layout
        layout = Layout()
        layout.split_column(
            Layout(progress, name="progress", size=10),
            Layout(output_table, name="output")
        )
        
        return Live(layout, console=self.console, refresh_per_second=2)
    
    def _is_coding_task(self, task: Dict[str, Any]) -> bool:
        """
        Determine if a task requires the enhanced coding workflow.
        
        Args:
            task: Task definition
            
        Returns:
            True if task requires code generation with testing
        """
        task_type = task.get('type', '').lower()
        description = task.get('description', '').lower()
        
        # Check task type
        coding_types = ['code_generation', 'coding', 'implementation', 'development']
        if task_type in coding_types:
            return True
        
        # Check description for coding keywords
        coding_keywords = [
            'implement', 'create', 'build', 'develop', 'code', 'function',
            'class', 'module', 'api', 'algorithm', 'write code', 'generate'
        ]
        
        return any(keyword in description for keyword in coding_keywords)
    
    async def _execute_coding_task_with_workflow(
        self,
        task: Dict[str, Any],
        agent_id: str,
        project_context: Dict[str, Any],
        dependencies: Optional[List[Dict[str, Any]]],
        progress: Progress,
        agent_task: TaskID,
        start_time: datetime
    ) -> Dict[str, Any]:
        """
        Execute a coding task with the enhanced workflow including testing.
        
        Args:
            task: Task definition
            agent_id: Agent identifier
            project_context: Project context
            dependencies: Task dependencies
            progress: Progress tracker
            agent_task: Progress task ID
            start_time: Task start time
            
        Returns:
            Enhanced task result with testing metrics
        """
        try:
            # Update progress
            progress.update(agent_task, advance=10, description=f"Agent {agent_id}: Analyzing task...")
            self._emit_output(agent_id, "Analyzing coding task requirements...")
            
            # Prepare enhanced project context
            enhanced_context = await self._prepare_enhanced_context(task, project_context, dependencies)
            
            # Check for cancellation
            if self.execution_state == ExecutionState.CANCELLED:
                raise asyncio.CancelledError("Execution cancelled by user")
            
            # Execute code generation with testing workflow
            progress.update(agent_task, advance=10, description=f"Agent {agent_id}: Generating code...")
            self._emit_output(agent_id, "Starting code generation with comprehensive testing...")
            
            # Enable web search for research if specified in task
            enable_web_search = task.get('enable_web_search', True)
            
            code_result = await self.code_generator.generate_code_with_tests(
                task_description=task['description'],
                project_context=enhanced_context,
                agent_id=agent_id,
                enable_web_search=enable_web_search
            )
            
            progress.update(agent_task, advance=50)
            
            # Emit detailed progress updates
            if code_result.success:
                self._emit_output(agent_id, f"✅ Code generation successful after {code_result.iterations} iterations")
                self._emit_output(agent_id, f"📊 Test coverage: {code_result.coverage_percentage:.1f}%")
                self._emit_output(agent_id, f"📁 Files created: {len(code_result.files_created)}")
            else:
                self._emit_output(agent_id, f"❌ Code generation failed: {'; '.join(code_result.errors)}")
            
            # Create enhanced result
            result = self._create_enhanced_task_result(
                task, code_result, agent_id, start_time
            )
            
            progress.update(agent_task, advance=20, description=f"Agent {agent_id}: Completed")
            
            return result
            
        except asyncio.CancelledError:
            self._emit_output(agent_id, "Task cancelled during code generation")
            raise
        except Exception as e:
            self._emit_output(agent_id, f"Code generation workflow failed: {str(e)}")
            raise e
    
    async def _prepare_enhanced_context(
        self,
        task: Dict[str, Any],
        project_context: Dict[str, Any],
        dependencies: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Prepare enhanced context for code generation workflow.
        
        Args:
            task: Task definition
            project_context: Base project context
            dependencies: Task dependencies
            
        Returns:
            Enhanced context with additional metadata
        """
        enhanced_context = project_context.copy()
        
        # Add task-specific constraints
        enhanced_context['task_constraints'] = {
            'target_coverage': 80.0,
            'max_iterations': 3,
            'require_tests': True,
            'require_documentation': True,
            'style_guide': task.get('constraints', {}).get('style', 'PEP8')
        }
        
        # Add dependency information
        if dependencies:
            enhanced_context['dependencies'] = {
                'previous_results': dependencies,
                'available_functions': self._extract_available_functions(dependencies),
                'shared_context': self._extract_shared_context(dependencies)
            }
        
        # Add file constraints
        enhanced_context['file_constraints'] = {
            'files_to_create': task.get('files_to_create', []),
            'files_to_modify': task.get('files_to_modify', []),
            'output_directory': task.get('output_directory', '.')
        }
        
        return enhanced_context
    
    def _extract_available_functions(self, dependencies: List[Dict[str, Any]]) -> List[str]:
        """Extract available functions from dependency results."""
        functions = []
        
        for dep in dependencies:
            output = dep.get('output', '')
            # Simple regex to find function definitions
            import re
            func_matches = re.findall(r'def\s+(\w+)\s*\(', output)
            functions.extend(func_matches)
        
        return list(set(functions))  # Remove duplicates
    
    def _extract_shared_context(self, dependencies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract shared context from dependency results."""
        shared_context = {
            'imports': set(),
            'constants': {},
            'patterns': []
        }
        
        for dep in dependencies:
            output = dep.get('output', '')
            
            # Extract imports
            import re
            import_matches = re.findall(r'(?:from\s+\S+\s+)?import\s+([^\n]+)', output)
            for match in import_matches:
                shared_context['imports'].add(match.strip())
        
        # Convert set to list for JSON serialization
        shared_context['imports'] = list(shared_context['imports'])
        
        return shared_context
    
    def _create_enhanced_task_result(
        self,
        task: Dict[str, Any],
        code_result: Any,  # CodeGenerationResult
        agent_id: str,
        start_time: datetime
    ) -> Dict[str, Any]:
        """
        Create enhanced task result with testing metrics.
        
        Args:
            task: Original task definition
            code_result: Code generation result
            agent_id: Agent identifier
            start_time: Task start time
            
        Returns:
            Enhanced result dictionary
        """
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        # Base result structure
        result = {
            'task_id': task.get('id', agent_id),
            'agent_id': agent_id,
            'description': task['description'],
            'status': 'completed' if code_result.success else 'failed',
            'execution_time': execution_time,
            'started_at': start_time.isoformat(),
            'completed_at': end_time.isoformat()
        }
        
        # Add code generation specific metrics
        result['code_generation'] = {
            'success': code_result.success,
            'iterations': code_result.iterations,
            'coverage_percentage': code_result.coverage_percentage,
            'files_created': code_result.files_created,
            'errors': code_result.errors
        }
        
        # Add test results if available
        if code_result.test_results:
            result['testing'] = code_result.test_results
        
        # Add generated artifacts
        result['artifacts'] = {
            'code': code_result.code[:500] + "..." if len(code_result.code) > 500 else code_result.code,
            'tests': code_result.tests[:500] + "..." if len(code_result.tests) > 500 else code_result.tests,
            'documentation': code_result.documentation
        }
        
        # Legacy fields for compatibility
        result['output'] = f"Generated {len(code_result.files_created)} files with {code_result.coverage_percentage:.1f}% test coverage"
        result['tool_calls'] = []  # Would be populated with actual tool calls
        result['files_created'] = code_result.files_created
        result['files_modified'] = []  # Would be populated with modified files
        result['tests_run'] = []  # Would be populated with test names
        
        return result
    
    def update_live_display(self, live: Live):
        """
        Update the live display with current agent status and output.
        
        Args:
            live: Rich Live display object
        """
        # Update output table
        output_table = Table(show_header=True, header_style="bold blue")
        output_table.add_column("Agent", style="cyan", width=12)
        output_table.add_column("Status", style="green", width=12)
        output_table.add_column("Latest Output", style="white")
        
        for agent_id, agent_info in self.active_agents.items():
            status = agent_info.get('status', 'unknown')
            latest_output = ""
            
            if agent_id in self.agent_outputs and self.agent_outputs[agent_id]:
                latest_output = self.agent_outputs[agent_id][-1][:60] + "..."
            
            # Color code status
            status_style = "green"
            if status == AgentStatus.FAILED.value:
                status_style = "red"
            elif status == AgentStatus.CANCELLED.value:
                status_style = "yellow"
            elif status == AgentStatus.RUNNING.value:
                status_style = "blue"
            
            output_table.add_row(
                agent_id,
                f"[{status_style}]{status}[/{status_style}]",
                latest_output
            )
        
        # Update layout
        layout = live.renderable
        layout["output"].update(output_table)
    
    async def execute_with_live_display(
        self,
        tasks: List[Dict[str, Any]],
        execution_mode: str = "parallel"
    ) -> List[Dict[str, Any]]:
        """
        Execute tasks with live display showing real-time progress and output.
        
        Args:
            tasks: List of task definitions
            execution_mode: "parallel" or "sequential"
            
        Returns:
            List of agent execution results
        """
        # Create progress and live display
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console
        )
        
        main_task = progress.add_task(
            f"Executing {len(tasks)} tasks ({execution_mode})",
            total=len(tasks)
        )
        
        # Set up live display update callback
        def output_callback(agent_id: str, output: str):
            # This will be called for real-time output updates
            pass
        
        self.add_output_callback(output_callback)
        
        # Execute based on mode
        if execution_mode == "parallel":
            return await self.execute_parallel(tasks, progress, main_task)
        else:
            return await self.execute_sequential(tasks, progress, main_task)