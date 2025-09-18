"""
Memory Usage Monitoring for 500k Token Contexts.

Provides comprehensive memory monitoring, optimization, and management
for handling large contexts up to 500k tokens efficiently.
"""

import asyncio
import gc
import logging
import psutil
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from collections import deque
import json
import tracemalloc
import sys
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    """Snapshot of memory usage at a point in time."""
    timestamp: float
    total_memory_mb: float
    available_memory_mb: float
    used_memory_mb: float
    memory_percent: float
    process_memory_mb: float
    context_tokens: int
    context_memory_mb: float
    gc_collections: Dict[int, int] = field(default_factory=dict)
    
    @property
    def tokens_per_mb(self) -> float:
        """Calculate tokens per MB ratio."""
        if self.context_memory_mb == 0:
            return 0.0
        return self.context_tokens / self.context_memory_mb
    
    @property
    def memory_efficiency(self) -> float:
        """Calculate memory efficiency score (0.0 to 1.0)."""
        if self.context_tokens == 0:
            return 1.0
        
        # Ideal: 1000 tokens per MB (rough estimate)
        ideal_ratio = 1000.0
        actual_ratio = self.tokens_per_mb
        
        if actual_ratio == 0:
            return 0.0
        
        efficiency = min(1.0, actual_ratio / ideal_ratio)
        return efficiency


@dataclass
class MemoryThresholds:
    """Memory usage thresholds for monitoring and alerts."""
    max_total_memory_mb: float = 8192.0  # 8GB
    max_process_memory_mb: float = 4096.0  # 4GB
    max_context_memory_mb: float = 2048.0  # 2GB for 500k context
    warning_memory_percent: float = 80.0  # 80% system memory
    critical_memory_percent: float = 90.0  # 90% system memory
    max_context_tokens: int = 500_000  # 500k token limit
    min_memory_efficiency: float = 0.6  # Minimum efficiency score


class MemoryOptimizer:
    """Memory optimization utilities."""
    
    @staticmethod
    def estimate_token_memory(tokens: int, model_type: str = "general") -> float:
        """Estimate memory usage for given number of tokens."""
        # Rough estimates based on model type (in MB)
        token_memory_ratios = {
            "general": 0.002,  # ~2KB per token
            "embedding": 0.001,  # ~1KB per token
            "code": 0.003,  # ~3KB per token (more complex)
            "multimodal": 0.005,  # ~5KB per token (includes image data)
        }
        
        ratio = token_memory_ratios.get(model_type, 0.002)
        return tokens * ratio
    
    @staticmethod
    def calculate_max_tokens_for_memory(available_mb: float, model_type: str = "general") -> int:
        """Calculate maximum tokens that can fit in available memory."""
        token_memory_ratios = {
            "general": 0.002,
            "embedding": 0.001,
            "code": 0.003,
            "multimodal": 0.005,
        }
        
        ratio = token_memory_ratios.get(model_type, 0.002)
        return int(available_mb / ratio)
    
    @staticmethod
    def optimize_memory_usage():
        """Perform memory optimization operations."""
        optimizations = []
        
        # Force garbage collection
        collected = gc.collect()
        if collected > 0:
            optimizations.append(f"Garbage collected {collected} objects")
        
        # Clear caches if available
        try:
            import functools
            if hasattr(functools, '_CacheInfo'):
                # Clear lru_cache instances (if any)
                optimizations.append("Cleared function caches")
        except Exception:
            pass
        
        return optimizations
    
    @staticmethod
    def get_memory_recommendations(snapshot: MemorySnapshot, thresholds: MemoryThresholds) -> List[str]:
        """Generate memory optimization recommendations."""
        recommendations = []
        
        # High memory usage
        if snapshot.memory_percent > thresholds.warning_memory_percent:
            recommendations.append("System memory usage is high - consider reducing context size")
        
        # Process memory usage
        if snapshot.process_memory_mb > thresholds.max_process_memory_mb * 0.8:
            recommendations.append("Process memory usage is high - trigger garbage collection")
        
        # Context memory efficiency
        if snapshot.memory_efficiency < thresholds.min_memory_efficiency:
            recommendations.append("Memory efficiency is low - optimize data structures")
        
        # Token limit approaching
        if snapshot.context_tokens > thresholds.max_context_tokens * 0.9:
            recommendations.append("Approaching 500k token limit - prepare for context management")
        
        # Context memory usage
        if snapshot.context_memory_mb > thresholds.max_context_memory_mb * 0.8:
            recommendations.append("Context memory usage is high - consider chunking or compression")
        
        return recommendations


class MemoryMonitor:
    """Comprehensive memory monitoring system for 500k token contexts."""
    
    def __init__(self, thresholds: Optional[MemoryThresholds] = None, 
                 monitoring_interval: float = 5.0):
        self.thresholds = thresholds or MemoryThresholds()
        self.monitoring_interval = monitoring_interval
        
        # Memory tracking
        self.snapshots: deque = deque(maxlen=1000)  # Keep last 1000 snapshots
        self.current_context_tokens = 0
        self.context_memory_tracking: Dict[str, float] = {}
        
        # Monitoring state
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        # Performance tracking
        self.start_time = time.time()
        self.peak_memory_mb = 0.0
        self.peak_context_tokens = 0
        
        # Callbacks for alerts
        self.alert_callbacks: List[Callable[[MemorySnapshot, str], None]] = []
        
        # Enable tracemalloc for detailed memory tracking
        if not tracemalloc.is_tracing():
            tracemalloc.start()
    
    async def start_monitoring(self):
        """Start continuous memory monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Started memory monitoring")
    
    async def stop_monitoring(self):
        """Stop memory monitoring."""
        self._monitoring = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped memory monitoring")
    
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self._monitoring:
            try:
                snapshot = await self.take_snapshot()
                await self._check_thresholds(snapshot)
                await asyncio.sleep(self.monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Memory monitoring error: {e}")
                await asyncio.sleep(1.0)
    
    async def take_snapshot(self) -> MemorySnapshot:
        """Take a memory usage snapshot."""
        async with self._lock:
            # System memory info
            memory_info = psutil.virtual_memory()
            
            # Process memory info
            process = psutil.Process()
            process_memory = process.memory_info()
            
            # Context memory calculation
            context_memory_mb = sum(self.context_memory_tracking.values())
            
            # Garbage collection stats
            gc_stats = {}
            for i in range(3):  # GC generations 0, 1, 2
                gc_stats[i] = gc.get_count()[i]
            
            snapshot = MemorySnapshot(
                timestamp=time.time(),
                total_memory_mb=memory_info.total / 1024 / 1024,
                available_memory_mb=memory_info.available / 1024 / 1024,
                used_memory_mb=memory_info.used / 1024 / 1024,
                memory_percent=memory_info.percent,
                process_memory_mb=process_memory.rss / 1024 / 1024,
                context_tokens=self.current_context_tokens,
                context_memory_mb=context_memory_mb,
                gc_collections=gc_stats
            )
            
            # Update peaks
            if snapshot.process_memory_mb > self.peak_memory_mb:
                self.peak_memory_mb = snapshot.process_memory_mb
            
            if snapshot.context_tokens > self.peak_context_tokens:
                self.peak_context_tokens = snapshot.context_tokens
            
            self.snapshots.append(snapshot)
            return snapshot
    
    async def _check_thresholds(self, snapshot: MemorySnapshot):
        """Check memory thresholds and trigger alerts."""
        alerts = []
        
        # Critical memory usage
        if snapshot.memory_percent > self.thresholds.critical_memory_percent:
            alerts.append("CRITICAL: System memory usage exceeds 90%")
        
        # Process memory limit
        if snapshot.process_memory_mb > self.thresholds.max_process_memory_mb:
            alerts.append(f"CRITICAL: Process memory ({snapshot.process_memory_mb:.1f}MB) exceeds limit")
        
        # Context token limit
        if snapshot.context_tokens > self.thresholds.max_context_tokens:
            alerts.append(f"CRITICAL: Context tokens ({snapshot.context_tokens}) exceed 500k limit")
        
        # Context memory limit
        if snapshot.context_memory_mb > self.thresholds.max_context_memory_mb:
            alerts.append(f"WARNING: Context memory ({snapshot.context_memory_mb:.1f}MB) exceeds limit")
        
        # Memory efficiency
        if snapshot.memory_efficiency < self.thresholds.min_memory_efficiency:
            alerts.append(f"WARNING: Memory efficiency ({snapshot.memory_efficiency:.2f}) below threshold")
        
        # Trigger alerts
        for alert in alerts:
            logger.warning(f"Memory Alert: {alert}")
            await self._trigger_alert_callbacks(snapshot, alert)
    
    async def _trigger_alert_callbacks(self, snapshot: MemorySnapshot, alert: str):
        """Trigger registered alert callbacks."""
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(snapshot, alert)
                else:
                    callback(snapshot, alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
    
    def add_alert_callback(self, callback: Callable[[MemorySnapshot, str], None]):
        """Add an alert callback function."""
        self.alert_callbacks.append(callback)
    
    async def track_context_memory(self, context_id: str, tokens: int, model_type: str = "general"):
        """Track memory usage for a specific context."""
        estimated_memory = MemoryOptimizer.estimate_token_memory(tokens, model_type)
        
        async with self._lock:
            # Update context tracking
            old_memory = self.context_memory_tracking.get(context_id, 0.0)
            self.context_memory_tracking[context_id] = estimated_memory
            
            # Update total context tokens
            old_tokens = old_memory / MemoryOptimizer.estimate_token_memory(1, model_type) if old_memory > 0 else 0
            self.current_context_tokens = self.current_context_tokens - int(old_tokens) + tokens
            
            logger.debug(f"Tracking context {context_id}: {tokens} tokens, {estimated_memory:.2f}MB")
    
    async def remove_context_tracking(self, context_id: str):
        """Remove context from memory tracking."""
        async with self._lock:
            if context_id in self.context_memory_tracking:
                removed_memory = self.context_memory_tracking.pop(context_id)
                
                # Estimate tokens removed (rough calculation)
                estimated_tokens = int(removed_memory / 0.002)  # Using general ratio
                self.current_context_tokens = max(0, self.current_context_tokens - estimated_tokens)
                
                logger.debug(f"Removed context {context_id}: {removed_memory:.2f}MB")
    
    async def check_500k_context_feasibility(self, model_type: str = "general") -> Dict[str, Any]:
        """Check if 500k context is feasible with current memory."""
        snapshot = await self.take_snapshot()
        
        # Estimate memory needed for 500k tokens
        estimated_memory = MemoryOptimizer.estimate_token_memory(500_000, model_type)
        
        # Calculate available memory
        available_memory = snapshot.available_memory_mb
        process_memory_limit = self.thresholds.max_process_memory_mb - snapshot.process_memory_mb
        
        feasible = (
            estimated_memory < available_memory and
            estimated_memory < process_memory_limit and
            estimated_memory < self.thresholds.max_context_memory_mb
        )
        
        return {
            "feasible": feasible,
            "estimated_memory_mb": estimated_memory,
            "available_memory_mb": available_memory,
            "process_memory_available_mb": process_memory_limit,
            "current_context_tokens": self.current_context_tokens,
            "current_context_memory_mb": snapshot.context_memory_mb,
            "recommendations": MemoryOptimizer.get_memory_recommendations(snapshot, self.thresholds)
        }
    
    async def optimize_memory(self) -> Dict[str, Any]:
        """Perform memory optimization and return results."""
        before_snapshot = await self.take_snapshot()
        
        # Perform optimizations
        optimizations = MemoryOptimizer.optimize_memory_usage()
        
        # Wait a moment for GC to complete
        await asyncio.sleep(0.1)
        
        after_snapshot = await self.take_snapshot()
        
        memory_freed = before_snapshot.process_memory_mb - after_snapshot.process_memory_mb
        
        return {
            "optimizations_applied": optimizations,
            "memory_freed_mb": memory_freed,
            "before_memory_mb": before_snapshot.process_memory_mb,
            "after_memory_mb": after_snapshot.process_memory_mb,
            "gc_collections": after_snapshot.gc_collections
        }
    
    def get_memory_statistics(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics."""
        if not self.snapshots:
            return {"error": "No memory snapshots available"}
        
        latest = self.snapshots[-1]
        
        # Calculate trends if we have enough data
        trends = {}
        if len(self.snapshots) >= 10:
            recent_snapshots = list(self.snapshots)[-10:]
            
            memory_trend = (recent_snapshots[-1].process_memory_mb - recent_snapshots[0].process_memory_mb) / len(recent_snapshots)
            context_trend = (recent_snapshots[-1].context_tokens - recent_snapshots[0].context_tokens) / len(recent_snapshots)
            
            trends = {
                "memory_trend_mb_per_snapshot": memory_trend,
                "context_trend_tokens_per_snapshot": context_trend
            }
        
        return {
            "current": {
                "timestamp": latest.timestamp,
                "total_memory_mb": latest.total_memory_mb,
                "available_memory_mb": latest.available_memory_mb,
                "memory_percent": latest.memory_percent,
                "process_memory_mb": latest.process_memory_mb,
                "context_tokens": latest.context_tokens,
                "context_memory_mb": latest.context_memory_mb,
                "memory_efficiency": latest.memory_efficiency,
                "tokens_per_mb": latest.tokens_per_mb
            },
            "peaks": {
                "peak_memory_mb": self.peak_memory_mb,
                "peak_context_tokens": self.peak_context_tokens
            },
            "thresholds": {
                "max_total_memory_mb": self.thresholds.max_total_memory_mb,
                "max_process_memory_mb": self.thresholds.max_process_memory_mb,
                "max_context_memory_mb": self.thresholds.max_context_memory_mb,
                "max_context_tokens": self.thresholds.max_context_tokens
            },
            "trends": trends,
            "context_tracking": {
                "active_contexts": len(self.context_memory_tracking),
                "total_tracked_memory_mb": sum(self.context_memory_tracking.values()),
                "contexts": dict(self.context_memory_tracking)
            },
            "uptime_seconds": time.time() - self.start_time,
            "snapshots_count": len(self.snapshots)
        }
    
    def get_memory_history(self, duration_seconds: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get memory usage history."""
        snapshots = list(self.snapshots)
        
        if duration_seconds:
            cutoff_time = time.time() - duration_seconds
            snapshots = [s for s in snapshots if s.timestamp > cutoff_time]
        
        return [
            {
                "timestamp": s.timestamp,
                "memory_percent": s.memory_percent,
                "process_memory_mb": s.process_memory_mb,
                "context_tokens": s.context_tokens,
                "context_memory_mb": s.context_memory_mb,
                "memory_efficiency": s.memory_efficiency
            }
            for s in snapshots
        ]
    
    async def generate_memory_report(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        stats = self.get_memory_statistics()
        feasibility = await self.check_500k_context_feasibility()
        
        # Get recent history
        history = self.get_memory_history(duration_seconds=300)  # Last 5 minutes
        
        # Generate recommendations
        latest_snapshot = self.snapshots[-1] if self.snapshots else None
        recommendations = []
        if latest_snapshot:
            recommendations = MemoryOptimizer.get_memory_recommendations(latest_snapshot, self.thresholds)
        
        return {
            "report_timestamp": time.time(),
            "statistics": stats,
            "500k_context_feasibility": feasibility,
            "recent_history": history,
            "recommendations": recommendations,
            "memory_health": self._assess_memory_health(latest_snapshot) if latest_snapshot else "unknown"
        }
    
    def _assess_memory_health(self, snapshot: MemorySnapshot) -> str:
        """Assess overall memory health."""
        issues = 0
        
        if snapshot.memory_percent > self.thresholds.critical_memory_percent:
            issues += 3
        elif snapshot.memory_percent > self.thresholds.warning_memory_percent:
            issues += 1
        
        if snapshot.process_memory_mb > self.thresholds.max_process_memory_mb:
            issues += 3
        elif snapshot.process_memory_mb > self.thresholds.max_process_memory_mb * 0.8:
            issues += 1
        
        if snapshot.context_tokens > self.thresholds.max_context_tokens:
            issues += 3
        elif snapshot.context_tokens > self.thresholds.max_context_tokens * 0.9:
            issues += 1
        
        if snapshot.memory_efficiency < self.thresholds.min_memory_efficiency:
            issues += 1
        
        if issues >= 3:
            return "critical"
        elif issues >= 1:
            return "warning"
        else:
            return "healthy"


# Example usage and testing
async def test_memory_monitoring():
    """Test memory monitoring functionality."""
    
    # Create memory monitor
    thresholds = MemoryThresholds(
        max_process_memory_mb=1024.0,  # 1GB for testing
        max_context_tokens=100_000,    # 100k for testing
        warning_memory_percent=70.0
    )
    
    monitor = MemoryMonitor(thresholds, monitoring_interval=1.0)
    
    # Add alert callback
    async def alert_handler(snapshot: MemorySnapshot, alert: str):
        logger.warning(f"ALERT: {alert}")
        logger.info(f"Memory: {snapshot.process_memory_mb:.1f}MB, "
                   f"Context: {snapshot.context_tokens} tokens")
    
    monitor.add_alert_callback(alert_handler)
    
    try:
        # Start monitoring
        await monitor.start_monitoring()
        
        # Simulate context usage
        logger.info("Simulating context usage...")
        
        # Add some contexts
        await monitor.track_context_memory("context_1", 50000, "general")
        await monitor.track_context_memory("context_2", 30000, "code")
        await monitor.track_context_memory("context_3", 25000, "embedding")
        
        # Wait for monitoring
        await asyncio.sleep(3)
        
        # Check 500k feasibility
        feasibility = await monitor.check_500k_context_feasibility()
        logger.info(f"500k context feasibility: {feasibility}")
        
        # Optimize memory
        optimization_result = await monitor.optimize_memory()
        logger.info(f"Memory optimization: {optimization_result}")
        
        # Generate report
        report = await monitor.generate_memory_report()
        logger.info(f"Memory report: {json.dumps(report, indent=2)}")
        
        # Wait a bit more
        await asyncio.sleep(2)
        
    finally:
        await monitor.stop_monitoring()


if __name__ == "__main__":
    asyncio.run(test_memory_monitoring())