"""
Agent Horizontal Scaling and Coordination System.

Provides optimized agent coordination with threading, performance monitoring,
and dynamic scaling based on workload and performance metrics.
"""

import asyncio
import threading
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Awaitable
from enum import Enum
import psutil
import json
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent status enumeration."""
    IDLE = "idle"
    BUSY = "busy"
    FAILED = "failed"
    TERMINATED = "terminated"


@dataclass
class AgentMetrics:
    """Metrics for individual agent performance."""
    agent_id: str
    status: AgentStatus
    tasks_completed: int = 0
    tasks_failed: int = 0
    avg_task_time: float = 0.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    last_activity: float = field(default_factory=time.time)
    
    @property
    def success_rate(self) -> float:
        """Calculate agent success rate."""
        total_tasks = self.tasks_completed + self.tasks_failed
        if total_tasks == 0:
            return 1.0
        return self.tasks_completed / total_tasks
    
    @property
    def efficiency_score(self) -> float:
        """Calculate agent efficiency score (0.0 to 1.0)."""
        if self.avg_task_time == 0:
            return 1.0
        
        # Combine success rate and speed
        speed_score = min(1.0, 10.0 / max(self.avg_task_time, 1.0))  # Faster = better
        return (self.success_rate * 0.7) + (speed_score * 0.3)


@dataclass
class ScalingMetrics:
    """System-wide scaling metrics."""
    total_agents: int = 0
    active_agents: int = 0
    idle_agents: int = 0
    failed_agents: int = 0
    queue_size: int = 0
    avg_queue_wait_time: float = 0.0
    system_cpu_usage: float = 0.0
    system_memory_usage: float = 0.0
    throughput_per_second: float = 0.0
    
    @property
    def utilization_rate(self) -> float:
        """Calculate agent utilization rate."""
        if self.total_agents == 0:
            return 0.0
        return self.active_agents / self.total_agents
    
    @property
    def needs_scaling_up(self) -> bool:
        """Determine if system needs more agents."""
        return (
            self.utilization_rate > 0.8 and  # High utilization
            self.queue_size > 5 and  # Queue building up
            self.avg_queue_wait_time > 2.0  # Long wait times
        )
    
    @property
    def needs_scaling_down(self) -> bool:
        """Determine if system can reduce agents."""
        return (
            self.utilization_rate < 0.3 and  # Low utilization
            self.queue_size < 2 and  # Small queue
            self.idle_agents > 2  # Multiple idle agents
        )


class AgentTask:
    """Represents a task to be executed by an agent."""
    
    def __init__(self, task_id: str, task_type: str, payload: Dict[str, Any], 
                 priority: int = 0, timeout: float = 300.0):
        self.task_id = task_id
        self.task_type = task_type
        self.payload = payload
        self.priority = priority
        self.timeout = timeout
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
    
    @property
    def wait_time(self) -> float:
        """Time spent waiting in queue."""
        start_time = self.started_at or time.time()
        return start_time - self.created_at
    
    @property
    def execution_time(self) -> float:
        """Time spent executing."""
        if not self.started_at:
            return 0.0
        end_time = self.completed_at or time.time()
        return end_time - self.started_at
    
    @property
    def is_expired(self) -> bool:
        """Check if task has exceeded timeout."""
        return time.time() - self.created_at > self.timeout


class OptimizedAgent:
    """Optimized agent with performance monitoring and error handling."""
    
    def __init__(self, agent_id: str, agent_type: str, config: Dict[str, Any]):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.config = config
        self.metrics = AgentMetrics(agent_id=agent_id, status=AgentStatus.IDLE)
        self.current_task: Optional[AgentTask] = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"agent-{agent_id}")
        self._shutdown = False
    
    async def execute_task(self, task: AgentTask) -> Any:
        """Execute a task with performance monitoring."""
        if self._shutdown:
            raise RuntimeError(f"Agent {self.agent_id} is shutdown")
        
        self.current_task = task
        self.metrics.status = AgentStatus.BUSY
        task.started_at = time.time()
        
        try:
            logger.info(f"Agent {self.agent_id} starting task {task.task_id}")
            
            # Execute task in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor, 
                self._execute_task_sync, 
                task
            )
            
            task.completed_at = time.time()
            task.result = result
            
            # Update metrics
            execution_time = task.execution_time
            self.metrics.tasks_completed += 1
            
            # Update average task time using exponential moving average
            if self.metrics.avg_task_time == 0:
                self.metrics.avg_task_time = execution_time
            else:
                self.metrics.avg_task_time = (
                    self.metrics.avg_task_time * 0.8 + execution_time * 0.2
                )
            
            self.metrics.status = AgentStatus.IDLE
            self.metrics.last_activity = time.time()
            self.current_task = None
            
            logger.info(f"Agent {self.agent_id} completed task {task.task_id} in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            task.completed_at = time.time()
            task.error = str(e)
            
            self.metrics.tasks_failed += 1
            self.metrics.status = AgentStatus.FAILED
            self.current_task = None
            
            logger.error(f"Agent {self.agent_id} failed task {task.task_id}: {e}")
            raise
    
    def _execute_task_sync(self, task: AgentTask) -> Any:
        """Synchronous task execution (runs in thread pool)."""
        try:
            # Simulate different task types
            if task.task_type == "code_generation":
                return self._execute_code_generation(task)
            elif task.task_type == "research":
                return self._execute_research(task)
            elif task.task_type == "analysis":
                return self._execute_analysis(task)
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
                
        except Exception as e:
            logger.error(f"Task execution error: {e}")
            raise
    
    def _execute_code_generation(self, task: AgentTask) -> Dict[str, Any]:
        """Execute code generation task."""
        # Simulate code generation work
        time.sleep(task.payload.get("complexity", 1.0))  # Simulate processing time
        
        return {
            "code": f"# Generated code for {task.payload.get('description', 'task')}",
            "tests": f"# Generated tests for {task.task_id}",
            "documentation": f"# Documentation for {task.task_id}"
        }
    
    def _execute_research(self, task: AgentTask) -> Dict[str, Any]:
        """Execute research task."""
        # Simulate research work
        time.sleep(task.payload.get("depth", 2.0))  # Simulate research time
        
        return {
            "findings": f"Research findings for {task.payload.get('query', 'unknown')}",
            "sources": ["source1.com", "source2.com"],
            "summary": f"Summary of research for {task.task_id}"
        }
    
    def _execute_analysis(self, task: AgentTask) -> Dict[str, Any]:
        """Execute analysis task."""
        # Simulate analysis work
        time.sleep(task.payload.get("complexity", 1.5))  # Simulate analysis time
        
        return {
            "analysis": f"Analysis results for {task.payload.get('data', 'unknown')}",
            "insights": ["insight1", "insight2"],
            "recommendations": ["recommendation1", "recommendation2"]
        }
    
    def get_resource_usage(self) -> Dict[str, float]:
        """Get current resource usage for this agent."""
        try:
            process = psutil.Process()
            return {
                "cpu_percent": process.cpu_percent(),
                "memory_mb": process.memory_info().rss / 1024 / 1024,
                "threads": process.num_threads()
            }
        except Exception:
            return {"cpu_percent": 0.0, "memory_mb": 0.0, "threads": 1}
    
    def shutdown(self):
        """Shutdown the agent gracefully."""
        self._shutdown = True
        self.metrics.status = AgentStatus.TERMINATED
        self.executor.shutdown(wait=True)


class AgentCoordinationSystem:
    """Optimized agent coordination system with horizontal scaling."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.agents: Dict[str, OptimizedAgent] = {}
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.completed_tasks: Dict[str, AgentTask] = {}
        self.scaling_metrics = ScalingMetrics()
        
        # Configuration
        self.min_agents = self.config.get("min_agents", 2)
        self.max_agents = self.config.get("max_agents", 10)
        self.scale_up_threshold = self.config.get("scale_up_threshold", 0.8)
        self.scale_down_threshold = self.config.get("scale_down_threshold", 0.3)
        self.monitoring_interval = self.config.get("monitoring_interval", 5.0)
        
        # Performance tracking
        self.performance_history: List[Dict[str, Any]] = []
        self.start_time = time.time()
        
        # Background tasks
        self._monitoring_task: Optional[asyncio.Task] = None
        self._scaling_task: Optional[asyncio.Task] = None
        self._shutdown = False
    
    async def start(self):
        """Start the coordination system."""
        logger.info("Starting agent coordination system")
        
        # Create initial agents
        for i in range(self.min_agents):
            await self.create_agent(f"agent_{i}", "general")
        
        # Start background tasks
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._scaling_task = asyncio.create_task(self._scaling_loop())
        
        logger.info(f"Started with {len(self.agents)} agents")
    
    async def shutdown(self):
        """Shutdown the coordination system gracefully."""
        logger.info("Shutting down agent coordination system")
        self._shutdown = True
        
        # Cancel background tasks
        if self._monitoring_task:
            self._monitoring_task.cancel()
        if self._scaling_task:
            self._scaling_task.cancel()
        
        # Shutdown all agents
        for agent in self.agents.values():
            agent.shutdown()
        
        self.agents.clear()
        logger.info("Agent coordination system shutdown complete")
    
    async def create_agent(self, agent_id: str, agent_type: str) -> OptimizedAgent:
        """Create a new agent."""
        if agent_id in self.agents:
            raise ValueError(f"Agent {agent_id} already exists")
        
        agent_config = self.config.get("agent_config", {})
        agent = OptimizedAgent(agent_id, agent_type, agent_config)
        self.agents[agent_id] = agent
        
        logger.info(f"Created agent {agent_id} of type {agent_type}")
        return agent
    
    async def remove_agent(self, agent_id: str):
        """Remove an agent."""
        if agent_id not in self.agents:
            return
        
        agent = self.agents[agent_id]
        agent.shutdown()
        del self.agents[agent_id]
        
        logger.info(f"Removed agent {agent_id}")
    
    async def submit_task(self, task: AgentTask) -> str:
        """Submit a task for execution."""
        if task.is_expired:
            raise ValueError(f"Task {task.task_id} has already expired")
        
        # Priority queue uses negative priority for max-heap behavior
        await self.task_queue.put((-task.priority, task.created_at, task))
        
        logger.debug(f"Submitted task {task.task_id} with priority {task.priority}")
        return task.task_id
    
    async def execute_tasks_parallel(self, tasks: List[AgentTask]) -> List[Any]:
        """Execute multiple tasks in parallel."""
        if not tasks:
            return []
        
        logger.info(f"Executing {len(tasks)} tasks in parallel")
        
        # Submit all tasks
        task_ids = []
        for task in tasks:
            task_id = await self.submit_task(task)
            task_ids.append(task_id)
        
        # Wait for all tasks to complete
        results = []
        for task_id in task_ids:
            result = await self.wait_for_task(task_id)
            results.append(result)
        
        return results
    
    async def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """Wait for a specific task to complete."""
        start_time = time.time()
        
        while True:
            if task_id in self.completed_tasks:
                task = self.completed_tasks[task_id]
                if task.error:
                    raise RuntimeError(f"Task {task_id} failed: {task.error}")
                return task.result
            
            if timeout and (time.time() - start_time) > timeout:
                raise TimeoutError(f"Task {task_id} timed out after {timeout}s")
            
            await asyncio.sleep(0.1)
    
    async def _monitoring_loop(self):
        """Background monitoring loop."""
        while not self._shutdown:
            try:
                await self._update_metrics()
                await self._log_performance()
                await asyncio.sleep(self.monitoring_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(1.0)
    
    async def _scaling_loop(self):
        """Background scaling loop."""
        while not self._shutdown:
            try:
                await self._check_scaling_needs()
                await asyncio.sleep(self.monitoring_interval * 2)  # Less frequent than monitoring
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scaling loop error: {e}")
                await asyncio.sleep(1.0)
    
    async def _update_metrics(self):
        """Update system metrics."""
        # Count agent statuses
        total_agents = len(self.agents)
        active_agents = sum(1 for agent in self.agents.values() 
                          if agent.metrics.status == AgentStatus.BUSY)
        idle_agents = sum(1 for agent in self.agents.values() 
                         if agent.metrics.status == AgentStatus.IDLE)
        failed_agents = sum(1 for agent in self.agents.values() 
                           if agent.metrics.status == AgentStatus.FAILED)
        
        # Update scaling metrics
        self.scaling_metrics.total_agents = total_agents
        self.scaling_metrics.active_agents = active_agents
        self.scaling_metrics.idle_agents = idle_agents
        self.scaling_metrics.failed_agents = failed_agents
        self.scaling_metrics.queue_size = self.task_queue.qsize()
        
        # Update system resource usage
        try:
            self.scaling_metrics.system_cpu_usage = psutil.cpu_percent()
            self.scaling_metrics.system_memory_usage = psutil.virtual_memory().percent
        except Exception:
            pass
        
        # Calculate throughput
        completed_count = len(self.completed_tasks)
        elapsed_time = time.time() - self.start_time
        if elapsed_time > 0:
            self.scaling_metrics.throughput_per_second = completed_count / elapsed_time
        
        # Process tasks from queue
        await self._process_task_queue()
    
    async def _process_task_queue(self):
        """Process tasks from the queue."""
        # Find available agents
        available_agents = [
            agent for agent in self.agents.values()
            if agent.metrics.status == AgentStatus.IDLE and not agent._shutdown
        ]
        
        # Assign tasks to available agents
        for agent in available_agents:
            if self.task_queue.empty():
                break
            
            try:
                # Get next task (non-blocking)
                priority, created_at, task = self.task_queue.get_nowait()
                
                # Check if task has expired
                if task.is_expired:
                    logger.warning(f"Skipping expired task {task.task_id}")
                    continue
                
                # Execute task asynchronously
                asyncio.create_task(self._execute_task_with_agent(agent, task))
                
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.error(f"Error processing task queue: {e}")
    
    async def _execute_task_with_agent(self, agent: OptimizedAgent, task: AgentTask):
        """Execute a task with a specific agent."""
        try:
            result = await agent.execute_task(task)
            self.completed_tasks[task.task_id] = task
            
        except Exception as e:
            task.error = str(e)
            self.completed_tasks[task.task_id] = task
            logger.error(f"Task {task.task_id} failed with agent {agent.agent_id}: {e}")
    
    async def _check_scaling_needs(self):
        """Check if scaling up or down is needed."""
        if self.scaling_metrics.needs_scaling_up and len(self.agents) < self.max_agents:
            await self._scale_up()
        elif self.scaling_metrics.needs_scaling_down and len(self.agents) > self.min_agents:
            await self._scale_down()
    
    async def _scale_up(self):
        """Scale up by adding more agents."""
        new_agent_id = f"agent_{len(self.agents)}_{int(time.time())}"
        await self.create_agent(new_agent_id, "general")
        
        logger.info(f"Scaled up: added agent {new_agent_id} "
                   f"(total: {len(self.agents)}, utilization: {self.scaling_metrics.utilization_rate:.2f})")
    
    async def _scale_down(self):
        """Scale down by removing idle agents."""
        # Find the least efficient idle agent
        idle_agents = [
            agent for agent in self.agents.values()
            if agent.metrics.status == AgentStatus.IDLE
        ]
        
        if idle_agents:
            # Remove agent with lowest efficiency score
            agent_to_remove = min(idle_agents, key=lambda a: a.metrics.efficiency_score)
            await self.remove_agent(agent_to_remove.agent_id)
            
            logger.info(f"Scaled down: removed agent {agent_to_remove.agent_id} "
                       f"(total: {len(self.agents)}, utilization: {self.scaling_metrics.utilization_rate:.2f})")
    
    async def _log_performance(self):
        """Log current performance metrics."""
        performance_data = {
            "timestamp": time.time(),
            "agents": {
                "total": self.scaling_metrics.total_agents,
                "active": self.scaling_metrics.active_agents,
                "idle": self.scaling_metrics.idle_agents,
                "failed": self.scaling_metrics.failed_agents,
                "utilization": self.scaling_metrics.utilization_rate
            },
            "queue": {
                "size": self.scaling_metrics.queue_size,
                "avg_wait_time": self.scaling_metrics.avg_queue_wait_time
            },
            "system": {
                "cpu_usage": self.scaling_metrics.system_cpu_usage,
                "memory_usage": self.scaling_metrics.system_memory_usage,
                "throughput": self.scaling_metrics.throughput_per_second
            },
            "agent_metrics": {
                agent_id: {
                    "status": agent.metrics.status.value,
                    "tasks_completed": agent.metrics.tasks_completed,
                    "tasks_failed": agent.metrics.tasks_failed,
                    "success_rate": agent.metrics.success_rate,
                    "avg_task_time": agent.metrics.avg_task_time,
                    "efficiency_score": agent.metrics.efficiency_score
                }
                for agent_id, agent in self.agents.items()
            }
        }
        
        self.performance_history.append(performance_data)
        
        # Keep only last 100 entries
        if len(self.performance_history) > 100:
            self.performance_history = self.performance_history[-100:]
        
        logger.debug(f"Performance: {self.scaling_metrics.total_agents} agents, "
                    f"{self.scaling_metrics.utilization_rate:.1%} utilization, "
                    f"{self.scaling_metrics.queue_size} queued, "
                    f"{self.scaling_metrics.throughput_per_second:.2f} tasks/s")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report."""
        return {
            "current_metrics": {
                "agents": {
                    "total": self.scaling_metrics.total_agents,
                    "active": self.scaling_metrics.active_agents,
                    "idle": self.scaling_metrics.idle_agents,
                    "failed": self.scaling_metrics.failed_agents,
                    "utilization_rate": self.scaling_metrics.utilization_rate
                },
                "queue": {
                    "size": self.scaling_metrics.queue_size,
                    "avg_wait_time": self.scaling_metrics.avg_queue_wait_time
                },
                "system": {
                    "cpu_usage": self.scaling_metrics.system_cpu_usage,
                    "memory_usage": self.scaling_metrics.system_memory_usage,
                    "throughput_per_second": self.scaling_metrics.throughput_per_second
                }
            },
            "agent_details": {
                agent_id: {
                    "status": agent.metrics.status.value,
                    "tasks_completed": agent.metrics.tasks_completed,
                    "tasks_failed": agent.metrics.tasks_failed,
                    "success_rate": agent.metrics.success_rate,
                    "avg_task_time": agent.metrics.avg_task_time,
                    "efficiency_score": agent.metrics.efficiency_score,
                    "last_activity": agent.metrics.last_activity
                }
                for agent_id, agent in self.agents.items()
            },
            "performance_history": self.performance_history[-10:],  # Last 10 entries
            "uptime_seconds": time.time() - self.start_time,
            "total_tasks_completed": len(self.completed_tasks)
        }


# Example usage and testing
async def test_agent_scaling():
    """Test agent scaling functionality."""
    config = {
        "min_agents": 2,
        "max_agents": 5,
        "monitoring_interval": 1.0,
        "agent_config": {
            "timeout": 30.0
        }
    }
    
    coordination_system = AgentCoordinationSystem(config)
    
    try:
        await coordination_system.start()
        
        # Create test tasks
        tasks = []
        for i in range(10):
            task = AgentTask(
                task_id=f"test_task_{i}",
                task_type="code_generation",
                payload={"description": f"Generate code for feature {i}", "complexity": 1.0},
                priority=i % 3  # Varying priorities
            )
            tasks.append(task)
        
        # Execute tasks in parallel
        logger.info("Executing test tasks...")
        results = await coordination_system.execute_tasks_parallel(tasks)
        
        logger.info(f"Completed {len(results)} tasks")
        
        # Get performance report
        report = coordination_system.get_performance_report()
        logger.info(f"Performance report: {json.dumps(report, indent=2)}")
        
        # Wait a bit to see scaling in action
        await asyncio.sleep(5)
        
    finally:
        await coordination_system.shutdown()


if __name__ == "__main__":
    asyncio.run(test_agent_scaling())