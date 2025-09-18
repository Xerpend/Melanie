//! Python bindings for the RAG engine using PyO3 with async support

use crate::config::RagConfig;
use crate::engine::RagEngine;
use crate::types::{Document, RetrievalMode, RetrievalResult, RagStats};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3_asyncio::tokio::future_into_py;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

/// Python wrapper for the RAG engine with async support and token limit monitoring
#[pyclass(name = "RagEngine")]
pub struct PyRagEngine {
    engine: Arc<RwLock<Option<RagEngine>>>,
    token_count: Arc<RwLock<usize>>,
    token_limit: usize,
    enable_user_prompts: bool,
}

#[pymethods]
impl PyRagEngine {
    /// Create a new RAG engine with default configuration
    #[new]
    #[pyo3(signature = (token_limit = 500000, enable_user_prompts = true))]
    fn new(token_limit: usize, enable_user_prompts: bool) -> PyResult<Self> {
        Ok(Self {
            engine: Arc::new(RwLock::new(None)),
            token_count: Arc::new(RwLock::new(0)),
            token_limit,
            enable_user_prompts,
        })
    }
    
    /// Initialize the RAG engine asynchronously
    fn initialize<'p>(&self, py: Python<'p>) -> PyResult<&'p PyAny> {
        let engine_arc = self.engine.clone();
        
        future_into_py(py, async move {
            let engine = RagEngine::with_default_config().await
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to create RAG engine: {}", e)))?;
            
            let mut engine_guard = engine_arc.write().await;
            *engine_guard = Some(engine);
            
            Ok(())
        })
    }
    
    /// Create a new RAG engine with custom configuration
    #[staticmethod]
    #[pyo3(signature = (_config_dict, token_limit = 500000, enable_user_prompts = true))]
    fn with_config(_config_dict: &PyDict, token_limit: usize, enable_user_prompts: bool) -> PyResult<Self> {
        Ok(Self {
            engine: Arc::new(RwLock::new(None)),
            token_count: Arc::new(RwLock::new(0)),
            token_limit,
            enable_user_prompts,
        })
    }
    
    /// Initialize the RAG engine with custom configuration asynchronously
    fn initialize_with_config<'p>(&self, py: Python<'p>, config_dict: &PyDict) -> PyResult<&'p PyAny> {
        let engine_arc = self.engine.clone();
        let config = python_dict_to_config(config_dict)?;
        
        future_into_py(py, async move {
            let engine = RagEngine::new(config).await
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to create RAG engine: {}", e)))?;
            
            let mut engine_guard = engine_arc.write().await;
            *engine_guard = Some(engine);
            
            Ok(())
        })
    }
    
    /// Ingest a document into the RAG system with token limit monitoring
    fn ingest_document<'p>(&self, py: Python<'p>, content: String, metadata: Option<&PyDict>) -> PyResult<&'p PyAny> {
        let engine_arc = self.engine.clone();
        let token_count_arc = self.token_count.clone();
        let token_limit = self.token_limit;
        let enable_prompts = self.enable_user_prompts;
        
        let metadata_map = if let Some(meta) = metadata {
            python_dict_to_string_map(meta)?
        } else {
            HashMap::new()
        };
        
        future_into_py(py, async move {
            // Check if engine is initialized
            let engine_guard = engine_arc.read().await;
            let engine = engine_guard.as_ref()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("RAG engine not initialized. Call initialize() first."))?;
            
            // Estimate token count for the document (rough approximation: 1 token ≈ 4 characters)
            let estimated_tokens = content.len() / 4;
            
            // Check token limit before ingestion
            {
                let mut current_count = token_count_arc.write().await;
                if *current_count + estimated_tokens > token_limit {
                    if enable_prompts {
                        return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                            format!("Token limit exceeded! Current: {}, Adding: {}, Limit: {}. Consider starting a new session or increasing the limit.", 
                                   *current_count, estimated_tokens, token_limit)
                        ));
                    } else {
                        return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Token limit exceeded"));
                    }
                }
                *current_count += estimated_tokens;
            }
            
            // Ingest the document
            let document_id = engine.ingest_document(content, metadata_map).await
                .map_err(|e| {
                    // Rollback token count on failure
                    tokio::spawn(async move {
                        let mut current_count = token_count_arc.write().await;
                        *current_count = current_count.saturating_sub(estimated_tokens);
                    });
                    PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to ingest document: {}", e))
                })?;
            
            Ok(document_id.to_string())
        })
    }
    
    /// Retrieve relevant context for a query with General/Research modes
    fn retrieve_context<'p>(&self, py: Python<'p>, query: String, mode: Option<String>) -> PyResult<&'p PyAny> {
        let engine_arc = self.engine.clone();
        let token_count_arc = self.token_count.clone();
        let token_limit = self.token_limit;
        let enable_prompts = self.enable_user_prompts;
        
        let retrieval_mode = match mode.as_deref() {
            Some("research") => RetrievalMode::Research,
            _ => RetrievalMode::General,
        };
        
        future_into_py(py, async move {
            // Check if engine is initialized
            let engine_guard = engine_arc.read().await;
            let engine = engine_guard.as_ref()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("RAG engine not initialized. Call initialize() first."))?;
            
            // Estimate tokens for the query
            let query_tokens = query.len() / 4;
            
            // Estimate tokens that will be returned based on mode
            let estimated_return_tokens = match retrieval_mode {
                RetrievalMode::General => 5000,   // 3k-5k tokens for general
                RetrievalMode::Research => 20000, // 15k-25k tokens for research
            };
            
            // Check token limit before retrieval
            {
                let current_count = token_count_arc.read().await;
                if *current_count + query_tokens + estimated_return_tokens > token_limit {
                    if enable_prompts {
                        return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                            format!("Token limit would be exceeded! Current: {}, Query: {}, Expected return: {}, Limit: {}. \
                                   Options: 1) Start new session, 2) Use 'general' mode instead of 'research', 3) Increase limit.", 
                                   *current_count, query_tokens, estimated_return_tokens, token_limit)
                        ));
                    } else {
                        return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Token limit would be exceeded"));
                    }
                }
            }
            
            // Retrieve context
            let results = engine.retrieve_context(&query, retrieval_mode).await
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to retrieve context: {}", e)))?;
            
            // Update token count with actual usage
            {
                let mut current_count = token_count_arc.write().await;
                let actual_tokens = results.iter()
                    .map(|r| r.chunk.content.len() / 4)
                    .sum::<usize>();
                *current_count += query_tokens + actual_tokens;
            }
            
            Ok(results.into_iter().map(PyRetrievalResult::from).collect::<Vec<_>>())
        })
    }
    
    /// Get current token count
    fn get_token_count<'p>(&self, py: Python<'p>) -> PyResult<&'p PyAny> {
        let token_count_arc = self.token_count.clone();
        
        future_into_py(py, async move {
            let count = token_count_arc.read().await;
            Ok(*count)
        })
    }
    
    /// Get token limit
    fn get_token_limit(&self) -> PyResult<usize> {
        Ok(self.token_limit)
    }
    
    /// Reset token count
    fn reset_token_count<'p>(&self, py: Python<'p>) -> PyResult<&'p PyAny> {
        let token_count_arc = self.token_count.clone();
        
        future_into_py(py, async move {
            let mut count = token_count_arc.write().await;
            *count = 0;
            Ok(())
        })
    }
    
    /// Check if approaching token limit (returns true if > 80% of limit)
    fn is_approaching_limit<'p>(&self, py: Python<'p>) -> PyResult<&'p PyAny> {
        let token_count_arc = self.token_count.clone();
        let token_limit = self.token_limit;
        
        future_into_py(py, async move {
            let count = token_count_arc.read().await;
            Ok(*count > (token_limit * 80 / 100))
        })
    }
    
    /// Get a document by ID
    fn get_document<'p>(&self, py: Python<'p>, document_id: String) -> PyResult<&'p PyAny> {
        let engine_arc = self.engine.clone();
        
        future_into_py(py, async move {
            let engine_guard = engine_arc.read().await;
            let engine = engine_guard.as_ref()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("RAG engine not initialized. Call initialize() first."))?;
            
            let doc_id = document_id.parse()
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid document ID: {}", e)))?;
            
            let document = engine.get_document(doc_id).await
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to get document: {}", e)))?;
            
            Ok(document.map(PyDocument::from))
        })
    }
    
    /// Delete a document
    fn delete_document<'p>(&self, py: Python<'p>, document_id: String) -> PyResult<&'p PyAny> {
        let engine_arc = self.engine.clone();
        
        future_into_py(py, async move {
            let engine_guard = engine_arc.read().await;
            let engine = engine_guard.as_ref()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("RAG engine not initialized. Call initialize() first."))?;
            
            let doc_id = document_id.parse()
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid document ID: {}", e)))?;
            
            engine.delete_document(doc_id).await
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to delete document: {}", e)))?;
            
            Ok(())
        })
    }
    
    /// List all documents
    fn list_documents<'p>(&self, py: Python<'p>) -> PyResult<&'p PyAny> {
        let engine_arc = self.engine.clone();
        
        future_into_py(py, async move {
            let engine_guard = engine_arc.read().await;
            let engine = engine_guard.as_ref()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("RAG engine not initialized. Call initialize() first."))?;
            
            let documents = engine.list_documents().await;
            Ok(documents.into_iter().map(PyDocument::from).collect::<Vec<_>>())
        })
    }
    
    /// Get engine statistics
    fn get_stats<'p>(&self, py: Python<'p>) -> PyResult<&'p PyAny> {
        let engine_arc = self.engine.clone();
        
        future_into_py(py, async move {
            let engine_guard = engine_arc.read().await;
            let engine = engine_guard.as_ref()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("RAG engine not initialized. Call initialize() first."))?;
            
            let stats = engine.get_stats().await;
            Ok(PyRagStats::from(stats))
        })
    }
    
    /// Clear all data and reset token count
    fn clear<'p>(&self, py: Python<'p>) -> PyResult<&'p PyAny> {
        let engine_arc = self.engine.clone();
        let token_count_arc = self.token_count.clone();
        
        future_into_py(py, async move {
            let engine_guard = engine_arc.read().await;
            let engine = engine_guard.as_ref()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("RAG engine not initialized. Call initialize() first."))?;
            
            engine.clear().await
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to clear data: {}", e)))?;
            
            // Reset token count
            let mut count = token_count_arc.write().await;
            *count = 0;
            
            Ok(())
        })
    }
    
    /// Perform maintenance
    fn maintenance<'p>(&self, py: Python<'p>) -> PyResult<&'p PyAny> {
        let engine_arc = self.engine.clone();
        
        future_into_py(py, async move {
            let engine_guard = engine_arc.read().await;
            let engine = engine_guard.as_ref()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("RAG engine not initialized. Call initialize() first."))?;
            
            engine.maintenance().await
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to perform maintenance: {}", e)))?;
            
            Ok(())
        })
    }
    
    /// Check engine health
    fn health_check<'p>(&self, py: Python<'p>) -> PyResult<&'p PyAny> {
        let engine_arc = self.engine.clone();
        
        future_into_py(py, async move {
            let engine_guard = engine_arc.read().await;
            let engine = engine_guard.as_ref()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("RAG engine not initialized. Call initialize() first."))?;
            
            let health = engine.health_check().await
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Health check failed: {}", e)))?;
            
            Ok(health)
        })
    }
}

/// Python wrapper for Document
#[pyclass(name = "Document")]
#[derive(Clone)]
pub struct PyDocument {
    #[pyo3(get)]
    id: String,
    #[pyo3(get)]
    content: String,
    #[pyo3(get)]
    metadata: HashMap<String, String>,
    #[pyo3(get)]
    chunk_ids: Vec<String>,
    #[pyo3(get)]
    created_at: String,
    #[pyo3(get)]
    updated_at: String,
}

impl From<Document> for PyDocument {
    fn from(doc: Document) -> Self {
        Self {
            id: doc.id.to_string(),
            content: doc.content,
            metadata: doc.metadata,
            chunk_ids: doc.chunk_ids.into_iter().map(|id| id.to_string()).collect(),
            created_at: doc.created_at.to_rfc3339(),
            updated_at: doc.updated_at.to_rfc3339(),
        }
    }
}

/// Python wrapper for Chunk
#[pyclass(name = "Chunk")]
#[derive(Clone)]
pub struct PyChunk {
    #[pyo3(get)]
    id: String,
    #[pyo3(get)]
    document_id: String,
    #[pyo3(get)]
    content: String,
    #[pyo3(get)]
    start_offset: usize,
    #[pyo3(get)]
    end_offset: usize,
    #[pyo3(get)]
    token_count: usize,
    #[pyo3(get)]
    metadata: HashMap<String, String>,
    #[pyo3(get)]
    created_at: String,
}

impl From<crate::types::Chunk> for PyChunk {
    fn from(chunk: crate::types::Chunk) -> Self {
        Self {
            id: chunk.id.to_string(),
            document_id: chunk.document_id.to_string(),
            content: chunk.content,
            start_offset: chunk.start_offset,
            end_offset: chunk.end_offset,
            token_count: chunk.token_count,
            metadata: chunk.metadata,
            created_at: chunk.created_at.to_rfc3339(),
        }
    }
}

/// Python wrapper for RetrievalResult
#[pyclass(name = "RetrievalResult")]
#[derive(Clone)]
pub struct PyRetrievalResult {
    #[pyo3(get)]
    chunk: PyChunk,
    #[pyo3(get)]
    similarity_score: f32,
    #[pyo3(get)]
    rerank_score: Option<f32>,
    #[pyo3(get)]
    final_score: f32,
}

impl From<RetrievalResult> for PyRetrievalResult {
    fn from(result: RetrievalResult) -> Self {
        Self {
            chunk: PyChunk::from(result.chunk),
            similarity_score: result.similarity_score,
            rerank_score: result.rerank_score,
            final_score: result.final_score,
        }
    }
}

/// Python wrapper for RagStats with token information
#[pyclass(name = "RagStats")]
#[derive(Clone)]
pub struct PyRagStats {
    #[pyo3(get)]
    document_count: usize,
    #[pyo3(get)]
    chunk_count: usize,
    #[pyo3(get)]
    embedding_count: usize,
    #[pyo3(get)]
    avg_chunk_size: f32,
    #[pyo3(get)]
    cache_hit_rate: f32,
    #[pyo3(get)]
    last_updated: String,
    #[pyo3(get)]
    estimated_total_tokens: usize,
}

impl From<RagStats> for PyRagStats {
    fn from(stats: RagStats) -> Self {
        // Estimate total tokens based on chunk count and average size
        let estimated_total_tokens = (stats.chunk_count as f32 * stats.avg_chunk_size) as usize;
        
        Self {
            document_count: stats.document_count,
            chunk_count: stats.chunk_count,
            embedding_count: stats.embedding_count,
            avg_chunk_size: stats.avg_chunk_size,
            cache_hit_rate: stats.cache_hit_rate,
            last_updated: stats.last_updated.to_rfc3339(),
            estimated_total_tokens,
        }
    }
}

/// Initialize logging for the RAG engine
#[pyfunction]
pub fn init_logging() -> PyResult<()> {
    crate::init_tracing();
    Ok(())
}

/// Get the version of the RAG engine
#[pyfunction]
pub fn get_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

/// Helper function to convert Python dict to HashMap<String, String>
fn python_dict_to_string_map(dict: &PyDict) -> PyResult<HashMap<String, String>> {
    let mut map = HashMap::new();
    
    for (key, value) in dict.iter() {
        let key_str = key.extract::<String>()?;
        let value_str = value.extract::<String>()?;
        map.insert(key_str, value_str);
    }
    
    Ok(map)
}

/// Helper function to convert Python dict to RagConfig
fn python_dict_to_config(_dict: &PyDict) -> PyResult<RagConfig> {
    // For now, return default config
    // TODO: Implement proper conversion from Python dict to RagConfig
    Ok(RagConfig::default())
}

#[cfg(test)]
mod tests {
    use super::*;
    use pyo3::types::IntoPyDict;
    
    #[test]
    fn test_python_bindings_creation() {
        pyo3::prepare_freethreaded_python();
        
        Python::with_gil(|py| {
            let result = PyRagEngine::new(500000, true);
            assert!(result.is_ok());
            
            let engine = result.unwrap();
            assert_eq!(engine.token_limit, 500000);
            assert_eq!(engine.enable_user_prompts, true);
        });
    }
    
    #[test]
    fn test_python_dict_conversion() {
        pyo3::prepare_freethreaded_python();
        
        Python::with_gil(|py| {
            let dict = [("key1", "value1"), ("key2", "value2")].into_py_dict(py);
            let map = python_dict_to_string_map(dict).unwrap();
            
            assert_eq!(map.len(), 2);
            assert_eq!(map.get("key1"), Some(&"value1".to_string()));
            assert_eq!(map.get("key2"), Some(&"value2".to_string()));
        });
    }
    
    #[test]
    fn test_token_limit_configuration() {
        pyo3::prepare_freethreaded_python();
        
        Python::with_gil(|py| {
            let engine = PyRagEngine::new(100000, false).unwrap();
            assert_eq!(engine.get_token_limit().unwrap(), 100000);
            assert_eq!(engine.enable_user_prompts, false);
        });
    }
}