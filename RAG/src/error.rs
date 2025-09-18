//! Error types for the RAG engine

use thiserror::Error;

/// Result type alias for RAG operations
pub type RagResult<T> = Result<T, RagError>;

/// Main error type for the RAG engine
#[derive(Error, Debug)]
pub enum RagError {
    /// IO errors (file operations, network, etc.)
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    
    /// Serialization/deserialization errors
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),
    
    /// Database errors
    #[error("Database error: {0}")]
    Database(#[from] sled::Error),
    
    /// HTTP client errors
    #[error("HTTP error: {0}")]
    Http(#[from] reqwest::Error),
    
    /// Tokenization errors
    #[error("Tokenization error: {0}")]
    Tokenization(String),
    
    /// Embedding errors
    #[error("Embedding error: {0}")]
    Embedding(String),
    
    /// Reranking errors
    #[error("Reranking error: {0}")]
    Reranking(String),
    
    /// Vector store errors
    #[error("Vector store error: {0}")]
    VectorStore(String),
    
    /// Configuration errors
    #[error("Configuration error: {0}")]
    Configuration(String),
    
    /// Document not found
    #[error("Document not found: {0}")]
    DocumentNotFound(String),
    
    /// Chunk not found
    #[error("Chunk not found: {0}")]
    ChunkNotFound(String),
    
    /// Invalid input
    #[error("Invalid input: {0}")]
    InvalidInput(String),
    
    /// Timeout errors
    #[error("Operation timed out: {0}")]
    Timeout(String),
    
    /// Cache errors
    #[error("Cache error: {0}")]
    Cache(String),
    
    /// Generic errors
    #[error("RAG engine error: {0}")]
    Generic(String),
}

impl RagError {
    /// Create a new tokenization error
    pub fn tokenization<S: Into<String>>(msg: S) -> Self {
        RagError::Tokenization(msg.into())
    }
    
    /// Create a new embedding error
    pub fn embedding<S: Into<String>>(msg: S) -> Self {
        RagError::Embedding(msg.into())
    }
    
    /// Create a new reranking error
    pub fn reranking<S: Into<String>>(msg: S) -> Self {
        RagError::Reranking(msg.into())
    }
    
    /// Create a new vector store error
    pub fn vector_store<S: Into<String>>(msg: S) -> Self {
        RagError::VectorStore(msg.into())
    }
    
    /// Create a new configuration error
    pub fn configuration<S: Into<String>>(msg: S) -> Self {
        RagError::Configuration(msg.into())
    }
    
    /// Create a new document not found error
    pub fn document_not_found<S: Into<String>>(id: S) -> Self {
        RagError::DocumentNotFound(id.into())
    }
    
    /// Create a new chunk not found error
    pub fn chunk_not_found<S: Into<String>>(id: S) -> Self {
        RagError::ChunkNotFound(id.into())
    }
    
    /// Create a new invalid input error
    pub fn invalid_input<S: Into<String>>(msg: S) -> Self {
        RagError::InvalidInput(msg.into())
    }
    
    /// Create a new timeout error
    pub fn timeout<S: Into<String>>(msg: S) -> Self {
        RagError::Timeout(msg.into())
    }
    
    /// Create a new cache error
    pub fn cache<S: Into<String>>(msg: S) -> Self {
        RagError::Cache(msg.into())
    }
    
    /// Create a new generic error
    pub fn generic<S: Into<String>>(msg: S) -> Self {
        RagError::Generic(msg.into())
    }
}

/// Convert anyhow errors to RagError
impl From<anyhow::Error> for RagError {
    fn from(err: anyhow::Error) -> Self {
        RagError::Generic(err.to_string())
    }
}

/// Convert UUID errors to RagError
impl From<uuid::Error> for RagError {
    fn from(err: uuid::Error) -> Self {
        RagError::InvalidInput(format!("Invalid UUID: {}", err))
    }
}