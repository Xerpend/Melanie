"""
Plan Generator for Melanie CLI.

Generates execution plans for coding requests using AI analysis
to determine optimal task breakdown and agent coordination.
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.text import Text
from rich.columns import Columns
from rich.align import Align

try:
    from .api_client import APIClient
    from .theme import DarkBlueTheme, Colors
except ImportError:
    from api_client import APIClient
    from theme import DarkBlueTheme, Colors


class ExecutionStrategy(Enum):
    """Execution strategy for agents."""
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    MIXED = "mixed"


@dataclass
class TaskDependency:
    """Represents a dependency between tasks."""
    task_id: str
    depends_on: List[str]
    dependency_type: str = "completion"  # completion, data, resource


@dataclass
class AgentAssignment:
    """Represents an agent assignment."""
    agent_id: str
    tasks: List[str]
    estimated_duration: int
    capabilities: List[str]


@dataclass
class ExecutionPlan:
    """Complete execution plan with all details."""
    summary: str
    tasks: List[Dict[str, Any]]
    agent_count: int
    execution_strategy: ExecutionStrategy
    estimated_duration: int
    dependencies: List[TaskDependency]
    agent_assignments: List[AgentAssignment]
    reasoning: str
    request: str
    project_dir: str
    generated_at: str
    
    def get_parallel_phases(self) -> List[List[str]]:
        """Get tasks grouped by parallel execution phases."""
        if self.execution_strategy == ExecutionStrategy.SEQUENTIAL:
            return [[task["id"]] for task in self.tasks]
        
        # Build dependency graph
        task_deps = {dep.task_id: dep.depends_on for dep in self.dependencies}
        
        # Group tasks into phases
        phases = []
        remaining_tasks = set(task["id"] for task in self.tasks)
        
        while remaining_tasks:
            # Find tasks with no remaining dependencies
            ready_tasks = []
            for task_id in remaining_tasks:
                deps = task_deps.get(task_id, [])
                if not any(dep in remaining_tasks for dep in deps):
                    ready_tasks.append(task_id)
            
            if not ready_tasks:
                # Circular dependency or error - add remaining tasks
                ready_tasks = list(remaining_tasks)
            
            phases.append(ready_tasks)
            remaining_tasks -= set(ready_tasks)
        
        return phases


class PlanGenerator:
    """
    Generates execution plans for coding requests.
    
    Uses Melanie-3-light to analyze coding requests and generate
    detailed execution plans with task breakdown, dependencies,
    and agent assignments.
    """
    
    def __init__(self, api_client: APIClient, console: Optional[Console] = None):
        """
        Initialize plan generator.
        
        Args:
            api_client: API client for communication with Melanie server
            console: Rich console for output (creates new if None)
        """
        self.api_client = api_client
        self.console = console or Console(theme=DarkBlueTheme())
        self.theme = DarkBlueTheme()
    
    async def generate_plan(
        self,
        request: str,
        project_dir: Path,
        suggested_agents: Optional[int] = None,
        force_parallel: Optional[bool] = None,
        interactive: bool = True
    ) -> ExecutionPlan:
        """
        Generate an execution plan for a coding request.
        
        Args:
            request: Coding task description
            project_dir: Project directory path
            suggested_agents: Suggested number of agents (1-3)
            force_parallel: Force parallel execution
            interactive: Enable interactive plan review and modification
            
        Returns:
            ExecutionPlan object
        """
        self.console.print(f"\n[bold {Colors.ACCENT}]🤖 Analyzing coding request...[/bold {Colors.ACCENT}]")
        
        # Analyze project structure
        project_context = await self._analyze_project_structure(project_dir)
        
        # Generate plan using AI
        plan_response = await self._generate_ai_plan(
            request, project_context, suggested_agents, force_parallel
        )
        
        if not plan_response.success:
            raise Exception(f"Failed to generate plan: {plan_response.error}")
        
        # Parse and validate plan
        raw_plan = self._extract_plan_from_response(plan_response.data)
        execution_plan = self._create_execution_plan(raw_plan, request, project_dir)
        
        # Display plan and get user confirmation
        if interactive:
            execution_plan = await self._interactive_plan_review(execution_plan)
        else:
            self._display_plan_summary(execution_plan)
        
        return execution_plan
    
    async def _analyze_project_structure(self, project_dir: Path) -> Dict[str, Any]:
        """
        Analyze project structure to understand context.
        
        Args:
            project_dir: Project directory path
            
        Returns:
            Project context dictionary
        """
        context = {
            'directory': str(project_dir),
            'files': [],
            'languages': set(),
            'frameworks': set(),
            'has_tests': False,
            'has_docs': False,
            'build_files': []
        }
        
        if not project_dir.exists():
            return context
        
        # Scan directory structure
        for file_path in project_dir.rglob('*'):
            if file_path.is_file() and not self._should_ignore_file(file_path):
                relative_path = file_path.relative_to(project_dir)
                context['files'].append(str(relative_path))
                
                # Detect language and framework
                self._detect_language_and_framework(file_path, context)
                
                # Check for special files
                if 'test' in file_path.name.lower():
                    context['has_tests'] = True
                if file_path.name.lower() in ['readme.md', 'readme.txt', 'docs']:
                    context['has_docs'] = True
                if file_path.name in ['package.json', 'requirements.txt', 'Cargo.toml', 'pom.xml']:
                    context['build_files'].append(str(relative_path))
        
        # Convert sets to lists for JSON serialization
        context['languages'] = list(context['languages'])
        context['frameworks'] = list(context['frameworks'])
        
        return context
    
    def _should_ignore_file(self, file_path: Path) -> bool:
        """Check if file should be ignored in analysis."""
        ignore_patterns = [
            '.git', '__pycache__', 'node_modules', '.venv', 'venv',
            '.DS_Store', '.pyc', '.log', 'target', 'build', 'dist'
        ]
        
        path_str = str(file_path)
        return any(pattern in path_str for pattern in ignore_patterns)
    
    def _detect_language_and_framework(self, file_path: Path, context: Dict[str, Any]):
        """Detect programming language and framework from file."""
        suffix = file_path.suffix.lower()
        name = file_path.name.lower()
        
        # Language detection
        language_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.java': 'Java',
            '.rs': 'Rust',
            '.go': 'Go',
            '.cpp': 'C++',
            '.c': 'C',
            '.cs': 'C#',
            '.php': 'PHP',
            '.rb': 'Ruby'
        }
        
        if suffix in language_map:
            context['languages'].add(language_map[suffix])
        
        # Framework detection
        if name == 'package.json':
            context['frameworks'].add('Node.js')
        elif name == 'requirements.txt' or name == 'pyproject.toml':
            context['frameworks'].add('Python')
        elif name == 'cargo.toml':
            context['frameworks'].add('Rust')
        elif name == 'pom.xml':
            context['frameworks'].add('Maven')
        elif name == 'build.gradle':
            context['frameworks'].add('Gradle')
    
    async def _generate_ai_plan(
        self,
        request: str,
        project_context: Dict[str, Any],
        suggested_agents: Optional[int],
        force_parallel: Optional[bool]
    ) -> Any:
        """Generate execution plan using AI."""
        
        system_prompt = """You are an expert coding task planner for the Melanie CLI system. Analyze the user's request and project context to generate a detailed execution plan.

Your response must be a JSON object with this exact structure:
{
  "summary": "Brief description of what will be accomplished",
  "tasks": [
    {
      "id": "task_1",
      "description": "Detailed task description focusing on specific coding actions",
      "agent_id": "agent_1",
      "type": "code_generation|testing|documentation|refactoring|debugging",
      "estimated_minutes": 15,
      "dependencies": ["task_id_that_must_complete_first"],
      "files_to_create": ["path/to/new_file.py"],
      "files_to_modify": ["path/to/existing_file.py"],
      "constraints": {"test_coverage": 80, "style": "PEP8", "documentation": true}
    }
  ],
  "agent_count": 2,
  "parallel": true,
  "estimated_duration": 45,
  "reasoning": "Detailed explanation of task breakdown, dependency analysis, and execution strategy decisions"
}

Planning Guidelines:
- Break complex requests into 3-8 manageable, specific tasks
- Each task should be completable in 10-30 minutes by a single agent
- Assign tasks to agents (agent_1, agent_2, agent_3) based on capabilities
- Use parallel execution when tasks are truly independent
- Create dependencies only when one task's output is required by another
- Focus on iterative development: code → test → debug → document
- Consider the existing project structure and programming languages
- Prioritize code quality, comprehensive testing (80% coverage), and documentation
- Include specific file paths for creation and modification
- Ensure each task has a clear, measurable outcome

Dependency Analysis:
- Only create dependencies when absolutely necessary
- Prefer parallel execution for independent tasks
- Consider resource dependencies (same files) vs logical dependencies (data flow)
- Keep dependency chains short (max 3 levels deep)

Agent Assignment Strategy:
- agent_1: Complex logic, architecture, and integration tasks
- agent_2: Testing, validation, and quality assurance tasks  
- agent_3: Documentation, refactoring, and optimization tasks
- Balance workload across agents for parallel efficiency"""
        
        # Add constraints based on parameters
        if suggested_agents:
            system_prompt += f"\n- Use exactly {suggested_agents} agents"
        if force_parallel is not None:
            execution_type = "parallel" if force_parallel else "sequential"
            system_prompt += f"\n- Use {execution_type} execution strategy"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""Request: {request}

Project Context:
{json.dumps(project_context, indent=2)}

Generate a detailed execution plan for this coding request."""
            }
        ]
        
        return await self.api_client.chat_completion(
            model="Melanie-3-light",
            messages=messages,
            temperature=0.3  # Lower temperature for more consistent planning
        )
    
    def _extract_plan_from_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract plan JSON from AI response."""
        choices = response_data.get('choices', [])
        if not choices:
            raise Exception("No response choices found")
        
        content = choices[0].get('message', {}).get('content', '')
        
        # Try to extract JSON from the response
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if not json_match:
            raise Exception("No JSON plan found in response")
        
        try:
            plan = json.loads(json_match.group())
            return plan
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON in plan: {e}")
    
    def _create_execution_plan(
        self,
        plan: Dict[str, Any],
        request: str,
        project_dir: Path
    ) -> ExecutionPlan:
        """Create ExecutionPlan object from raw plan data."""
        
        # Ensure required fields exist
        required_fields = ['summary', 'tasks', 'agent_count', 'parallel', 'estimated_duration']
        for field in required_fields:
            if field not in plan:
                raise Exception(f"Missing required field in plan: {field}")
        
        # Validate tasks
        if not plan['tasks']:
            raise Exception("Plan must contain at least one task")
        
        # Ensure agent count is reasonable
        agent_count = min(max(plan.get('agent_count', 2), 1), 3)
        
        # Validate and enhance task structure
        for i, task in enumerate(plan['tasks']):
            required_task_fields = ['id', 'description', 'agent_id', 'type']
            for field in required_task_fields:
                if field not in task:
                    task[field] = self._generate_default_task_field(field, i)
            
            # Ensure dependencies are valid
            if 'dependencies' not in task:
                task['dependencies'] = []
            
            # Add default estimates
            if 'estimated_minutes' not in task:
                task['estimated_minutes'] = 20
        
        # Analyze dependencies and execution strategy
        dependencies = self._analyze_dependencies(plan['tasks'])
        execution_strategy = self._determine_execution_strategy(
            plan['tasks'], dependencies, plan.get('parallel', True)
        )
        agent_assignments = self._create_agent_assignments(plan['tasks'], agent_count)
        
        return ExecutionPlan(
            summary=plan['summary'],
            tasks=plan['tasks'],
            agent_count=agent_count,
            execution_strategy=execution_strategy,
            estimated_duration=plan.get('estimated_duration', 60),
            dependencies=dependencies,
            agent_assignments=agent_assignments,
            reasoning=plan.get('reasoning', 'No reasoning provided'),
            request=request,
            project_dir=str(project_dir),
            generated_at=__import__('datetime').datetime.now().isoformat()
        )
    
    def _generate_default_task_field(self, field: str, task_index: int) -> str:
        """Generate default value for missing task field."""
        defaults = {
            'id': f'task_{task_index + 1}',
            'description': f'Task {task_index + 1}',
            'agent_id': f'agent_{(task_index % 3) + 1}',
            'type': 'code_generation'
        }
        return defaults.get(field, '')
    
    def _analyze_dependencies(self, tasks: List[Dict[str, Any]]) -> List[TaskDependency]:
        """Analyze task dependencies to determine execution order."""
        dependencies = []
        
        for task in tasks:
            task_id = task['id']
            deps = task.get('dependencies', [])
            
            if deps:
                dependencies.append(TaskDependency(
                    task_id=task_id,
                    depends_on=deps,
                    dependency_type="completion"
                ))
        
        return dependencies
    
    def _determine_execution_strategy(
        self,
        tasks: List[Dict[str, Any]],
        dependencies: List[TaskDependency],
        prefer_parallel: bool = True
    ) -> ExecutionStrategy:
        """Determine optimal execution strategy based on dependencies."""
        
        # If no dependencies, can run in parallel
        if not dependencies:
            return ExecutionStrategy.PARALLEL if prefer_parallel else ExecutionStrategy.SEQUENTIAL
        
        # Check for complex dependency chains
        task_deps = {dep.task_id: dep.depends_on for dep in dependencies}
        max_chain_length = 0
        
        for task_id in task_deps:
            chain_length = self._calculate_dependency_chain_length(task_id, task_deps)
            max_chain_length = max(max_chain_length, chain_length)
        
        # If most tasks are independent, use mixed strategy
        independent_tasks = len(tasks) - len(dependencies)
        if independent_tasks > len(dependencies):
            return ExecutionStrategy.MIXED if prefer_parallel else ExecutionStrategy.SEQUENTIAL
        
        # If long dependency chains, use sequential
        if max_chain_length > 2:
            return ExecutionStrategy.SEQUENTIAL
        
        return ExecutionStrategy.PARALLEL if prefer_parallel else ExecutionStrategy.SEQUENTIAL
    
    def _calculate_dependency_chain_length(
        self,
        task_id: str,
        task_deps: Dict[str, List[str]],
        visited: Optional[set] = None
    ) -> int:
        """Calculate the length of the longest dependency chain for a task."""
        if visited is None:
            visited = set()
        
        if task_id in visited:
            return 0  # Circular dependency
        
        visited.add(task_id)
        deps = task_deps.get(task_id, [])
        
        if not deps:
            return 1
        
        max_depth = 0
        for dep in deps:
            depth = self._calculate_dependency_chain_length(dep, task_deps, visited.copy())
            max_depth = max(max_depth, depth)
        
        return max_depth + 1
    
    def _create_agent_assignments(
        self,
        tasks: List[Dict[str, Any]],
        agent_count: int
    ) -> List[AgentAssignment]:
        """Create agent assignments based on tasks and capabilities."""
        assignments = []
        
        # Group tasks by agent_id
        agent_tasks = {}
        for task in tasks:
            agent_id = task.get('agent_id', 'agent_1')
            if agent_id not in agent_tasks:
                agent_tasks[agent_id] = []
            agent_tasks[agent_id].append(task['id'])
        
        # Create assignments
        for i in range(1, agent_count + 1):
            agent_id = f'agent_{i}'
            task_ids = agent_tasks.get(agent_id, [])
            
            # Calculate estimated duration
            duration = sum(
                task.get('estimated_minutes', 20)
                for task in tasks
                if task['id'] in task_ids
            )
            
            # Determine capabilities based on task types
            task_types = set(
                task.get('type', 'code_generation')
                for task in tasks
                if task['id'] in task_ids
            )
            
            capabilities = list(task_types) if task_types else ['code_generation']
            
            assignments.append(AgentAssignment(
                agent_id=agent_id,
                tasks=task_ids,
                estimated_duration=duration,
                capabilities=capabilities
            ))
        
        return assignments
    
    def _display_plan_summary(self, plan: ExecutionPlan):
        """Display a summary of the execution plan."""
        
        # Main plan panel
        plan_content = Text()
        plan_content.append(f"📋 {plan.summary}\n\n", style=f"bold {Colors.TEXT}")
        plan_content.append(f"🎯 Strategy: {plan.execution_strategy.value.title()}\n", style=Colors.ACCENT)
        plan_content.append(f"👥 Agents: {plan.agent_count}\n", style=Colors.ACCENT)
        plan_content.append(f"⏱️  Duration: ~{plan.estimated_duration} minutes\n", style=Colors.ACCENT)
        plan_content.append(f"📝 Tasks: {len(plan.tasks)}", style=Colors.ACCENT)
        
        self.console.print(Panel(
            plan_content,
            title="[bold]Execution Plan[/bold]",
            border_style=Colors.ACCENT,
            padding=(1, 2)
        ))
    
    async def _interactive_plan_review(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Interactive plan review and modification."""
        
        while True:
            # Display detailed plan
            self._display_detailed_plan(plan)
            
            # Show options
            self.console.print(f"\n[bold {Colors.ACCENT}]Plan Review Options:[/bold {Colors.ACCENT}]")
            options = [
                "1. Accept plan and proceed",
                "2. Modify agent count",
                "3. Change execution strategy", 
                "4. View task details",
                "5. View dependencies",
                "6. Regenerate plan"
            ]
            
            for option in options:
                self.console.print(f"  {option}", style=Colors.TEXT)
            
            choice = Prompt.ask(
                f"\n[bold {Colors.ACCENT}]Choose an option[/bold {Colors.ACCENT}]",
                choices=["1", "2", "3", "4", "5", "6"],
                default="1"
            )
            
            if choice == "1":
                self.console.print(f"\n[bold {Colors.SUCCESS}]✅ Plan accepted![/bold {Colors.SUCCESS}]")
                break
            elif choice == "2":
                plan = self._modify_agent_count(plan)
            elif choice == "3":
                plan = self._modify_execution_strategy(plan)
            elif choice == "4":
                self._display_task_details(plan)
            elif choice == "5":
                self._display_dependencies(plan)
            elif choice == "6":
                self.console.print(f"[bold {Colors.WARNING}]🔄 Regenerating plan...[/bold {Colors.WARNING}]")
                # Would regenerate plan - for now just continue
                continue
        
        return plan
    
    def _display_detailed_plan(self, plan: ExecutionPlan):
        """Display detailed plan with Rich formatting."""
        
        # Header
        self.console.print(f"\n[bold {Colors.PRIMARY}]{'='*60}[/bold {Colors.PRIMARY}]")
        self.console.print(f"[bold {Colors.ACCENT}]📋 EXECUTION PLAN[/bold {Colors.ACCENT}]", justify="center")
        self.console.print(f"[bold {Colors.PRIMARY}]{'='*60}[/bold {Colors.PRIMARY}]")
        
        # Summary panel
        summary_text = Text()
        summary_text.append(f"🎯 {plan.summary}\n\n", style=f"bold {Colors.TEXT}")
        summary_text.append(f"Strategy: {plan.execution_strategy.value.title()}\n", style=Colors.ACCENT)
        summary_text.append(f"Agents: {plan.agent_count} | Tasks: {len(plan.tasks)} | Duration: ~{plan.estimated_duration}min", style=Colors.MUTED)
        
        self.console.print(Panel(
            summary_text,
            title="[bold]Overview[/bold]",
            border_style=Colors.ACCENT
        ))
        
        # Tasks table
        self._display_tasks_table(plan)
        
        # Agent assignments
        self._display_agent_assignments(plan)
        
        # Execution phases
        if plan.execution_strategy != ExecutionStrategy.SEQUENTIAL:
            self._display_execution_phases(plan)
    
    def _display_tasks_table(self, plan: ExecutionPlan):
        """Display tasks in a formatted table."""
        
        table = Table(title="Tasks Breakdown", border_style=Colors.ACCENT)
        table.add_column("ID", style=Colors.ACCENT, width=8)
        table.add_column("Description", style=Colors.TEXT, width=40)
        table.add_column("Agent", style=Colors.SUCCESS, width=8)
        table.add_column("Type", style=Colors.WARNING, width=12)
        table.add_column("Duration", style=Colors.MUTED, width=8)
        
        for task in plan.tasks:
            table.add_row(
                task['id'],
                task['description'][:37] + "..." if len(task['description']) > 40 else task['description'],
                task.get('agent_id', 'N/A'),
                task.get('type', 'N/A'),
                f"{task.get('estimated_minutes', 20)}min"
            )
        
        self.console.print(table)
    
    def _display_agent_assignments(self, plan: ExecutionPlan):
        """Display agent assignments."""
        
        columns = []
        for assignment in plan.agent_assignments:
            if assignment.tasks:  # Only show agents with tasks
                agent_text = Text()
                agent_text.append(f"👤 {assignment.agent_id.upper()}\n", style=f"bold {Colors.ACCENT}")
                agent_text.append(f"⏱️  {assignment.estimated_duration}min\n", style=Colors.MUTED)
                agent_text.append(f"🛠️  {', '.join(assignment.capabilities)}\n\n", style=Colors.WARNING)
                
                for task_id in assignment.tasks:
                    agent_text.append(f"• {task_id}\n", style=Colors.TEXT)
                
                panel = Panel(
                    agent_text,
                    title=f"[bold]{assignment.agent_id}[/bold]",
                    border_style=Colors.SUCCESS,
                    width=25
                )
                columns.append(panel)
        
        if columns:
            self.console.print(Columns(columns, equal=True, expand=True))
    
    def _display_execution_phases(self, plan: ExecutionPlan):
        """Display execution phases for parallel/mixed strategies."""
        
        phases = plan.get_parallel_phases()
        if len(phases) <= 1:
            return
        
        tree = Tree(f"[bold {Colors.ACCENT}]Execution Phases[/bold {Colors.ACCENT}]")
        
        for i, phase in enumerate(phases):
            phase_node = tree.add(f"[bold {Colors.SUCCESS}]Phase {i+1}[/bold {Colors.SUCCESS}]")
            for task_id in phase:
                task = next((t for t in plan.tasks if t['id'] == task_id), None)
                if task:
                    phase_node.add(f"[{Colors.TEXT}]{task_id}: {task['description'][:30]}...[/{Colors.TEXT}]")
        
        self.console.print(tree)
    
    def _display_task_details(self, plan: ExecutionPlan):
        """Display detailed task information."""
        
        self.console.print(f"\n[bold {Colors.ACCENT}]📝 Task Details[/bold {Colors.ACCENT}]")
        
        for task in plan.tasks:
            task_panel = Text()
            task_panel.append(f"ID: {task['id']}\n", style=f"bold {Colors.ACCENT}")
            task_panel.append(f"Description: {task['description']}\n", style=Colors.TEXT)
            task_panel.append(f"Type: {task.get('type', 'N/A')}\n", style=Colors.WARNING)
            task_panel.append(f"Agent: {task.get('agent_id', 'N/A')}\n", style=Colors.SUCCESS)
            task_panel.append(f"Duration: {task.get('estimated_minutes', 20)} minutes\n", style=Colors.MUTED)
            
            if task.get('dependencies'):
                task_panel.append(f"Dependencies: {', '.join(task['dependencies'])}\n", style=Colors.ERROR)
            
            if task.get('files_to_create'):
                task_panel.append(f"Files to create: {', '.join(task['files_to_create'])}\n", style=Colors.SUCCESS)
            
            if task.get('files_to_modify'):
                task_panel.append(f"Files to modify: {', '.join(task['files_to_modify'])}\n", style=Colors.WARNING)
            
            self.console.print(Panel(
                task_panel,
                title=f"[bold]{task['id']}[/bold]",
                border_style=Colors.ACCENT,
                padding=(0, 1)
            ))
    
    def _display_dependencies(self, plan: ExecutionPlan):
        """Display task dependencies."""
        
        if not plan.dependencies:
            self.console.print(f"\n[bold {Colors.SUCCESS}]✅ No dependencies - all tasks can run independently[/bold {Colors.SUCCESS}]")
            return
        
        self.console.print(f"\n[bold {Colors.ACCENT}]🔗 Task Dependencies[/bold {Colors.ACCENT}]")
        
        tree = Tree(f"[bold {Colors.WARNING}]Dependency Graph[/bold {Colors.WARNING}]")
        
        for dep in plan.dependencies:
            dep_node = tree.add(f"[bold {Colors.ACCENT}]{dep.task_id}[/bold {Colors.ACCENT}]")
            for dependency in dep.depends_on:
                dep_node.add(f"[{Colors.TEXT}]depends on: {dependency}[/{Colors.TEXT}]")
        
        self.console.print(tree)
    
    def _modify_agent_count(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Modify the number of agents in the plan."""
        
        current_count = plan.agent_count
        new_count = IntPrompt.ask(
            f"[bold {Colors.ACCENT}]Current agent count: {current_count}. Enter new count[/bold {Colors.ACCENT}]",
            default=current_count,
            show_default=True
        )
        
        if new_count != current_count and 1 <= new_count <= 3:
            plan.agent_count = new_count
            plan.agent_assignments = self._create_agent_assignments(plan.tasks, new_count)
            self.console.print(f"[bold {Colors.SUCCESS}]✅ Agent count updated to {new_count}[/bold {Colors.SUCCESS}]")
        
        return plan
    
    def _modify_execution_strategy(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Modify the execution strategy."""
        
        strategies = {
            "1": ExecutionStrategy.PARALLEL,
            "2": ExecutionStrategy.SEQUENTIAL, 
            "3": ExecutionStrategy.MIXED
        }
        
        self.console.print(f"\n[bold {Colors.ACCENT}]Execution Strategies:[/bold {Colors.ACCENT}]")
        self.console.print("1. Parallel - Run independent tasks simultaneously")
        self.console.print("2. Sequential - Run all tasks one after another")
        self.console.print("3. Mixed - Parallel where possible, sequential where needed")
        
        choice = Prompt.ask(
            f"[bold {Colors.ACCENT}]Choose strategy[/bold {Colors.ACCENT}]",
            choices=["1", "2", "3"],
            default="1"
        )
        
        new_strategy = strategies[choice]
        if new_strategy != plan.execution_strategy:
            plan.execution_strategy = new_strategy
            self.console.print(f"[bold {Colors.SUCCESS}]✅ Execution strategy updated to {new_strategy.value}[/bold {Colors.SUCCESS}]")
        
        return plan