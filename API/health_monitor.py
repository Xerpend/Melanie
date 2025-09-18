"""
Health monitoring system for Melanie AI API

This module implements:
- Comprehensive health checks for all system components
- Performance monitoring and metrics collection
- Service dependency validation
- System resource monitoring
"""

import asyncio
import json
import logging
import os
import psutil
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ComponentHealth(BaseModel):
    """Health status for a system component."""
    name: str
    status: str = Field(..., pattern="^(healthy|degraded|unhealthy|unknown)$")
    message: str
    last_check: datetime
    response_time_ms: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


class SystemHealth(BaseModel):
    """Overall system health status."""
    status: str = Field(..., pattern="^(healthy|degraded|unhealthy)$")
    timestamp: datetime
    components: List[ComponentHealth]
    system_info: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    uptime_seconds: float


class HealthMonitor:
    """Comprehensive health monitoring system."""
    
    def __init__(self):
        self.start_time = time.time()
        self.component_checkers = {}
        self.performance_history = []
        self.max_history_size = 100
        
        # Register default component checkers
        self._register_default_checkers()
    
    def _register_default_checkers(self):
        """Register default health checkers for system components."""
        self.component_checkers = {
            "tailscale": self._check_tailscale_health,
            "database": self._check_database_health,
            "ai_models": self._check_ai_models_health,
            "rag_system": self._check_rag_health,
            "file_system": self._check_file_system_health,
            "memory": self._check_memory_health,
            "disk": self._check_disk_health,
            "network": self._check_network_health
        }
    
    async def get_system_health(self) -> SystemHealth:
        """
        Get comprehensive system health status.
        
        Returns:
            SystemHealth: Complete system health information
        """
        start_time = time.time()
        
        # Check all components
        components = []
        for name, checker in self.component_checkers.items():
            try:
                component_health = await checker()
                components.append(component_health)
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                components.append(ComponentHealth(
                    name=name,
                    status="unknown",
                    message=f"Health check failed: {str(e)}",
                    last_check=datetime.utcnow()
                ))
        
        # Determine overall system status
        overall_status = self._determine_overall_status(components)
        
        # Collect system information
        system_info = self._get_system_info()
        
        # Collect performance metrics
        performance_metrics = self._get_performance_metrics()
        
        # Calculate uptime
        uptime_seconds = time.time() - self.start_time
        
        # Record performance
        check_duration = (time.time() - start_time) * 1000
        self._record_performance("health_check", check_duration)
        
        return SystemHealth(
            status=overall_status,
            timestamp=datetime.utcnow(),
            components=components,
            system_info=system_info,
            performance_metrics=performance_metrics,
            uptime_seconds=uptime_seconds
        )
    
    def _determine_overall_status(self, components: List[ComponentHealth]) -> str:
        """Determine overall system status based on component health."""
        unhealthy_count = sum(1 for c in components if c.status == "unhealthy")
        degraded_count = sum(1 for c in components if c.status == "degraded")
        
        if unhealthy_count > 0:
            return "unhealthy"
        elif degraded_count > 0:
            return "degraded"
        else:
            return "healthy"
    
    async def _check_tailscale_health(self) -> ComponentHealth:
        """Check Tailscale network health."""
        start_time = time.time()
        
        try:
            # Import here to avoid circular imports
            from server import TailscaleDetector
            
            tailscale_ip = TailscaleDetector.get_tailscale_ip()
            is_available = TailscaleDetector.is_tailscale_available()
            
            response_time = (time.time() - start_time) * 1000
            
            if is_available and tailscale_ip:
                return ComponentHealth(
                    name="tailscale",
                    status="healthy",
                    message="Tailscale network is available and configured",
                    last_check=datetime.utcnow(),
                    response_time_ms=response_time,
                    details={
                        "tailscale_ip": tailscale_ip,
                        "interfaces_detected": True
                    }
                )
            else:
                return ComponentHealth(
                    name="tailscale",
                    status="unhealthy",
                    message="Tailscale network not available",
                    last_check=datetime.utcnow(),
                    response_time_ms=response_time,
                    details={
                        "tailscale_ip": tailscale_ip,
                        "interfaces_detected": False
                    }
                )
        
        except Exception as e:
            return ComponentHealth(
                name="tailscale",
                status="unknown",
                message=f"Tailscale check failed: {str(e)}",
                last_check=datetime.utcnow()
            )
    
    async def _check_database_health(self) -> ComponentHealth:
        """Check database/storage health."""
        start_time = time.time()
        
        try:
            # Check file storage directory
            storage_path = Path("file_storage")
            if storage_path.exists():
                # Check if we can write to storage
                test_file = storage_path / "health_check.tmp"
                test_file.write_text("health_check")
                test_file.unlink()
                
                response_time = (time.time() - start_time) * 1000
                
                return ComponentHealth(
                    name="database",
                    status="healthy",
                    message="File storage is accessible and writable",
                    last_check=datetime.utcnow(),
                    response_time_ms=response_time,
                    details={
                        "storage_path": str(storage_path),
                        "writable": True
                    }
                )
            else:
                return ComponentHealth(
                    name="database",
                    status="degraded",
                    message="File storage directory does not exist",
                    last_check=datetime.utcnow(),
                    details={
                        "storage_path": str(storage_path),
                        "exists": False
                    }
                )
        
        except Exception as e:
            return ComponentHealth(
                name="database",
                status="unhealthy",
                message=f"Database check failed: {str(e)}",
                last_check=datetime.utcnow()
            )
    
    async def _check_ai_models_health(self) -> ComponentHealth:
        """Check AI models availability."""
        start_time = time.time()
        
        try:
            # Check if model classes can be imported
            model_status = {}
            
            try:
                import sys
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'AI'))
                
                from melanie_three_model import MelanieThree
                model_status["Melanie-3"] = "available"
            except ImportError as e:
                model_status["Melanie-3"] = f"unavailable: {str(e)}"
            
            try:
                from melanie_three_light_model import MelanieThreeLight
                model_status["Melanie-3-light"] = "available"
            except ImportError as e:
                model_status["Melanie-3-light"] = f"unavailable: {str(e)}"
            
            try:
                from melanie_three_code_model import MelanieThreeCode
                model_status["Melanie-3-code"] = "available"
            except ImportError as e:
                model_status["Melanie-3-code"] = f"unavailable: {str(e)}"
            
            response_time = (time.time() - start_time) * 1000
            
            available_models = sum(1 for status in model_status.values() if status == "available")
            total_models = len(model_status)
            
            if available_models == total_models:
                status = "healthy"
                message = "All AI models are available"
            elif available_models > 0:
                status = "degraded"
                message = f"{available_models}/{total_models} AI models available"
            else:
                status = "unhealthy"
                message = "No AI models available"
            
            return ComponentHealth(
                name="ai_models",
                status=status,
                message=message,
                last_check=datetime.utcnow(),
                response_time_ms=response_time,
                details={
                    "models": model_status,
                    "available_count": available_models,
                    "total_count": total_models
                }
            )
        
        except Exception as e:
            return ComponentHealth(
                name="ai_models",
                status="unknown",
                message=f"AI models check failed: {str(e)}",
                last_check=datetime.utcnow()
            )
    
    async def _check_rag_health(self) -> ComponentHealth:
        """Check RAG system health."""
        start_time = time.time()
        
        try:
            # Check if RAG client can be imported and initialized
            try:
                import sys
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'AI'))
                from rag_integration_client import RagIntegrationClient
                
                # Try to create client (don't actually use it to avoid side effects)
                rag_available = True
                rag_error = None
            except ImportError as e:
                rag_available = False
                rag_error = str(e)
            
            # Check RAG data directory
            rag_data_path = Path("rag_data")
            rag_data_exists = rag_data_path.exists()
            
            response_time = (time.time() - start_time) * 1000
            
            if rag_available and rag_data_exists:
                status = "healthy"
                message = "RAG system is available and configured"
            elif rag_available:
                status = "degraded"
                message = "RAG system available but data directory missing"
            else:
                status = "unhealthy"
                message = f"RAG system unavailable: {rag_error}"
            
            return ComponentHealth(
                name="rag_system",
                status=status,
                message=message,
                last_check=datetime.utcnow(),
                response_time_ms=response_time,
                details={
                    "client_available": rag_available,
                    "data_directory_exists": rag_data_exists,
                    "data_path": str(rag_data_path),
                    "error": rag_error
                }
            )
        
        except Exception as e:
            return ComponentHealth(
                name="rag_system",
                status="unknown",
                message=f"RAG system check failed: {str(e)}",
                last_check=datetime.utcnow()
            )
    
    async def _check_file_system_health(self) -> ComponentHealth:
        """Check file system health."""
        start_time = time.time()
        
        try:
            # Check disk usage for current directory
            disk_usage = psutil.disk_usage('.')
            free_space_gb = disk_usage.free / (1024**3)
            total_space_gb = disk_usage.total / (1024**3)
            usage_percent = (disk_usage.used / disk_usage.total) * 100
            
            response_time = (time.time() - start_time) * 1000
            
            if usage_percent < 80:
                status = "healthy"
                message = f"File system healthy ({usage_percent:.1f}% used)"
            elif usage_percent < 90:
                status = "degraded"
                message = f"File system usage high ({usage_percent:.1f}% used)"
            else:
                status = "unhealthy"
                message = f"File system usage critical ({usage_percent:.1f}% used)"
            
            return ComponentHealth(
                name="file_system",
                status=status,
                message=message,
                last_check=datetime.utcnow(),
                response_time_ms=response_time,
                details={
                    "free_space_gb": round(free_space_gb, 2),
                    "total_space_gb": round(total_space_gb, 2),
                    "usage_percent": round(usage_percent, 1)
                }
            )
        
        except Exception as e:
            return ComponentHealth(
                name="file_system",
                status="unknown",
                message=f"File system check failed: {str(e)}",
                last_check=datetime.utcnow()
            )
    
    async def _check_memory_health(self) -> ComponentHealth:
        """Check memory usage health."""
        start_time = time.time()
        
        try:
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            available_gb = memory.available / (1024**3)
            total_gb = memory.total / (1024**3)
            
            response_time = (time.time() - start_time) * 1000
            
            if memory_percent < 80:
                status = "healthy"
                message = f"Memory usage normal ({memory_percent:.1f}% used)"
            elif memory_percent < 90:
                status = "degraded"
                message = f"Memory usage high ({memory_percent:.1f}% used)"
            else:
                status = "unhealthy"
                message = f"Memory usage critical ({memory_percent:.1f}% used)"
            
            return ComponentHealth(
                name="memory",
                status=status,
                message=message,
                last_check=datetime.utcnow(),
                response_time_ms=response_time,
                details={
                    "available_gb": round(available_gb, 2),
                    "total_gb": round(total_gb, 2),
                    "usage_percent": round(memory_percent, 1)
                }
            )
        
        except Exception as e:
            return ComponentHealth(
                name="memory",
                status="unknown",
                message=f"Memory check failed: {str(e)}",
                last_check=datetime.utcnow()
            )
    
    async def _check_disk_health(self) -> ComponentHealth:
        """Check disk I/O health."""
        start_time = time.time()
        
        try:
            # Get disk I/O statistics
            disk_io = psutil.disk_io_counters()
            
            response_time = (time.time() - start_time) * 1000
            
            if disk_io:
                return ComponentHealth(
                    name="disk",
                    status="healthy",
                    message="Disk I/O is functioning normally",
                    last_check=datetime.utcnow(),
                    response_time_ms=response_time,
                    details={
                        "read_bytes": disk_io.read_bytes,
                        "write_bytes": disk_io.write_bytes,
                        "read_count": disk_io.read_count,
                        "write_count": disk_io.write_count
                    }
                )
            else:
                return ComponentHealth(
                    name="disk",
                    status="degraded",
                    message="Disk I/O statistics not available",
                    last_check=datetime.utcnow(),
                    response_time_ms=response_time
                )
        
        except Exception as e:
            return ComponentHealth(
                name="disk",
                status="unknown",
                message=f"Disk check failed: {str(e)}",
                last_check=datetime.utcnow()
            )
    
    async def _check_network_health(self) -> ComponentHealth:
        """Check network connectivity health."""
        start_time = time.time()
        
        try:
            # Get network I/O statistics
            network_io = psutil.net_io_counters()
            
            # Get network interfaces
            interfaces = psutil.net_if_addrs()
            active_interfaces = len([name for name, addrs in interfaces.items() 
                                   if any(addr.family == 2 for addr in addrs)])
            
            response_time = (time.time() - start_time) * 1000
            
            if network_io and active_interfaces > 0:
                return ComponentHealth(
                    name="network",
                    status="healthy",
                    message=f"Network is functioning normally ({active_interfaces} interfaces)",
                    last_check=datetime.utcnow(),
                    response_time_ms=response_time,
                    details={
                        "bytes_sent": network_io.bytes_sent,
                        "bytes_recv": network_io.bytes_recv,
                        "packets_sent": network_io.packets_sent,
                        "packets_recv": network_io.packets_recv,
                        "active_interfaces": active_interfaces
                    }
                )
            else:
                return ComponentHealth(
                    name="network",
                    status="degraded",
                    message="Network statistics not available or no active interfaces",
                    last_check=datetime.utcnow(),
                    response_time_ms=response_time,
                    details={
                        "active_interfaces": active_interfaces
                    }
                )
        
        except Exception as e:
            return ComponentHealth(
                name="network",
                status="unknown",
                message=f"Network check failed: {str(e)}",
                last_check=datetime.utcnow()
            )
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        try:
            return {
                "platform": os.name,
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": psutil.cpu_percent(interval=1),
                "boot_time": psutil.boot_time(),
                "process_count": len(psutil.pids())
            }
        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            return {"error": str(e)}
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        try:
            # Calculate average response times from history
            if self.performance_history:
                recent_history = self.performance_history[-20:]  # Last 20 operations
                avg_response_time = sum(h["duration"] for h in recent_history) / len(recent_history)
                
                # Group by operation type
                operation_metrics = {}
                for record in recent_history:
                    op_type = record["operation"]
                    if op_type not in operation_metrics:
                        operation_metrics[op_type] = []
                    operation_metrics[op_type].append(record["duration"])
                
                # Calculate averages per operation
                for op_type, durations in operation_metrics.items():
                    operation_metrics[op_type] = {
                        "avg_ms": sum(durations) / len(durations),
                        "min_ms": min(durations),
                        "max_ms": max(durations),
                        "count": len(durations)
                    }
            else:
                avg_response_time = 0
                operation_metrics = {}
            
            return {
                "avg_response_time_ms": avg_response_time,
                "operation_metrics": operation_metrics,
                "history_size": len(self.performance_history)
            }
        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}")
            return {"error": str(e)}
    
    def _record_performance(self, operation: str, duration_ms: float):
        """Record performance data for monitoring."""
        self.performance_history.append({
            "operation": operation,
            "duration": duration_ms,
            "timestamp": time.time()
        })
        
        # Keep history size manageable
        if len(self.performance_history) > self.max_history_size:
            self.performance_history = self.performance_history[-self.max_history_size:]
    
    async def get_component_health(self, component_name: str) -> Optional[ComponentHealth]:
        """
        Get health status for a specific component.
        
        Args:
            component_name: Name of the component to check
            
        Returns:
            ComponentHealth or None if component not found
        """
        if component_name in self.component_checkers:
            try:
                return await self.component_checkers[component_name]()
            except Exception as e:
                logger.error(f"Health check failed for {component_name}: {e}")
                return ComponentHealth(
                    name=component_name,
                    status="unknown",
                    message=f"Health check failed: {str(e)}",
                    last_check=datetime.utcnow()
                )
        return None
    
    def get_available_components(self) -> List[str]:
        """Get list of available components for health checking."""
        return list(self.component_checkers.keys())


# Global health monitor instance
health_monitor = HealthMonitor()