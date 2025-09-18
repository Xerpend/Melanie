//! Main RAG engine implementation

use crate::cache::RagCache;
use crate::chunker::SmartChunker;
use crate::config::RagConfig;
use crate::embedder::EmbeddingClient;
use crate::error::{RagError, RagResult};
use crate::reranker::RerankingClient;
use crate::types::{
    Chunk, Document, DocumentId, RetrievalMode, RetrievalResult, RagStats,
};
use crate::vector_store::{create_vector_store, VectorStore};
// use rayon::prelude::*;  // Commented out for now
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{debug, info, warn};

/// Main RAG engine that orchestrates all components
pub struct RagEngine {
    /// Smart chunker for document processing
    chunker: SmartChunker,
    /// Embedding client for vector generation
    embedder: EmbeddingClient,
    /// Reranking client for result scoring
    reranker: RerankingClient,
    /// Vector store for similarity search
    vector_store: Box<dyn VectorStore>,
    /// Cache for performance optimization
    cache: RagCache,
    /// Document metadata storage
    documents: Arc<RwLock<HashMap<DocumentId, Document>>>,
    /// Configuration
    config: RagConfig,
    /// Engine statistics
    stats: Arc<RwLock<RagStats>>,
}

impl RagEngine {
    /// Create a new RAG engine with the given configuration
    pub async fn new(config: RagConfig) -> RagResult<Self> {
        // Validate configuration
        config.validate()?;
        
        info!("Initializing RAG engine with config: {:?}", config);
        
        // Initialize components
        let chunker = SmartChunker::with_default_tokenizer(config.chunking.clone()).await?;
        let embedder = EmbeddingClient::new(config.embedding.clone())?;
        let reranker = RerankingClient::new(config.reranking.clone())?;
        let vector_store = create_vector_store(config.vector_store.clone()).await?;
        let cache = RagCache::new(config.cache.clone())?;
        
        // Initialize storage
        let documents = Arc::new(RwLock::new(HashMap::new()));
        let stats = Arc::new(RwLock::new(RagStats::default()));
        
        Ok(Self {
            chunker,
            embedder,
            reranker,
            vector_store,
            cache,
            documents,
            config,
            stats,
        })
    }
    
    /// Create a RAG engine with default configuration
    pub async fn with_default_config() -> RagResult<Self> {
        let config = RagConfig::default();
        Self::new(config).await
    }
    
    /// Ingest a document into the RAG system
    pub async fn ingest_document(&self, content: String, metadata: HashMap<String, String>) -> RagResult<DocumentId> {
        if content.trim().is_empty() {
            return Err(RagError::invalid_input("Document content cannot be empty"));
        }
        
        info!("Ingesting document with {} characters", content.len());
        
        // Create document
        let mut document = Document::new(content.clone(), metadata);
        let document_id = document.id;
        
        // Chunk the document
        let mut chunks = self.chunker.chunk_document(document_id, &content).await?;
        
        if chunks.is_empty() {
            warn!("No chunks generated for document {}", document_id);
            return Ok(document_id);
        }
        
        info!("Generated {} chunks for document {}", chunks.len(), document_id);
        
        // Generate embeddings for chunks
        self.embedder.embed_chunks(&mut chunks).await?;
        
        // Store chunks in vector store
        self.vector_store.store_chunks(&chunks).await?;
        
        // Update document with chunk IDs
        for chunk in &chunks {
            document.add_chunk(chunk.id);
        }
        
        // Store document metadata
        {
            let mut documents = self.documents.write().await;
            documents.insert(document_id, document);
        }
        
        // Update statistics
        {
            let mut stats = self.stats.write().await;
            stats.document_count += 1;
            stats.chunk_count += chunks.len();
            stats.embedding_count += chunks.iter().filter(|c| c.has_embedding()).count();
            
            // Update average chunk size
            let total_tokens: usize = chunks.iter().map(|c| c.token_count).sum();
            let new_avg = total_tokens as f32 / chunks.len() as f32;
            stats.avg_chunk_size = if stats.chunk_count == chunks.len() {
                new_avg
            } else {
                (stats.avg_chunk_size * (stats.chunk_count - chunks.len()) as f32 + total_tokens as f32) / stats.chunk_count as f32
            };
            
            stats.last_updated = chrono::Utc::now();
        }
        
        info!("Successfully ingested document {} with {} chunks", document_id, chunks.len());
        Ok(document_id)
    }
    
    /// Retrieve relevant context for a query
    pub async fn retrieve_context(&self, query: &str, mode: RetrievalMode) -> RagResult<Vec<RetrievalResult>> {
        if query.trim().is_empty() {
            return Err(RagError::invalid_input("Query cannot be empty"));
        }
        
        debug!("Retrieving context for query: '{}' in mode: {:?}", query, mode);
        
        // Check cache first
        if let Some(cached_results) = self.cache.get_retrieval(query).await {
            debug!("Found cached results for query");
            return Ok(cached_results);
        }
        
        // Generate query embedding
        let query_embedding = self.embedder.embed_single(query).await?;
        
        // Search for similar chunks
        let max_candidates = match mode {
            RetrievalMode::General => 100,  // Get more candidates for better reranking
            RetrievalMode::Research => 200, // Even more for research mode
        };
        
        let similar_chunks = self.vector_store.search_similar(&query_embedding, max_candidates).await?;
        
        if similar_chunks.is_empty() {
            debug!("No similar chunks found for query");
            return Ok(Vec::new());
        }
        
        debug!("Found {} similar chunks", similar_chunks.len());
        
        // Retrieve full chunks
        let mut chunks = Vec::new();
        for (chunk_id, similarity_score) in similar_chunks {
            if let Some(chunk) = self.vector_store.get_chunk(chunk_id).await? {
                let result = RetrievalResult::new(chunk, similarity_score);
                chunks.push(result);
            }
        }
        
        // Create sub-chunks for reranking
        let chunk_refs: Vec<Chunk> = chunks.iter().map(|r| r.chunk.clone()).collect();
        let sub_chunks = self.chunker.create_sub_chunks(&chunk_refs).await?;
        
        // Rerank sub-chunks
        let reranked_sub_chunks = self.reranker.rerank_sub_chunks(query, &sub_chunks).await?;
        
        // Convert back to retrieval results and apply threshold
        let mut final_results = Vec::new();
        let mut seen_chunks = std::collections::HashSet::new();
        
        for (sub_chunk, rerank_score) in reranked_sub_chunks {
            // Find the parent chunk
            if let Some(parent_result) = chunks.iter().find(|r| r.chunk.id == sub_chunk.parent_chunk_id) {
                if seen_chunks.insert(parent_result.chunk.id) {
                    let mut result = parent_result.clone();
                    result.set_rerank_score(rerank_score);
                    
                    if result.meets_threshold(self.config.reranking.threshold) {
                        final_results.push(result);
                    }
                }
            }
        }
        
        // Sort by final score and limit results
        final_results.sort_by(|a, b| b.final_score.partial_cmp(&a.final_score).unwrap_or(std::cmp::Ordering::Equal));
        final_results.truncate(mode.max_chunks());
        
        // Ensure diversity in results
        let diverse_results = self.reranker.ensure_diversity(&final_results, 0.8);
        
        debug!("Returning {} diverse results", diverse_results.len());
        
        // Cache results
        self.cache.cache_retrieval(query, &diverse_results).await?;
        
        Ok(diverse_results)
    }
    
    /// Get document by ID
    pub async fn get_document(&self, document_id: DocumentId) -> RagResult<Option<Document>> {
        let documents = self.documents.read().await;
        Ok(documents.get(&document_id).cloned())
    }
    
    /// Delete a document and all its chunks
    pub async fn delete_document(&self, document_id: DocumentId) -> RagResult<()> {
        info!("Deleting document {}", document_id);
        
        // Get document to find chunk IDs
        let document = {
            let documents = self.documents.read().await;
            documents.get(&document_id).cloned()
        };
        
        if let Some(doc) = document {
            // Delete all chunks from vector store
            for chunk_id in &doc.chunk_ids {
                self.vector_store.delete_chunk(*chunk_id).await?;
            }
            
            // Remove document from metadata
            {
                let mut documents = self.documents.write().await;
                documents.remove(&document_id);
            }
            
            // Update statistics
            {
                let mut stats = self.stats.write().await;
                stats.document_count = stats.document_count.saturating_sub(1);
                stats.chunk_count = stats.chunk_count.saturating_sub(doc.chunk_ids.len());
                stats.embedding_count = stats.embedding_count.saturating_sub(doc.chunk_ids.len());
                stats.last_updated = chrono::Utc::now();
            }
            
            info!("Successfully deleted document {} and {} chunks", document_id, doc.chunk_ids.len());
        } else {
            return Err(RagError::document_not_found(document_id.to_string()));
        }
        
        Ok(())
    }
    
    /// List all documents
    pub async fn list_documents(&self) -> Vec<Document> {
        let documents = self.documents.read().await;
        documents.values().cloned().collect()
    }
    
    /// Get engine statistics
    pub async fn get_stats(&self) -> RagStats {
        let mut stats = self.stats.read().await.clone();
        
        // Update cache hit rate
        let cache_stats = self.cache.get_stats().await;
        stats.cache_hit_rate = cache_stats.overall_hit_rate() as f32;
        
        stats
    }
    
    /// Clear all data
    pub async fn clear(&self) -> RagResult<()> {
        info!("Clearing all RAG data");
        
        // Clear vector store
        self.vector_store.clear().await?;
        
        // Clear documents
        {
            let mut documents = self.documents.write().await;
            documents.clear();
        }
        
        // Clear cache
        self.cache.clear().await?;
        
        // Reset statistics
        {
            let mut stats = self.stats.write().await;
            *stats = RagStats::default();
        }
        
        info!("Successfully cleared all RAG data");
        Ok(())
    }
    
    /// Perform maintenance tasks (cleanup expired cache items, etc.)
    pub async fn maintenance(&self) -> RagResult<()> {
        debug!("Performing RAG engine maintenance");
        
        // Cleanup expired cache items
        let removed = self.cache.cleanup_expired().await?;
        if removed > 0 {
            debug!("Removed {} expired cache items", removed);
        }
        
        // Update statistics timestamp
        {
            let mut stats = self.stats.write().await;
            stats.last_updated = chrono::Utc::now();
        }
        
        Ok(())
    }
    
    /// Get configuration
    pub fn get_config(&self) -> &RagConfig {
        &self.config
    }
    
    /// Check if the engine is healthy
    pub async fn health_check(&self) -> RagResult<bool> {
        // Check vector store
        let _count = self.vector_store.count().await?;
        
        // Check if we can generate embeddings
        let _test_embedding = self.embedder.embed_single("health check").await?;
        
        Ok(true)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;
    
    async fn create_test_engine() -> (RagEngine, TempDir) {
        let temp_dir = TempDir::new().unwrap();
        let mut config = RagConfig::default();
        config.vector_store.db_path = temp_dir.path().to_path_buf();
        
        let engine = RagEngine::new(config).await.unwrap();
        (engine, temp_dir)
    }
    
    #[tokio::test]
    async fn test_engine_creation() {
        let (_engine, _temp_dir) = create_test_engine().await;
        // If we get here, engine creation succeeded
    }
    
    #[tokio::test]
    async fn test_document_ingestion() {
        let (engine, _temp_dir) = create_test_engine().await;
        
        let content = "This is a test document with some content that should be chunked and indexed.".to_string();
        let metadata = HashMap::new();
        
        let doc_id = engine.ingest_document(content, metadata).await.unwrap();
        
        // Verify document was stored
        let document = engine.get_document(doc_id).await.unwrap();
        assert!(document.is_some());
        
        // Verify statistics were updated
        let stats = engine.get_stats().await;
        assert_eq!(stats.document_count, 1);
        assert!(stats.chunk_count > 0);
    }
    
    #[tokio::test]
    async fn test_context_retrieval() {
        let (engine, _temp_dir) = create_test_engine().await;
        
        // Ingest a test document
        let content = "Artificial intelligence is a branch of computer science. Machine learning is a subset of AI.".to_string();
        let metadata = HashMap::new();
        
        engine.ingest_document(content, metadata).await.unwrap();
        
        // Retrieve context
        let results = engine.retrieve_context("artificial intelligence", RetrievalMode::General).await.unwrap();
        
        // Should find relevant chunks
        assert!(!results.is_empty());
        assert!(results[0].final_score > 0.0);
    }
    
    #[tokio::test]
    async fn test_document_deletion() {
        let (engine, _temp_dir) = create_test_engine().await;
        
        // Ingest a test document
        let content = "Test document for deletion".to_string();
        let metadata = HashMap::new();
        
        let doc_id = engine.ingest_document(content, metadata).await.unwrap();
        
        // Verify document exists
        assert!(engine.get_document(doc_id).await.unwrap().is_some());
        
        // Delete document
        engine.delete_document(doc_id).await.unwrap();
        
        // Verify document is gone
        assert!(engine.get_document(doc_id).await.unwrap().is_none());
        
        // Verify statistics were updated
        let stats = engine.get_stats().await;
        assert_eq!(stats.document_count, 0);
    }
    
    #[tokio::test]
    async fn test_empty_query() {
        let (engine, _temp_dir) = create_test_engine().await;
        
        let result = engine.retrieve_context("", RetrievalMode::General).await;
        assert!(result.is_err());
    }
    
    #[tokio::test]
    async fn test_health_check() {
        let (engine, _temp_dir) = create_test_engine().await;
        
        let health = engine.health_check().await.unwrap();
        assert!(health);
    }
}