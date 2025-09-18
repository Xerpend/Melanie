//! Configuration management for the RAG engine

use crate::types::ChunkingConfig;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

/// Main configuration for the RAG engine
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RagConfig {
    /// Chunking configuration
    pub chunking: ChunkingConfig,
    
    /// Vector store configuration
    pub vector_store: VectorStoreConfig,
    
    /// Embedding service configuration
    pub embedding: EmbeddingConfig,
    
    /// Reranking service configuration
    pub reranking: RerankingConfig,
    
    /// Cache configuration
    pub cache: CacheConfig,
    
    /// Performance configuration
    pub performance: PerformanceConfig,
}

impl Default for RagConfig {
    fn default() -> Self {
        Self {
            chunking: ChunkingConfig::default(),
            vector_store: VectorStoreConfig::default(),
            embedding: EmbeddingConfig::default(),
            reranking: RerankingConfig::default(),
            cache: CacheConfig::default(),
            performance: PerformanceConfig::default(),
        }
    }
}

/// Vector store configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VectorStoreConfig {
    /// Backend type (sled, faiss)
    pub backend: VectorStoreBackend,
    
    /// Database path for file-based backends
    pub db_path: PathBuf,
    
    /// Vector dimension
    pub dimension: usize,
    
    /// Index type for FAISS
    pub index_type: String,
    
    /// Number of clusters for IVF indices
    pub nlist: Option<usize>,
    
    /// Search parameter for IVF indices
    pub nprobe: Option<usize>,
}

impl Default for VectorStoreConfig {
    fn default() -> Self {
        Self {
            backend: VectorStoreBackend::Sled,
            db_path: PathBuf::from("./rag_data"),
            dimension: 1536, // OpenAI embedding dimension
            index_type: "Flat".to_string(),
            nlist: None,
            nprobe: None,
        }
    }
}

/// Vector store backend types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum VectorStoreBackend {
    /// Sled-based storage (default)
    Sled,
    /// FAISS-like in-memory storage (for demonstration)
    Faiss,
}

/// Embedding service configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmbeddingConfig {
    /// API endpoint for embedding service
    pub endpoint: String,
    
    /// API key for embedding service
    pub api_key: Option<String>,
    
    /// Model name
    pub model: String,
    
    /// Batch size for embedding requests
    pub batch_size: usize,
    
    /// Request timeout in seconds
    pub timeout: u64,
    
    /// Maximum retries
    pub max_retries: usize,
}

impl Default for EmbeddingConfig {
    fn default() -> Self {
        Self {
            endpoint: "python://melanie_embedding".to_string(),  // Use Python integration by default
            api_key: None,
            model: "nvidia/nv-embedqa-mistral-7b-v2".to_string(),
            batch_size: 100,
            timeout: 300,  // Longer timeout for Python integration
            max_retries: 3,
        }
    }
}

/// Reranking service configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RerankingConfig {
    /// API endpoint for reranking service
    pub endpoint: String,
    
    /// API key for reranking service
    pub api_key: Option<String>,
    
    /// Model name
    pub model: String,
    
    /// Reranking threshold (0.0 to 1.0)
    pub threshold: f32,
    
    /// Maximum number of candidates to rerank
    pub max_candidates: usize,
    
    /// Request timeout in seconds
    pub timeout: u64,
    
    /// Maximum retries
    pub max_retries: usize,
}

impl Default for RerankingConfig {
    fn default() -> Self {
        Self {
            endpoint: "python://melanie_reranking".to_string(),  // Use Python integration by default
            api_key: None,
            model: "nvidia/nv-rerankqa-mistral-4b-v3".to_string(),
            threshold: 0.7,
            max_candidates: 100,
            timeout: 300,  // Longer timeout for Python integration
            max_retries: 3,
        }
    }
}

/// Cache configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheConfig {
    /// Enable caching
    pub enabled: bool,
    
    /// Maximum cache size (number of entries)
    pub max_size: usize,
    
    /// Cache TTL in seconds
    pub ttl: u64,
    
    /// Cache embeddings
    pub cache_embeddings: bool,
    
    /// Cache reranking results
    pub cache_reranking: bool,
    
    /// Cache retrieval results
    pub cache_retrieval: bool,
}

impl Default for CacheConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            max_size: 10000,
            ttl: 3600, // 1 hour
            cache_embeddings: true,
            cache_reranking: true,
            cache_retrieval: true,
        }
    }
}

/// Performance configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceConfig {
    /// Number of parallel threads for processing
    pub num_threads: Option<usize>,
    
    /// Batch size for parallel operations
    pub batch_size: usize,
    
    /// Maximum memory usage in MB
    pub max_memory_mb: Option<usize>,
    
    /// Enable parallel chunking
    pub parallel_chunking: bool,
    
    /// Enable parallel embedding
    pub parallel_embedding: bool,
    
    /// Enable parallel vector operations
    pub parallel_vector_ops: bool,
}

impl Default for PerformanceConfig {
    fn default() -> Self {
        Self {
            num_threads: None, // Use system default
            batch_size: 100,
            max_memory_mb: None, // No limit
            parallel_chunking: true,
            parallel_embedding: true,
            parallel_vector_ops: true,
        }
    }
}

impl RagConfig {
    /// Load configuration from a file
    pub fn from_file<P: AsRef<std::path::Path>>(path: P) -> crate::error::RagResult<Self> {
        let content = std::fs::read_to_string(path)?;
        let config: RagConfig = serde_json::from_str(&content)?;
        Ok(config)
    }
    
    /// Save configuration to a file
    pub fn to_file<P: AsRef<std::path::Path>>(&self, path: P) -> crate::error::RagResult<()> {
        let content = serde_json::to_string_pretty(self)?;
        std::fs::write(path, content)?;
        Ok(())
    }
    
    /// Load configuration from environment variables
    pub fn from_env() -> Self {
        let mut config = RagConfig::default();
        
        // Override with environment variables if present
        if let Ok(chunk_size) = std::env::var("RAG_CHUNK_SIZE") {
            if let Ok(size) = chunk_size.parse() {
                config.chunking.chunk_size = size;
            }
        }
        
        if let Ok(overlap) = std::env::var("RAG_OVERLAP") {
            if let Ok(size) = overlap.parse() {
                config.chunking.overlap = size;
            }
        }
        
        if let Ok(db_path) = std::env::var("RAG_DB_PATH") {
            config.vector_store.db_path = PathBuf::from(db_path);
        }
        
        if let Ok(embedding_endpoint) = std::env::var("RAG_EMBEDDING_ENDPOINT") {
            config.embedding.endpoint = embedding_endpoint;
        }
        
        if let Ok(embedding_key) = std::env::var("RAG_EMBEDDING_API_KEY") {
            config.embedding.api_key = Some(embedding_key);
        }
        
        if let Ok(rerank_endpoint) = std::env::var("RAG_RERANK_ENDPOINT") {
            config.reranking.endpoint = rerank_endpoint;
        }
        
        if let Ok(rerank_key) = std::env::var("RAG_RERANK_API_KEY") {
            config.reranking.api_key = Some(rerank_key);
        }
        
        config
    }
    
    /// Validate the configuration
    pub fn validate(&self) -> crate::error::RagResult<()> {
        // Validate chunking config
        if self.chunking.chunk_size < self.chunking.min_chunk_size {
            return Err(crate::error::RagError::configuration(
                "Chunk size cannot be less than minimum chunk size"
            ));
        }
        
        if self.chunking.chunk_size > self.chunking.max_chunk_size {
            return Err(crate::error::RagError::configuration(
                "Chunk size cannot be greater than maximum chunk size"
            ));
        }
        
        if self.chunking.overlap >= self.chunking.chunk_size {
            return Err(crate::error::RagError::configuration(
                "Overlap cannot be greater than or equal to chunk size"
            ));
        }
        
        // Validate vector store config
        if self.vector_store.dimension == 0 {
            return Err(crate::error::RagError::configuration(
                "Vector dimension must be greater than 0"
            ));
        }
        
        // Validate reranking config
        if self.reranking.threshold < 0.0 || self.reranking.threshold > 1.0 {
            return Err(crate::error::RagError::configuration(
                "Reranking threshold must be between 0.0 and 1.0"
            ));
        }
        
        Ok(())
    }
}