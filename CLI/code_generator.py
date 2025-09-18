"""
Code Generator for Melanie CLI.

Handles code generation with comments and tests, iterative debugging,
test execution with pytest integration, and coverage enforcement.
"""

import asyncio
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
import re

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

try:
    from .api_client import APIClient, APIResponse
    from .theme import Colors
except ImportError:
    from api_client import APIClient, APIResponse
    from theme import Colors


class TestResult(Enum):
    """Test execution results."""
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class CodeGenerationResult:
    """Result of code generation process."""
    success: bool
    code: str
    tests: str
    documentation: str
    files_created: List[str]
    test_results: Optional[Dict[str, Any]] = None
    coverage_percentage: float = 0.0
    iterations: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


@dataclass
class TestExecutionResult:
    """Result of test execution."""
    success: bool
    passed: int
    failed: int
    total: int
    coverage: float
    output: str
    failed_tests: List[str]
    errors: List[str]


class CodeGenerator:
    """
    Handles code generation with comprehensive testing workflow.
    
    Generates code with comments and tests, executes iterative debugging
    with retry cycles, runs pytest with coverage enforcement, and integrates
    with web search/MCP for research capabilities.
    """
    
    def __init__(self, api_client: APIClient, console: Console):
        """
        Initialize code generator.
        
        Args:
            api_client: API client for communication with Melanie server
            console: Rich console for output
        """
        self.api_client = api_client
        self.console = console
        self.max_iterations = 3
        self.target_coverage = 80.0
        
    async def generate_code_with_tests(
        self,
        task_description: str,
        project_context: Dict[str, Any],
        agent_id: str = "code_agent",
        enable_web_search: bool = True
    ) -> CodeGenerationResult:
        """
        Generate code with comprehensive testing workflow.
        
        Args:
            task_description: Description of the coding task
            project_context: Project context and constraints
            agent_id: Identifier for the agent
            enable_web_search: Enable web search for research
            
        Returns:
            CodeGenerationResult with all artifacts and metrics
        """
        self.console.print(f"\n[bold {Colors.ACCENT}]🔧 Starting code generation workflow[/bold {Colors.ACCENT}]")
        
        result = CodeGenerationResult(
            success=False,
            code="",
            tests="",
            documentation="",
            files_created=[]
        )
        
        try:
            # Phase 1: Research and planning (if web search enabled)
            if enable_web_search:
                research_context = await self._conduct_research(task_description, project_context)
                project_context['research'] = research_context
            
            # Phase 2: Initial code generation
            self.console.print(f"[info]Generating initial code with tests...[/info]")
            initial_generation = await self._generate_initial_code(
                task_description, project_context, agent_id
            )
            
            if not initial_generation.success:
                result.errors.extend(initial_generation.errors)
                if not result.errors:
                    result.errors.append("Failed to generate initial code")
                return result
            
            result.code = initial_generation.code
            result.tests = initial_generation.tests
            result.documentation = initial_generation.documentation
            result.files_created = initial_generation.files_created
            
            # Phase 3: Iterative debugging and testing
            for iteration in range(1, self.max_iterations + 1):
                self.console.print(f"[info]Testing iteration {iteration}/{self.max_iterations}...[/info]")
                
                # Create temporary test environment
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    
                    # Write code and tests to temporary files
                    await self._write_code_files(temp_path, result)
                    
                    # Execute tests with coverage
                    test_result = await self._execute_tests_with_coverage(temp_path)
                    result.test_results = test_result.__dict__
                    result.coverage_percentage = test_result.coverage
                    result.iterations = iteration
                    
                    # Check if we meet success criteria
                    if test_result.success and test_result.coverage >= self.target_coverage:
                        result.success = True
                        self.console.print(f"[success]✅ Code generation successful! Coverage: {test_result.coverage:.1f}%[/success]")
                        break
                    
                    # If not successful and not last iteration, debug and improve
                    if iteration < self.max_iterations:
                        self.console.print(f"[warning]Tests failed or coverage insufficient ({test_result.coverage:.1f}%). Debugging...[/warning]")
                        
                        debug_result = await self._debug_and_improve(
                            task_description, project_context, result, test_result, agent_id
                        )
                        
                        if debug_result.success:
                            result.code = debug_result.code
                            result.tests = debug_result.tests
                            result.documentation = debug_result.documentation
                        else:
                            result.errors.append(f"Debug iteration {iteration} failed")
            
            # Final status
            if not result.success:
                if result.coverage_percentage < self.target_coverage:
                    result.errors.append(f"Coverage {result.coverage_percentage:.1f}% below target {self.target_coverage}%")
                if result.test_results and not result.test_results.get('success', False):
                    result.errors.append("Tests still failing after all iterations")
            
        except Exception as e:
            result.errors.append(f"Code generation workflow failed: {str(e)}")
            self.console.print(f"[error]Code generation error: {e}[/error]")
        
        return result
    
    async def _conduct_research(
        self,
        task_description: str,
        project_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Conduct research using web search and MCP integration."""
        
        self.console.print("[info]Conducting research for task context...[/info]")
        
        # Prepare research query
        research_query = self._prepare_research_query(task_description, project_context)
        
        # Use light search for quick research
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a research assistant helping with coding tasks. "
                    "Search for relevant documentation, best practices, and examples "
                    "that will help with the coding task. Focus on current practices "
                    "and reliable sources."
                )
            },
            {
                "role": "user",
                "content": f"Research query: {research_query}"
            }
        ]
        
        try:
            response = await self.api_client.chat_completion(
                model="Melanie-3-light",
                messages=messages,
                web_search=True,
                tools=[
                    {"type": "function", "function": {"name": "light-search"}},
                    {"type": "function", "function": {"name": "medium-search"}}
                ]
            )
            
            if response.success:
                research_content = response.data.get('choices', [{}])[0].get('message', {}).get('content', '')
                return {
                    'query': research_query,
                    'findings': research_content,
                    'timestamp': __import__('datetime').datetime.now().isoformat()
                }
        except Exception as e:
            self.console.print(f"[warning]Research failed: {e}[/warning]")
        
        return {'query': research_query, 'findings': '', 'timestamp': ''}
    
    def _prepare_research_query(self, task_description: str, project_context: Dict[str, Any]) -> str:
        """Prepare research query based on task and context."""
        
        languages = project_context.get('languages', [])
        frameworks = project_context.get('frameworks', [])
        
        query_parts = [task_description]
        
        if languages:
            query_parts.append(f"programming language: {', '.join(languages)}")
        
        if frameworks:
            query_parts.append(f"frameworks: {', '.join(frameworks)}")
        
        query_parts.extend([
            "best practices",
            "testing patterns",
            "code examples"
        ])
        
        return " ".join(query_parts)
    
    async def _generate_initial_code(
        self,
        task_description: str,
        project_context: Dict[str, Any],
        agent_id: str
    ) -> CodeGenerationResult:
        """Generate initial code with tests and documentation."""
        
        # Prepare comprehensive prompt for code generation
        system_prompt = """You are an expert software developer specializing in high-quality code generation with comprehensive testing.

Your task is to generate production-ready code that includes:
1. Well-structured, commented code following best practices
2. Comprehensive unit tests with 80%+ coverage
3. Clear documentation and docstrings
4. Error handling and edge case coverage
5. Type hints where applicable

Requirements:
- Generate complete, runnable code
- Include comprehensive test suite using pytest
- Add detailed comments explaining complex logic
- Follow language-specific style guides (PEP8 for Python, etc.)
- Include setup/teardown for tests if needed
- Handle edge cases and error conditions
- Provide clear documentation

Response format:
```python
# Main code implementation
[your code here]
```

```python
# Test file (test_*.py)
[your test code here]
```

```markdown
# Documentation
[documentation here]
```"""
        
        # Add project context to user message
        context_info = []
        if project_context.get('languages'):
            context_info.append(f"Languages: {', '.join(project_context['languages'])}")
        if project_context.get('frameworks'):
            context_info.append(f"Frameworks: {', '.join(project_context['frameworks'])}")
        if project_context.get('research'):
            context_info.append(f"Research findings: {project_context['research']['findings'][:500]}...")
        
        user_message = f"""Task: {task_description}

Project Context:
{chr(10).join(context_info)}

Generate high-quality code with comprehensive tests and documentation."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        try:
            response = await self.api_client.chat_completion(
                model="Melanie-3-code",
                messages=messages,
                temperature=0.3  # Lower temperature for more consistent code
            )
            
            if response.success:
                content = response.data.get('choices', [{}])[0].get('message', {}).get('content', '')
                if not content:
                    return CodeGenerationResult(
                        success=False,
                        code="",
                        tests="",
                        documentation="",
                        files_created=[],
                        errors=["Empty response content from API"]
                    )
                
                parsed_result = self._parse_code_response(content)
                if not parsed_result.success:
                    parsed_result.errors.append("Failed to parse AI response into code and tests")
                return parsed_result
            else:
                return CodeGenerationResult(
                    success=False,
                    code="",
                    tests="",
                    documentation="",
                    files_created=[],
                    errors=[f"API call failed: {response.error}"]
                )
        
        except Exception as e:
            return CodeGenerationResult(
                success=False,
                code="",
                tests="",
                documentation="",
                files_created=[],
                errors=[f"Code generation failed: {str(e)}"]
            )
    
    def _parse_code_response(self, content: str) -> CodeGenerationResult:
        """Parse the AI response to extract code, tests, and documentation."""
        
        result = CodeGenerationResult(
            success=False,
            code="",
            tests="",
            documentation="",
            files_created=[]
        )
        
        try:
            # Extract code blocks using regex - more flexible patterns
            python_blocks = re.findall(r'```(?:python|py)?\s*\n(.*?)\n```', content, re.DOTALL | re.IGNORECASE)
            markdown_blocks = re.findall(r'```markdown\s*\n(.*?)\n```', content, re.DOTALL | re.IGNORECASE)
            
            # If no python blocks found, try without language specifier
            if not python_blocks:
                python_blocks = re.findall(r'```\s*\n(.*?)\n```', content, re.DOTALL)
            
            # Identify which block is code vs tests
            code_block = None
            test_block = None
            
            for i, block in enumerate(python_blocks):
                block_content = block.strip()
                
                # Check if this looks like a test file
                if ('test_' in block_content.lower() or 
                    'import pytest' in block_content or 
                    'class Test' in block_content or
                    'def test_' in block_content):
                    test_block = block_content
                    result.files_created.append("test_main.py")
                else:
                    # Assume it's main code
                    code_block = block_content
                    result.files_created.append("main.py")
            
            # Assign the blocks
            if code_block:
                result.code = code_block
            if test_block:
                result.tests = test_block
            
            # If we only have one block and it contains both code and tests, try to split
            if len(python_blocks) == 1 and not (code_block and test_block):
                single_block = python_blocks[0].strip()
                
                # Try to split by common patterns
                if 'import pytest' in single_block or 'def test_' in single_block:
                    # This looks like it might contain both
                    lines = single_block.split('\n')
                    code_lines = []
                    test_lines = []
                    in_test_section = False
                    
                    for line in lines:
                        if ('import pytest' in line or 
                            line.strip().startswith('def test_') or
                            line.strip().startswith('class Test')):
                            in_test_section = True
                        
                        if in_test_section:
                            test_lines.append(line)
                        else:
                            code_lines.append(line)
                    
                    if code_lines and test_lines:
                        result.code = '\n'.join(code_lines).strip()
                        result.tests = '\n'.join(test_lines).strip()
                        result.files_created = ["main.py", "test_main.py"]
                    else:
                        # Treat as code only
                        result.code = single_block
                        result.files_created = ["main.py"]
                else:
                    # Treat as code only
                    result.code = single_block
                    result.files_created = ["main.py"]
            
            # Extract documentation
            if markdown_blocks:
                result.documentation = markdown_blocks[0].strip()
            
            # Check success criteria - we need at least code
            if result.code:
                result.success = True
                if not result.tests:
                    result.errors.append("Warning: No tests found in response")
            else:
                result.errors.append("No code found in response")
        
        except Exception as e:
            result.errors.append(f"Failed to parse code response: {str(e)}")
        
        return result
    
    async def _write_code_files(self, temp_path: Path, result: CodeGenerationResult):
        """Write code and test files to temporary directory."""
        
        # Write main code file
        if result.code:
            main_file = temp_path / "main.py"
            with open(main_file, 'w', encoding='utf-8') as f:
                f.write(result.code)
        
        # Write test file
        if result.tests:
            test_file = temp_path / "test_main.py"
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write(result.tests)
        
        # Write requirements.txt for pytest
        requirements_file = temp_path / "requirements.txt"
        with open(requirements_file, 'w', encoding='utf-8') as f:
            f.write("pytest>=7.0.0\npytest-cov>=4.0.0\n")
        
        # Write pytest configuration
        pytest_ini = temp_path / "pytest.ini"
        with open(pytest_ini, 'w', encoding='utf-8') as f:
            f.write("""[tool:pytest]
testpaths = .
python_files = test_*.py
python_functions = test_*
addopts = --cov=. --cov-report=term-missing --cov-report=json
""")
    
    async def _execute_tests_with_coverage(self, temp_path: Path) -> TestExecutionResult:
        """Execute tests with coverage measurement using pytest."""
        
        try:
            # Install requirements first
            install_result = await self._run_command(
                ["python", "-m", "pip", "install", "-r", "requirements.txt"],
                cwd=temp_path,
                timeout=60
            )
            
            if install_result.returncode != 0:
                return TestExecutionResult(
                    success=False,
                    passed=0,
                    failed=0,
                    total=0,
                    coverage=0.0,
                    output=install_result.stderr,
                    failed_tests=[],
                    errors=["Failed to install test dependencies"]
                )
            
            # Run pytest with coverage
            test_result = await self._run_command(
                ["python", "-m", "pytest", "--cov=.", "--cov-report=json", "--cov-report=term", "-v"],
                cwd=temp_path,
                timeout=120
            )
            
            # Parse test results
            output = test_result.stdout + test_result.stderr
            
            # Extract test counts from pytest output
            passed = len(re.findall(r'PASSED', output))
            failed = len(re.findall(r'FAILED', output))
            total = passed + failed
            
            # Extract coverage from coverage.json if available
            coverage = 0.0
            coverage_file = temp_path / "coverage.json"
            if coverage_file.exists():
                try:
                    with open(coverage_file, 'r') as f:
                        coverage_data = json.load(f)
                        coverage = coverage_data.get('totals', {}).get('percent_covered', 0.0)
                except Exception:
                    pass
            
            # Extract failed test names
            failed_tests = re.findall(r'FAILED (test_\w+)', output)
            
            return TestExecutionResult(
                success=(test_result.returncode == 0 and failed == 0),
                passed=passed,
                failed=failed,
                total=total,
                coverage=coverage,
                output=output,
                failed_tests=failed_tests,
                errors=[] if test_result.returncode == 0 else ["Test execution failed"]
            )
        
        except Exception as e:
            return TestExecutionResult(
                success=False,
                passed=0,
                failed=0,
                total=0,
                coverage=0.0,
                output="",
                failed_tests=[],
                errors=[f"Test execution error: {str(e)}"]
            )
    
    async def _run_command(
        self,
        command: List[str],
        cwd: Path,
        timeout: int = 60
    ) -> subprocess.CompletedProcess:
        """Run a command asynchronously with timeout."""
        
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            return subprocess.CompletedProcess(
                args=command,
                returncode=process.returncode,
                stdout=stdout.decode('utf-8', errors='ignore'),
                stderr=stderr.decode('utf-8', errors='ignore')
            )
        
        except asyncio.TimeoutError:
            if process:
                process.kill()
                await process.wait()
            
            return subprocess.CompletedProcess(
                args=command,
                returncode=-1,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds"
            )
    
    async def _debug_and_improve(
        self,
        task_description: str,
        project_context: Dict[str, Any],
        current_result: CodeGenerationResult,
        test_result: TestExecutionResult,
        agent_id: str
    ) -> CodeGenerationResult:
        """Debug and improve code based on test failures."""
        
        # Prepare debugging prompt
        debug_prompt = f"""You are debugging and improving code that has test failures or insufficient coverage.

Original task: {task_description}

Current code:
```python
{current_result.code}
```

Current tests:
```python
{current_result.tests}
```

Test execution results:
- Passed: {test_result.passed}
- Failed: {test_result.failed}
- Coverage: {test_result.coverage:.1f}%
- Target coverage: {self.target_coverage}%

Failed tests: {', '.join(test_result.failed_tests)}

Test output:
{test_result.output[-1000:]}  # Last 1000 chars

Please fix the issues and improve the code to:
1. Make all tests pass
2. Achieve at least {self.target_coverage}% test coverage
3. Add more comprehensive tests if needed
4. Fix any bugs or edge cases

Provide the improved code and tests in the same format as before."""
        
        messages = [
            {
                "role": "system",
                "content": "You are an expert debugger and code improver. Fix issues and enhance test coverage."
            },
            {
                "role": "user",
                "content": debug_prompt
            }
        ]
        
        try:
            response = await self.api_client.chat_completion(
                model="Melanie-3-code",
                messages=messages,
                temperature=0.2  # Even lower temperature for debugging
            )
            
            if response.success:
                content = response.data.get('choices', [{}])[0].get('message', {}).get('content', '')
                return self._parse_code_response(content)
            else:
                return CodeGenerationResult(
                    success=False,
                    code=current_result.code,
                    tests=current_result.tests,
                    documentation=current_result.documentation,
                    files_created=current_result.files_created,
                    errors=[f"Debug API call failed: {response.error}"]
                )
        
        except Exception as e:
            return CodeGenerationResult(
                success=False,
                code=current_result.code,
                tests=current_result.tests,
                documentation=current_result.documentation,
                files_created=current_result.files_created,
                errors=[f"Debug process failed: {str(e)}"]
            )
    
    def display_generation_results(self, result: CodeGenerationResult):
        """Display code generation results in a formatted way."""
        
        # Results summary
        status_color = Colors.SUCCESS if result.success else Colors.ERROR
        status_text = "✅ SUCCESS" if result.success else "❌ FAILED"
        
        summary_text = Text()
        summary_text.append(f"{status_text}\n\n", style=f"bold {status_color}")
        summary_text.append(f"Iterations: {result.iterations}\n", style=Colors.TEXT)
        summary_text.append(f"Coverage: {result.coverage_percentage:.1f}%\n", style=Colors.ACCENT)
        summary_text.append(f"Files created: {len(result.files_created)}\n", style=Colors.TEXT)
        
        if result.test_results:
            test_info = result.test_results
            summary_text.append(f"Tests: {test_info.get('passed', 0)} passed, {test_info.get('failed', 0)} failed", style=Colors.MUTED)
        
        summary_panel = Panel(
            summary_text,
            title="[bold]Code Generation Results[/bold]",
            border_style=status_color
        )
        self.console.print(summary_panel)
        
        # Show errors if any
        if result.errors:
            self.console.print(f"\n[bold {Colors.ERROR}]Errors:[/bold {Colors.ERROR}]")
            for error in result.errors:
                self.console.print(f"  • {error}", style=Colors.ERROR)
        
        # Show files created
        if result.files_created:
            file_table = Table(title="Generated Files", border_style=Colors.ACCENT)
            file_table.add_column("File", style=Colors.TEXT)
            file_table.add_column("Type", style=Colors.ACCENT)
            
            for file_name in result.files_created:
                file_type = "Test" if file_name.startswith("test_") else "Code"
                file_table.add_row(file_name, file_type)
            
            self.console.print(file_table)