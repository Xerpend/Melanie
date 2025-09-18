# Melanie RAG PyO3 Bindings

This document describes the Python bindings for the Melanie RAG engine, implemented using PyO3 for high-performance async operations.

## Features

- **Async Python Interface**: Full async/await support for all operations
- **Token Limit Monitoring**: Built-in 500k token limit with user prompts
- **General/Research Modes**: Context retrieval optimized for different use cases
- **Document Management**: Full CRUD operations for documents and chunks
- **Error Handling**: Comprehensive error handling with detailed messages
- **Statistics**: Real-time engine statistics and health monitoring

## Installation

### Prerequisites

- Python 3.8+
- Rust toolchain (for building from source)
- maturin (for Python extension building)

### Building from Source

1. **Install Rust** (if not already installed):
   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   source ~/.cargo/env
   ```

2. **Install maturin**:
   ```bash
   pip install maturin
   ```

3. **Build the module**:
   ```bash
   cd RAG
   maturin develop --features python-bindings
   ```

4. **Verify installation**:
   ```bash
   python -c "import melanie_rag; print(f'Version: {melanie_rag.get_version()}')"
   ```

### Using the Build Script

Alternatively, use the provided build script:

```bash
cd RAG
python build_python_module.py
```

## Quick Start

```python
import asyncio
import melanie_rag

async def main():
    # Create RAG engine with custom token limit
    engine = melanie_rag.RagEngine(
        token_limit=100000,  # 100k tokens
        enable_user_prompts=True
    )
    
    # Initialize the engine
    await engine.initialize()
    
    # Ingest a document
    doc_id = await engine.ingest_document(
        "This is a sample document about AI.",
        {"source": "example", "category": "ai"}
    )
    
    # Retrieve context (General mode)
    results = await engine.retrieve_context(
        "What is AI?", 
        mode="general"
    )
    
    # Print results
    for result in results:
        print(f"Score: {result.final_score:.3f}")
        print(f"Content: {result.chunk.content}")
    
    # Check token usage
    count = await engine.get_token_count()
    limit = engine.get_token_limit()
    print(f"Token usage: {count}/{limit}")

# Run the example
asyncio.run(main())
```

## API Reference

### RagEngine Class

#### Constructor

```python
engine = melanie_rag.RagEngine(
    token_limit: int = 500000,
    enable_user_prompts: bool = True
)
```

**Parameters:**
- `token_limit`: Maximum number of tokens allowed (default: 500,000)
- `enable_user_prompts`: Whether to show detailed error messages for token limits

#### Initialization

```python
await engine.initialize()
```

Initialize the RAG engine. Must be called before using other methods.

#### Document Operations

```python
# Ingest document
doc_id = await engine.ingest_document(
    content: str,
    metadata: dict = None
) -> str

# Get document
document = await engine.get_document(doc_id: str) -> Document | None

# List all documents
documents = await engine.list_documents() -> List[Document]

# Delete document
await engine.delete_document(doc_id: str)
```

#### Context Retrieval

```python
# Retrieve context
results = await engine.retrieve_context(
    query: str,
    mode: str = "general"  # "general" or "research"
) -> List[RetrievalResult]
```

**Modes:**
- `"general"`: Returns top 20 chunks (3k-5k tokens)
- `"research"`: Returns top 100 chunks (15k-25k tokens)

#### Token Management

```python
# Get current token count
count = await engine.get_token_count() -> int

# Get token limit
limit = engine.get_token_limit() -> int

# Reset token count
await engine.reset_token_count()

# Check if approaching limit (>80%)
approaching = await engine.is_approaching_limit() -> bool
```

#### Statistics and Health

```python
# Get engine statistics
stats = await engine.get_stats() -> RagStats

# Health check
healthy = await engine.health_check() -> bool

# Perform maintenance
await engine.maintenance()

# Clear all data
await engine.clear()
```

### Data Classes

#### Document

```python
class Document:
    id: str
    content: str
    metadata: Dict[str, str]
    chunk_ids: List[str]
    created_at: str
    updated_at: str
```

#### RetrievalResult

```python
class RetrievalResult:
    chunk: Chunk
    similarity_score: float
    rerank_score: Optional[float]
    final_score: float
```

#### Chunk

```python
class Chunk:
    id: str
    document_id: str
    content: str
    start_offset: int
    end_offset: int
    token_count: int
    metadata: Dict[str, str]
    created_at: str
```

#### RagStats

```python
class RagStats:
    document_count: int
    chunk_count: int
    embedding_count: int
    avg_chunk_size: float
    cache_hit_rate: float
    estimated_total_tokens: int
    last_updated: str
```

## Token Limit Management

The RAG engine includes built-in token limit monitoring to prevent memory issues:

### Default Limits

- **Default limit**: 500,000 tokens
- **Warning threshold**: 80% of limit (400,000 tokens by default)
- **Estimation**: ~4 characters per token

### Token Limit Behavior

1. **Document Ingestion**: Checks if adding document would exceed limit
2. **Context Retrieval**: Estimates return tokens based on mode:
   - General mode: ~5,000 tokens
   - Research mode: ~20,000 tokens
3. **User Prompts**: Detailed error messages when limits are exceeded

### Example Error Handling

```python
try:
    await engine.ingest_document(large_content)
except RuntimeError as e:
    if "Token limit exceeded" in str(e):
        print("Consider starting a new session or increasing the limit")
        # Options: reset count, increase limit, or start new engine
        await engine.reset_token_count()
```

## Retrieval Modes

### General Mode

- **Use case**: Quick queries, specific information lookup
- **Returns**: Top 20 most relevant chunks
- **Token range**: 3,000-5,000 tokens
- **Performance**: Faster, lower memory usage

### Research Mode

- **Use case**: Comprehensive research, deep analysis
- **Returns**: Top 100 most relevant chunks  
- **Token range**: 15,000-25,000 tokens
- **Performance**: Slower, higher memory usage

## Error Handling

### Common Errors

1. **Uninitialized Engine**:
   ```
   RuntimeError: RAG engine not initialized. Call initialize() first.
   ```

2. **Token Limit Exceeded**:
   ```
   RuntimeError: Token limit exceeded! Current: 450000, Adding: 60000, Limit: 500000
   ```

3. **Embedding API Error**:
   ```
   RuntimeError: Failed to ingest document: Embedding error: API error: HTTP 401
   ```

### Best Practices

```python
async def robust_rag_usage():
    engine = melanie_rag.RagEngine(token_limit=100000)
    
    try:
        await engine.initialize()
    except RuntimeError as e:
        print(f"Initialization failed: {e}")
        return
    
    # Check token usage before operations
    if await engine.is_approaching_limit():
        print("Warning: Approaching token limit")
    
    try:
        doc_id = await engine.ingest_document(content)
    except RuntimeError as e:
        if "Token limit exceeded" in str(e):
            await engine.reset_token_count()
            doc_id = await engine.ingest_document(content)
        else:
            raise
```

## Performance Considerations

### Memory Usage

- **Token counting**: Approximate (4 chars/token)
- **Chunk storage**: Efficient Rust-based storage
- **Caching**: LRU cache for frequent queries

### Concurrency

- **Thread safety**: Engine is thread-safe
- **Async operations**: All I/O operations are async
- **Parallel processing**: Rust backend uses rayon for parallel operations

### Optimization Tips

1. **Use appropriate retrieval mode** for your use case
2. **Monitor token usage** to prevent memory issues
3. **Reset token count** periodically for long-running applications
4. **Use maintenance()** to clean up expired cache items

## Testing

### Run Basic Tests

```bash
python -m pytest AI/test_rag_pyo3_basic.py -v
```

### Run Demo

```bash
python AI/demo_rag_pyo3_bindings.py
```

### Integration Tests

For full integration tests (requires API keys):

```bash
python -m pytest AI/test_rag_pyo3_integration.py -v
```

## Module Constants

```python
melanie_rag.__version__           # "0.1.0"
melanie_rag.DEFAULT_CHUNK_SIZE    # 450
melanie_rag.DEFAULT_OVERLAP       # 50
melanie_rag.RERANK_THRESHOLD      # 0.7
melanie_rag.DEFAULT_TOKEN_LIMIT   # 500000
melanie_rag.TOKEN_LIMIT_WARNING_THRESHOLD  # 0.8
```

## Utility Functions

```python
# Get version
version = melanie_rag.get_version()

# Initialize logging
melanie_rag.init_logging()
```

## Troubleshooting

### Build Issues

1. **Rust not found**: Install Rust toolchain
2. **Maturin not found**: `pip install maturin`
3. **PyO3 version conflicts**: Update dependencies

### Runtime Issues

1. **Import error**: Rebuild module with `maturin develop`
2. **Database lock errors**: Use unique database paths for concurrent tests
3. **API authentication**: Set valid `NVIDIA_API_KEY` environment variable

### Performance Issues

1. **Slow initialization**: Check embedding model connectivity
2. **High memory usage**: Monitor token limits and reset periodically
3. **Slow queries**: Use general mode for simple queries

## Contributing

1. **Code changes**: Modify Rust source in `src/`
2. **Rebuild**: Run `maturin develop --features python-bindings`
3. **Test**: Run test suite to verify changes
4. **Documentation**: Update this README for API changes

## License

MIT License - see LICENSE file for details.