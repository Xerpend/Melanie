//! Vector storage implementations for the RAG engine

use crate::cache::RagCache;
use crate::config::VectorStoreConfig;
use crate::error::{RagError, RagResult};
use crate::types::{Chunk, ChunkId, Embedding, RetrievalResult};
use async_trait::async_trait;
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use sled::Db;
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Instant;

/// Trait for vector storage backends
#[async_trait]
pub trait VectorStore: Send + Sync {
    /// Store a chunk with its embedding
    async fn store_chunk(&self, chunk: &Chunk) -> RagResult<()>;
    
    /// Store multiple chunks in batch
    async fn store_chunks(&self, chunks: &[Chunk]) -> RagResult<()>;
    
    /// Retrieve a chunk by ID
    async fn get_chunk(&self, id: ChunkId) -> RagResult<Option<Chunk>>;
    
    /// Search for similar vectors with configurable result count
    async fn search_similar(
        &self,
        query_embedding: &Embedding,
        top_k: usize,
    ) -> RagResult<Vec<(ChunkId, f32)>>;
    
    /// Advanced similarity search with filtering and caching
    async fn search_similar_advanced(
        &self,
        query_embedding: &Embedding,
        top_k: usize,
        min_score: Option<f32>,
        use_cache: bool,
    ) -> RagResult<Vec<RetrievalResult>>;
    
    /// Batch similarity search for multiple queries
    async fn batch_search_similar(
        &self,
        query_embeddings: &[Embedding],
        top_k: usize,
    ) -> RagResult<Vec<Vec<(ChunkId, f32)>>>;
    
    /// Delete a chunk
    async fn delete_chunk(&self, id: ChunkId) -> RagResult<()>;
    
    /// Delete multiple chunks in batch
    async fn delete_chunks(&self, ids: &[ChunkId]) -> RagResult<()>;
    
    /// Get total number of stored chunks
    async fn count(&self) -> RagResult<usize>;
    
    /// Get storage statistics
    async fn get_stats(&self) -> RagResult<VectorStoreStats>;
    
    /// Clear all data
    async fn clear(&self) -> RagResult<()>;
    
    /// Optimize the index (for backends that support it)
    async fn optimize(&self) -> RagResult<()>;
}

/// Vector store statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VectorStoreStats {
    pub total_chunks: usize,
    pub total_embeddings: usize,
    pub index_size_mb: f64,
    pub avg_search_time_ms: f64,
    pub cache_hit_rate: f64,
    pub last_optimization: Option<chrono::DateTime<chrono::Utc>>,
}

/// Sled-based vector store implementation
pub struct SledVectorStore {
    /// Sled database for chunk metadata
    db: Arc<Db>,
    /// In-memory index for fast similarity search
    index: Arc<tokio::sync::RwLock<VectorIndex>>,
    /// Configuration
    config: VectorStoreConfig,
    /// Cache for frequent queries
    cache: Option<Arc<RagCache>>,
    /// Performance statistics
    stats: Arc<tokio::sync::RwLock<VectorStoreStats>>,
}

/// In-memory vector index for fast similarity search
#[derive(Debug, Clone)]
struct VectorIndex {
    /// Mapping from chunk ID to embedding
    embeddings: HashMap<ChunkId, Embedding>,
    /// Mapping from chunk ID to metadata
    metadata: HashMap<ChunkId, ChunkMetadata>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ChunkMetadata {
    document_id: uuid::Uuid,
    content_length: usize,
    token_count: usize,
    created_at: chrono::DateTime<chrono::Utc>,
}

impl SledVectorStore {
    /// Create a new Sled vector store
    pub async fn new(config: VectorStoreConfig) -> RagResult<Self> {
        Self::new_with_cache(config, None).await
    }
    
    /// Create a new Sled vector store with cache
    pub async fn new_with_cache(config: VectorStoreConfig, cache: Option<Arc<RagCache>>) -> RagResult<Self> {
        // Create database directory if it doesn't exist
        if let Some(parent) = config.db_path.parent() {
            tokio::fs::create_dir_all(parent).await
                .map_err(|e| RagError::vector_store(format!("Failed to create db directory: {}", e)))?;
        }
        
        // Open Sled database
        let db = sled::open(&config.db_path)
            .map_err(|e| RagError::vector_store(format!("Failed to open database: {}", e)))?;
        
        let store = Self {
            db: Arc::new(db),
            index: Arc::new(tokio::sync::RwLock::new(VectorIndex {
                embeddings: HashMap::new(),
                metadata: HashMap::new(),
            })),
            config,
            cache,
            stats: Arc::new(tokio::sync::RwLock::new(VectorStoreStats {
                total_chunks: 0,
                total_embeddings: 0,
                index_size_mb: 0.0,
                avg_search_time_ms: 0.0,
                cache_hit_rate: 0.0,
                last_optimization: None,
            })),
        };
        
        // Load existing data into memory index
        store.load_index().await?;
        
        Ok(store)
    }
    
    /// Load existing data into the in-memory index
    async fn load_index(&self) -> RagResult<()> {
        let mut index = self.index.write().await;
        
        // Load chunks from database
        for result in self.db.iter() {
            let (key, value) = result
                .map_err(|e| RagError::vector_store(format!("Database iteration error: {}", e)))?;
            
            // Parse chunk ID from key
            let chunk_id_str = String::from_utf8(key.to_vec())
                .map_err(|e| RagError::vector_store(format!("Invalid key format: {}", e)))?;
            let chunk_id: ChunkId = chunk_id_str.parse()
                .map_err(|e| RagError::vector_store(format!("Invalid chunk ID: {}", e)))?;
            
            // Deserialize chunk
            let chunk: Chunk = serde_json::from_slice(&value)
                .map_err(|e| RagError::vector_store(format!("Failed to deserialize chunk: {}", e)))?;
            
            // Add to index if chunk has embedding
            if let Some(embedding) = &chunk.embedding {
                index.embeddings.insert(chunk_id, embedding.clone());
                index.metadata.insert(chunk_id, ChunkMetadata {
                    document_id: chunk.document_id,
                    content_length: chunk.content.len(),
                    token_count: chunk.token_count,
                    created_at: chunk.created_at,
                });
            }
        }
        
        Ok(())
    }
    
    /// Calculate cosine similarity between embeddings
    pub fn cosine_similarity(a: &Embedding, b: &Embedding) -> f32 {
        if a.len() != b.len() {
            return 0.0;
        }
        
        let dot_product: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
        let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
        let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
        
        if norm_a == 0.0 || norm_b == 0.0 {
            return 0.0;
        }
        
        dot_product / (norm_a * norm_b)
    }
    
    /// Parallel similarity calculation for multiple embeddings
    pub fn parallel_similarity_search(
        query_embedding: &Embedding,
        embeddings: &HashMap<ChunkId, Embedding>,
        top_k: usize,
        min_score: Option<f32>,
    ) -> Vec<(ChunkId, f32)> {
        let mut similarities: Vec<(ChunkId, f32)> = embeddings
            .par_iter()
            .map(|(chunk_id, embedding)| {
                let similarity = Self::cosine_similarity(query_embedding, embedding);
                (*chunk_id, similarity)
            })
            .filter(|(_, score)| {
                if let Some(min) = min_score {
                    *score >= min
                } else {
                    true
                }
            })
            .collect();
        
        // Sort by similarity (descending) and take top k
        similarities.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        similarities.truncate(top_k);
        
        similarities
    }
    
    /// Update statistics after search operation
    async fn update_search_stats(&self, search_time_ms: f64) {
        let mut stats = self.stats.write().await;
        
        // Update average search time using exponential moving average
        if stats.avg_search_time_ms == 0.0 {
            stats.avg_search_time_ms = search_time_ms;
        } else {
            stats.avg_search_time_ms = stats.avg_search_time_ms * 0.9 + search_time_ms * 0.1;
        }
        
        // Update cache hit rate if cache is available
        if let Some(cache) = &self.cache {
            let cache_stats = cache.get_stats().await;
            stats.cache_hit_rate = cache_stats.overall_hit_rate();
        }
    }
}

#[async_trait]
impl VectorStore for SledVectorStore {
    async fn store_chunk(&self, chunk: &Chunk) -> RagResult<()> {
        // Serialize chunk
        let chunk_data = serde_json::to_vec(chunk)
            .map_err(|e| RagError::vector_store(format!("Failed to serialize chunk: {}", e)))?;
        
        // Store in database
        let key = chunk.id.to_string();
        self.db.insert(key.as_bytes(), chunk_data)
            .map_err(|e| RagError::vector_store(format!("Failed to store chunk: {}", e)))?;
        
        // Update in-memory index if chunk has embedding
        if let Some(embedding) = &chunk.embedding {
            let mut index = self.index.write().await;
            index.embeddings.insert(chunk.id, embedding.clone());
            index.metadata.insert(chunk.id, ChunkMetadata {
                document_id: chunk.document_id,
                content_length: chunk.content.len(),
                token_count: chunk.token_count,
                created_at: chunk.created_at,
            });
        }
        
        Ok(())
    }
    
    async fn store_chunks(&self, chunks: &[Chunk]) -> RagResult<()> {
        if chunks.is_empty() {
            return Ok(());
        }
        
        // Prepare batch operations
        let mut batch_ops = Vec::new();
        let mut index_updates = Vec::new();
        
        for chunk in chunks {
            // Serialize chunk
            let chunk_data = serde_json::to_vec(chunk)
                .map_err(|e| RagError::vector_store(format!("Failed to serialize chunk: {}", e)))?;
            
            let key = chunk.id.to_string();
            batch_ops.push((key.as_bytes().to_vec(), chunk_data));
            
            // Prepare index update if chunk has embedding
            if let Some(embedding) = &chunk.embedding {
                index_updates.push((chunk.id, embedding.clone(), ChunkMetadata {
                    document_id: chunk.document_id,
                    content_length: chunk.content.len(),
                    token_count: chunk.token_count,
                    created_at: chunk.created_at,
                }));
            }
        }
        
        // Execute batch operations
        let mut batch = sled::Batch::default();
        for (key, value) in batch_ops {
            batch.insert(key, value);
        }
        
        self.db.apply_batch(batch)
            .map_err(|e| RagError::vector_store(format!("Failed to store batch: {}", e)))?;
        
        // Update in-memory index
        let mut index = self.index.write().await;
        for (chunk_id, embedding, metadata) in index_updates {
            index.embeddings.insert(chunk_id, embedding);
            index.metadata.insert(chunk_id, metadata);
        }
        
        Ok(())
    }
    
    async fn get_chunk(&self, id: ChunkId) -> RagResult<Option<Chunk>> {
        let key = id.to_string();
        
        match self.db.get(key.as_bytes()) {
            Ok(Some(data)) => {
                let chunk: Chunk = serde_json::from_slice(&data)
                    .map_err(|e| RagError::vector_store(format!("Failed to deserialize chunk: {}", e)))?;
                Ok(Some(chunk))
            }
            Ok(None) => Ok(None),
            Err(e) => Err(RagError::vector_store(format!("Failed to retrieve chunk: {}", e))),
        }
    }
    
    async fn search_similar(
        &self,
        query_embedding: &Embedding,
        top_k: usize,
    ) -> RagResult<Vec<(ChunkId, f32)>> {
        let start_time = Instant::now();
        let index = self.index.read().await;
        
        if index.embeddings.is_empty() {
            return Ok(Vec::new());
        }
        
        // Use parallel similarity search
        let similarities = Self::parallel_similarity_search(
            query_embedding,
            &index.embeddings,
            top_k,
            None,
        );
        
        // Update statistics
        let search_time_ms = start_time.elapsed().as_millis() as f64;
        drop(index); // Release read lock before updating stats
        self.update_search_stats(search_time_ms).await;
        
        Ok(similarities)
    }
    
    async fn search_similar_advanced(
        &self,
        query_embedding: &Embedding,
        top_k: usize,
        min_score: Option<f32>,
        use_cache: bool,
    ) -> RagResult<Vec<RetrievalResult>> {
        let start_time = Instant::now();
        
        // Check cache first if enabled
        if use_cache {
            if let Some(cache) = &self.cache {
                let query_key = format!("{:?}_{}__{:?}", query_embedding, top_k, min_score);
                if let Some(cached_results) = cache.get_retrieval(&query_key).await {
                    return Ok(cached_results);
                }
            }
        }
        
        let index = self.index.read().await;
        
        if index.embeddings.is_empty() {
            return Ok(Vec::new());
        }
        
        // Use parallel similarity search with filtering
        let similarities = Self::parallel_similarity_search(
            query_embedding,
            &index.embeddings,
            top_k,
            min_score,
        );
        
        // Convert to RetrievalResult and fetch chunks
        let mut results = Vec::new();
        for (chunk_id, similarity_score) in similarities {
            if let Ok(Some(chunk)) = self.get_chunk(chunk_id).await {
                let mut result = RetrievalResult::new(chunk, similarity_score);
                result.final_score = similarity_score;
                results.push(result);
            }
        }
        
        // Cache results if enabled
        if use_cache {
            if let Some(cache) = &self.cache {
                let query_key = format!("{:?}_{}__{:?}", query_embedding, top_k, min_score);
                let _ = cache.cache_retrieval(&query_key, &results).await;
            }
        }
        
        // Update statistics
        let search_time_ms = start_time.elapsed().as_millis() as f64;
        drop(index); // Release read lock before updating stats
        self.update_search_stats(search_time_ms).await;
        
        Ok(results)
    }
    
    async fn batch_search_similar(
        &self,
        query_embeddings: &[Embedding],
        top_k: usize,
    ) -> RagResult<Vec<Vec<(ChunkId, f32)>>> {
        let start_time = Instant::now();
        let index = self.index.read().await;
        
        if index.embeddings.is_empty() {
            return Ok(vec![Vec::new(); query_embeddings.len()]);
        }
        
        // Process queries in parallel
        let results: Vec<Vec<(ChunkId, f32)>> = query_embeddings
            .par_iter()
            .map(|query_embedding| {
                Self::parallel_similarity_search(
                    query_embedding,
                    &index.embeddings,
                    top_k,
                    None,
                )
            })
            .collect();
        
        // Update statistics
        let search_time_ms = start_time.elapsed().as_millis() as f64;
        drop(index); // Release read lock before updating stats
        self.update_search_stats(search_time_ms).await;
        
        Ok(results)
    }
    
    async fn delete_chunk(&self, id: ChunkId) -> RagResult<()> {
        let key = id.to_string();
        
        // Remove from database
        self.db.remove(key.as_bytes())
            .map_err(|e| RagError::vector_store(format!("Failed to delete chunk: {}", e)))?;
        
        // Remove from in-memory index
        let mut index = self.index.write().await;
        index.embeddings.remove(&id);
        index.metadata.remove(&id);
        
        // Update statistics
        let mut stats = self.stats.write().await;
        stats.total_chunks = stats.total_chunks.saturating_sub(1);
        if index.embeddings.len() < stats.total_embeddings {
            stats.total_embeddings = index.embeddings.len();
        }
        
        Ok(())
    }
    
    async fn delete_chunks(&self, ids: &[ChunkId]) -> RagResult<()> {
        if ids.is_empty() {
            return Ok(());
        }
        
        // Prepare batch operations
        let mut batch = sled::Batch::default();
        for id in ids {
            let key = id.to_string();
            batch.remove(key.as_bytes());
        }
        
        // Execute batch delete
        self.db.apply_batch(batch)
            .map_err(|e| RagError::vector_store(format!("Failed to delete batch: {}", e)))?;
        
        // Remove from in-memory index
        let mut index = self.index.write().await;
        for id in ids {
            index.embeddings.remove(id);
            index.metadata.remove(id);
        }
        
        // Update statistics
        let mut stats = self.stats.write().await;
        stats.total_chunks = stats.total_chunks.saturating_sub(ids.len());
        stats.total_embeddings = index.embeddings.len();
        
        Ok(())
    }
    
    async fn count(&self) -> RagResult<usize> {
        Ok(self.db.len())
    }
    
    async fn get_stats(&self) -> RagResult<VectorStoreStats> {
        let stats = self.stats.read().await;
        let index = self.index.read().await;
        
        // Calculate approximate index size in MB
        let embedding_count = index.embeddings.len();
        let avg_embedding_size = if embedding_count > 0 {
            index.embeddings.values().next().map(|e| e.len()).unwrap_or(0)
        } else {
            0
        };
        let index_size_mb = (embedding_count * avg_embedding_size * 4) as f64 / (1024.0 * 1024.0);
        
        Ok(VectorStoreStats {
            total_chunks: self.db.len(),
            total_embeddings: embedding_count,
            index_size_mb,
            avg_search_time_ms: stats.avg_search_time_ms,
            cache_hit_rate: stats.cache_hit_rate,
            last_optimization: stats.last_optimization,
        })
    }
    
    async fn clear(&self) -> RagResult<()> {
        // Clear database
        self.db.clear()
            .map_err(|e| RagError::vector_store(format!("Failed to clear database: {}", e)))?;
        
        // Clear in-memory index
        let mut index = self.index.write().await;
        index.embeddings.clear();
        index.metadata.clear();
        
        // Reset statistics
        let mut stats = self.stats.write().await;
        stats.total_chunks = 0;
        stats.total_embeddings = 0;
        stats.index_size_mb = 0.0;
        
        Ok(())
    }
    
    async fn optimize(&self) -> RagResult<()> {
        // For Sled, we can flush and compact the database
        self.db.flush_async().await
            .map_err(|e| RagError::vector_store(format!("Failed to flush database: {}", e)))?;
        
        // Update optimization timestamp
        let mut stats = self.stats.write().await;
        stats.last_optimization = Some(chrono::Utc::now());
        
        Ok(())
    }
}

/// In-memory FAISS-like vector store implementation
/// This is a simplified implementation for demonstration purposes
pub struct FaissVectorStore {
    /// In-memory storage for chunks
    chunks: Arc<tokio::sync::RwLock<HashMap<ChunkId, Chunk>>>,
    /// In-memory index for fast similarity search
    index: Arc<tokio::sync::RwLock<VectorIndex>>,
    /// Configuration
    config: VectorStoreConfig,
    /// Cache for frequent queries
    cache: Option<Arc<RagCache>>,
    /// Performance statistics
    stats: Arc<tokio::sync::RwLock<VectorStoreStats>>,
}

impl FaissVectorStore {
    /// Create a new FAISS-like vector store
    pub async fn new(config: VectorStoreConfig) -> RagResult<Self> {
        Self::new_with_cache(config, None).await
    }
    
    /// Create a new FAISS-like vector store with cache
    pub async fn new_with_cache(config: VectorStoreConfig, cache: Option<Arc<RagCache>>) -> RagResult<Self> {
        Ok(Self {
            chunks: Arc::new(tokio::sync::RwLock::new(HashMap::new())),
            index: Arc::new(tokio::sync::RwLock::new(VectorIndex {
                embeddings: HashMap::new(),
                metadata: HashMap::new(),
            })),
            config,
            cache,
            stats: Arc::new(tokio::sync::RwLock::new(VectorStoreStats {
                total_chunks: 0,
                total_embeddings: 0,
                index_size_mb: 0.0,
                avg_search_time_ms: 0.0,
                cache_hit_rate: 0.0,
                last_optimization: None,
            })),
        })
    }
    
    /// Update statistics after search operation
    async fn update_search_stats(&self, search_time_ms: f64) {
        let mut stats = self.stats.write().await;
        
        // Update average search time using exponential moving average
        if stats.avg_search_time_ms == 0.0 {
            stats.avg_search_time_ms = search_time_ms;
        } else {
            stats.avg_search_time_ms = stats.avg_search_time_ms * 0.9 + search_time_ms * 0.1;
        }
        
        // Update cache hit rate if cache is available
        if let Some(cache) = &self.cache {
            let cache_stats = cache.get_stats().await;
            stats.cache_hit_rate = cache_stats.overall_hit_rate();
        }
    }
}

#[async_trait]
impl VectorStore for FaissVectorStore {
    async fn store_chunk(&self, chunk: &Chunk) -> RagResult<()> {
        // Store chunk
        let mut chunks = self.chunks.write().await;
        chunks.insert(chunk.id, chunk.clone());
        
        // Update index if chunk has embedding
        if let Some(embedding) = &chunk.embedding {
            let mut index = self.index.write().await;
            index.embeddings.insert(chunk.id, embedding.clone());
            index.metadata.insert(chunk.id, ChunkMetadata {
                document_id: chunk.document_id,
                content_length: chunk.content.len(),
                token_count: chunk.token_count,
                created_at: chunk.created_at,
            });
        }
        
        // Update statistics
        let mut stats = self.stats.write().await;
        let index_read = self.index.read().await;
        stats.total_chunks = chunks.len();
        stats.total_embeddings = index_read.embeddings.len();
        
        Ok(())
    }
    
    async fn store_chunks(&self, chunks: &[Chunk]) -> RagResult<()> {
        if chunks.is_empty() {
            return Ok(());
        }
        
        let mut chunk_store = self.chunks.write().await;
        let mut index = self.index.write().await;
        
        for chunk in chunks {
            chunk_store.insert(chunk.id, chunk.clone());
            
            if let Some(embedding) = &chunk.embedding {
                index.embeddings.insert(chunk.id, embedding.clone());
                index.metadata.insert(chunk.id, ChunkMetadata {
                    document_id: chunk.document_id,
                    content_length: chunk.content.len(),
                    token_count: chunk.token_count,
                    created_at: chunk.created_at,
                });
            }
        }
        
        // Update statistics
        let mut stats = self.stats.write().await;
        stats.total_chunks = chunk_store.len();
        stats.total_embeddings = index.embeddings.len();
        
        Ok(())
    }
    
    async fn get_chunk(&self, id: ChunkId) -> RagResult<Option<Chunk>> {
        let chunks = self.chunks.read().await;
        Ok(chunks.get(&id).cloned())
    }
    
    async fn search_similar(
        &self,
        query_embedding: &Embedding,
        top_k: usize,
    ) -> RagResult<Vec<(ChunkId, f32)>> {
        let start_time = Instant::now();
        let index = self.index.read().await;
        
        if index.embeddings.is_empty() {
            return Ok(Vec::new());
        }
        
        // Use parallel similarity search
        let similarities = SledVectorStore::parallel_similarity_search(
            query_embedding,
            &index.embeddings,
            top_k,
            None,
        );
        
        // Update statistics
        let search_time_ms = start_time.elapsed().as_millis() as f64;
        drop(index);
        self.update_search_stats(search_time_ms).await;
        
        Ok(similarities)
    }
    
    async fn search_similar_advanced(
        &self,
        query_embedding: &Embedding,
        top_k: usize,
        min_score: Option<f32>,
        use_cache: bool,
    ) -> RagResult<Vec<RetrievalResult>> {
        let start_time = Instant::now();
        
        // Check cache first if enabled
        if use_cache {
            if let Some(cache) = &self.cache {
                let query_key = format!("{:?}_{}__{:?}", query_embedding, top_k, min_score);
                if let Some(cached_results) = cache.get_retrieval(&query_key).await {
                    return Ok(cached_results);
                }
            }
        }
        
        let index = self.index.read().await;
        
        if index.embeddings.is_empty() {
            return Ok(Vec::new());
        }
        
        // Use parallel similarity search with filtering
        let similarities = SledVectorStore::parallel_similarity_search(
            query_embedding,
            &index.embeddings,
            top_k,
            min_score,
        );
        
        // Convert to RetrievalResult and fetch chunks
        let mut results = Vec::new();
        for (chunk_id, similarity_score) in similarities {
            if let Ok(Some(chunk)) = self.get_chunk(chunk_id).await {
                let mut result = RetrievalResult::new(chunk, similarity_score);
                result.final_score = similarity_score;
                results.push(result);
            }
        }
        
        // Cache results if enabled
        if use_cache {
            if let Some(cache) = &self.cache {
                let query_key = format!("{:?}_{}__{:?}", query_embedding, top_k, min_score);
                let _ = cache.cache_retrieval(&query_key, &results).await;
            }
        }
        
        // Update statistics
        let search_time_ms = start_time.elapsed().as_millis() as f64;
        drop(index);
        self.update_search_stats(search_time_ms).await;
        
        Ok(results)
    }
    
    async fn batch_search_similar(
        &self,
        query_embeddings: &[Embedding],
        top_k: usize,
    ) -> RagResult<Vec<Vec<(ChunkId, f32)>>> {
        let start_time = Instant::now();
        let index = self.index.read().await;
        
        if index.embeddings.is_empty() {
            return Ok(vec![Vec::new(); query_embeddings.len()]);
        }
        
        // Process queries in parallel
        let results: Vec<Vec<(ChunkId, f32)>> = query_embeddings
            .par_iter()
            .map(|query_embedding| {
                SledVectorStore::parallel_similarity_search(
                    query_embedding,
                    &index.embeddings,
                    top_k,
                    None,
                )
            })
            .collect();
        
        // Update statistics
        let search_time_ms = start_time.elapsed().as_millis() as f64;
        drop(index);
        self.update_search_stats(search_time_ms).await;
        
        Ok(results)
    }
    
    async fn delete_chunk(&self, id: ChunkId) -> RagResult<()> {
        let mut chunks = self.chunks.write().await;
        let mut index = self.index.write().await;
        
        chunks.remove(&id);
        index.embeddings.remove(&id);
        index.metadata.remove(&id);
        
        // Update statistics
        let mut stats = self.stats.write().await;
        stats.total_chunks = chunks.len();
        stats.total_embeddings = index.embeddings.len();
        
        Ok(())
    }
    
    async fn delete_chunks(&self, ids: &[ChunkId]) -> RagResult<()> {
        if ids.is_empty() {
            return Ok(());
        }
        
        let mut chunks = self.chunks.write().await;
        let mut index = self.index.write().await;
        
        for id in ids {
            chunks.remove(id);
            index.embeddings.remove(id);
            index.metadata.remove(id);
        }
        
        // Update statistics
        let mut stats = self.stats.write().await;
        stats.total_chunks = chunks.len();
        stats.total_embeddings = index.embeddings.len();
        
        Ok(())
    }
    
    async fn count(&self) -> RagResult<usize> {
        let chunks = self.chunks.read().await;
        Ok(chunks.len())
    }
    
    async fn get_stats(&self) -> RagResult<VectorStoreStats> {
        let stats = self.stats.read().await;
        let index = self.index.read().await;
        
        // Calculate approximate index size in MB
        let embedding_count = index.embeddings.len();
        let avg_embedding_size = if embedding_count > 0 {
            index.embeddings.values().next().map(|e| e.len()).unwrap_or(0)
        } else {
            0
        };
        let index_size_mb = (embedding_count * avg_embedding_size * 4) as f64 / (1024.0 * 1024.0);
        
        Ok(VectorStoreStats {
            total_chunks: self.chunks.read().await.len(),
            total_embeddings: embedding_count,
            index_size_mb,
            avg_search_time_ms: stats.avg_search_time_ms,
            cache_hit_rate: stats.cache_hit_rate,
            last_optimization: stats.last_optimization,
        })
    }
    
    async fn clear(&self) -> RagResult<()> {
        let mut chunks = self.chunks.write().await;
        let mut index = self.index.write().await;
        
        chunks.clear();
        index.embeddings.clear();
        index.metadata.clear();
        
        // Reset statistics
        let mut stats = self.stats.write().await;
        stats.total_chunks = 0;
        stats.total_embeddings = 0;
        stats.index_size_mb = 0.0;
        
        Ok(())
    }
    
    async fn optimize(&self) -> RagResult<()> {
        // For in-memory store, optimization is a no-op
        // Update optimization timestamp
        let mut stats = self.stats.write().await;
        stats.last_optimization = Some(chrono::Utc::now());
        
        Ok(())
    }
}

/// Factory function to create vector store based on configuration
pub async fn create_vector_store(config: VectorStoreConfig) -> RagResult<Box<dyn VectorStore>> {
    match config.backend {
        crate::config::VectorStoreBackend::Sled => {
            let store = SledVectorStore::new(config).await?;
            Ok(Box::new(store))
        }
        crate::config::VectorStoreBackend::Faiss => {
            let store = FaissVectorStore::new(config).await?;
            Ok(Box::new(store))
        }
    }
}

/// Factory function to create vector store with cache
pub async fn create_vector_store_with_cache(
    config: VectorStoreConfig,
    cache: Option<Arc<RagCache>>,
) -> RagResult<Box<dyn VectorStore>> {
    match config.backend {
        crate::config::VectorStoreBackend::Sled => {
            let store = SledVectorStore::new_with_cache(config, cache).await?;
            Ok(Box::new(store))
        }
        crate::config::VectorStoreBackend::Faiss => {
            let store = FaissVectorStore::new_with_cache(config, cache).await?;
            Ok(Box::new(store))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cache::RagCache;
    use crate::config::CacheConfig;
    use crate::types::Chunk;
    use tempfile::TempDir;
    use uuid::Uuid;
    
    async fn create_test_sled_store() -> (SledVectorStore, TempDir) {
        let temp_dir = TempDir::new().unwrap();
        let config = VectorStoreConfig {
            backend: crate::config::VectorStoreBackend::Sled,
            db_path: temp_dir.path().to_path_buf(),
            ..Default::default()
        };
        let store = SledVectorStore::new(config).await.unwrap();
        (store, temp_dir)
    }
    
    async fn create_test_faiss_store() -> FaissVectorStore {
        let config = VectorStoreConfig {
            backend: crate::config::VectorStoreBackend::Faiss,
            ..Default::default()
        };
        FaissVectorStore::new(config).await.unwrap()
    }
    
    async fn create_test_store_with_cache() -> (Box<dyn VectorStore>, Arc<RagCache>) {
        let cache_config = CacheConfig::default();
        let cache = Arc::new(RagCache::new(cache_config).unwrap());
        
        let config = VectorStoreConfig {
            backend: crate::config::VectorStoreBackend::Faiss,
            ..Default::default()
        };
        
        let store = create_vector_store_with_cache(config, Some(cache.clone())).await.unwrap();
        (store, cache)
    }
    
    #[tokio::test]
    async fn test_sled_store_and_retrieve_chunk() {
        let (store, _temp_dir) = create_test_sled_store().await;
        
        let document_id = Uuid::new_v4();
        let mut chunk = Chunk::new(document_id, "test content".to_string(), 0, 12, 2);
        chunk.set_embedding(vec![1.0, 0.0, 0.0]);
        
        // Store chunk
        store.store_chunk(&chunk).await.unwrap();
        
        // Retrieve chunk
        let retrieved = store.get_chunk(chunk.id).await.unwrap();
        assert!(retrieved.is_some());
        
        let retrieved_chunk = retrieved.unwrap();
        assert_eq!(retrieved_chunk.id, chunk.id);
        assert_eq!(retrieved_chunk.content, chunk.content);
        assert_eq!(retrieved_chunk.embedding, chunk.embedding);
    }
    
    #[tokio::test]
    async fn test_faiss_store_and_retrieve_chunk() {
        let store = create_test_faiss_store().await;
        
        let document_id = Uuid::new_v4();
        let mut chunk = Chunk::new(document_id, "test content".to_string(), 0, 12, 2);
        chunk.set_embedding(vec![1.0, 0.0, 0.0]);
        
        // Store chunk
        store.store_chunk(&chunk).await.unwrap();
        
        // Retrieve chunk
        let retrieved = store.get_chunk(chunk.id).await.unwrap();
        assert!(retrieved.is_some());
        
        let retrieved_chunk = retrieved.unwrap();
        assert_eq!(retrieved_chunk.id, chunk.id);
        assert_eq!(retrieved_chunk.content, chunk.content);
        assert_eq!(retrieved_chunk.embedding, chunk.embedding);
    }
    
    #[tokio::test]
    async fn test_parallel_similarity_search() {
        let store = create_test_faiss_store().await;
        
        let document_id = Uuid::new_v4();
        
        // Create test chunks with embeddings
        let mut chunk1 = Chunk::new(document_id, "content 1".to_string(), 0, 9, 2);
        chunk1.set_embedding(vec![1.0, 0.0, 0.0]);
        
        let mut chunk2 = Chunk::new(document_id, "content 2".to_string(), 0, 9, 2);
        chunk2.set_embedding(vec![0.8, 0.6, 0.0]);
        
        let mut chunk3 = Chunk::new(document_id, "content 3".to_string(), 0, 9, 2);
        chunk3.set_embedding(vec![0.0, 1.0, 0.0]);
        
        // Store chunks
        store.store_chunks(&[chunk1.clone(), chunk2.clone(), chunk3.clone()]).await.unwrap();
        
        // Search for similar vectors
        let query_embedding = vec![1.0, 0.0, 0.0];
        let results = store.search_similar(&query_embedding, 2).await.unwrap();
        
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].0, chunk1.id); // Most similar should be first
        assert!(results[0].1 > results[1].1); // First should have higher similarity
    }
    
    #[tokio::test]
    async fn test_advanced_similarity_search() {
        let store = create_test_faiss_store().await;
        
        let document_id = Uuid::new_v4();
        
        // Create test chunks with embeddings
        let mut chunk1 = Chunk::new(document_id, "content 1".to_string(), 0, 9, 2);
        chunk1.set_embedding(vec![1.0, 0.0, 0.0]);
        
        let mut chunk2 = Chunk::new(document_id, "content 2".to_string(), 0, 9, 2);
        chunk2.set_embedding(vec![0.5, 0.0, 0.0]); // Lower similarity
        
        let mut chunk3 = Chunk::new(document_id, "content 3".to_string(), 0, 9, 2);
        chunk3.set_embedding(vec![0.0, 1.0, 0.0]); // Very different
        
        // Store chunks
        store.store_chunks(&[chunk1.clone(), chunk2.clone(), chunk3.clone()]).await.unwrap();
        
        // Search with minimum score threshold
        let query_embedding = vec![1.0, 0.0, 0.0];
        let results = store.search_similar_advanced(&query_embedding, 10, Some(0.8), false).await.unwrap();
        
        // Should have at least one result that meets the 0.8 threshold
        assert!(!results.is_empty());
        
        // Verify all results meet the threshold
        for result in &results {
            assert!(result.similarity_score >= 0.8);
        }
        
        // The highest scoring result should be chunk1 (perfect match)
        let chunk1_result = results.iter().find(|r| r.chunk.id == chunk1.id);
        assert!(chunk1_result.is_some());
        let chunk1_result = chunk1_result.unwrap();
        assert!(chunk1_result.similarity_score >= 0.99); // Should be very close to 1.0
    }
    
    #[tokio::test]
    async fn test_batch_search_similar() {
        let store = create_test_faiss_store().await;
        
        let document_id = Uuid::new_v4();
        
        // Create test chunks with embeddings
        let mut chunk1 = Chunk::new(document_id, "content 1".to_string(), 0, 9, 2);
        chunk1.set_embedding(vec![1.0, 0.0, 0.0]);
        
        let mut chunk2 = Chunk::new(document_id, "content 2".to_string(), 0, 9, 2);
        chunk2.set_embedding(vec![0.0, 1.0, 0.0]);
        
        // Store chunks
        store.store_chunks(&[chunk1.clone(), chunk2.clone()]).await.unwrap();
        
        // Batch search with multiple queries
        let query_embeddings = vec![
            vec![1.0, 0.0, 0.0], // Should match chunk1 better
            vec![0.0, 1.0, 0.0], // Should match chunk2 better
        ];
        
        let results = store.batch_search_similar(&query_embeddings, 1).await.unwrap();
        
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].len(), 1);
        assert_eq!(results[1].len(), 1);
        
        // First query should return chunk1 as most similar
        assert_eq!(results[0][0].0, chunk1.id);
        // Second query should return chunk2 as most similar
        assert_eq!(results[1][0].0, chunk2.id);
    }
    
    #[tokio::test]
    async fn test_batch_operations() {
        let store = create_test_faiss_store().await;
        
        let document_id = Uuid::new_v4();
        let mut chunks = Vec::new();
        
        for i in 0..10 {
            let mut chunk = Chunk::new(document_id, format!("content {}", i), 0, 9, 2);
            chunk.set_embedding(vec![i as f32 / 10.0, 0.0, 0.0]);
            chunks.push(chunk);
        }
        
        // Store batch
        store.store_chunks(&chunks).await.unwrap();
        
        // Verify count
        let count = store.count().await.unwrap();
        assert_eq!(count, 10);
        
        // Verify retrieval
        for chunk in &chunks {
            let retrieved = store.get_chunk(chunk.id).await.unwrap();
            assert!(retrieved.is_some());
        }
    }
    
    #[tokio::test]
    async fn test_delete_operations() {
        let store = create_test_faiss_store().await;
        
        let document_id = Uuid::new_v4();
        let mut chunks = Vec::new();
        
        for i in 0..5 {
            let mut chunk = Chunk::new(document_id, format!("content {}", i), 0, 9, 2);
            chunk.set_embedding(vec![i as f32 / 10.0, 0.0, 0.0]);
            chunks.push(chunk);
        }
        
        // Store chunks
        store.store_chunks(&chunks).await.unwrap();
        assert_eq!(store.count().await.unwrap(), 5);
        
        // Delete single chunk
        store.delete_chunk(chunks[0].id).await.unwrap();
        assert_eq!(store.count().await.unwrap(), 4);
        assert!(store.get_chunk(chunks[0].id).await.unwrap().is_none());
        
        // Delete multiple chunks
        let ids_to_delete = vec![chunks[1].id, chunks[2].id];
        store.delete_chunks(&ids_to_delete).await.unwrap();
        assert_eq!(store.count().await.unwrap(), 2);
        
        for id in ids_to_delete {
            assert!(store.get_chunk(id).await.unwrap().is_none());
        }
    }
    
    #[tokio::test]
    async fn test_statistics() {
        let store = create_test_faiss_store().await;
        
        let document_id = Uuid::new_v4();
        let mut chunk = Chunk::new(document_id, "test content".to_string(), 0, 12, 2);
        chunk.set_embedding(vec![1.0, 0.0, 0.0]);
        
        // Store chunk
        store.store_chunk(&chunk).await.unwrap();
        
        // Get statistics
        let stats = store.get_stats().await.unwrap();
        assert_eq!(stats.total_chunks, 1);
        assert_eq!(stats.total_embeddings, 1);
        assert!(stats.index_size_mb > 0.0);
        
        // Perform search to update search stats
        let query_embedding = vec![1.0, 0.0, 0.0];
        store.search_similar(&query_embedding, 1).await.unwrap();
        
        let updated_stats = store.get_stats().await.unwrap();
        assert!(updated_stats.avg_search_time_ms >= 0.0);
    }
    
    #[tokio::test]
    async fn test_caching_integration() {
        let (store, cache) = create_test_store_with_cache().await;
        
        let document_id = Uuid::new_v4();
        let mut chunk = Chunk::new(document_id, "test content".to_string(), 0, 12, 2);
        chunk.set_embedding(vec![1.0, 0.0, 0.0]);
        
        // Store chunk
        store.store_chunk(&chunk).await.unwrap();
        
        // First search (cache miss)
        let query_embedding = vec![1.0, 0.0, 0.0];
        let results1 = store.search_similar_advanced(&query_embedding, 1, None, true).await.unwrap();
        assert_eq!(results1.len(), 1);
        
        // Second search (should hit cache)
        let results2 = store.search_similar_advanced(&query_embedding, 1, None, true).await.unwrap();
        assert_eq!(results2.len(), 1);
        
        // Verify cache statistics
        let cache_stats = cache.get_stats().await;
        assert!(cache_stats.retrieval_hits > 0 || cache_stats.retrieval_misses > 0);
    }
    
    #[tokio::test]
    async fn test_optimization() {
        let store = create_test_faiss_store().await;
        
        // Optimize should complete without error
        store.optimize().await.unwrap();
        
        // Check that optimization timestamp was updated
        let stats = store.get_stats().await.unwrap();
        assert!(stats.last_optimization.is_some());
    }
    
    #[tokio::test]
    async fn test_clear_operations() {
        let store = create_test_faiss_store().await;
        
        let document_id = Uuid::new_v4();
        let mut chunk = Chunk::new(document_id, "test content".to_string(), 0, 12, 2);
        chunk.set_embedding(vec![1.0, 0.0, 0.0]);
        
        // Store chunk
        store.store_chunk(&chunk).await.unwrap();
        assert_eq!(store.count().await.unwrap(), 1);
        
        // Clear all data
        store.clear().await.unwrap();
        assert_eq!(store.count().await.unwrap(), 0);
        
        // Verify chunk is gone
        assert!(store.get_chunk(chunk.id).await.unwrap().is_none());
    }
    
    #[tokio::test]
    async fn test_factory_functions() {
        // Test Sled backend
        let sled_config = VectorStoreConfig {
            backend: crate::config::VectorStoreBackend::Sled,
            db_path: std::env::temp_dir().join("test_sled"),
            ..Default::default()
        };
        let _sled_store = create_vector_store(sled_config).await.unwrap();
        
        // Test FAISS backend
        let faiss_config = VectorStoreConfig {
            backend: crate::config::VectorStoreBackend::Faiss,
            ..Default::default()
        };
        let _faiss_store = create_vector_store(faiss_config).await.unwrap();
        
        // Test with cache
        let cache_config = CacheConfig::default();
        let cache = Arc::new(RagCache::new(cache_config).unwrap());
        
        let config_with_cache = VectorStoreConfig {
            backend: crate::config::VectorStoreBackend::Faiss,
            ..Default::default()
        };
        let _store_with_cache = create_vector_store_with_cache(config_with_cache, Some(cache)).await.unwrap();
    }
}