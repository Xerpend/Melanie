# Melanie RAG Engine

A high-performance Retrieval-Augmented Generation (RAG) engine implemented in Rust with Python bindings.

## Features

- **Smart Chunking**: Semantic-aware chunking with 400-500 tokens per chunk and 50-token overlap
- **High-Performance Vector Storage**: Parallel processing with Sled backend (FAISS support planned)
- **Embedding Integration**: Async HTTP client for embedding services
- **Reranking System**: Advanced relevance scoring with configurable thresholds
- **Caching Layer**: LRU cache with TTL for embeddings, reranking, and retrieval results
- **Python Bindings**: Full PyO3 integration for seamless Python usage
- **Configurable**: Comprehensive configuration system with environment variable support
- **Production Ready**: Comprehensive error handling, logging, and monitoring

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Python API    │    │   Rust Core     │    │  Vector Store   │
│                 │    │                 │    │                 │
│ - RagEngine     │◄──►│ - SmartChunker  │◄──►│ - Sled Backend  │
│ - Document      │    │ - EmbeddingClient│    │ - FAISS (future)│
│ - Chunk         │    │ - RerankingClient│    │ - Parallel Ops  │
│ - RetrievalResult│    │ - RagCache      │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Requirements

- Rust 1.70+
- Python 3.8+ (for Python bindings)
- Tokenizers library
- Optional: FAISS (for FAISS backend)

## Installation

### Rust Library

Add to your `Cargo.toml`:

```toml
[dependencies]
melanie-rag = { path = "../RAG" }
```

### Python Package

```bash
# Install with pip (after building)
pip install maturin
maturin develop

# Or build wheel
maturin build --release
pip install target/wheels/melanie_rag-*.whl
```

## Usage

### Rust

```rust
use melanie_rag::{RagEngine, RagConfig, RetrievalMode};
use std::collections::HashMap;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Create RAG engine
    let engine = RagEngine::with_default_config().await?;
    
    // Ingest document
    let content = "Your document content here...";
    let metadata = HashMap::new();
    let doc_id = engine.ingest_document(content.to_string(), metadata).await?;
    
    // Retrieve context
    let results = engine.retrieve_context("your query", RetrievalMode::General).await?;
    
    for result in results {
        println!("Score: {:.3}, Content: {}", result.final_score, result.chunk.content);
    }
    
    Ok(())
}
```

### Python

```python
import melanie_rag

# Create RAG engine
engine = melanie_rag.RagEngine()

# Ingest document
doc_id = engine.ingest_document(
    "Your document content here...",
    {"title": "Example Document"}
)

# Retrieve context
results = engine.retrieve_context("your query", "general")

for result in results:
    print(f"Score: {result.final_score:.3f}")
    print(f"Content: {result.chunk.content}")
```

## Configuration

### Environment Variables

```bash
# Chunking
export RAG_CHUNK_SIZE=450
export RAG_OVERLAP=50

# Vector Store
export RAG_DB_PATH="./rag_data"

# Embedding Service
export RAG_EMBEDDING_ENDPOINT="http://localhost:8000/embed"
export RAG_EMBEDDING_API_KEY="your-api-key"

# Reranking Service
export RAG_RERANK_ENDPOINT="http://localhost:8000/rerank"
export RAG_RERANK_API_KEY="your-api-key"
```

### Configuration File

```json
{
  "chunking": {
    "chunk_size": 450,
    "overlap": 50,
    "min_chunk_size": 100,
    "max_chunk_size": 600
  },
  "vector_store": {
    "backend": "Sled",
    "db_path": "./rag_data",
    "dimension": 1536
  },
  "embedding": {
    "endpoint": "http://localhost:8000/embed",
    "model": "text-embedding-ada-002",
    "batch_size": 100,
    "timeout": 30
  },
  "reranking": {
    "endpoint": "http://localhost:8000/rerank",
    "model": "rerank-english-v2.0",
    "threshold": 0.7,
    "max_candidates": 100
  },
  "cache": {
    "enabled": true,
    "max_size": 10000,
    "ttl": 3600
  }
}
```

## Performance

The RAG engine is designed for high performance:

- **Parallel Processing**: Uses Rayon for parallel chunking and vector operations
- **Async I/O**: Non-blocking HTTP requests for embeddings and reranking
- **Efficient Storage**: Sled database with in-memory indexing for fast similarity search
- **Smart Caching**: LRU cache with TTL for frequently accessed data
- **Batch Operations**: Optimized batch processing for embeddings and storage

### Benchmarks

Run benchmarks with:

```bash
cargo bench
```

Expected performance (on modern hardware):
- Chunking: ~1000 documents/second
- Vector Storage: ~10,000 chunks/second (batch)
- Similarity Search: <1ms for 10k vectors
- End-to-end Retrieval: <100ms

## Development

### Building

```bash
# Build Rust library
cargo build --release

# Build Python bindings
maturin develop

# Run tests
cargo test

# Run benchmarks
cargo bench
```

### Features

- `default`: Sled backend
- `faiss-backend`: Enable FAISS support (requires FAISS installation)

### Testing

```bash
# Unit tests
cargo test

# Integration tests
cargo test --test integration

# Python binding tests
python -m pytest tests/
```

## API Reference

### Core Types

- `RagEngine`: Main engine for document ingestion and retrieval
- `Document`: Document with metadata and chunk references
- `Chunk`: Text chunk with embedding and metadata
- `RetrievalResult`: Search result with similarity and rerank scores
- `RetrievalMode`: General (20 chunks) or Research (100 chunks)

### Key Methods

- `ingest_document(content, metadata)`: Add document to RAG system
- `retrieve_context(query, mode)`: Find relevant chunks for query
- `get_document(id)`: Retrieve document by ID
- `delete_document(id)`: Remove document and chunks
- `get_stats()`: Get engine statistics
- `health_check()`: Verify engine health

## Integration with Melanie AI

This RAG engine is designed to integrate seamlessly with the Melanie AI ecosystem:

1. **API Integration**: Called from FastAPI server for context retrieval
2. **Model Integration**: Works with embedding and reranking model wrappers
3. **Tool Orchestration**: Provides context for agent workflows
4. **Performance**: Meets <1s retrieval requirement for 500k token contexts

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Roadmap

- [ ] FAISS backend implementation
- [ ] Distributed vector storage
- [ ] Advanced chunking strategies
- [ ] Multi-modal support (images, PDFs)
- [ ] Real-time indexing
- [ ] Kubernetes deployment