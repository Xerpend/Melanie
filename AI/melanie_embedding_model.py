"""
Melanie Embedding Model wrapper implementing BaseAIModel interface.

This module provides:
- MelanieEmbedding class implementing BaseAIModel interface for text-to-vector conversion
- NVIDIA API integration with async HTTP client
- Batch processing capabilities for efficiency
- Comprehensive error handling and retry logic
- RAG system integration interfaces
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

# Import from API models - adjust path as needed
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'API'))

try:
    from models import (
        BaseAIModel, 
        ChatMessage, 
        ChatCompletionRequest, 
        ChatCompletionResponse,
        Tool,
        Choice,
        Usage,
        APIError,
        MessageRole
    )
except ImportError:
    # Fallback for testing - create minimal stubs
    from abc import ABC, abstractmethod
    from typing import List, Optional, Dict, Any
    from pydantic import BaseModel
    from enum import Enum
    
    class MessageRole(str, Enum):
        USER = "user"
        ASSISTANT = "assistant"
        SYSTEM = "system"
    
    class ChatMessage(BaseModel):
        role: MessageRole
        content: str
        name: Optional[str] = None
    
    class Usage(BaseModel):
        prompt_tokens: int
        completion_tokens: int
        total_tokens: int
    
    class Choice(BaseModel):
        index: int
        message: Dict[str, Any]
        finish_reason: Optional[str] = None
    
    class ChatCompletionResponse(BaseModel):
        id: str
        object: str = "chat.completion"
        created: int
        model: str
        choices: List[Choice]
        usage: Usage
        research_plan: Optional[Dict[str, Any]] = None
    
    class ToolFunction(BaseModel):
        name: str
        description: Optional[str] = None
        parameters: Optional[Dict[str, Any]] = None
    
    class Tool(BaseModel):
        function: ToolFunction
    
    class ChatCompletionRequest(BaseModel):
        model: str
        messages: List[ChatMessage]
        tools: Optional[List[Tool]] = None
    
    class BaseAIModel(ABC):
        def __init__(self, model_name: str, api_key: str, **kwargs):
            self.model_name = model_name
            self.api_key = api_key
            self.config = kwargs
        
        @abstractmethod
        async def generate(self, messages: List[ChatMessage], tools: Optional[List[Tool]] = None, **kwargs) -> ChatCompletionResponse:
            pass
        
        @abstractmethod
        async def validate_request(self, request: ChatCompletionRequest) -> bool:
            pass
        
        @abstractmethod
        def get_capabilities(self) -> List[str]:
            pass
        
        @abstractmethod
        def get_max_tokens(self) -> int:
            pass
        
        def get_model_info(self) -> Dict[str, Any]:
            return {
                "name": self.model_name,
                "capabilities": self.get_capabilities(),
                "max_tokens": self.get_max_tokens(),
                "config": self.config
            }
    
    class APIError(Exception):
        pass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """Result from embedding generation."""
    text: str
    embedding: List[float]
    model: str
    input_type: str
    token_count: Optional[int] = None


@dataclass
class BatchEmbeddingResult:
    """Result from batch embedding generation."""
    results: List[EmbeddingResult]
    total_tokens: int
    processing_time: float
    batch_size: int


class EmbeddingRequest(BaseModel):
    """Embedding request model."""
    texts: List[str] = Field(..., min_length=1, max_length=1000)
    model: str = Field(default="nvidia/nv-embedqa-mistral-7b-v2")
    input_type: str = Field(default="query", pattern="^(query|passage)$")
    encoding_format: str = Field(default="float")
    truncate: str = Field(default="NONE")
    
    @field_validator('texts')
    @classmethod
    def validate_texts(cls, v):
        """Validate text inputs."""
        if not v:
            raise ValueError("At least one text is required")
        
        for i, text in enumerate(v):
            if not text or not text.strip():
                raise ValueError(f"Text at index {i} cannot be empty")
            
            if len(text) > 100000:  # 100k character limit per text
                raise ValueError(f"Text at index {i} exceeds maximum length of 100,000 characters")
        
        return v


class EmbeddingResponse(BaseModel):
    """Embedding response model."""
    object: str = "list"
    data: List[Dict[str, Any]]
    model: str
    usage: Dict[str, int]


class MelanieEmbeddingError(Exception):
    """Custom exception for MelanieEmbedding model errors."""
    pass


class MelanieEmbeddingTimeoutError(MelanieEmbeddingError):
    """Timeout error for MelanieEmbedding model."""
    def __init__(self, timeout: float):
        self.timeout = timeout
        super().__init__(f"Embedding request timed out after {timeout} seconds")


class MelanieEmbeddingRateLimitError(MelanieEmbeddingError):
    """Rate limit error for MelanieEmbedding model."""
    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        message = "Rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after} seconds"
        super().__init__(message)


class MelanieEmbedding(BaseAIModel):
    """
    Melanie Embedding Model wrapper implementing BaseAIModel interface.
    
    Provides text-to-vector conversion using NVIDIA's embedding API with
    batch processing capabilities and RAG system integration.
    """
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize MelanieEmbedding model.
        
        Args:
            api_key: NVIDIA API key (defaults to NVIDIA_API_KEY env var)
            **kwargs: Additional configuration options
        """
        api_key = api_key or os.getenv("NVIDIA_API_KEY")
        if not api_key:
            raise ValueError("NVIDIA_API_KEY environment variable or api_key parameter is required")
        
        super().__init__(
            model_name="nvidia/nv-embedqa-mistral-7b-v2",
            api_key=api_key,
            **kwargs
        )
        
        # Configuration
        self.base_url = kwargs.get("base_url", "https://integrate.api.nvidia.com/v1")
        self.timeout = kwargs.get("timeout", 300)  # 5 minutes for batch operations
        self.max_retries = kwargs.get("max_retries", 3)
        self.retry_delay = kwargs.get("retry_delay", 1.0)
        
        # Batch processing settings
        self.max_batch_size = kwargs.get("max_batch_size", 100)
        self.max_concurrent_batches = kwargs.get("max_concurrent_batches", 5)
        
        # HTTP client configuration
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        )
        
        # Concurrency control
        self.batch_semaphore = asyncio.Semaphore(self.max_concurrent_batches)
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
    
    def _chunk_texts(self, texts: List[str], chunk_size: int) -> List[List[str]]:
        """
        Split texts into chunks for batch processing.
        
        Args:
            texts: List of texts to chunk
            chunk_size: Maximum size of each chunk
            
        Returns:
            List of text chunks
        """
        chunks = []
        for i in range(0, len(texts), chunk_size):
            chunks.append(texts[i:i + chunk_size])
        return chunks
    
    async def _make_embedding_request(
        self, 
        texts: List[str], 
        input_type: str = "query",
        model: Optional[str] = None
    ) -> EmbeddingResponse:
        """
        Make embedding request to NVIDIA API.
        
        Args:
            texts: List of texts to embed
            input_type: Type of input ("query" or "passage")
            model: Model to use (defaults to instance model)
            
        Returns:
            EmbeddingResponse: API response
            
        Raises:
            MelanieEmbeddingError: On API or network errors
        """
        model = model or self.model_name
        
        payload = {
            "input": texts,
            "model": model,
            "encoding_format": "float",
            "extra_body": {
                "input_type": input_type,
                "truncate": "NONE"
            }
        }
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Making embedding request for {len(texts)} texts (attempt {attempt + 1})")
                
                response = await self.client.post("/embeddings", json=payload)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    if attempt < self.max_retries:
                        logger.warning(f"Rate limited, waiting {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        raise MelanieEmbeddingRateLimitError(retry_after)
                
                # Handle other HTTP errors
                if response.status_code >= 400:
                    error_data = response.json() if response.content else {}
                    error_message = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                    raise MelanieEmbeddingError(f"API error: {error_message}")
                
                # Success
                response_data = response.json()
                return EmbeddingResponse(**response_data)
                
            except httpx.TimeoutException as e:
                last_exception = MelanieEmbeddingTimeoutError(self.timeout)
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Request timed out, retrying in {delay} seconds")
                    await asyncio.sleep(delay)
                    continue
                    
            except httpx.RequestError as e:
                last_exception = MelanieEmbeddingError(f"Network error: {str(e)}")
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Network error, retrying in {delay} seconds")
                    await asyncio.sleep(delay)
                    continue
                    
            except Exception as e:
                last_exception = MelanieEmbeddingError(f"Unexpected error: {str(e)}")
                break
        
        # All retries exhausted
        raise last_exception or MelanieEmbeddingError("Request failed after all retries")
    
    async def embed_single(
        self, 
        text: str, 
        input_type: str = "query",
        model: Optional[str] = None
    ) -> EmbeddingResult:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            input_type: Type of input ("query" or "passage")
            model: Model to use (defaults to instance model)
            
        Returns:
            EmbeddingResult: Embedding result
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        response = await self._make_embedding_request([text], input_type, model)
        
        if not response.data:
            raise MelanieEmbeddingError("No embedding data returned")
        
        embedding_data = response.data[0]
        
        return EmbeddingResult(
            text=text,
            embedding=embedding_data["embedding"],
            model=response.model,
            input_type=input_type,
            token_count=response.usage.get("total_tokens", 0)
        )
    
    async def embed_batch(
        self, 
        texts: List[str], 
        input_type: str = "query",
        model: Optional[str] = None
    ) -> BatchEmbeddingResult:
        """
        Generate embeddings for multiple texts with batch processing.
        
        Args:
            texts: List of texts to embed
            input_type: Type of input ("query" or "passage")
            model: Model to use (defaults to instance model)
            
        Returns:
            BatchEmbeddingResult: Batch embedding results
        """
        if not texts:
            raise ValueError("At least one text is required")
        
        start_time = time.time()
        
        # Validate texts
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise ValueError(f"Text at index {i} cannot be empty")
        
        # Split into chunks for batch processing
        text_chunks = self._chunk_texts(texts, self.max_batch_size)
        
        # Process chunks concurrently
        async def process_chunk(chunk: List[str]) -> List[EmbeddingResult]:
            async with self.batch_semaphore:
                response = await self._make_embedding_request(chunk, input_type, model)
                
                results = []
                for i, (text, embedding_data) in enumerate(zip(chunk, response.data)):
                    result = EmbeddingResult(
                        text=text,
                        embedding=embedding_data["embedding"],
                        model=response.model,
                        input_type=input_type,
                        token_count=None  # Individual token counts not available in batch
                    )
                    results.append(result)
                
                return results
        
        # Execute all chunks concurrently
        chunk_tasks = [process_chunk(chunk) for chunk in text_chunks]
        chunk_results = await asyncio.gather(*chunk_tasks)
        
        # Flatten results
        all_results = []
        total_tokens = 0
        
        for chunk_result in chunk_results:
            all_results.extend(chunk_result)
        
        # Estimate total tokens (rough approximation)
        total_chars = sum(len(text) for text in texts)
        total_tokens = total_chars // 4  # Rough token estimation
        
        processing_time = time.time() - start_time
        
        return BatchEmbeddingResult(
            results=all_results,
            total_tokens=total_tokens,
            processing_time=processing_time,
            batch_size=len(texts)
        )
    
    async def embed_for_rag(
        self, 
        texts: List[str], 
        chunk_metadata: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate embeddings optimized for RAG system integration.
        
        Args:
            texts: List of text chunks to embed
            chunk_metadata: Optional metadata for each chunk
            
        Returns:
            List of dictionaries with embedding and metadata for RAG system
        """
        if not texts:
            return []
        
        # Use "passage" input type for RAG chunks
        batch_result = await self.embed_batch(texts, input_type="passage")
        
        rag_embeddings = []
        
        for i, result in enumerate(batch_result.results):
            rag_embedding = {
                "text": result.text,
                "embedding": result.embedding,
                "model": result.model,
                "input_type": result.input_type,
                "embedding_dimension": len(result.embedding),
                "created_at": time.time()
            }
            
            # Add metadata if provided
            if chunk_metadata and i < len(chunk_metadata):
                rag_embedding["metadata"] = chunk_metadata[i]
            
            rag_embeddings.append(rag_embedding)
        
        return rag_embeddings
    
    async def embed_query_for_retrieval(self, query: str) -> List[float]:
        """
        Generate embedding for a query optimized for retrieval.
        
        Args:
            query: Query text to embed
            
        Returns:
            List of floats representing the query embedding
        """
        result = await self.embed_single(query, input_type="query")
        return result.embedding
    
    # BaseAIModel interface implementation
    async def generate(
        self, 
        messages: List[ChatMessage], 
        tools: Optional[List[Tool]] = None,
        **kwargs
    ) -> ChatCompletionResponse:
        """
        Generate embeddings based on chat messages (BaseAIModel interface).
        
        This method adapts the embedding functionality to the BaseAIModel interface
        by extracting text from messages and returning embeddings in a chat format.
        """
        # Extract text from messages
        texts = [msg.content for msg in messages if msg.content.strip()]
        
        if not texts:
            raise MelanieEmbeddingError("No valid text content found in messages")
        
        # Generate embeddings
        batch_result = await self.embed_batch(texts, input_type="query")
        
        # Format as chat completion response
        embedding_content = {
            "embeddings": [
                {
                    "text": result.text,
                    "embedding": result.embedding,
                    "dimension": len(result.embedding)
                }
                for result in batch_result.results
            ],
            "total_embeddings": len(batch_result.results),
            "processing_time": batch_result.processing_time,
            "model": self.model_name
        }
        
        choice = Choice(
            index=0,
            message={
                "role": "assistant",
                "content": json.dumps(embedding_content, indent=2)
            },
            finish_reason="stop"
        )
        
        usage = Usage(
            prompt_tokens=batch_result.total_tokens,
            completion_tokens=0,
            total_tokens=batch_result.total_tokens
        )
        
        return ChatCompletionResponse(
            id=f"embed-{int(time.time())}-{hash(str(texts)) % 10000}",
            object="chat.completion",
            created=int(time.time()),
            model=self.model_name,
            choices=[choice],
            usage=usage
        )
    
    async def validate_request(self, request: ChatCompletionRequest) -> bool:
        """
        Validate if request is compatible with embedding model.
        
        Args:
            request: Chat completion request
            
        Returns:
            bool: True if request is valid for embedding generation
        """
        try:
            # Check if we have valid messages with content
            if not request.messages:
                return False
            
            # Check if messages contain text content
            valid_content = any(
                msg.content and msg.content.strip() 
                for msg in request.messages
            )
            
            if not valid_content:
                return False
            
            # Check total content length
            total_chars = sum(len(msg.content) for msg in request.messages)
            if total_chars > 1000000:  # 1M character limit
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Request validation failed: {str(e)}")
            return False
    
    def get_capabilities(self) -> List[str]:
        """
        Get list of embedding model capabilities.
        
        Returns:
            List[str]: List of capability names
        """
        return [
            "text_embedding",
            "batch_processing",
            "rag_integration",
            "query_embedding",
            "passage_embedding",
            "semantic_search",
            "similarity_computation",
            "vector_generation"
        ]
    
    def get_max_tokens(self) -> int:
        """
        Get maximum token limit for embedding model.
        
        Returns:
            int: Maximum token limit per text
        """
        return 8192  # Typical limit for embedding models
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get comprehensive model information.
        
        Returns:
            Dict: Model information including capabilities and limits
        """
        info = super().get_model_info()
        info.update({
            "provider": "NVIDIA",
            "version": "nv-embedqa-mistral-7b-v2",
            "embedding_dimension": 4096,  # Typical dimension for this model
            "max_batch_size": self.max_batch_size,
            "max_concurrent_batches": self.max_concurrent_batches,
            "supports_query_passage_types": True,
            "supports_batch_processing": True,
            "supports_rag_integration": True,
            "pricing_per_1k_tokens": {
                "embedding": 0.0002  # Example pricing
            }
        })
        return info


# Convenience functions for backward compatibility
async def get_embeddings_async(
    texts: Union[str, List[str]], 
    model: str = "nvidia/nv-embedqa-mistral-7b-v2", 
    input_type: str = "query"
) -> List[List[float]]:
    """
    Async version of get_embeddings function for backward compatibility.
    
    Args:
        texts: Text(s) to embed
        model: Model to use
        input_type: Type of input
        
    Returns:
        List of embedding vectors
    """
    async with MelanieEmbedding() as embedding_model:
        if isinstance(texts, str):
            result = await embedding_model.embed_single(texts, input_type, model)
            return [result.embedding]
        else:
            batch_result = await embedding_model.embed_batch(texts, input_type, model)
            return [result.embedding for result in batch_result.results]


async def get_single_embedding_async(
    text: str, 
    model: str = "nvidia/nv-embedqa-mistral-7b-v2", 
    input_type: str = "query"
) -> List[float]:
    """
    Async version of get_single_embedding function for backward compatibility.
    
    Args:
        text: Text to embed
        model: Model to use
        input_type: Type of input
        
    Returns:
        Single embedding vector
    """
    async with MelanieEmbedding() as embedding_model:
        result = await embedding_model.embed_single(text, input_type, model)
        return result.embedding


# Example usage and testing
if __name__ == "__main__":
    async def test_embedding_functionality():
        """Test embedding functionality."""
        try:
            async with MelanieEmbedding() as model:
                # Test single embedding
                single_result = await model.embed_single("What is the capital of France?")
                print(f"Single embedding dimension: {len(single_result.embedding)}")
                print(f"Model: {single_result.model}")
                
                # Test batch embedding
                texts = [
                    "What is the capital of France?",
                    "Paris is the capital of France.",
                    "The weather in Paris is nice today."
                ]
                
                batch_result = await model.embed_batch(texts)
                print(f"Batch embeddings count: {len(batch_result.results)}")
                print(f"Processing time: {batch_result.processing_time:.2f}s")
                print(f"Total tokens: {batch_result.total_tokens}")
                
                # Test RAG integration
                rag_embeddings = await model.embed_for_rag(texts)
                print(f"RAG embeddings count: {len(rag_embeddings)}")
                
                # Test query embedding for retrieval
                query_embedding = await model.embed_query_for_retrieval("Find information about Paris")
                print(f"Query embedding dimension: {len(query_embedding)}")
                
        except Exception as e:
            print(f"Test failed: {str(e)}")
    
    # Run test
    asyncio.run(test_embedding_functionality())