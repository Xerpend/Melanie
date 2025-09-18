"""
Result Compiler for Melanie CLI.

Compiles and processes results from multiple agents into
a comprehensive summary with file changes and statistics.
"""

import json
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime

from rich.console import Console


class ResultCompiler:
    """
    Compiles results from multiple agent executions.
    
    Processes agent outputs, file changes, test results,
    and other execution artifacts into a comprehensive
    summary for user review.
    """
    
    def __init__(self, console: Console):
        """
        Initialize result compiler.
        
        Args:
            console: Rich console for output
        """
        self.console = console
    
    async def compile_results(self, agent_results: List[Dict[str, Any]], project_dir: Path = None) -> Dict[str, Any]:
        """
        Compile results from multiple agent executions.
        
        Args:
            agent_results: List of agent execution results
            project_dir: Project directory for file analysis
            
        Returns:
            Compiled results dictionary
        """
        compiled = {
            'summary': {},
            'tasks': [],
            'files': {
                'created': [],
                'modified': [],
                'deleted': []
            },
            'tests': {
                'passed': 0,
                'failed': 0,
                'total': 0,
                'coverage': 0.0,
                'results': []
            },
            'code_quality': {
                'lines_added': 0,
                'lines_removed': 0,
                'functions_created': 0,
                'classes_created': 0,
                'issues': []
            },
            'execution': {
                'total_time': 0.0,
                'agents_used': set(),
                'tasks_completed': 0,
                'tasks_failed': 0
            },
            'artifacts': [],
            'errors': [],
            'warnings': [],
            'project_structure': {},
            'recommendations': []
        }
        
        # Process each agent result
        for result in agent_results:
            await self._process_agent_result(result, compiled)
        
        # Analyze project structure if directory provided
        if project_dir:
            compiled['project_structure'] = await self._analyze_project_structure(project_dir)
        
        # Generate summary statistics and recommendations
        self._generate_summary(compiled)
        self._generate_recommendations(compiled)
        
        # Convert sets to lists for JSON serialization
        compiled['execution']['agents_used'] = list(compiled['execution']['agents_used'])
        
        return compiled
    
    async def _process_agent_result(self, result: Dict[str, Any], compiled: Dict[str, Any]):
        """Process a single agent result."""
        
        # Track execution info
        compiled['execution']['agents_used'].add(result.get('agent_id', 'unknown'))
        compiled['execution']['total_time'] += result.get('execution_time', 0.0)
        
        if result.get('status') == 'completed':
            compiled['execution']['tasks_completed'] += 1
        else:
            compiled['execution']['tasks_failed'] += 1
            if 'error' in result:
                compiled['errors'].append({
                    'agent_id': result.get('agent_id'),
                    'task': result.get('description', 'Unknown task'),
                    'error': result['error']
                })
        
        # Process task info
        compiled['tasks'].append({
            'id': result.get('task_id'),
            'agent_id': result.get('agent_id'),
            'description': result.get('description'),
            'status': result.get('status'),
            'execution_time': result.get('execution_time', 0.0),
            'output_summary': self._summarize_output(result.get('output', ''))
        })
        
        # Process file changes
        await self._process_file_changes(result, compiled)
        
        # Process tool calls for additional insights
        await self._process_tool_calls(result.get('tool_calls', []), compiled)
        
        # Extract code quality metrics
        self._extract_code_metrics(result, compiled)
    
    def _summarize_output(self, output: str) -> str:
        """Create a brief summary of agent output."""
        if not output:
            return "No output"
        
        # Take first few lines or first paragraph
        lines = output.split('\n')
        summary_lines = []
        
        for line in lines[:5]:  # First 5 lines
            line = line.strip()
            if line and not line.startswith('#'):  # Skip empty lines and headers
                summary_lines.append(line)
                if len(summary_lines) >= 2:  # Max 2 meaningful lines
                    break
        
        summary = ' '.join(summary_lines)
        if len(summary) > 150:
            summary = summary[:147] + "..."
        
        return summary or "Task completed"
    
    async def _process_file_changes(self, result: Dict[str, Any], compiled: Dict[str, Any]):
        """Process file changes from agent result."""
        
        # Files created
        for file_path in result.get('files_created', []):
            compiled['files']['created'].append({
                'path': file_path,
                'agent_id': result.get('agent_id'),
                'lines': await self._count_file_lines(file_path)
            })
        
        # Files modified
        for file_path in result.get('files_modified', []):
            compiled['files']['modified'].append({
                'path': file_path,
                'agent_id': result.get('agent_id'),
                'added_lines': 0,  # Would be calculated from diff
                'removed_lines': 0  # Would be calculated from diff
            })
    
    async def _process_tool_calls(self, tool_calls: List[Dict[str, Any]], compiled: Dict[str, Any]):
        """Process tool calls to extract additional information."""
        
        for tool_call in tool_calls:
            function_name = tool_call.get('function', {}).get('name', '')
            
            if function_name == 'coder':
                # Extract code generation info
                self._process_coder_tool_call(tool_call, compiled)
            elif function_name == 'multimodal':
                # Extract multimodal processing info
                self._process_multimodal_tool_call(tool_call, compiled)
    
    def _process_coder_tool_call(self, tool_call: Dict[str, Any], compiled: Dict[str, Any]):
        """Process coder tool call results."""
        # This would extract information about code generation
        # For now, just track that coding was performed
        compiled['artifacts'].append({
            'type': 'code_generation',
            'tool_call_id': tool_call.get('id'),
            'timestamp': datetime.now().isoformat()
        })
    
    def _process_multimodal_tool_call(self, tool_call: Dict[str, Any], compiled: Dict[str, Any]):
        """Process multimodal tool call results."""
        # This would extract information about multimodal processing
        compiled['artifacts'].append({
            'type': 'multimodal_processing',
            'tool_call_id': tool_call.get('id'),
            'timestamp': datetime.now().isoformat()
        })
    
    def _extract_code_metrics(self, result: Dict[str, Any], compiled: Dict[str, Any]):
        """Extract code quality metrics from agent output."""
        output = result.get('output', '')
        
        # Simple heuristics for code metrics
        # In a real implementation, this would parse actual code
        
        # Count function definitions
        function_count = output.count('def ') + output.count('function ')
        compiled['code_quality']['functions_created'] += function_count
        
        # Count class definitions
        class_count = output.count('class ') + output.count('interface ')
        compiled['code_quality']['classes_created'] += class_count
        
        # Estimate lines of code
        code_lines = len([line for line in output.split('\n') if line.strip() and not line.strip().startswith('#')])
        compiled['code_quality']['lines_added'] += code_lines
    
    async def _count_file_lines(self, file_path: str) -> int:
        """Count lines in a file."""
        try:
            path = Path(file_path)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return len(f.readlines())
        except Exception:
            pass
        return 0
    
    def _generate_summary(self, compiled: Dict[str, Any]):
        """Generate summary statistics."""
        
        # Basic counts
        compiled['summary'] = {
            'completed_tasks': compiled['execution']['tasks_completed'],
            'failed_tasks': compiled['execution']['tasks_failed'],
            'total_agents': len(compiled['execution']['agents_used']),
            'execution_time': compiled['execution']['total_time'],
            'created_files': len(compiled['files']['created']),
            'modified_files': len(compiled['files']['modified']),
            'tests_passed': compiled['tests']['passed'],
            'total_tests': compiled['tests']['total'],
            'lines_added': compiled['code_quality']['lines_added'],
            'functions_created': compiled['code_quality']['functions_created'],
            'classes_created': compiled['code_quality']['classes_created']
        }
        
        # Success rate
        total_tasks = compiled['summary']['completed_tasks'] + compiled['summary']['failed_tasks']
        if total_tasks > 0:
            compiled['summary']['success_rate'] = compiled['summary']['completed_tasks'] / total_tasks
        else:
            compiled['summary']['success_rate'] = 0.0
        
        # Test coverage (placeholder)
        if compiled['tests']['total'] > 0:
            compiled['tests']['coverage'] = compiled['tests']['passed'] / compiled['tests']['total']
        
        # Quality assessment
        compiled['summary']['quality_score'] = self._calculate_quality_score(compiled)
    
    def _calculate_quality_score(self, compiled: Dict[str, Any]) -> float:
        """Calculate overall quality score (0-100)."""
        score = 0.0
        
        # Success rate (40% of score)
        score += compiled['summary']['success_rate'] * 40
        
        # Test coverage (30% of score)
        score += compiled['tests']['coverage'] * 30
        
        # Code quality (30% of score)
        if compiled['code_quality']['lines_added'] > 0:
            # Ratio of functions/classes to lines (higher is better structure)
            structure_ratio = (
                compiled['code_quality']['functions_created'] + 
                compiled['code_quality']['classes_created']
            ) / compiled['code_quality']['lines_added']
            
            # Normalize to 0-1 range (assume 0.1 is good ratio)
            structure_score = min(structure_ratio / 0.1, 1.0)
            score += structure_score * 30
        
        return min(score, 100.0)
    
    async def _analyze_project_structure(self, project_dir: Path) -> Dict[str, Any]:
        """Analyze project structure and organization."""
        structure = {
            'total_files': 0,
            'python_files': 0,
            'test_files': 0,
            'config_files': 0,
            'documentation_files': 0,
            'directories': [],
            'main_modules': [],
            'has_tests': False,
            'has_requirements': False,
            'has_readme': False,
            'has_setup': False
        }
        
        try:
            for item in project_dir.rglob('*'):
                if item.is_file():
                    structure['total_files'] += 1
                    
                    # Categorize files
                    if item.suffix == '.py':
                        structure['python_files'] += 1
                        if 'test' in item.name.lower():
                            structure['test_files'] += 1
                        else:
                            structure['main_modules'].append(str(item.relative_to(project_dir)))
                    
                    elif item.suffix in ['.json', '.yaml', '.yml', '.toml', '.cfg', '.ini']:
                        structure['config_files'] += 1
                    
                    elif item.suffix in ['.md', '.rst', '.txt']:
                        structure['documentation_files'] += 1
                    
                    # Check for important files
                    if item.name.lower() in ['requirements.txt', 'pyproject.toml', 'setup.py']:
                        structure['has_requirements'] = True
                    elif item.name.lower() in ['readme.md', 'readme.rst', 'readme.txt']:
                        structure['has_readme'] = True
                    elif item.name.lower() in ['setup.py', 'setup.cfg']:
                        structure['has_setup'] = True
                
                elif item.is_dir() and not item.name.startswith('.'):
                    structure['directories'].append(str(item.relative_to(project_dir)))
            
            structure['has_tests'] = structure['test_files'] > 0
            
        except Exception as e:
            structure['error'] = f"Failed to analyze project structure: {e}"
        
        return structure
    
    def _generate_recommendations(self, compiled: Dict[str, Any]):
        """Generate recommendations based on compilation results."""
        recommendations = []
        
        # Test coverage recommendations
        if compiled['tests']['coverage'] < 80.0:
            recommendations.append({
                'type': 'testing',
                'priority': 'high',
                'message': f"Test coverage is {compiled['tests']['coverage']:.1f}%. Consider adding more tests to reach 80% target.",
                'action': 'Add unit tests for uncovered code paths'
            })
        
        # Code quality recommendations
        if compiled['code_quality']['lines_added'] > 0:
            functions_per_line = compiled['code_quality']['functions_created'] / compiled['code_quality']['lines_added']
            if functions_per_line < 0.05:  # Less than 1 function per 20 lines
                recommendations.append({
                    'type': 'code_quality',
                    'priority': 'medium',
                    'message': 'Consider breaking down large code blocks into smaller functions for better maintainability.',
                    'action': 'Refactor large functions into smaller, focused functions'
                })
        
        # Error handling recommendations
        if compiled['errors']:
            recommendations.append({
                'type': 'reliability',
                'priority': 'high',
                'message': f"Found {len(compiled['errors'])} errors during execution. Address these before proceeding.",
                'action': 'Review and fix execution errors'
            })
        
        # Project structure recommendations
        if 'project_structure' in compiled:
            structure = compiled['project_structure']
            
            if not structure.get('has_tests', False):
                recommendations.append({
                    'type': 'testing',
                    'priority': 'high',
                    'message': 'No test files detected. Consider adding a test suite.',
                    'action': 'Create test directory and add unit tests'
                })
            
            if not structure.get('has_readme', False):
                recommendations.append({
                    'type': 'documentation',
                    'priority': 'medium',
                    'message': 'No README file found. Consider adding project documentation.',
                    'action': 'Create README.md with project description and usage instructions'
                })
            
            if not structure.get('has_requirements', False) and structure.get('python_files', 0) > 0:
                recommendations.append({
                    'type': 'dependencies',
                    'priority': 'medium',
                    'message': 'No requirements file found. Consider documenting dependencies.',
                    'action': 'Create requirements.txt or pyproject.toml'
                })
        
        compiled['recommendations'] = recommendations
    
    async def generate_summary_report(self, compiled: Dict[str, Any]) -> str:
        """Generate a comprehensive summary report in markdown format."""
        
        report_lines = [
            "# Execution Summary Report",
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Overview",
            f"- **Tasks Completed**: {compiled['summary'].get('completed_tasks', 0)}/{compiled['summary'].get('completed_tasks', 0) + compiled['summary'].get('failed_tasks', 0)}",
            f"- **Success Rate**: {compiled['summary'].get('success_rate', 0.0):.1%}",
            f"- **Execution Time**: {compiled['summary'].get('execution_time', 0.0):.2f} seconds",
            f"- **Quality Score**: {compiled['summary'].get('quality_score', 0.0):.1f}/100",
            "",
            "## File Changes",
            f"- **Files Created**: {len(compiled.get('files', {}).get('created', []))}",
            f"- **Files Modified**: {len(compiled.get('files', {}).get('modified', []))}",
            f"- **Lines Added**: {compiled.get('code_quality', {}).get('lines_added', 0)}",
            ""
        ]
        
        # Add file details
        files = compiled.get('files', {})
        if files.get('created'):
            report_lines.extend([
                "### Created Files",
                ""
            ])
            for file_info in files['created']:
                lines = file_info.get('lines', 'unknown')
                report_lines.append(f"- `{file_info['path']}` ({lines} lines)")
            report_lines.append("")
        
        if files.get('modified'):
            report_lines.extend([
                "### Modified Files",
                ""
            ])
            for file_info in files['modified']:
                added = file_info.get('added_lines', 0)
                removed = file_info.get('removed_lines', 0)
                report_lines.append(f"- `{file_info['path']}` (+{added}/-{removed} lines)")
            report_lines.append("")
        
        # Add test results
        tests = compiled.get('tests', {})
        if tests.get('total', 0) > 0:
            report_lines.extend([
                "## Test Results",
                f"- **Total Tests**: {tests.get('total', 0)}",
                f"- **Passed**: {tests.get('passed', 0)}",
                f"- **Failed**: {tests.get('failed', 0)}",
                f"- **Coverage**: {tests.get('coverage', 0.0):.1f}%",
                ""
            ])
        
        # Add recommendations
        recommendations = compiled.get('recommendations', [])
        if recommendations:
            report_lines.extend([
                "## Recommendations",
                ""
            ])
            
            for rec in recommendations:
                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(rec.get('priority', 'medium'), "⚪")
                report_lines.extend([
                    f"### {priority_emoji} {rec.get('type', 'General').title()}",
                    f"**Issue**: {rec.get('message', 'No message')}",
                    f"**Action**: {rec.get('action', 'No action specified')}",
                    ""
                ])
        
        # Add errors and warnings
        errors = compiled.get('errors', [])
        if errors:
            report_lines.extend([
                "## Errors",
                ""
            ])
            for error in errors:
                report_lines.append(f"- ❌ {error}")
            report_lines.append("")
        
        warnings = compiled.get('warnings', [])
        if warnings:
            report_lines.extend([
                "## Warnings",
                ""
            ])
            for warning in warnings:
                report_lines.append(f"- ⚠️ {warning}")
            report_lines.append("")
        
        return "\n".join(report_lines)