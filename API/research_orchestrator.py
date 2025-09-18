"""
Deep Research Orchestration System for Melanie AI ecosystem.

This module provides:
- DeepResearchOrchestrator class for comprehensive research workflows
- Research plan generation and analysis
- Concurrent agent spawning (1-5 agents) with Melanie-3-light
- Agent failure handling with 2x retry and 5min timeout
- Markdown compilation and PDF generation
- RAG integration for context management

Requirements implemented: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import tempfile
import markdown
from pathlib import Path

# Import model classes
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'AI'))

try:
    from melanie_three_model import MelanieThree
    from melanie_three_light_model import MelanieThreeLight, AgentTask, AgentResult
except ImportError as e:
    logging.warning(f"Could not import AI models: {e}")
    # Create placeholder classes for testing
    class MelanieThree:
        pass
    class MelanieThreeLight:
        pass
    class AgentTask:
        pass
    class AgentResult:
        pass

try:
    from models import ChatMessage, MessageRole, ChatCompletionResponse
    from tools import ToolManager, ToolType, ToolCall, ToolResult
except ImportError:
    # Fallback for testing
    from pydantic import BaseModel
    from enum import Enum
    from typing import List, Optional, Dict, Any
    
    class MessageRole(str, Enum):
        USER = "user"
        ASSISTANT = "assistant"
        SYSTEM = "system"
    
    class ChatMessage(BaseModel):
        role: MessageRole
        content: str
        name: Optional[str] = None
    
    class ChatCompletionResponse(BaseModel):
        id: str
        object: str = "chat.completion"
        created: int
        model: str
        choices: List[Dict]
        usage: Dict[str, int]
        research_plan: Optional[Dict[str, Any]] = None
    
    class ToolManager:
        pass
    class ToolType:
        pass
    class ToolCall:
        pass
    class ToolResult:
        pass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ResearchStatus(str, Enum):
    """Status of research workflow."""
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPILING = "compiling"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ResearchSubtask:
    """Represents a subtask in the research plan."""
    id: str
    title: str
    description: str
    instructions: str
    priority: int = 0
    estimated_duration: int = 300  # 5 minutes default
    tools_required: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class ResearchPlan:
    """Comprehensive research plan for deep investigation."""
    id: str
    query: str
    title: str
    description: str
    subtasks: List[ResearchSubtask]
    estimated_agents: int
    estimated_duration: int
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentExecution:
    """Tracks execution of a research agent."""
    id: str
    subtask_id: str
    agent_instructions: str
    status: str = "pending"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 2
    timeout: float = 300.0  # 5 minutes
    result: Optional[AgentResult] = None
    error: Optional[str] = None


@dataclass
class ResearchResult:
    """Final result of research orchestration."""
    plan: ResearchPlan
    agent_executions: List[AgentExecution]
    compiled_markdown: str
    pdf_path: Optional[str] = None
    rag_document_id: Optional[str] = None
    synthesis_response: Optional[ChatCompletionResponse] = None
    execution_time: float = 0.0
    status: ResearchStatus = ResearchStatus.COMPLETED
    metadata: Dict[str, Any] = field(default_factory=dict)


class DeepResearchOrchestratorError(Exception):
    """Base exception for research orchestrator errors."""
    pass


class ResearchPlanGenerationError(DeepResearchOrchestratorError):
    """Error in research plan generation."""
    pass


class AgentExecutionError(DeepResearchOrchestratorError):
    """Error in agent execution."""
    pass


class MarkdownCompilationError(DeepResearchOrchestratorError):
    """Error in markdown compilation."""
    pass


class PDFGenerationError(DeepResearchOrchestratorError):
    """Error in PDF generation."""
    pass


class DeepResearchOrchestrator:
    """
    Orchestrates comprehensive research workflows using multiple AI agents.
    
    Implements requirements 4.1-4.8:
    - Research plan generation and analysis (4.1)
    - Concurrent agent spawning (1-5 agents) (4.2)
    - Agent tool access with diversity rules (4.3)
    - Markdown compilation (4.4)
    - RAG integration for compression (4.5)
    - Synthesis with main Melanie-3 (4.6)
    - PDF generation with formatting (4.7)
    - Agent failure handling with retry (4.8)
    """
    
    def __init__(self, **kwargs):
        """
        Initialize deep research orchestrator.
        
        Args:
            **kwargs: Configuration options
        """
        self.config = kwargs
        
        # Initialize AI models
        self.main_model = None  # MelanieThree for synthesis
        self.light_model = None  # MelanieThreeLight for agents
        
        # Initialize tool manager
        self.tool_manager = ToolManager(**kwargs.get("tools", {}))
        
        # Research configuration
        self.max_agents = kwargs.get("max_agents", 5)
        self.min_agents = kwargs.get("min_agents", 1)
        self.agent_timeout = kwargs.get("agent_timeout", 300.0)  # 5 minutes
        self.max_retries = kwargs.get("max_retries", 2)
        
        # RAG integration (will be initialized when needed)
        self.rag_client = None
        
        # Active research sessions
        self.active_research: Dict[str, ResearchResult] = {}
        self._lock = asyncio.Lock()
    
    async def _get_main_model(self) -> MelanieThree:
        """Get or initialize the main Melanie-3 model for synthesis."""
        if self.main_model is None:
            try:
                self.main_model = MelanieThree()
            except Exception as e:
                logger.error(f"Failed to initialize MelanieThree: {e}")
                raise DeepResearchOrchestratorError(f"Main model initialization failed: {e}")
        return self.main_model
    
    async def _get_light_model(self) -> MelanieThreeLight:
        """Get or initialize the Melanie-3-light model for agents."""
        if self.light_model is None:
            try:
                self.light_model = MelanieThreeLight()
            except Exception as e:
                logger.error(f"Failed to initialize MelanieThreeLight: {e}")
                raise DeepResearchOrchestratorError(f"Light model initialization failed: {e}")
        return self.light_model
    
    async def _get_rag_client(self):
        """Get or initialize RAG client for document ingestion."""
        if self.rag_client is None:
            try:
                # Import RAG client
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'AI'))
                from rag_integration_client import RagIntegrationClient
                self.rag_client = RagIntegrationClient()
            except ImportError as e:
                logger.warning(f"RAG client not available: {e}")
                self.rag_client = None
        return self.rag_client
    
    async def generate_research_plan(self, query: str) -> ResearchPlan:
        """
        Generate detailed research plan from query.
        
        Implements requirement 4.1: analyze query and output detailed research plan.
        
        Args:
            query: Research query or topic
            
        Returns:
            ResearchPlan: Comprehensive research plan
            
        Raises:
            ResearchPlanGenerationError: If plan generation fails
        """
        try:
            main_model = await self._get_main_model()
            
            # Create system prompt for research plan generation
            system_prompt = """You are Melanie, an expert research coordinator. Your task is to analyze research queries and create comprehensive research plans.

For the given query, create a detailed research plan with:
1. A clear title and description
2. 3-5 specific subtasks that cover different aspects/perspectives
3. Estimated number of agents needed (1-5)
4. Estimated duration for the entire research
5. Tools required for each subtask

Each subtask should:
- Have a specific focus area or perspective
- Include detailed instructions for the research agent
- Specify required tools (light-search, medium-search, coder, multimodal)
- Be diverse enough to avoid redundancy

Respond in JSON format with the following structure:
{
    "title": "Research Title",
    "description": "Brief description of the research scope",
    "subtasks": [
        {
            "title": "Subtask Title",
            "description": "What this subtask covers",
            "instructions": "Detailed instructions for the agent",
            "priority": 1,
            "estimated_duration": 300,
            "tools_required": ["light-search", "medium-search"],
            "dependencies": []
        }
    ],
    "estimated_agents": 3,
    "estimated_duration": 900
}"""
            
            user_prompt = f"Create a comprehensive research plan for: {query}"
            
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=MessageRole.USER, content=user_prompt)
            ]
            
            # Generate research plan
            response = await main_model.generate(messages, max_tokens=4000)
            
            # Parse JSON response
            plan_content = response.choices[0].message["content"]
            
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in plan_content:
                json_start = plan_content.find("```json") + 7
                json_end = plan_content.find("```", json_start)
                plan_content = plan_content[json_start:json_end].strip()
            elif "```" in plan_content:
                json_start = plan_content.find("```") + 3
                json_end = plan_content.find("```", json_start)
                plan_content = plan_content[json_start:json_end].strip()
            
            try:
                plan_data = json.loads(plan_content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse research plan JSON: {e}")
                logger.error(f"Raw content: {plan_content}")
                raise ResearchPlanGenerationError(f"Invalid JSON in research plan: {e}")
            
            # Create ResearchPlan object
            plan_id = f"research-{int(time.time())}-{uuid.uuid4().hex[:8]}"
            
            subtasks = []
            for i, subtask_data in enumerate(plan_data.get("subtasks", [])):
                subtask = ResearchSubtask(
                    id=f"{plan_id}-subtask-{i+1}",
                    title=subtask_data.get("title", f"Subtask {i+1}"),
                    description=subtask_data.get("description", ""),
                    instructions=subtask_data.get("instructions", ""),
                    priority=subtask_data.get("priority", i+1),
                    estimated_duration=subtask_data.get("estimated_duration", 300),
                    tools_required=subtask_data.get("tools_required", ["light-search"]),
                    dependencies=subtask_data.get("dependencies", [])
                )
                subtasks.append(subtask)
            
            # Validate agent count
            estimated_agents = plan_data.get("estimated_agents", len(subtasks))
            estimated_agents = max(self.min_agents, min(self.max_agents, estimated_agents))
            
            research_plan = ResearchPlan(
                id=plan_id,
                query=query,
                title=plan_data.get("title", f"Research: {query[:50]}..."),
                description=plan_data.get("description", ""),
                subtasks=subtasks,
                estimated_agents=estimated_agents,
                estimated_duration=plan_data.get("estimated_duration", 900),
                metadata={
                    "generation_model": main_model.model_name,
                    "generation_usage": response.usage.dict() if hasattr(response.usage, 'dict') else response.usage
                }
            )
            
            logger.info(f"Generated research plan '{research_plan.title}' with {len(subtasks)} subtasks")
            return research_plan
            
        except Exception as e:
            logger.error(f"Research plan generation failed: {str(e)}")
            if isinstance(e, ResearchPlanGenerationError):
                raise
            else:
                raise ResearchPlanGenerationError(f"Plan generation failed: {str(e)}")
    
    async def spawn_research_agents(self, plan: ResearchPlan) -> List[AgentExecution]:
        """
        Spawn concurrent research agents for subtasks.
        
        Implements requirement 4.2: spawn 1-5 concurrent Melanie-3-light agents.
        
        Args:
            plan: Research plan with subtasks
            
        Returns:
            List[AgentExecution]: Agent execution trackers
        """
        try:
            light_model = await self._get_light_model()
            
            # Create agent executions for each subtask
            agent_executions = []
            
            for subtask in plan.subtasks:
                # Create agent instructions
                agent_instructions = f"""You are a research agent working on: {subtask.title}

Research Context:
- Main Query: {plan.query}
- Your Focus: {subtask.description}
- Available Tools: {', '.join(subtask.tools_required)}

Instructions:
{subtask.instructions}

Guidelines:
1. Use the available tools to gather comprehensive information
2. Follow query diversity rules when making multiple tool calls
3. Provide detailed, well-structured findings
4. Include sources and citations where possible
5. Focus on your specific aspect while considering the broader research context

Your response should be a comprehensive research report on your assigned topic."""
                
                agent_execution = AgentExecution(
                    id=f"{subtask.id}-agent",
                    subtask_id=subtask.id,
                    agent_instructions=agent_instructions,
                    timeout=subtask.estimated_duration,
                    max_retries=self.max_retries
                )
                
                agent_executions.append(agent_execution)
            
            logger.info(f"Created {len(agent_executions)} agent executions for research plan {plan.id}")
            return agent_executions
            
        except Exception as e:
            logger.error(f"Agent spawning failed: {str(e)}")
            raise AgentExecutionError(f"Failed to spawn agents: {str(e)}")
    
    async def execute_research_agents(self, agent_executions: List[AgentExecution]) -> List[AgentExecution]:
        """
        Execute research agents concurrently with failure handling.
        
        Implements requirements 4.3 and 4.8:
        - Agent tool access with diversity rules (4.3)
        - Agent failure handling with 2x retry and 5min timeout (4.8)
        
        Args:
            agent_executions: List of agent executions to run
            
        Returns:
            List[AgentExecution]: Updated executions with results
        """
        try:
            light_model = await self._get_light_model()
            
            # Create agent tasks
            agent_tasks = []
            for execution in agent_executions:
                # Create messages for the agent
                messages = [
                    ChatMessage(role=MessageRole.USER, content=execution.agent_instructions)
                ]
                
                # Create agent task
                task = AgentTask(
                    id=execution.id,
                    messages=messages,
                    tools=None,  # Tools will be handled by the model
                    timeout=execution.timeout,
                    max_retries=execution.max_retries,
                    metadata={"subtask_id": execution.subtask_id}
                )
                
                agent_tasks.append(task)
                
                # Update execution status
                execution.status = "running"
                execution.start_time = datetime.now()
            
            logger.info(f"Executing {len(agent_tasks)} research agents concurrently")
            
            # Execute agents concurrently using the light model's coordination
            results = await light_model.coordinate_agents(agent_tasks)
            
            # Update executions with results
            for i, result in enumerate(results):
                execution = agent_executions[i]
                execution.result = result
                execution.end_time = datetime.now()
                execution.retry_count = result.retry_count
                
                if result.success:
                    execution.status = "completed"
                    logger.info(f"Agent {execution.id} completed successfully")
                else:
                    execution.status = "failed"
                    execution.error = result.error
                    logger.error(f"Agent {execution.id} failed: {result.error}")
            
            # Log summary
            successful = sum(1 for e in agent_executions if e.status == "completed")
            failed = len(agent_executions) - successful
            logger.info(f"Agent execution complete: {successful} successful, {failed} failed")
            
            return agent_executions
            
        except Exception as e:
            logger.error(f"Agent execution failed: {str(e)}")
            
            # Update all executions as failed
            for execution in agent_executions:
                if execution.status == "running":
                    execution.status = "failed"
                    execution.error = f"Execution failed: {str(e)}"
                    execution.end_time = datetime.now()
            
            raise AgentExecutionError(f"Agent execution failed: {str(e)}")
    
    async def compile_results_to_markdown(
        self, 
        plan: ResearchPlan, 
        agent_executions: List[AgentExecution]
    ) -> str:
        """
        Compile agent results into structured Markdown format.
        
        Implements requirement 4.4: compile results into structured Markdown format.
        
        Args:
            plan: Original research plan
            agent_executions: Completed agent executions
            
        Returns:
            str: Compiled Markdown document
            
        Raises:
            MarkdownCompilationError: If compilation fails
        """
        try:
            # Start building markdown document
            markdown_content = []
            
            # Title and metadata
            markdown_content.append(f"# {plan.title}")
            markdown_content.append("")
            markdown_content.append(f"**Research Query:** {plan.query}")
            markdown_content.append("")
            markdown_content.append(f"**Description:** {plan.description}")
            markdown_content.append("")
            markdown_content.append(f"**Generated:** {plan.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            markdown_content.append("")
            markdown_content.append("---")
            markdown_content.append("")
            
            # Table of Contents
            markdown_content.append("## Table of Contents")
            markdown_content.append("")
            for i, subtask in enumerate(plan.subtasks, 1):
                markdown_content.append(f"{i}. [{subtask.title}](#{subtask.title.lower().replace(' ', '-')})")
            markdown_content.append("")
            markdown_content.append("---")
            markdown_content.append("")
            
            # Research sections
            successful_executions = [e for e in agent_executions if e.status == "completed" and e.result]
            
            for execution in successful_executions:
                # Find corresponding subtask
                subtask = next((s for s in plan.subtasks if s.id == execution.subtask_id), None)
                if not subtask:
                    continue
                
                # Section header
                markdown_content.append(f"## {subtask.title}")
                markdown_content.append("")
                markdown_content.append(f"**Focus:** {subtask.description}")
                markdown_content.append("")
                
                # Agent result content
                if execution.result and execution.result.response:
                    agent_content = execution.result.response.choices[0].message.get("content", "")
                    markdown_content.append(agent_content)
                else:
                    markdown_content.append("*No content available from this research agent.*")
                
                markdown_content.append("")
                markdown_content.append("---")
                markdown_content.append("")
            
            # Failed executions summary
            failed_executions = [e for e in agent_executions if e.status == "failed"]
            if failed_executions:
                markdown_content.append("## Research Limitations")
                markdown_content.append("")
                markdown_content.append("The following research areas could not be completed:")
                markdown_content.append("")
                
                for execution in failed_executions:
                    subtask = next((s for s in plan.subtasks if s.id == execution.subtask_id), None)
                    if subtask:
                        markdown_content.append(f"- **{subtask.title}**: {execution.error or 'Unknown error'}")
                
                markdown_content.append("")
                markdown_content.append("---")
                markdown_content.append("")
            
            # Metadata section
            markdown_content.append("## Research Metadata")
            markdown_content.append("")
            markdown_content.append(f"- **Plan ID:** {plan.id}")
            markdown_content.append(f"- **Agents Deployed:** {len(agent_executions)}")
            markdown_content.append(f"- **Successful Agents:** {len(successful_executions)}")
            markdown_content.append(f"- **Failed Agents:** {len(failed_executions)}")
            markdown_content.append(f"- **Total Duration:** {plan.estimated_duration} seconds (estimated)")
            
            # Join all content
            compiled_markdown = "\n".join(markdown_content)
            
            logger.info(f"Compiled research results into {len(compiled_markdown)} character markdown document")
            return compiled_markdown
            
        except Exception as e:
            logger.error(f"Markdown compilation failed: {str(e)}")
            raise MarkdownCompilationError(f"Failed to compile markdown: {str(e)}")
    
    async def ingest_to_rag(self, markdown_content: str, plan: ResearchPlan) -> Optional[str]:
        """
        Ingest compiled markdown into RAG system for compression.
        
        Implements requirement 4.5: ingest Markdown via RAG for compression and context management.
        
        Args:
            markdown_content: Compiled markdown document
            plan: Research plan for metadata
            
        Returns:
            Optional[str]: RAG document ID if successful, None if RAG unavailable
        """
        try:
            rag_client = await self._get_rag_client()
            
            if not rag_client:
                logger.warning("RAG client not available, skipping ingestion")
                return None
            
            # Ingest document with metadata
            document_id = await rag_client.ingest_text(
                content=markdown_content,
                metadata={
                    "type": "research_report",
                    "plan_id": plan.id,
                    "query": plan.query,
                    "title": plan.title,
                    "created_at": plan.created_at.isoformat(),
                    "agent_count": len(plan.subtasks)
                }
            )
            
            logger.info(f"Ingested research document to RAG with ID: {document_id}")
            return document_id
            
        except Exception as e:
            logger.error(f"RAG ingestion failed: {str(e)}")
            # Don't fail the entire research process if RAG fails
            return None
    
    async def synthesize_final_report(
        self, 
        plan: ResearchPlan, 
        markdown_content: str,
        rag_document_id: Optional[str] = None
    ) -> ChatCompletionResponse:
        """
        Synthesize final analysis using main Melanie-3 model.
        
        Implements requirement 4.6: pass processed chunks to main Melanie-3 for final analysis.
        
        Args:
            plan: Original research plan
            markdown_content: Compiled research content
            rag_document_id: Optional RAG document ID for context retrieval
            
        Returns:
            ChatCompletionResponse: Final synthesis response
        """
        try:
            main_model = await self._get_main_model()
            
            # Get RAG context if available
            rag_context = ""
            if rag_document_id:
                try:
                    rag_client = await self._get_rag_client()
                    if rag_client:
                        context_chunks = await rag_client.get_context(plan.query, mode="research")
                        if context_chunks:
                            rag_context = "\n\n".join([chunk["content"] for chunk in context_chunks[:10]])
                except Exception as e:
                    logger.warning(f"Failed to retrieve RAG context: {e}")
            
            # Create synthesis prompt
            system_prompt = """You are Melanie, an expert research analyst. Your task is to synthesize comprehensive research findings into a coherent, insightful analysis.

Review the compiled research data and provide:
1. Executive Summary (2-3 paragraphs)
2. Key Findings (bullet points)
3. Analysis and Insights (detailed discussion)
4. Conclusions and Implications
5. Recommendations for further research

Focus on:
- Identifying patterns and connections across different research areas
- Highlighting the most significant findings
- Providing actionable insights
- Noting any gaps or limitations in the research

Your synthesis should be comprehensive yet accessible, suitable for both technical and general audiences."""
            
            user_prompt = f"""Please synthesize the following research on: {plan.query}

## Research Plan
{plan.description}

## Compiled Research Data
{markdown_content[:50000]}  # Limit to avoid token limits

## Additional Context (if available)
{rag_context[:10000] if rag_context else "No additional context available"}

Please provide a comprehensive synthesis of these research findings."""
            
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=MessageRole.USER, content=user_prompt)
            ]
            
            # Generate synthesis
            response = await main_model.generate(messages, max_tokens=8000)
            
            logger.info(f"Generated final synthesis for research plan {plan.id}")
            return response
            
        except Exception as e:
            logger.error(f"Synthesis generation failed: {str(e)}")
            raise DeepResearchOrchestratorError(f"Failed to synthesize final report: {str(e)}")
    
    async def generate_pdf_report(
        self, 
        markdown_content: str, 
        synthesis_content: str,
        plan: ResearchPlan
    ) -> str:
        """
        Generate formatted PDF report with TOC, headings, tables, and embedded images.
        
        Implements requirement 4.7: generate formatted PDF with TOC, headings, tables, and embedded images.
        
        Args:
            markdown_content: Compiled research markdown
            synthesis_content: Final synthesis content
            plan: Research plan for metadata
            
        Returns:
            str: Path to generated PDF file
            
        Raises:
            PDFGenerationError: If PDF generation fails
        """
        try:
            # Create temporary directory for PDF generation
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create complete document with synthesis
                complete_content = []
                
                # Title page
                complete_content.append(f"# {plan.title}")
                complete_content.append("")
                complete_content.append(f"**Research Query:** {plan.query}")
                complete_content.append("")
                complete_content.append(f"**Generated:** {plan.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                complete_content.append("")
                complete_content.append("---")
                complete_content.append("")
                
                # Executive Summary from synthesis
                complete_content.append("# Executive Summary")
                complete_content.append("")
                complete_content.append(synthesis_content)
                complete_content.append("")
                complete_content.append("---")
                complete_content.append("")
                
                # Full research content
                complete_content.append("# Detailed Research Findings")
                complete_content.append("")
                complete_content.append(markdown_content)
                
                # Write to temporary markdown file
                md_file = temp_path / "research_report.md"
                with open(md_file, 'w', encoding='utf-8') as f:
                    f.write("\n".join(complete_content))
                
                # Generate PDF using pandoc (if available) or weasyprint
                pdf_file = temp_path / "research_report.pdf"
                
                try:
                    # Try pandoc first (better formatting)
                    import subprocess
                    result = subprocess.run([
                        "pandoc", 
                        str(md_file), 
                        "-o", str(pdf_file),
                        "--pdf-engine=wkhtmltopdf",
                        "--toc",
                        "--toc-depth=3",
                        "-V", "geometry:margin=1in",
                        "-V", "fontsize=11pt"
                    ], capture_output=True, text=True)
                    
                    if result.returncode != 0:
                        raise subprocess.CalledProcessError(result.returncode, "pandoc")
                        
                except (subprocess.CalledProcessError, FileNotFoundError):
                    # Fallback to weasyprint
                    try:
                        import weasyprint
                        
                        # Convert markdown to HTML first
                        html_content = markdown.markdown(
                            "\n".join(complete_content),
                            extensions=['toc', 'tables', 'codehilite']
                        )
                        
                        # Add CSS styling
                        styled_html = f"""
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <meta charset="utf-8">
                            <title>{plan.title}</title>
                            <style>
                                body {{ font-family: Arial, sans-serif; margin: 1in; }}
                                h1 {{ color: #001F3F; border-bottom: 2px solid #007BFF; }}
                                h2 {{ color: #007BFF; }}
                                code {{ background-color: #f5f5f5; padding: 2px 4px; }}
                                pre {{ background-color: #f5f5f5; padding: 10px; }}
                                table {{ border-collapse: collapse; width: 100%; }}
                                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                                th {{ background-color: #f2f2f2; }}
                            </style>
                        </head>
                        <body>
                        {html_content}
                        </body>
                        </html>
                        """
                        
                        # Generate PDF
                        weasyprint.HTML(string=styled_html).write_pdf(str(pdf_file))
                        
                    except ImportError:
                        # Final fallback - just save as HTML
                        html_file = temp_path / "research_report.html"
                        html_content = markdown.markdown(
                            "\n".join(complete_content),
                            extensions=['toc', 'tables', 'codehilite']
                        )
                        
                        with open(html_file, 'w', encoding='utf-8') as f:
                            f.write(html_content)
                        
                        logger.warning("PDF generation libraries not available, saved as HTML instead")
                        
                        # Copy to permanent location
                        output_dir = Path("research_reports")
                        output_dir.mkdir(exist_ok=True)
                        final_path = output_dir / f"{plan.id}_report.html"
                        
                        import shutil
                        shutil.copy2(html_file, final_path)
                        
                        return str(final_path)
                
                # Copy PDF to permanent location
                output_dir = Path("research_reports")
                output_dir.mkdir(exist_ok=True)
                final_path = output_dir / f"{plan.id}_report.pdf"
                
                import shutil
                shutil.copy2(pdf_file, final_path)
                
                logger.info(f"Generated PDF report: {final_path}")
                return str(final_path)
                
        except Exception as e:
            logger.error(f"PDF generation failed: {str(e)}")
            raise PDFGenerationError(f"Failed to generate PDF: {str(e)}")
    
    async def conduct_research(self, query: str) -> ResearchResult:
        """
        Conduct comprehensive deep research workflow.
        
        Orchestrates the complete research process implementing all requirements 4.1-4.8.
        
        Args:
            query: Research query or topic
            
        Returns:
            ResearchResult: Complete research results
            
        Raises:
            DeepResearchOrchestratorError: If research workflow fails
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting deep research for query: {query}")
            
            # Step 1: Generate research plan (Requirement 4.1)
            logger.info("Step 1: Generating research plan...")
            plan = await self.generate_research_plan(query)
            
            # Step 2: Spawn research agents (Requirement 4.2)
            logger.info("Step 2: Spawning research agents...")
            agent_executions = await self.spawn_research_agents(plan)
            
            # Step 3: Execute agents with tool access and failure handling (Requirements 4.3, 4.8)
            logger.info("Step 3: Executing research agents...")
            completed_executions = await self.execute_research_agents(agent_executions)
            
            # Step 4: Compile results to markdown (Requirement 4.4)
            logger.info("Step 4: Compiling results to markdown...")
            compiled_markdown = await self.compile_results_to_markdown(plan, completed_executions)
            
            # Step 5: Ingest to RAG for compression (Requirement 4.5)
            logger.info("Step 5: Ingesting to RAG system...")
            rag_document_id = await self.ingest_to_rag(compiled_markdown, plan)
            
            # Step 6: Synthesize final report (Requirement 4.6)
            logger.info("Step 6: Synthesizing final report...")
            synthesis_response = await self.synthesize_final_report(
                plan, compiled_markdown, rag_document_id
            )
            
            # Step 7: Generate PDF report (Requirement 4.7)
            logger.info("Step 7: Generating PDF report...")
            synthesis_content = synthesis_response.choices[0].message.get("content", "")
            pdf_path = await self.generate_pdf_report(compiled_markdown, synthesis_content, plan)
            
            # Create final result
            execution_time = time.time() - start_time
            
            result = ResearchResult(
                plan=plan,
                agent_executions=completed_executions,
                compiled_markdown=compiled_markdown,
                pdf_path=pdf_path,
                rag_document_id=rag_document_id,
                synthesis_response=synthesis_response,
                execution_time=execution_time,
                status=ResearchStatus.COMPLETED,
                metadata={
                    "successful_agents": len([e for e in completed_executions if e.status == "completed"]),
                    "failed_agents": len([e for e in completed_executions if e.status == "failed"]),
                    "total_agents": len(completed_executions),
                    "pdf_generated": pdf_path is not None,
                    "rag_ingested": rag_document_id is not None
                }
            )
            
            # Store in active research
            async with self._lock:
                self.active_research[plan.id] = result
            
            logger.info(f"Deep research completed successfully in {execution_time:.2f} seconds")
            logger.info(f"Research ID: {plan.id}")
            logger.info(f"PDF Report: {pdf_path}")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Deep research failed after {execution_time:.2f} seconds: {str(e)}")
            
            # Create failed result if we have a plan
            if 'plan' in locals():
                result = ResearchResult(
                    plan=plan,
                    agent_executions=locals().get('completed_executions', []),
                    compiled_markdown="",
                    execution_time=execution_time,
                    status=ResearchStatus.FAILED,
                    metadata={"error": str(e)}
                )
                
                async with self._lock:
                    self.active_research[plan.id] = result
            
            raise DeepResearchOrchestratorError(f"Research workflow failed: {str(e)}")
    
    async def get_research_status(self, research_id: str) -> Optional[ResearchResult]:
        """
        Get status of active or completed research.
        
        Args:
            research_id: Research plan ID
            
        Returns:
            Optional[ResearchResult]: Research result if found
        """
        async with self._lock:
            return self.active_research.get(research_id)
    
    async def list_active_research(self) -> List[str]:
        """
        List all active research IDs.
        
        Returns:
            List[str]: List of research IDs
        """
        async with self._lock:
            return list(self.active_research.keys())
    
    async def cleanup_completed_research(self, max_age_hours: int = 24):
        """
        Clean up old completed research from memory.
        
        Args:
            max_age_hours: Maximum age in hours before cleanup
        """
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        
        async with self._lock:
            to_remove = []
            for research_id, result in self.active_research.items():
                if result.plan.created_at.timestamp() < cutoff_time:
                    to_remove.append(research_id)
            
            for research_id in to_remove:
                del self.active_research[research_id]
                logger.info(f"Cleaned up old research: {research_id}")
    
    async def shutdown(self):
        """Shutdown the orchestrator and cleanup resources."""
        try:
            if self.main_model and hasattr(self.main_model, '__aexit__'):
                await self.main_model.__aexit__(None, None, None)
            
            if self.light_model and hasattr(self.light_model, '__aexit__'):
                await self.light_model.__aexit__(None, None, None)
            
            logger.info("Deep research orchestrator shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during orchestrator shutdown: {e}")


# Example usage and testing
if __name__ == "__main__":
    async def test_research_orchestration():
        """Test the deep research orchestration system."""
        try:
            orchestrator = DeepResearchOrchestrator()
            
            # Test research query
            query = "What are the latest developments in AI safety and alignment research?"
            
            # Conduct research
            result = await orchestrator.conduct_research(query)
            
            print(f"Research completed: {result.plan.title}")
            print(f"Status: {result.status}")
            print(f"Execution time: {result.execution_time:.2f} seconds")
            print(f"PDF report: {result.pdf_path}")
            print(f"Successful agents: {result.metadata.get('successful_agents', 0)}")
            print(f"Failed agents: {result.metadata.get('failed_agents', 0)}")
            
            # Cleanup
            await orchestrator.shutdown()
            
        except Exception as e:
            print(f"Test failed: {str(e)}")
    
    # Run test
    asyncio.run(test_research_orchestration())