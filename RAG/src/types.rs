//! Core data types for the RAG engine

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// Unique identifier for documents
pub type DocumentId = Uuid;

/// Unique identifier for chunks
pub type ChunkId = Uuid;

/// Vector embedding type
pub type Embedding = Vec<f32>;

/// Retrieval mode for different use cases
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RetrievalMode {
    /// General queries - top 20 chunks, 3k-5k tokens
    General,
    /// Research queries - top 100 chunks, 15k-25k tokens
    Research,
}

impl RetrievalMode {
    /// Get the maximum number of chunks to return for this mode
    pub fn max_chunks(&self) -> usize {
        match self {
            RetrievalMode::General => 20,
            RetrievalMode::Research => 100,
        }
    }
    
    /// Get the target token range for this mode
    pub fn token_range(&self) -> (usize, usize) {
        match self {
            RetrievalMode::General => (3000, 5000),
            RetrievalMode::Research => (15000, 25000),
        }
    }
}

/// A document in the RAG system
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Document {
    /// Unique document identifier
    pub id: DocumentId,
    /// Original document content
    pub content: String,
    /// Document metadata
    pub metadata: HashMap<String, String>,
    /// List of chunk IDs belonging to this document
    pub chunk_ids: Vec<ChunkId>,
    /// When the document was created
    pub created_at: DateTime<Utc>,
    /// When the document was last updated
    pub updated_at: DateTime<Utc>,
}

impl Document {
    /// Create a new document
    pub fn new(content: String, metadata: HashMap<String, String>) -> Self {
        let now = Utc::now();
        Self {
            id: Uuid::new_v4(),
            content,
            metadata,
            chunk_ids: Vec::new(),
            created_at: now,
            updated_at: now,
        }
    }
    
    /// Add a chunk ID to this document
    pub fn add_chunk(&mut self, chunk_id: ChunkId) {
        self.chunk_ids.push(chunk_id);
        self.updated_at = Utc::now();
    }
}

/// A text chunk with embedding and metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Chunk {
    /// Unique chunk identifier
    pub id: ChunkId,
    /// Parent document ID
    pub document_id: DocumentId,
    /// Chunk text content
    pub content: String,
    /// Vector embedding of the content
    pub embedding: Option<Embedding>,
    /// Start position in the original document
    pub start_offset: usize,
    /// End position in the original document
    pub end_offset: usize,
    /// Number of tokens in this chunk
    pub token_count: usize,
    /// Chunk metadata
    pub metadata: HashMap<String, String>,
    /// When the chunk was created
    pub created_at: DateTime<Utc>,
}

impl Chunk {
    /// Create a new chunk
    pub fn new(
        document_id: DocumentId,
        content: String,
        start_offset: usize,
        end_offset: usize,
        token_count: usize,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            document_id,
            content,
            embedding: None,
            start_offset,
            end_offset,
            token_count,
            metadata: HashMap::new(),
            created_at: Utc::now(),
        }
    }
    
    /// Set the embedding for this chunk
    pub fn set_embedding(&mut self, embedding: Embedding) {
        self.embedding = Some(embedding);
    }
    
    /// Check if this chunk has an embedding
    pub fn has_embedding(&self) -> bool {
        self.embedding.is_some()
    }
}

/// Result of a retrieval operation with similarity score
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RetrievalResult {
    /// The retrieved chunk
    pub chunk: Chunk,
    /// Similarity score (0.0 to 1.0)
    pub similarity_score: f32,
    /// Reranking score (optional, 0.0 to 1.0)
    pub rerank_score: Option<f32>,
    /// Final combined score
    pub final_score: f32,
}

impl RetrievalResult {
    /// Create a new retrieval result
    pub fn new(chunk: Chunk, similarity_score: f32) -> Self {
        Self {
            chunk,
            similarity_score,
            rerank_score: None,
            final_score: similarity_score,
        }
    }
    
    /// Set the reranking score and update final score
    pub fn set_rerank_score(&mut self, rerank_score: f32) {
        self.rerank_score = Some(rerank_score);
        // Combine similarity and rerank scores (weighted average)
        self.final_score = (self.similarity_score * 0.3) + (rerank_score * 0.7);
    }
    
    /// Check if this result meets the quality threshold
    pub fn meets_threshold(&self, threshold: f32) -> bool {
        self.final_score >= threshold
    }
}

/// Sub-chunk for reranking (150-250 tokens)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubChunk {
    /// Parent chunk ID
    pub parent_chunk_id: ChunkId,
    /// Sub-chunk content
    pub content: String,
    /// Start position within the parent chunk
    pub start_offset: usize,
    /// End position within the parent chunk
    pub end_offset: usize,
    /// Number of tokens in this sub-chunk
    pub token_count: usize,
}

impl SubChunk {
    /// Create a new sub-chunk
    pub fn new(
        parent_chunk_id: ChunkId,
        content: String,
        start_offset: usize,
        end_offset: usize,
        token_count: usize,
    ) -> Self {
        Self {
            parent_chunk_id,
            content,
            start_offset,
            end_offset,
            token_count,
        }
    }
}

/// Configuration for chunking parameters
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChunkingConfig {
    /// Target chunk size in tokens (400-500)
    pub chunk_size: usize,
    /// Overlap between chunks in tokens (50)
    pub overlap: usize,
    /// Minimum chunk size in tokens
    pub min_chunk_size: usize,
    /// Maximum chunk size in tokens
    pub max_chunk_size: usize,
}

impl Default for ChunkingConfig {
    fn default() -> Self {
        Self {
            chunk_size: 450,
            overlap: 50,
            min_chunk_size: 100,
            max_chunk_size: 600,
        }
    }
}

/// Statistics about the RAG system
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RagStats {
    /// Total number of documents
    pub document_count: usize,
    /// Total number of chunks
    pub chunk_count: usize,
    /// Total number of embeddings
    pub embedding_count: usize,
    /// Average chunk size in tokens
    pub avg_chunk_size: f32,
    /// Cache hit rate
    pub cache_hit_rate: f32,
    /// Last update timestamp
    pub last_updated: DateTime<Utc>,
}

impl Default for RagStats {
    fn default() -> Self {
        Self {
            document_count: 0,
            chunk_count: 0,
            embedding_count: 0,
            avg_chunk_size: 0.0,
            cache_hit_rate: 0.0,
            last_updated: Utc::now(),
        }
    }
}