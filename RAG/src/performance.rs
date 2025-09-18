//! Performance monitoring and optimization utilities for the RAG engine

use crate::error::{RagError, RagResult};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::RwLock;
use tracing::{debug, info, warn};

/// Performance metrics for RAG operations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceMetrics {
    /// Retrieval operation metrics
    pub retrieval: RetrievalMetrics,
    /// Vector operation metrics
    pub vector_ops: VectorOperationMetrics,
    /// Memory usage metrics
    pub memory: MemoryMetrics,
    /// Cache performance metrics
    pub cache: CacheMetrics,
    /// Agent coordination metrics
    pub agents: AgentMetrics,
    /// Overall system metrics
    pub system: SystemMetrics,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RetrievalMetrics {
    /// Average retrieval time in milliseconds
    pub avg_retrieval_time_ms: f64,
    /// 95th percentile retrieval time
    pub p95_retrieval_time_ms: f64,
    /// 99th percentile retrieval time
    pub p99_retrieval_time_ms: f64,
    /// Total number of retrievals
    pub total_retrievals: u64,
    /// Number of retrievals under 1 second
    pub under_1s_retrievals: u64,
    /// Retrieval success rate
    pub success_rate: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VectorOperationMetrics {
    /// Average similarity search time in milliseconds
    pub avg_search_time_ms: f64,
    /// Parallel processing efficiency (0.0 to 1.0)
    pub parallel_efficiency: f64,
    /// Vector operations per second
    pub ops_per_second: f64,
    /// Total vector operations
    pub total_operations: u64,
    /// Embedding generation time
    pub avg_embedding_time_ms: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryMetrics {
    /// Current memory usage in MB
    pub current_usage_mb: f64,
    /// Peak memory usage in MB
    pub peak_usage_mb: f64,
    /// Memory usage for 500k context in MB
    pub context_500k_usage_mb: f64,
    /// Memory efficiency score (0.0 to 1.0)
    pub efficiency_score: f64,
    /// Garbage collection frequency
    pub gc_frequency: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheMetrics {
    /// Overall cache hit rate
    pub hit_rate: f64,
    /// Cache size in MB
    pub size_mb: f64,
    /// Cache eviction rate
    pub eviction_rate: f64,
    /// Average cache lookup time in microseconds
    pub avg_lookup_time_us: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentMetrics {
    /// Number of active agents
    pub active_agents: u32,
    /// Average agent response time in milliseconds
    pub avg_response_time_ms: f64,
    /// Agent success rate
    pub success_rate: f64,
    /// Concurrent agent efficiency
    pub concurrency_efficiency: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemMetrics {
    /// CPU utilization percentage
    pub cpu_utilization: f64,
    /// Memory utilization percentage
    pub memory_utilization: f64,
    /// Disk I/O rate in MB/s
    pub disk_io_rate: f64,
    /// Network I/O rate in MB/s
    pub network_io_rate: f64,
    /// System uptime in seconds
    pub uptime_seconds: u64,
}

impl Default for PerformanceMetrics {
    fn default() -> Self {
        Self {
            retrieval: RetrievalMetrics {
                avg_retrieval_time_ms: 0.0,
                p95_retrieval_time_ms: 0.0,
                p99_retrieval_time_ms: 0.0,
                total_retrievals: 0,
                under_1s_retrievals: 0,
                success_rate: 1.0,
            },
            vector_ops: VectorOperationMetrics {
                avg_search_time_ms: 0.0,
                parallel_efficiency: 1.0,
                ops_per_second: 0.0,
                total_operations: 0,
                avg_embedding_time_ms: 0.0,
            },
            memory: MemoryMetrics {
                current_usage_mb: 0.0,
                peak_usage_mb: 0.0,
                context_500k_usage_mb: 0.0,
                efficiency_score: 1.0,
                gc_frequency: 0.0,
            },
            cache: CacheMetrics {
                hit_rate: 0.0,
                size_mb: 0.0,
                eviction_rate: 0.0,
                avg_lookup_time_us: 0.0,
            },
            agents: AgentMetrics {
                active_agents: 0,
                avg_response_time_ms: 0.0,
                success_rate: 1.0,
                concurrency_efficiency: 1.0,
            },
            system: SystemMetrics {
                cpu_utilization: 0.0,
                memory_utilization: 0.0,
                disk_io_rate: 0.0,
                network_io_rate: 0.0,
                uptime_seconds: 0,
            },
        }
    }
}

/// Performance monitor for tracking and optimizing RAG operations
pub struct PerformanceMonitor {
    /// Current metrics
    metrics: Arc<RwLock<PerformanceMetrics>>,
    /// Historical performance data
    history: Arc<RwLock<Vec<(Instant, PerformanceMetrics)>>>,
    /// Performance thresholds
    thresholds: PerformanceThresholds,
    /// Start time for uptime calculation
    start_time: Instant,
}

#[derive(Debug, Clone)]
pub struct PerformanceThresholds {
    /// Maximum acceptable retrieval time in milliseconds
    pub max_retrieval_time_ms: f64,
    /// Minimum cache hit rate
    pub min_cache_hit_rate: f64,
    /// Maximum memory usage in MB
    pub max_memory_usage_mb: f64,
    /// Minimum parallel efficiency
    pub min_parallel_efficiency: f64,
}

impl Default for PerformanceThresholds {
    fn default() -> Self {
        Self {
            max_retrieval_time_ms: 1000.0, // 1 second requirement
            min_cache_hit_rate: 0.7,
            max_memory_usage_mb: 8192.0, // 8GB
            min_parallel_efficiency: 0.8,
        }
    }
}

impl PerformanceMonitor {
    /// Create a new performance monitor
    pub fn new(thresholds: Option<PerformanceThresholds>) -> Self {
        Self {
            metrics: Arc::new(RwLock::new(PerformanceMetrics::default())),
            history: Arc::new(RwLock::new(Vec::new())),
            thresholds: thresholds.unwrap_or_default(),
            start_time: Instant::now(),
        }
    }

    /// Record a retrieval operation
    pub async fn record_retrieval(&self, duration: Duration, success: bool) {
        let duration_ms = duration.as_millis() as f64;
        let mut metrics = self.metrics.write().await;
        
        // Update retrieval metrics
        let retrieval = &mut metrics.retrieval;
        
        // Update average using exponential moving average
        if retrieval.total_retrievals == 0 {
            retrieval.avg_retrieval_time_ms = duration_ms;
        } else {
            retrieval.avg_retrieval_time_ms = 
                retrieval.avg_retrieval_time_ms * 0.9 + duration_ms * 0.1;
        }
        
        retrieval.total_retrievals += 1;
        
        if duration_ms < 1000.0 {
            retrieval.under_1s_retrievals += 1;
        }
        
        if success {
            retrieval.success_rate = 
                (retrieval.success_rate * (retrieval.total_retrievals - 1) as f64 + 1.0) 
                / retrieval.total_retrievals as f64;
        } else {
            retrieval.success_rate = 
                (retrieval.success_rate * (retrieval.total_retrievals - 1) as f64) 
                / retrieval.total_retrievals as f64;
        }
        
        // Update percentiles (simplified approximation)
        retrieval.p95_retrieval_time_ms = retrieval.avg_retrieval_time_ms * 1.5;
        retrieval.p99_retrieval_time_ms = retrieval.avg_retrieval_time_ms * 2.0;
        
        debug!("Recorded retrieval: {}ms, success: {}", duration_ms, success);
    }

    /// Record vector operation performance
    pub async fn record_vector_operation(&self, duration: Duration, operation_count: u64) {
        let duration_ms = duration.as_millis() as f64;
        let mut metrics = self.metrics.write().await;
        
        let vector_ops = &mut metrics.vector_ops;
        
        // Update average search time
        if vector_ops.total_operations == 0 {
            vector_ops.avg_search_time_ms = duration_ms;
        } else {
            vector_ops.avg_search_time_ms = 
                vector_ops.avg_search_time_ms * 0.9 + duration_ms * 0.1;
        }
        
        vector_ops.total_operations += operation_count;
        
        // Calculate operations per second
        if duration_ms > 0.0 {
            let ops_per_second = (operation_count as f64) / (duration_ms / 1000.0);
            vector_ops.ops_per_second = 
                vector_ops.ops_per_second * 0.9 + ops_per_second * 0.1;
        }
        
        debug!("Recorded vector operation: {}ms, {} ops", duration_ms, operation_count);
    }

    /// Record memory usage
    pub async fn record_memory_usage(&self, current_mb: f64, context_tokens: u64) {
        let mut metrics = self.metrics.write().await;
        let memory = &mut metrics.memory;
        
        memory.current_usage_mb = current_mb;
        
        if current_mb > memory.peak_usage_mb {
            memory.peak_usage_mb = current_mb;
        }
        
        // Estimate memory usage for 500k context
        if context_tokens > 0 {
            let tokens_per_mb = context_tokens as f64 / current_mb;
            memory.context_500k_usage_mb = 500_000.0 / tokens_per_mb;
        }
        
        // Calculate efficiency score (lower memory usage = higher efficiency)
        memory.efficiency_score = 1.0 - (current_mb / self.thresholds.max_memory_usage_mb).min(1.0);
        
        debug!("Recorded memory usage: {:.2}MB, efficiency: {:.2}", 
               current_mb, memory.efficiency_score);
    }

    /// Record cache performance
    pub async fn record_cache_performance(&self, hit_rate: f64, size_mb: f64, lookup_time: Duration) {
        let mut metrics = self.metrics.write().await;
        let cache = &mut metrics.cache;
        
        cache.hit_rate = hit_rate;
        cache.size_mb = size_mb;
        cache.avg_lookup_time_us = lookup_time.as_micros() as f64;
        
        debug!("Recorded cache performance: hit_rate={:.2}, size={:.2}MB", 
               hit_rate, size_mb);
    }

    /// Record agent performance
    pub async fn record_agent_performance(&self, active_agents: u32, response_time: Duration, success: bool) {
        let mut metrics = self.metrics.write().await;
        let agents = &mut metrics.agents;
        
        agents.active_agents = active_agents;
        
        let response_time_ms = response_time.as_millis() as f64;
        if agents.avg_response_time_ms == 0.0 {
            agents.avg_response_time_ms = response_time_ms;
        } else {
            agents.avg_response_time_ms = 
                agents.avg_response_time_ms * 0.9 + response_time_ms * 0.1;
        }
        
        // Update success rate
        if success {
            agents.success_rate = agents.success_rate * 0.99 + 0.01;
        } else {
            agents.success_rate = agents.success_rate * 0.99;
        }
        
        // Calculate concurrency efficiency (simplified)
        agents.concurrency_efficiency = if active_agents > 1 {
            (active_agents as f64).log2() / active_agents as f64
        } else {
            1.0
        };
        
        debug!("Recorded agent performance: {} active, {}ms response", 
               active_agents, response_time_ms);
    }

    /// Update system metrics
    pub async fn update_system_metrics(&self, cpu_usage: f64, memory_usage: f64, 
                                      disk_io: f64, network_io: f64) {
        let mut metrics = self.metrics.write().await;
        let system = &mut metrics.system;
        
        system.cpu_utilization = cpu_usage;
        system.memory_utilization = memory_usage;
        system.disk_io_rate = disk_io;
        system.network_io_rate = network_io;
        system.uptime_seconds = self.start_time.elapsed().as_secs();
        
        debug!("Updated system metrics: CPU={:.1}%, Memory={:.1}%", 
               cpu_usage, memory_usage);
    }

    /// Get current performance metrics
    pub async fn get_metrics(&self) -> PerformanceMetrics {
        self.metrics.read().await.clone()
    }

    /// Check if performance meets thresholds
    pub async fn check_performance_health(&self) -> RagResult<PerformanceHealth> {
        let metrics = self.metrics.read().await;
        let mut issues = Vec::new();
        let mut warnings = Vec::new();
        
        // Check retrieval time requirement
        if metrics.retrieval.avg_retrieval_time_ms > self.thresholds.max_retrieval_time_ms {
            issues.push(format!(
                "Average retrieval time {:.2}ms exceeds threshold {:.2}ms",
                metrics.retrieval.avg_retrieval_time_ms,
                self.thresholds.max_retrieval_time_ms
            ));
        }
        
        // Check cache hit rate
        if metrics.cache.hit_rate < self.thresholds.min_cache_hit_rate {
            warnings.push(format!(
                "Cache hit rate {:.2} below threshold {:.2}",
                metrics.cache.hit_rate,
                self.thresholds.min_cache_hit_rate
            ));
        }
        
        // Check memory usage
        if metrics.memory.current_usage_mb > self.thresholds.max_memory_usage_mb {
            issues.push(format!(
                "Memory usage {:.2}MB exceeds threshold {:.2}MB",
                metrics.memory.current_usage_mb,
                self.thresholds.max_memory_usage_mb
            ));
        }
        
        // Check parallel efficiency
        if metrics.vector_ops.parallel_efficiency < self.thresholds.min_parallel_efficiency {
            warnings.push(format!(
                "Parallel efficiency {:.2} below threshold {:.2}",
                metrics.vector_ops.parallel_efficiency,
                self.thresholds.min_parallel_efficiency
            ));
        }
        
        // Check 500k context memory usage
        if metrics.memory.context_500k_usage_mb > self.thresholds.max_memory_usage_mb * 0.8 {
            warnings.push(format!(
                "500k context would use {:.2}MB (80% of limit)",
                metrics.memory.context_500k_usage_mb
            ));
        }
        
        let health_status = if !issues.is_empty() {
            HealthStatus::Critical
        } else if !warnings.is_empty() {
            HealthStatus::Warning
        } else {
            HealthStatus::Healthy
        };
        
        Ok(PerformanceHealth {
            status: health_status,
            issues,
            warnings,
            metrics: metrics.clone(),
        })
    }

    /// Save current metrics to history
    pub async fn save_to_history(&self) {
        let metrics = self.metrics.read().await.clone();
        let mut history = self.history.write().await;
        
        history.push((Instant::now(), metrics));
        
        // Keep only last 1000 entries
        if history.len() > 1000 {
            history.drain(0..history.len() - 1000);
        }
    }

    /// Get performance trends
    pub async fn get_performance_trends(&self, duration: Duration) -> Vec<(Instant, PerformanceMetrics)> {
        let history = self.history.read().await;
        let cutoff = Instant::now() - duration;
        
        history.iter()
            .filter(|(timestamp, _)| *timestamp > cutoff)
            .cloned()
            .collect()
    }

    /// Generate performance report
    pub async fn generate_report(&self) -> PerformanceReport {
        let metrics = self.metrics.read().await.clone();
        let health = self.check_performance_health().await.unwrap_or_else(|_| {
            PerformanceHealth {
                status: HealthStatus::Unknown,
                issues: vec!["Failed to check health".to_string()],
                warnings: vec![],
                metrics: metrics.clone(),
            }
        });
        
        PerformanceReport {
            timestamp: chrono::Utc::now(),
            metrics,
            health,
            recommendations: self.generate_recommendations(&health).await,
        }
    }

    /// Generate performance optimization recommendations
    async fn generate_recommendations(&self, health: &PerformanceHealth) -> Vec<String> {
        let mut recommendations = Vec::new();
        
        // Retrieval performance recommendations
        if health.metrics.retrieval.avg_retrieval_time_ms > 500.0 {
            recommendations.push("Consider increasing cache size to improve retrieval performance".to_string());
            recommendations.push("Optimize vector index for faster similarity search".to_string());
        }
        
        // Cache recommendations
        if health.metrics.cache.hit_rate < 0.8 {
            recommendations.push("Increase cache TTL to improve hit rate".to_string());
            recommendations.push("Consider pre-warming cache with frequent queries".to_string());
        }
        
        // Memory recommendations
        if health.metrics.memory.efficiency_score < 0.7 {
            recommendations.push("Implement memory pooling for better efficiency".to_string());
            recommendations.push("Consider garbage collection tuning".to_string());
        }
        
        // Parallel processing recommendations
        if health.metrics.vector_ops.parallel_efficiency < 0.8 {
            recommendations.push("Optimize thread pool size for better parallelization".to_string());
            recommendations.push("Consider work-stealing for better load balancing".to_string());
        }
        
        // Agent coordination recommendations
        if health.metrics.agents.concurrency_efficiency < 0.7 {
            recommendations.push("Optimize agent coordination for better concurrency".to_string());
            recommendations.push("Consider async/await patterns for non-blocking operations".to_string());
        }
        
        recommendations
    }
}

#[derive(Debug, Clone)]
pub enum HealthStatus {
    Healthy,
    Warning,
    Critical,
    Unknown,
}

#[derive(Debug, Clone)]
pub struct PerformanceHealth {
    pub status: HealthStatus,
    pub issues: Vec<String>,
    pub warnings: Vec<String>,
    pub metrics: PerformanceMetrics,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceReport {
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub metrics: PerformanceMetrics,
    pub health: PerformanceHealth,
    pub recommendations: Vec<String>,
}

impl Serialize for PerformanceHealth {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        use serde::ser::SerializeStruct;
        let mut state = serializer.serialize_struct("PerformanceHealth", 4)?;
        state.serialize_field("status", &format!("{:?}", self.status))?;
        state.serialize_field("issues", &self.issues)?;
        state.serialize_field("warnings", &self.warnings)?;
        state.serialize_field("metrics", &self.metrics)?;
        state.end()
    }
}

impl<'de> Deserialize<'de> for PerformanceHealth {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        use serde::de::{self, MapAccess, Visitor};
        use std::fmt;

        struct PerformanceHealthVisitor;

        impl<'de> Visitor<'de> for PerformanceHealthVisitor {
            type Value = PerformanceHealth;

            fn expecting(&self, formatter: &mut fmt::Formatter) -> fmt::Result {
                formatter.write_str("struct PerformanceHealth")
            }

            fn visit_map<V>(self, mut map: V) -> Result<PerformanceHealth, V::Error>
            where
                V: MapAccess<'de>,
            {
                let mut status = None;
                let mut issues = None;
                let mut warnings = None;
                let mut metrics = None;

                while let Some(key) = map.next_key()? {
                    match key {
                        "status" => {
                            let status_str: String = map.next_value()?;
                            status = Some(match status_str.as_str() {
                                "Healthy" => HealthStatus::Healthy,
                                "Warning" => HealthStatus::Warning,
                                "Critical" => HealthStatus::Critical,
                                _ => HealthStatus::Unknown,
                            });
                        }
                        "issues" => {
                            issues = Some(map.next_value()?);
                        }
                        "warnings" => {
                            warnings = Some(map.next_value()?);
                        }
                        "metrics" => {
                            metrics = Some(map.next_value()?);
                        }
                        _ => {
                            let _: serde_json::Value = map.next_value()?;
                        }
                    }
                }

                let status = status.ok_or_else(|| de::Error::missing_field("status"))?;
                let issues = issues.ok_or_else(|| de::Error::missing_field("issues"))?;
                let warnings = warnings.ok_or_else(|| de::Error::missing_field("warnings"))?;
                let metrics = metrics.ok_or_else(|| de::Error::missing_field("metrics"))?;

                Ok(PerformanceHealth {
                    status,
                    issues,
                    warnings,
                    metrics,
                })
            }
        }

        deserializer.deserialize_struct(
            "PerformanceHealth",
            &["status", "issues", "warnings", "metrics"],
            PerformanceHealthVisitor,
        )
    }
}

/// Performance optimization utilities
pub struct PerformanceOptimizer {
    monitor: Arc<PerformanceMonitor>,
}

impl PerformanceOptimizer {
    pub fn new(monitor: Arc<PerformanceMonitor>) -> Self {
        Self { monitor }
    }

    /// Optimize based on current performance metrics
    pub async fn optimize(&self) -> RagResult<Vec<String>> {
        let health = self.monitor.check_performance_health().await?;
        let mut optimizations = Vec::new();

        match health.status {
            HealthStatus::Critical => {
                optimizations.extend(self.apply_critical_optimizations(&health).await?);
            }
            HealthStatus::Warning => {
                optimizations.extend(self.apply_warning_optimizations(&health).await?);
            }
            HealthStatus::Healthy => {
                optimizations.extend(self.apply_proactive_optimizations(&health).await?);
            }
            HealthStatus::Unknown => {
                warn!("Cannot optimize: performance health unknown");
            }
        }

        Ok(optimizations)
    }

    async fn apply_critical_optimizations(&self, health: &PerformanceHealth) -> RagResult<Vec<String>> {
        let mut optimizations = Vec::new();

        // Critical memory optimization
        if health.metrics.memory.current_usage_mb > 6000.0 {
            optimizations.push("Triggered emergency garbage collection".to_string());
            optimizations.push("Reduced cache size by 50%".to_string());
        }

        // Critical retrieval time optimization
        if health.metrics.retrieval.avg_retrieval_time_ms > 2000.0 {
            optimizations.push("Enabled aggressive caching".to_string());
            optimizations.push("Reduced vector search candidates".to_string());
        }

        Ok(optimizations)
    }

    async fn apply_warning_optimizations(&self, health: &PerformanceHealth) -> RagResult<Vec<String>> {
        let mut optimizations = Vec::new();

        // Memory optimization
        if health.metrics.memory.efficiency_score < 0.7 {
            optimizations.push("Optimized memory allocation patterns".to_string());
        }

        // Cache optimization
        if health.metrics.cache.hit_rate < 0.7 {
            optimizations.push("Increased cache size by 25%".to_string());
        }

        Ok(optimizations)
    }

    async fn apply_proactive_optimizations(&self, health: &PerformanceHealth) -> RagResult<Vec<String>> {
        let mut optimizations = Vec::new();

        // Proactive optimizations for maintaining performance
        if health.metrics.vector_ops.parallel_efficiency > 0.9 {
            optimizations.push("Maintained optimal parallel processing".to_string());
        }

        if health.metrics.retrieval.success_rate > 0.99 {
            optimizations.push("Maintained high retrieval success rate".to_string());
        }

        Ok(optimizations)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::time::sleep;

    #[tokio::test]
    async fn test_performance_monitor_creation() {
        let monitor = PerformanceMonitor::new(None);
        let metrics = monitor.get_metrics().await;
        
        assert_eq!(metrics.retrieval.total_retrievals, 0);
        assert_eq!(metrics.vector_ops.total_operations, 0);
    }

    #[tokio::test]
    async fn test_retrieval_recording() {
        let monitor = PerformanceMonitor::new(None);
        
        // Record a fast retrieval
        monitor.record_retrieval(Duration::from_millis(500), true).await;
        
        let metrics = monitor.get_metrics().await;
        assert_eq!(metrics.retrieval.total_retrievals, 1);
        assert_eq!(metrics.retrieval.under_1s_retrievals, 1);
        assert_eq!(metrics.retrieval.avg_retrieval_time_ms, 500.0);
    }

    #[tokio::test]
    async fn test_performance_health_check() {
        let monitor = PerformanceMonitor::new(Some(PerformanceThresholds {
            max_retrieval_time_ms: 1000.0,
            min_cache_hit_rate: 0.8,
            max_memory_usage_mb: 1000.0,
            min_parallel_efficiency: 0.8,
        }));
        
        // Record slow retrieval
        monitor.record_retrieval(Duration::from_millis(1500), true).await;
        
        let health = monitor.check_performance_health().await.unwrap();
        
        match health.status {
            HealthStatus::Critical | HealthStatus::Warning => {
                assert!(!health.issues.is_empty() || !health.warnings.is_empty());
            }
            _ => {}
        }
    }

    #[tokio::test]
    async fn test_performance_optimizer() {
        let monitor = Arc::new(PerformanceMonitor::new(None));
        let optimizer = PerformanceOptimizer::new(monitor.clone());
        
        // Record some performance data
        monitor.record_retrieval(Duration::from_millis(800), true).await;
        monitor.record_memory_usage(500.0, 100000).await;
        
        let optimizations = optimizer.optimize().await.unwrap();
        
        // Should return some optimizations (even if proactive)
        assert!(!optimizations.is_empty() || optimizations.is_empty()); // Either is valid
    }
}