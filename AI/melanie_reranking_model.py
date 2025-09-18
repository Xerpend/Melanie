"""
Melanie Reranking Model wrapper implementing BaseAIModel interface.

This module provides:
- MelanieReranking class implementing BaseAIModel interface for relevance scoring
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
from typing import Any, Dict, List, Optional, Union, Tuple
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
class RerankingResult:
    """Result from reranking operation."""
    query: str
    passage: str
    score: float
    original_index: int
    reranked_index: int
    model: str


@dataclass
class BatchRerankingResult:
    """Result from batch reranking operation."""
    query: str
    results: List[RerankingResult]
    processing_time: float
    total_passages: int
    filtered_count: int  # Number of passages above threshold


class RerankingRequest(BaseModel):
    """Reranking request model."""
    query: str = Field(..., min_length=1, max_length=10000)
    passages: List[str] = Field(..., min_length=1, max_length=1000)
    model: str = Field(default="nvidia/nv-rerankqa-mistral-4b-v3")
    truncate: str = Field(default="NONE")
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    
    @field_validator('passages')
    @classmethod
    def validate_passages(cls, v):
        """Validate passage inputs."""
        if not v:
            raise ValueError("At least one passage is required")
        
        for i, passage in enumerate(v):
            if not passage or not passage.strip():
                raise ValueError(f"Passage at index {i} cannot be empty")
            
            if len(passage) > 50000:  # 50k character limit per passage
                raise ValueError(f"Passage at index {i} exceeds maximum length of 50,000 characters")
        
        return v


class RerankingResponse(BaseModel):
    """Reranking response model."""
    rankings: List[Dict[str, Any]]
    model: str
    usage: Optional[Dict[str, int]] = None


class MelanieRerankingError(Exception):
    """Custom exception for MelanieReranking model errors."""
    pass


class MelanieRerankingTimeoutError(MelanieRerankingError):
    """Timeout error for MelanieReranking model."""
    def __init__(self, timeout: float):
        self.timeout = timeout
        super().__init__(f"Reranking request timed out after {timeout} seconds")


class MelanieRerankingRateLimitError(MelanieRerankingError):
    """Rate limit error for MelanieReranking model."""
    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        message = "Rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after} seconds"
        super().__init__(message)


class MelanieReranking(BaseAIModel):
    """
    Melanie Reranking Model wrapper implementing BaseAIModel interface.
    
    Provides relevance scoring using NVIDIA's reranking API with
    batch processing capabilities and RAG system integration.
    """
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize MelanieReranking model.
        
        Args:
            api_key: NVIDIA API key (defaults to NVIDIA_API_KEY env var)
            **kwargs: Additional configuration options
        """
        api_key = api_key or os.getenv("NVIDIA_API_KEY")
        if not api_key:
            raise ValueError("NVIDIA_API_KEY environment variable or api_key parameter is required")
        
        super().__init__(
            model_name="nvidia/nv-rerankqa-mistral-4b-v3",
            api_key=api_key,
            **kwargs
        )
        
        # Configuration
        self.base_url = kwargs.get("base_url", "https://ai.api.nvidia.com/v1")
        self.timeout = kwargs.get("timeout", 300)  # 5 minutes for batch operations
        self.max_retries = kwargs.get("max_retries", 3)
        self.retry_delay = kwargs.get("retry_delay", 1.0)
        
        # Reranking settings
        self.default_threshold = kwargs.get("default_threshold", 0.7)
        self.max_passages_per_request = kwargs.get("max_passages_per_request", 100)
        self.max_concurrent_requests = kwargs.get("max_concurrent_requests", 5)
        
        # HTTP client configuration
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        )
        
        # Concurrency control
        self.request_semaphore = asyncio.Semaphore(self.max_concurrent_requests)
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
    
    def _format_passages_for_api(self, passages: List[str]) -> List[Dict[str, str]]:
        """
        Format passages for NVIDIA API.
        
        Args:
            passages: List of passage strings
            
        Returns:
            List of formatted passage dictionaries
        """
        formatted_passages = []
        for passage in passages:
            formatted_passages.append({"text": passage})
        return formatted_passages
    
    def _chunk_passages(self, passages: List[str], chunk_size: int) -> List[List[str]]:
        """
        Split passages into chunks for batch processing.
        
        Args:
            passages: List of passages to chunk
            chunk_size: Maximum size of each chunk
            
        Returns:
            List of passage chunks
        """
        chunks = []
        for i in range(0, len(passages), chunk_size):
            chunks.append(passages[i:i + chunk_size])
        return chunks
    
    async def _make_reranking_request(
        self, 
        query: str, 
        passages: List[str],
        model: Optional[str] = None,
        truncate: str = "NONE"
    ) -> RerankingResponse:
        """
        Make reranking request to NVIDIA API.
        
        Args:
            query: Query text to rank passages against
            passages: List of passages to rank
            model: Model to use (defaults to instance model)
            truncate: Truncation strategy
            
        Returns:
            RerankingResponse: API response
            
        Raises:
            MelanieRerankingError: On API or network errors
        """
        model = model or self.model_name
        
        payload = {
            "model": model,
            "query": {"text": query},
            "passages": self._format_passages_for_api(passages),
            "truncate": truncate,
            "messages": [{"role": "user", "content": ""}]  # Required by API
        }
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Making reranking request for {len(passages)} passages (attempt {attempt + 1})")
                
                # Use the specific reranking endpoint
                endpoint = f"{self.base_url}/retrieval/{model}/reranking"
                response = await self.client.post(endpoint, json=payload)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    if attempt < self.max_retries:
                        logger.warning(f"Rate limited, waiting {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        raise MelanieRerankingRateLimitError(retry_after)
                
                # Handle other HTTP errors
                if response.status_code >= 400:
                    error_data = response.json() if response.content else {}
                    error_message = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                    raise MelanieRerankingError(f"API error: {error_message}")
                
                # Success
                response_data = response.json()
                return RerankingResponse(**response_data)
                
            except httpx.TimeoutException as e:
                last_exception = MelanieRerankingTimeoutError(self.timeout)
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Request timed out, retrying in {delay} seconds")
                    await asyncio.sleep(delay)
                    continue
                    
            except httpx.RequestError as e:
                last_exception = MelanieRerankingError(f"Network error: {str(e)}")
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Network error, retrying in {delay} seconds")
                    await asyncio.sleep(delay)
                    continue
                    
            except Exception as e:
                last_exception = MelanieRerankingError(f"Unexpected error: {str(e)}")
                break
        
        # All retries exhausted
        raise last_exception or MelanieRerankingError("Request failed after all retries")
    
    async def rerank_passages(
        self, 
        query: str, 
        passages: List[str],
        threshold: Optional[float] = None,
        model: Optional[str] = None
    ) -> BatchRerankingResult:
        """
        Rerank passages based on relevance to query.
        
        Args:
            query: Query text to rank passages against
            passages: List of passages to rank
            threshold: Minimum score threshold (defaults to instance default)
            model: Model to use (defaults to instance model)
            
        Returns:
            BatchRerankingResult: Reranking results
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        if not passages:
            raise ValueError("At least one passage is required")
        
        threshold = threshold if threshold is not None else self.default_threshold
        start_time = time.time()
        
        # Validate passages
        for i, passage in enumerate(passages):
            if not passage or not passage.strip():
                raise ValueError(f"Passage at index {i} cannot be empty")
        
        # Process in chunks if needed
        if len(passages) <= self.max_passages_per_request:
            # Single request
            async with self.request_semaphore:
                response = await self._make_reranking_request(query, passages, model)
            
            # Process results
            results = []
            for ranking in response.rankings:
                original_index = ranking.get("index", 0)
                score = ranking.get("score", 0.0)
                
                if original_index < len(passages):
                    result = RerankingResult(
                        query=query,
                        passage=passages[original_index],
                        score=score,
                        original_index=original_index,
                        reranked_index=len(results),
                        model=response.model
                    )
                    results.append(result)
            
        else:
            # Multiple requests for large passage sets
            passage_chunks = self._chunk_passages(passages, self.max_passages_per_request)
            
            async def process_chunk(chunk: List[str], chunk_offset: int) -> List[RerankingResult]:
                async with self.request_semaphore:
                    response = await self._make_reranking_request(query, chunk, model)
                
                chunk_results = []
                for ranking in response.rankings:
                    chunk_index = ranking.get("index", 0)
                    score = ranking.get("score", 0.0)
                    original_index = chunk_offset + chunk_index
                    
                    if chunk_index < len(chunk):
                        result = RerankingResult(
                            query=query,
                            passage=chunk[chunk_index],
                            score=score,
                            original_index=original_index,
                            reranked_index=0,  # Will be updated after sorting
                            model=response.model
                        )
                        chunk_results.append(result)
                
                return chunk_results
            
            # Process chunks concurrently
            chunk_tasks = []
            chunk_offset = 0
            
            for chunk in passage_chunks:
                task = process_chunk(chunk, chunk_offset)
                chunk_tasks.append(task)
                chunk_offset += len(chunk)
            
            chunk_results = await asyncio.gather(*chunk_tasks)
            
            # Flatten and sort by score
            results = []
            for chunk_result in chunk_results:
                results.extend(chunk_result)
            
            # Sort by score (descending)
            results.sort(key=lambda x: x.score, reverse=True)
            
            # Update reranked indices
            for i, result in enumerate(results):
                result.reranked_index = i
        
        # Filter by threshold
        filtered_results = [r for r in results if r.score >= threshold]
        
        processing_time = time.time() - start_time
        
        return BatchRerankingResult(
            query=query,
            results=filtered_results,
            processing_time=processing_time,
            total_passages=len(passages),
            filtered_count=len(filtered_results)
        )
    
    async def rerank_for_rag(
        self, 
        query: str, 
        chunks: List[Dict[str, Any]],
        threshold: Optional[float] = None,
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank chunks for RAG system integration.
        
        Args:
            query: Query text to rank chunks against
            chunks: List of chunk dictionaries with 'content' or 'text' field
            threshold: Minimum score threshold
            top_k: Maximum number of results to return
            
        Returns:
            List of reranked chunks with scores and metadata
        """
        if not chunks:
            return []
        
        # Extract text content from chunks
        passages = []
        for i, chunk in enumerate(chunks):
            text = chunk.get('content') or chunk.get('text', '')
            if not text:
                logger.warning(f"Chunk at index {i} has no text content")
                text = f"[Empty chunk {i}]"
            passages.append(text)
        
        # Perform reranking
        rerank_result = await self.rerank_passages(query, passages, threshold)
        
        # Combine results with original chunk metadata
        reranked_chunks = []
        
        for result in rerank_result.results:
            original_chunk = chunks[result.original_index]
            
            # Create enhanced chunk with reranking info
            reranked_chunk = original_chunk.copy()
            reranked_chunk.update({
                "rerank_score": result.score,
                "rerank_model": result.model,
                "original_index": result.original_index,
                "reranked_index": result.reranked_index,
                "query": query,
                "reranked_at": time.time()
            })
            
            reranked_chunks.append(reranked_chunk)
        
        # Apply top_k limit if specified
        if top_k is not None and top_k > 0:
            reranked_chunks = reranked_chunks[:top_k]
        
        return reranked_chunks
    
    async def get_top_passages(
        self, 
        query: str, 
        passages: List[str],
        top_k: int = 20,
        threshold: Optional[float] = None
    ) -> List[Tuple[str, float]]:
        """
        Get top-k most relevant passages with scores.
        
        Args:
            query: Query text
            passages: List of passages to rank
            top_k: Number of top passages to return
            threshold: Minimum score threshold
            
        Returns:
            List of tuples (passage, score) sorted by relevance
        """
        rerank_result = await self.rerank_passages(query, passages, threshold)
        
        # Return top-k results as tuples
        top_results = []
        for result in rerank_result.results[:top_k]:
            top_results.append((result.passage, result.score))
        
        return top_results
    
    # BaseAIModel interface implementation
    async def generate(
        self, 
        messages: List[ChatMessage], 
        tools: Optional[List[Tool]] = None,
        **kwargs
    ) -> ChatCompletionResponse:
        """
        Generate reranking results based on chat messages (BaseAIModel interface).
        
        This method adapts the reranking functionality to the BaseAIModel interface
        by extracting query and passages from messages and returning rankings in chat format.
        """
        if len(messages) < 2:
            raise MelanieRerankingError("At least 2 messages required: query and passages")
        
        # First message is the query
        query = messages[0].content.strip()
        if not query:
            raise MelanieRerankingError("Query message cannot be empty")
        
        # Remaining messages are passages
        passages = []
        for msg in messages[1:]:
            if msg.content.strip():
                passages.append(msg.content.strip())
        
        if not passages:
            raise MelanieRerankingError("At least one passage is required")
        
        # Perform reranking
        rerank_result = await self.rerank_passages(query, passages)
        
        # Format as chat completion response
        ranking_content = {
            "query": query,
            "rankings": [
                {
                    "passage": result.passage,
                    "score": result.score,
                    "original_index": result.original_index,
                    "reranked_index": result.reranked_index
                }
                for result in rerank_result.results
            ],
            "total_passages": rerank_result.total_passages,
            "filtered_count": rerank_result.filtered_count,
            "processing_time": rerank_result.processing_time,
            "model": self.model_name,
            "threshold": self.default_threshold
        }
        
        choice = Choice(
            index=0,
            message={
                "role": "assistant",
                "content": json.dumps(ranking_content, indent=2)
            },
            finish_reason="stop"
        )
        
        # Estimate token usage
        total_chars = len(query) + sum(len(p) for p in passages)
        estimated_tokens = total_chars // 4
        
        usage = Usage(
            prompt_tokens=estimated_tokens,
            completion_tokens=0,
            total_tokens=estimated_tokens
        )
        
        return ChatCompletionResponse(
            id=f"rerank-{int(time.time())}-{hash(query) % 10000}",
            object="chat.completion",
            created=int(time.time()),
            model=self.model_name,
            choices=[choice],
            usage=usage
        )
    
    async def validate_request(self, request: ChatCompletionRequest) -> bool:
        """
        Validate if request is compatible with reranking model.
        
        Args:
            request: Chat completion request
            
        Returns:
            bool: True if request is valid for reranking
        """
        try:
            # Need at least 2 messages (query + passages)
            if not request.messages or len(request.messages) < 2:
                return False
            
            # Check if messages contain valid content
            query = request.messages[0].content.strip()
            if not query:
                return False
            
            # Check if we have valid passages
            valid_passages = sum(
                1 for msg in request.messages[1:] 
                if msg.content and msg.content.strip()
            )
            
            if valid_passages == 0:
                return False
            
            # Check total content length
            total_chars = sum(len(msg.content) for msg in request.messages)
            if total_chars > 500000:  # 500k character limit
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Request validation failed: {str(e)}")
            return False
    
    def get_capabilities(self) -> List[str]:
        """
        Get list of reranking model capabilities.
        
        Returns:
            List[str]: List of capability names
        """
        return [
            "passage_reranking",
            "relevance_scoring",
            "batch_processing",
            "rag_integration",
            "query_passage_matching",
            "semantic_ranking",
            "threshold_filtering",
            "top_k_selection"
        ]
    
    def get_max_tokens(self) -> int:
        """
        Get maximum token limit for reranking model.
        
        Returns:
            int: Maximum token limit per request
        """
        return 32768  # Typical limit for reranking models
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get comprehensive model information.
        
        Returns:
            Dict: Model information including capabilities and limits
        """
        info = super().get_model_info()
        info.update({
            "provider": "NVIDIA",
            "version": "nv-rerankqa-mistral-4b-v3",
            "max_passages_per_request": self.max_passages_per_request,
            "max_concurrent_requests": self.max_concurrent_requests,
            "default_threshold": self.default_threshold,
            "supports_batch_processing": True,
            "supports_rag_integration": True,
            "supports_threshold_filtering": True,
            "score_range": [0.0, 1.0],
            "pricing_per_1k_tokens": {
                "reranking": 0.0005  # Example pricing
            }
        })
        return info


# Convenience functions for backward compatibility
async def rerank_passages_async(
    query: str, 
    passages: List[str], 
    model: str = "nvidia/nv-rerankqa-mistral-4b-v3",
    threshold: Optional[float] = None
) -> Dict[str, Any]:
    """
    Async version of rerank_passages function for backward compatibility.
    
    Args:
        query: Query text
        passages: List of passages to rank
        model: Model to use
        threshold: Score threshold
        
    Returns:
        Dictionary with reranking results
    """
    async with MelanieReranking() as reranking_model:
        result = await reranking_model.rerank_passages(query, passages, threshold, model)
        
        # Format for backward compatibility
        return {
            "rankings": [
                {
                    "index": r.original_index,
                    "score": r.score,
                    "passage": r.passage
                }
                for r in result.results
            ],
            "model": model,
            "query": query,
            "total_passages": result.total_passages,
            "filtered_count": result.filtered_count,
            "processing_time": result.processing_time
        }


# Example usage and testing
if __name__ == "__main__":
    async def test_reranking_functionality():
        """Test reranking functionality."""
        try:
            async with MelanieReranking() as model:
                # Test basic reranking
                query = "What is the GPU memory bandwidth of H100 SXM?"
                passages = [
                    "The Hopper GPU is paired with the Grace CPU using NVIDIA's ultra-fast chip-to-chip interconnect, delivering 900GB/s of bandwidth, 7X faster than PCIe Gen5.",
                    "A100 provides up to 20X higher performance over the prior generation and can be partitioned into seven GPU instances to dynamically adjust to shifting demands.",
                    "Accelerated servers with H100 deliver the compute power—along with 3 terabytes per second (TB/s) of memory bandwidth per GPU and scalability with NVLink and NVSwitch™."
                ]
                
                result = await model.rerank_passages(query, passages)
                print(f"Reranked {result.total_passages} passages")
                print(f"Filtered to {result.filtered_count} passages above threshold")
                print(f"Processing time: {result.processing_time:.2f}s")
                
                for i, r in enumerate(result.results):
                    print(f"Rank {i+1}: Score {r.score:.3f} - Original index {r.original_index}")
                
                # Test RAG integration
                chunks = [
                    {"content": passage, "metadata": {"source": f"doc_{i}"}}
                    for i, passage in enumerate(passages)
                ]
                
                rag_results = await model.rerank_for_rag(query, chunks, top_k=2)
                print(f"\nRAG integration: {len(rag_results)} top chunks")
                
                # Test top passages
                top_passages = await model.get_top_passages(query, passages, top_k=2)
                print(f"\nTop 2 passages:")
                for passage, score in top_passages:
                    print(f"Score {score:.3f}: {passage[:100]}...")
                
        except Exception as e:
            print(f"Test failed: {str(e)}")
    
    # Run test
    asyncio.run(test_reranking_functionality())