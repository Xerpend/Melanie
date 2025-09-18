//! Enhanced caching system for RAG operations with performance optimization

use crate::config::CacheConfig;
use crate::error::{RagError, RagResult};
use crate::types::{Embedding, RetrievalResult};
use lru::LruCache;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, hash_map::DefaultHasher};
use std::hash::{Hash, Hasher};
use std::num::NonZeroUsize;
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tokio::sync::RwLock;
use tracing::{debug, info, warn};
use rayon::prelude::*;

/// Cache key type for fast lookups
type CacheKey = u64;

/// Enhanced cached item with metadata and performance tracking
#[derive(Debug, Clone)]
struct EnhancedCachedItem<T> {
    value: T,
    created_at: Instant,
    last_accessed: Instant,
    access_count: u64,
    ttl: Duration,
    size_bytes: usize,
    priority: CachePriority,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
enum CachePriority {
    Low = 1,
    Normal = 2,
    High = 3,
    Critical = 4,
}

impl<T> EnhancedCachedItem<T> {
    fn new(value: T, ttl: Duration, size_bytes: usize, priority: CachePriority) -> Self {
        let now = Instant::now();
        Self {
            value,
            created_at: now,
            last_accessed: now,
            access_count: 0,
            ttl,
            size_bytes,
            priority,
        }
    }
    
    fn is_expired(&self) -> bool {
        self.created_at.elapsed() > self.ttl
    }
    
    fn access(&mut self) -> &T {
        self.last_accessed = Instant::now();
        self.access_count += 1;
        &self.value
    }
    
    fn access_frequency(&self) -> f64 {
        let age_seconds = self.created_at.elapsed().as_secs_f64();
        if age_seconds == 0.0 {
            return 0.0;
        }
        self.access_count as f64 / age_seconds
    }
    
    fn cache_score(&self) -> f64 {
        let frequency = self.access_frequency();
        let recency = 1.0 / (1.0 + self.last_accessed.elapsed().as_secs_f64());
        let priority_weight = self.priority as u8 as f64 / 4.0;
        
        (frequency * 0.4) + (recency * 0.4) + (priority_weight * 0.2)
    }
}

/// Enhanced cache statistics with detailed metrics
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct EnhancedCacheStats {
    // Hit/miss statistics
    pub embedding_hits: u64,
    pub embedding_misses: u64,
    pub reranking_hits: u64,
    pub reranking_misses: u64,
    pub retrieval_hits: u64,
    pub retrieval_misses: u64,
    
    // Performance metrics
    pub avg_lookup_time_us: f64,
    pub avg_insert_time_us: f64,
    pub total_lookups: u64,
    pub total_inserts: u64,
    
    // Memory metrics
    pub total_size_bytes: usize,
    pub max_size_bytes: usize,
    pub evictions: u64,
    pub expired_items: u64,
    
    // Efficiency metrics
    pub cache_efficiency: f64,
    pub memory_efficiency: f64,
    pub hit_rate_trend: f64,
    
    // Timing
    pub last_cleanup: Option<SystemTime>,
    pub uptime_seconds: u64,
}

impl EnhancedCacheStats {
    pub fn embedding_hit_rate(&self) -> f64 {
        let total = self.embedding_hits + self.embedding_misses;
        if total == 0 { 0.0 } else { self.embedding_hits as f64 / total as f64 }
    }
    
    pub fn reranking_hit_rate(&self) -> f64 {
        let total = self.reranking_hits + self.reranking_misses;
        if total == 0 { 0.0 } else { self.reranking_hits as f64 / total as f64 }
    }
    
    pub fn retrieval_hit_rate(&self) -> f64 {
        let total = sel