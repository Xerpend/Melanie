//! Melanie RAG Engine - High-performance Retrieval-Augmented Generation
//! 
//! This crate provides a production-grade RAG system with the following features:
//! - Smart chunking with 400-500 tokens per chunk and 50-token overlap
//! - High-performance vector storage with parallel processing
//! - Embedding and reranking integration
//! - Python bindings via PyO3
//! - Configurable backends (Sled, FAISS)

#[cfg(feature = "python-bindings")]
use pyo3::prelude::*;
#[cfg(feature = "python-bindings")]
use pyo3::types::PyModule;

// Core modules
pub mod chunker;
pub mod embedder;
pub mod reranker;
pub mod vector_store;
pub mod engine;
pub mod types;
pub mod error;
pub mod config;
pub mod cache;

// Python bindings (optional)
#[cfg(feature = "python-bindings")]
pub mod python_bindings;

// Re-exports for convenience
pub use engine::RagEngine;
pub use types::{Chunk, Document, RetrievalMode, RetrievalResult};
pub use error::{RagError, RagResult};
pub use config::RagConfig;

/// Initialize tracing for the RAG engine
pub fn init_tracing() {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();
}

/// Python module definition (only available with python-bindings feature)
#[cfg(feature = "python-bindings")]
#[pyo3::pymodule]
fn melanie_rag(_py: pyo3::Python, m: &PyModule) -> pyo3::PyResult<()> {
    use pyo3::wrap_pyfunction;
    
    // Add Python classes and functions
    m.add_class::<python_bindings::PyRagEngine>()?;
    m.add_class::<python_bindings::PyChunk>()?;
    m.add_class::<python_bindings::PyDocument>()?;
    m.add_class::<python_bindings::PyRetrievalResult>()?;
    m.add_class::<python_bindings::PyRagStats>()?;
    
    // Add utility functions
    m.add_function(wrap_pyfunction!(python_bindings::init_logging, m)?)?;
    m.add_function(wrap_pyfunction!(python_bindings::get_version, m)?)?;
    
    // Add constants
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("DEFAULT_CHUNK_SIZE", 450)?;
    m.add("DEFAULT_OVERLAP", 50)?;
    m.add("RERANK_THRESHOLD", 0.7)?;
    m.add("DEFAULT_TOKEN_LIMIT", 500000)?;
    m.add("TOKEN_LIMIT_WARNING_THRESHOLD", 0.8)?;
    
    Ok(())
}