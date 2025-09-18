//! Caching layer for the RAG engine

use crate::config::CacheConfig;
use crate::error::{RagError, RagResult};
use crate::types::{Embedding, RetrievalResult};
use lru::LruCache;
use serde::{Deserialize, Serialize};
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::num::NonZeroUsize;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::RwLock;

/// Cache key type
type CacheKey = u64;

/// Cached item with TTL
#[derive(Debug, Clone)]
struct CachedItem<T> {
    value: T,
    created_at: Instant,
    ttl: Duration,
}

impl<T> CachedItem<T> {
    fn new(value: T, ttl: Duration) -> Self {
        Self {
            value,
            created_at: Instant::now(),
            ttl,
        }
    }
    
    fn is_expired(&self) -> bool {
        self.created_at.elapsed() > self.ttl
    }
}

/// Multi-purpose cache for RAG operations
pub struct RagCache {
    /// Embedding cache
    embeddings: Arc<RwLock<LruCache<CacheKey, CachedItem<Embedding>>>>,
    /// Reranking results cache
    reranking: Arc<RwLock<LruCache<CacheKey, CachedItem<Vec<f32>>>>>,
    /// Retrieval results cache
    retrieval: Arc<RwLock<LruCache<CacheKey, CachedItem<Vec<RetrievalResult>>>>>,
    /// Configuration
    config: CacheConfig,
    /// Cache statistics
    stats: Arc<RwLock<CacheStats>>,
}

/// Cache statistics
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct CacheStats {
    pub embedding_hits: u64,
    pub embedding_misses: u64,
    pub reranking_hits: u64,
    pub reranking_misses: u64,
    pub retrieval_hits: u64,
    pub retrieval_misses: u64,
    pub evictions: u64,
}

impl CacheStats {
    pub fn embedding_hit_rate(&self) -> f64 {
        let total = self.embedding_hits + self.embedding_misses;
        if total == 0 {
            0.0
        } else {
            self.embedding_hits as f64 / total as f64
        }
    }
    
    pub fn reranking_hit_rate(&self) -> f64 {
        let total = self.reranking_hits + self.reranking_misses;
        if total == 0 {
            0.0
        } else {
            self.reranking_hits as f64 / total as f64
        }
    }
    
    pub fn retrieval_hit_rate(&self) -> f64 {
        let total = self.retrieval_hits + self.retrieval_misses;
        if total == 0 {
            0.0
        } else {
            self.retrieval_hits as f64 / total as f64
        }
    }
    
    pub fn overall_hit_rate(&self) -> f64 {
        let total_hits = self.embedding_hits + self.reranking_hits + self.retrieval_hits;
        let total_requests = total_hits + self.embedding_misses + self.reranking_misses + self.retrieval_misses;
        
        if total_requests == 0 {
            0.0
        } else {
            total_hits as f64 / total_requests as f64
        }
    }
}

impl RagCache {
    /// Create a new RAG cache
    pub fn new(config: CacheConfig) -> RagResult<Self> {
        if !config.enabled {
            // Create minimal caches when disabled
            return Ok(Self {
                embeddings: Arc::new(RwLock::new(LruCache::new(NonZeroUsize::new(1).unwrap()))),
                reranking: Arc::new(RwLock::new(LruCache::new(NonZeroUsize::new(1).unwrap()))),
                retrieval: Arc::new(RwLock::new(LruCache::new(NonZeroUsize::new(1).unwrap()))),
                config,
                stats: Arc::new(RwLock::new(CacheStats::default())),
            });
        }
        
        let cache_size = NonZeroUsize::new(config.max_size)
            .ok_or_else(|| RagError::cache("Cache size must be greater than 0"))?;
        
        Ok(Self {
            embeddings: Arc::new(RwLock::new(LruCache::new(cache_size))),
            reranking: Arc::new(RwLock::new(LruCache::new(cache_size))),
            retrieval: Arc::new(RwLock::new(LruCache::new(cache_size))),
            config,
            stats: Arc::new(RwLock::new(CacheStats::default())),
        })
    }
    
    /// Generate cache key from text
    fn generate_key(text: &str) -> CacheKey {
        let mut hasher = DefaultHasher::new();
        text.hash(&mut hasher);
        hasher.finish()
    }
    
    /// Generate cache key from multiple texts
    fn generate_key_multi(texts: &[String]) -> CacheKey {
        let mut hasher = DefaultHasher::new();
        for text in texts {
            text.hash(&mut hasher);
        }
        hasher.finish()
    }
    
    /// Cache embedding for text
    pub async fn cache_embedding(&self, text: &str, embedding: Embedding) -> RagResult<()> {
        if !self.config.enabled || !self.config.cache_embeddings {
            return Ok(());
        }
        
        let key = Self::generate_key(text);
        let item = CachedItem::new(embedding, Duration::from_secs(self.config.ttl));
        
        let mut cache = self.embeddings.write().await;
        if cache.put(key, item).is_some() {
            // Item was evicted
            let mut stats = self.stats.write().await;
            stats.evictions += 1;
        }
        
        Ok(())
    }
    
    /// Get cached embedding for text
    pub async fn get_embedding(&self, text: &str) -> Option<Embedding> {
        if !self.config.enabled || !self.config.cache_embeddings {
            return None;
        }
        
        let key = Self::generate_key(text);
        let mut cache = self.embeddings.write().await;
        let mut stats = self.stats.write().await;
        
        match cache.get(&key) {
            Some(item) => {
                if item.is_expired() {
                    cache.pop(&key);
                    stats.embedding_misses += 1;
                    None
                } else {
                    stats.embedding_hits += 1;
                    Some(item.value.clone())
                }
            }
            None => {
                stats.embedding_misses += 1;
                None
            }
        }
    }
    
    /// Cache embeddings for multiple texts
    pub async fn cache_embeddings(&self, texts: &[String], embeddings: &[Embedding]) -> RagResult<()> {
        if !self.config.enabled || !self.config.cache_embeddings {
            return Ok(());
        }
        
        if texts.len() != embeddings.len() {
            return Err(RagError::cache("Text and embedding counts don't match"));
        }
        
        let ttl = Duration::from_secs(self.config.ttl);
        let mut cache = self.embeddings.write().await;
        let mut evictions = 0;
        
        for (text, embedding) in texts.iter().zip(embeddings.iter()) {
            let key = Self::generate_key(text);
            let item = CachedItem::new(embedding.clone(), ttl);
            
            if cache.put(key, item).is_some() {
                evictions += 1;
            }
        }
        
        if evictions > 0 {
            let mut stats = self.stats.write().await;
            stats.evictions += evictions;
        }
        
        Ok(())
    }
    
    /// Cache reranking results
    pub async fn cache_reranking(&self, query: &str, documents: &[String], scores: &[f32]) -> RagResult<()> {
        if !self.config.enabled || !self.config.cache_reranking {
            return Ok(());
        }
        
        let mut combined = vec![query.to_string()];
        combined.extend(documents.iter().cloned());
        
        let key = Self::generate_key_multi(&combined);
        let item = CachedItem::new(scores.to_vec(), Duration::from_secs(self.config.ttl));
        
        let mut cache = self.reranking.write().await;
        if cache.put(key, item).is_some() {
            let mut stats = self.stats.write().await;
            stats.evictions += 1;
        }
        
        Ok(())
    }
    
    /// Get cached reranking results
    pub async fn get_reranking(&self, query: &str, documents: &[String]) -> Option<Vec<f32>> {
        if !self.config.enabled || !self.config.cache_reranking {
            return None;
        }
        
        let mut combined = vec![query.to_string()];
        combined.extend(documents.iter().cloned());
        
        let key = Self::generate_key_multi(&combined);
        let mut cache = self.reranking.write().await;
        let mut stats = self.stats.write().await;
        
        match cache.get(&key) {
            Some(item) => {
                if item.is_expired() {
                    cache.pop(&key);
                    stats.reranking_misses += 1;
                    None
                } else {
                    stats.reranking_hits += 1;
                    Some(item.value.clone())
                }
            }
            None => {
                stats.reranking_misses += 1;
                None
            }
        }
    }
    
    /// Cache retrieval results
    pub async fn cache_retrieval(&self, query: &str, results: &[RetrievalResult]) -> RagResult<()> {
        if !self.config.enabled || !self.config.cache_retrieval {
            return Ok(());
        }
        
        let key = Self::generate_key(query);
        let item = CachedItem::new(results.to_vec(), Duration::from_secs(self.config.ttl));
        
        let mut cache = self.retrieval.write().await;
        if cache.put(key, item).is_some() {
            let mut stats = self.stats.write().await;
            stats.evictions += 1;
        }
        
        Ok(())
    }
    
    /// Get cached retrieval results
    pub async fn get_retrieval(&self, query: &str) -> Option<Vec<RetrievalResult>> {
        if !self.config.enabled || !self.config.cache_retrieval {
            return None;
        }
        
        let key = Self::generate_key(query);
        let mut cache = self.retrieval.write().await;
        let mut stats = self.stats.write().await;
        
        match cache.get(&key) {
            Some(item) => {
                if item.is_expired() {
                    cache.pop(&key);
                    stats.retrieval_misses += 1;
                    None
                } else {
                    stats.retrieval_hits += 1;
                    Some(item.value.clone())
                }
            }
            None => {
                stats.retrieval_misses += 1;
                None
            }
        }
    }
    
    /// Clear all caches
    pub async fn clear(&self) -> RagResult<()> {
        let mut embeddings = self.embeddings.write().await;
        let mut reranking = self.reranking.write().await;
        let mut retrieval = self.retrieval.write().await;
        
        embeddings.clear();
        reranking.clear();
        retrieval.clear();
        
        // Reset stats
        let mut stats = self.stats.write().await;
        *stats = CacheStats::default();
        
        Ok(())
    }
    
    /// Get cache statistics
    pub async fn get_stats(&self) -> CacheStats {
        self.stats.read().await.clone()
    }
    
    /// Get cache sizes
    pub async fn get_sizes(&self) -> (usize, usize, usize) {
        let embeddings = self.embeddings.read().await;
        let reranking = self.reranking.read().await;
        let retrieval = self.retrieval.read().await;
        
        (embeddings.len(), reranking.len(), retrieval.len())
    }
    
    /// Cleanup expired items
    pub async fn cleanup_expired(&self) -> RagResult<usize> {
        let mut total_removed = 0;
        
        // Cleanup embeddings
        {
            let mut cache = self.embeddings.write().await;
            let keys_to_remove: Vec<CacheKey> = cache
                .iter()
                .filter_map(|(key, item)| if item.is_expired() { Some(*key) } else { None })
                .collect();
            
            for key in keys_to_remove {
                cache.pop(&key);
                total_removed += 1;
            }
        }
        
        // Cleanup reranking
        {
            let mut cache = self.reranking.write().await;
            let keys_to_remove: Vec<CacheKey> = cache
                .iter()
                .filter_map(|(key, item)| if item.is_expired() { Some(*key) } else { None })
                .collect();
            
            for key in keys_to_remove {
                cache.pop(&key);
                total_removed += 1;
            }
        }
        
        // Cleanup retrieval
        {
            let mut cache = self.retrieval.write().await;
            let keys_to_remove: Vec<CacheKey> = cache
                .iter()
                .filter_map(|(key, item)| if item.is_expired() { Some(*key) } else { None })
                .collect();
            
            for key in keys_to_remove {
                cache.pop(&key);
                total_removed += 1;
            }
        }
        
        Ok(total_removed)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    
    #[tokio::test]
    async fn test_embedding_cache() {
        let config = CacheConfig::default();
        let cache = RagCache::new(config).unwrap();
        
        let text = "test text";
        let embedding = vec![1.0, 2.0, 3.0];
        
        // Cache should be empty initially
        assert!(cache.get_embedding(text).await.is_none());
        
        // Cache embedding
        cache.cache_embedding(text, embedding.clone()).await.unwrap();
        
        // Should now be cached
        let cached = cache.get_embedding(text).await;
        assert!(cached.is_some());
        assert_eq!(cached.unwrap(), embedding);
    }
    
    #[tokio::test]
    async fn test_reranking_cache() {
        let config = CacheConfig::default();
        let cache = RagCache::new(config).unwrap();
        
        let query = "test query";
        let documents = vec!["doc1".to_string(), "doc2".to_string()];
        let scores = vec![0.8, 0.6];
        
        // Cache should be empty initially
        assert!(cache.get_reranking(query, &documents).await.is_none());
        
        // Cache scores
        cache.cache_reranking(query, &documents, &scores).await.unwrap();
        
        // Should now be cached
        let cached = cache.get_reranking(query, &documents).await;
        assert!(cached.is_some());
        assert_eq!(cached.unwrap(), scores);
    }
    
    #[tokio::test]
    async fn test_cache_expiration() {
        let config = CacheConfig {
            ttl: 1, // 1 second TTL
            ..Default::default()
        };
        let cache = RagCache::new(config).unwrap();
        
        let text = "test text";
        let embedding = vec![1.0, 2.0, 3.0];
        
        // Cache embedding
        cache.cache_embedding(text, embedding.clone()).await.unwrap();
        
        // Should be cached immediately
        assert!(cache.get_embedding(text).await.is_some());
        
        // Wait for expiration
        tokio::time::sleep(Duration::from_secs(2)).await;
        
        // Should be expired now
        assert!(cache.get_embedding(text).await.is_none());
    }
    
    #[tokio::test]
    async fn test_cache_stats() {
        let config = CacheConfig::default();
        let cache = RagCache::new(config).unwrap();
        
        let text = "test text";
        let embedding = vec![1.0, 2.0, 3.0];
        
        // Initial stats should be zero
        let stats = cache.get_stats().await;
        assert_eq!(stats.embedding_hits, 0);
        assert_eq!(stats.embedding_misses, 0);
        
        // Miss
        cache.get_embedding(text).await;
        let stats = cache.get_stats().await;
        assert_eq!(stats.embedding_misses, 1);
        
        // Cache and hit
        cache.cache_embedding(text, embedding).await.unwrap();
        cache.get_embedding(text).await;
        let stats = cache.get_stats().await;
        assert_eq!(stats.embedding_hits, 1);
        assert_eq!(stats.embedding_misses, 1);
    }
    
    #[tokio::test]
    async fn test_disabled_cache() {
        let config = CacheConfig {
            enabled: false,
            ..Default::default()
        };
        let cache = RagCache::new(config).unwrap();
        
        let text = "test text";
        let embedding = vec![1.0, 2.0, 3.0];
        
        // Cache embedding (should be no-op)
        cache.cache_embedding(text, embedding).await.unwrap();
        
        // Should not be cached
        assert!(cache.get_embedding(text).await.is_none());
    }
}