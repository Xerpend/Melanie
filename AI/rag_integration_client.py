"""
RAG Integration Client for Embedding and Reranking Models.

This module provides async clients that integrate the Python embedding and reranking
models with the Rust RAG engine, enabling efficient batch processing and sub-chunking
for optimal RAG performance.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from melanie_embedding_model import MelanieEmbedding, EmbeddingResult, BatchEmbeddingResult
from melanie_reranking_model import MelanieReranking, RerankingResult, BatchRerankingResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SubChunk:
    """Sub-chunk for reranking (150-250 tokens)."""
    parent_chunk_id: str
    content: str
    start_offset: int
    end_offset: int
    token_count: int
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class RagChunk:
    """RAG chunk with embedding and metadata."""
    id: str
    content: str
    embedding: Optional[List[float]] = None
    token_count: int = 0
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[float] = None


@dataclass
class RetrievalCandidate:
    """Candidate chunk from vector similarity search."""
    chunk: RagChunk
    similarity_score: float
    original_index: int


@dataclass
class RerankingCandidate:
    """Candidate after reranking with relevance score."""
    chunk: RagChunk
    similarity_score: float
    rerank_score: float
    final_score: float
    original_index: int
    reranked_index: int


class RagEmbeddingClient:
    """
    Async client for embedding operations optimized for RAG workflows.
    
    Provides efficient batch processing and integration with the Rust RAG engine.
    """
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize RAG embedding client.
        
        Args:
            api_key: NVIDIA API key
            **kwargs: Additional configuration options
        """
        self.api_key = api_key
        self.config = kwargs
        
        # Batch processing settings
        self.max_batch_size = kwargs.get("max_batch_size", 100)
        self.max_concurrent_batches = kwargs.get("max_concurrent_batches", 5)
        
        # Performance settings
        self.enable_parallel_processing = kwargs.get("enable_parallel_processing", True)
        self.thread_pool_size = kwargs.get("thread_pool_size", 4)
        
        # Initialize thread pool for CPU-bound operations
        if self.enable_parallel_processing:
            self.thread_pool = ThreadPoolExecutor(max_workers=self.thread_pool_size)
        else:
            self.thread_pool = None
        
        # Embedding model instance (will be created when needed)
        self._embedding_model = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._embedding_model = MelanieEmbedding(api_key=self.api_key, **self.config)
        await self._embedding_model.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._embedding_model:
            await self._embedding_model.__aexit__(exc_type, exc_val, exc_tb)
        
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)
    
    async def embed_chunks_for_rag(
        self, 
        chunks: List[RagChunk],
        batch_size: Optional[int] = None
    ) -> List[RagChunk]:
        """
        Embed chunks for RAG system with optimized batch processing.
        
        Args:
            chunks: List of RAG chunks to embed
            batch_size: Override default batch size
            
        Returns:
            List of chunks with embeddings added
        """
        if not chunks:
            return []
        
        batch_size = batch_size or self.max_batch_size
        start_time = time.time()
        
        logger.info(f"Embedding {len(chunks)} chunks for RAG system")
        
        # Extract texts and metadata
        texts = [chunk.content for chunk in chunks]
        chunk_metadata = []
        
        for chunk in chunks:
            metadata = {
                "chunk_id": chunk.id,
                "token_count": chunk.token_count,
                "created_at": chunk.created_at or time.time()
            }
            if chunk.metadata:
                metadata.update(chunk.metadata)
            chunk_metadata.append(metadata)
        
        # Generate embeddings using the embedding model
        rag_embeddings = await self._embedding_model.embed_for_rag(texts, chunk_metadata)
        
        # Update chunks with embeddings
        embedded_chunks = []
        for i, (chunk, embedding_data) in enumerate(zip(chunks, rag_embeddings)):
            updated_chunk = RagChunk(
                id=chunk.id,
                content=chunk.content,
                embedding=embedding_data["embedding"],
                token_count=chunk.token_count,
                metadata=chunk.metadata,
                created_at=chunk.created_at
            )
            embedded_chunks.append(updated_chunk)
        
        processing_time = time.time() - start_time
        logger.info(f"Embedded {len(chunks)} chunks in {processing_time:.2f}s")
        
        return embedded_chunks
    
    async def embed_query_for_retrieval(self, query: str) -> List[float]:
        """
        Embed query for vector similarity search.
        
        Args:
            query: Query text to embed
            
        Returns:
            Query embedding vector
        """
        if not query.strip():
            raise ValueError("Query cannot be empty")
        
        logger.debug(f"Embedding query for retrieval: '{query[:50]}...'")
        
        embedding = await self._embedding_model.embed_query_for_retrieval(query)
        
        logger.debug(f"Generated query embedding with dimension {len(embedding)}")
        return embedding
    
    def _estimate_token_count(self, text: str) -> int:
        """
        Estimate token count for text (rough approximation).
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        # Rough estimation: 1 token ≈ 4 characters
        return len(text) // 4
    
    async def create_sub_chunks(
        self, 
        chunks: List[RagChunk],
        target_token_range: Tuple[int, int] = (150, 250)
    ) -> List[SubChunk]:
        """
        Create sub-chunks from larger chunks for reranking.
        
        Args:
            chunks: List of chunks to sub-divide
            target_token_range: Target token range for sub-chunks (min, max)
            
        Returns:
            List of sub-chunks
        """
        if not chunks:
            return []
        
        min_tokens, max_tokens = target_token_range
        sub_chunks = []
        
        logger.info(f"Creating sub-chunks from {len(chunks)} chunks (target: {min_tokens}-{max_tokens} tokens)")
        
        for chunk in chunks:
            chunk_tokens = chunk.token_count or self._estimate_token_count(chunk.content)
            
            if chunk_tokens <= max_tokens:
                # Chunk is already small enough, use as-is
                sub_chunk = SubChunk(
                    parent_chunk_id=chunk.id,
                    content=chunk.content,
                    start_offset=0,
                    end_offset=len(chunk.content),
                    token_count=chunk_tokens,
                    metadata=chunk.metadata
                )
                sub_chunks.append(sub_chunk)
            else:
                # Split chunk into sub-chunks
                words = chunk.content.split()
                current_words = []
                current_tokens = 0
                start_word_idx = 0
                
                for i, word in enumerate(words):
                    word_tokens = self._estimate_token_count(word)
                    
                    if current_tokens + word_tokens > max_tokens and current_words:
                        # Create sub-chunk from current words
                        sub_content = " ".join(current_words)
                        start_offset = len(" ".join(words[:start_word_idx]))
                        if start_word_idx > 0:
                            start_offset += 1  # Account for space
                        end_offset = start_offset + len(sub_content)
                        
                        sub_chunk = SubChunk(
                            parent_chunk_id=chunk.id,
                            content=sub_content,
                            start_offset=start_offset,
                            end_offset=end_offset,
                            token_count=current_tokens,
                            metadata=chunk.metadata
                        )
                        sub_chunks.append(sub_chunk)
                        
                        # Reset for next sub-chunk
                        current_words = [word]
                        current_tokens = word_tokens
                        start_word_idx = i
                    else:
                        current_words.append(word)
                        current_tokens += word_tokens
                
                # Handle remaining words
                if current_words:
                    sub_content = " ".join(current_words)
                    start_offset = len(" ".join(words[:start_word_idx]))
                    if start_word_idx > 0:
                        start_offset += 1
                    end_offset = start_offset + len(sub_content)
                    
                    sub_chunk = SubChunk(
                        parent_chunk_id=chunk.id,
                        content=sub_content,
                        start_offset=start_offset,
                        end_offset=end_offset,
                        token_count=current_tokens,
                        metadata=chunk.metadata
                    )
                    sub_chunks.append(sub_chunk)
        
        logger.info(f"Created {len(sub_chunks)} sub-chunks from {len(chunks)} original chunks")
        return sub_chunks


class RagRerankingClient:
    """
    Async client for reranking operations optimized for RAG workflows.
    
    Provides efficient batch processing with 0.7 threshold filtering and
    integration with the Rust RAG engine.
    """
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize RAG reranking client.
        
        Args:
            api_key: NVIDIA API key
            **kwargs: Additional configuration options
        """
        self.api_key = api_key
        self.config = kwargs
        
        # Reranking settings
        self.default_threshold = kwargs.get("default_threshold", 0.7)
        self.max_candidates = kwargs.get("max_candidates", 100)
        self.max_concurrent_requests = kwargs.get("max_concurrent_requests", 5)
        
        # Performance settings
        self.enable_diversity_filtering = kwargs.get("enable_diversity_filtering", True)
        self.diversity_threshold = kwargs.get("diversity_threshold", 0.8)
        
        # Reranking model instance (will be created when needed)
        self._reranking_model = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._reranking_model = MelanieReranking(api_key=self.api_key, **self.config)
        await self._reranking_model.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._reranking_model:
            await self._reranking_model.__aexit__(exc_type, exc_val, exc_tb)
    
    async def rerank_sub_chunks(
        self,
        query: str,
        sub_chunks: List[SubChunk],
        threshold: Optional[float] = None,
        top_k: Optional[int] = None
    ) -> List[Tuple[SubChunk, float]]:
        """
        Rerank sub-chunks based on query relevance with threshold filtering.
        
        Args:
            query: Query text to rank against
            sub_chunks: List of sub-chunks to rerank
            threshold: Minimum relevance score (defaults to 0.7)
            top_k: Maximum number of results to return
            
        Returns:
            List of tuples (sub_chunk, relevance_score) sorted by relevance
        """
        if not sub_chunks:
            return []
        
        threshold = threshold if threshold is not None else self.default_threshold
        
        logger.info(f"Reranking {len(sub_chunks)} sub-chunks with threshold {threshold}")
        
        # Extract passages for reranking
        passages = [sub_chunk.content for sub_chunk in sub_chunks]
        
        # Perform reranking
        rerank_result = await self._reranking_model.rerank_passages(
            query=query,
            passages=passages,
            threshold=threshold
        )
        
        # Map results back to sub-chunks
        reranked_sub_chunks = []
        
        for result in rerank_result.results:
            original_sub_chunk = sub_chunks[result.original_index]
            reranked_sub_chunks.append((original_sub_chunk, result.score))
        
        # Apply top_k limit if specified
        if top_k is not None and top_k > 0:
            reranked_sub_chunks = reranked_sub_chunks[:top_k]
        
        logger.info(f"Filtered to {len(reranked_sub_chunks)} sub-chunks above threshold {threshold}")
        
        return reranked_sub_chunks
    
    async def rerank_retrieval_candidates(
        self,
        query: str,
        candidates: List[RetrievalCandidate],
        threshold: Optional[float] = None,
        top_k: Optional[int] = None,
        enable_diversity: Optional[bool] = None
    ) -> List[RerankingCandidate]:
        """
        Rerank retrieval candidates with comprehensive scoring and filtering.
        
        Args:
            query: Query text to rank against
            candidates: List of retrieval candidates
            threshold: Minimum relevance score (defaults to 0.7)
            top_k: Maximum number of results to return
            enable_diversity: Enable diversity filtering
            
        Returns:
            List of reranking candidates sorted by final score
        """
        if not candidates:
            return []
        
        threshold = threshold if threshold is not None else self.default_threshold
        enable_diversity = enable_diversity if enable_diversity is not None else self.enable_diversity_filtering
        
        logger.info(f"Reranking {len(candidates)} retrieval candidates")
        
        # Prepare chunks for reranking
        chunks = []
        for candidate in candidates:
            chunk_dict = {
                "content": candidate.chunk.content,
                "metadata": {
                    "chunk_id": candidate.chunk.id,
                    "similarity_score": candidate.similarity_score,
                    "original_index": candidate.original_index
                }
            }
            if candidate.chunk.metadata:
                chunk_dict["metadata"].update(candidate.chunk.metadata)
            chunks.append(chunk_dict)
        
        # Perform reranking
        reranked_chunks = await self._reranking_model.rerank_for_rag(
            query=query,
            chunks=chunks,
            threshold=threshold,
            top_k=top_k
        )
        
        # Convert to reranking candidates
        reranking_candidates = []
        
        for i, reranked_chunk in enumerate(reranked_chunks):
            original_index = reranked_chunk["metadata"]["original_index"]
            original_candidate = candidates[original_index]
            
            # Calculate final score (weighted combination)
            similarity_score = original_candidate.similarity_score
            rerank_score = reranked_chunk["rerank_score"]
            final_score = (similarity_score * 0.3) + (rerank_score * 0.7)
            
            reranking_candidate = RerankingCandidate(
                chunk=original_candidate.chunk,
                similarity_score=similarity_score,
                rerank_score=rerank_score,
                final_score=final_score,
                original_index=original_index,
                reranked_index=i
            )
            reranking_candidates.append(reranking_candidate)
        
        # Apply diversity filtering if enabled
        if enable_diversity and len(reranking_candidates) > 1:
            reranking_candidates = self._apply_diversity_filtering(
                reranking_candidates, 
                self.diversity_threshold
            )
        
        logger.info(f"Final result: {len(reranking_candidates)} reranked candidates")
        
        return reranking_candidates
    
    def _apply_diversity_filtering(
        self, 
        candidates: List[RerankingCandidate], 
        diversity_threshold: float
    ) -> List[RerankingCandidate]:
        """
        Apply diversity filtering to remove similar candidates.
        
        Args:
            candidates: List of reranking candidates
            diversity_threshold: Minimum diversity score (0.0 to 1.0)
            
        Returns:
            Filtered list with diverse candidates
        """
        if not candidates:
            return []
        
        diverse_candidates = [candidates[0]]  # Always include top result
        
        for candidate in candidates[1:]:
            is_diverse = True
            
            # Check diversity against all selected candidates
            for selected in diverse_candidates:
                diversity = self._calculate_content_diversity(
                    candidate.chunk.content, 
                    selected.chunk.content
                )
                
                if diversity < diversity_threshold:
                    is_diverse = False
                    break
            
            if is_diverse:
                diverse_candidates.append(candidate)
        
        logger.debug(f"Diversity filtering: {len(candidates)} -> {len(diverse_candidates)} candidates")
        
        return diverse_candidates
    
    def _calculate_content_diversity(self, text1: str, text2: str) -> float:
        """
        Calculate diversity score between two texts using Jaccard distance.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Diversity score (0.0 = identical, 1.0 = completely different)
        """
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        if union == 0:
            return 1.0  # Both texts are empty, consider them different
        
        jaccard_similarity = intersection / union
        return 1.0 - jaccard_similarity  # Convert to diversity (distance)


class RagIntegrationPipeline:
    """
    Complete RAG integration pipeline combining embedding and reranking.
    
    Provides end-to-end processing for RAG workflows with optimized
    batch processing and sub-chunking.
    """
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize RAG integration pipeline.
        
        Args:
            api_key: NVIDIA API key
            **kwargs: Additional configuration options
        """
        self.api_key = api_key
        self.config = kwargs
        
        # Pipeline settings
        self.sub_chunk_token_range = kwargs.get("sub_chunk_token_range", (150, 250))
        self.rerank_threshold = kwargs.get("rerank_threshold", 0.7)
        self.max_final_results = kwargs.get("max_final_results", 20)
        
        # Client instances
        self.embedding_client = None
        self.reranking_client = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.embedding_client = RagEmbeddingClient(api_key=self.api_key, **self.config)
        self.reranking_client = RagRerankingClient(api_key=self.api_key, **self.config)
        
        await self.embedding_client.__aenter__()
        await self.reranking_client.__aenter__()
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.reranking_client:
            await self.reranking_client.__aexit__(exc_type, exc_val, exc_tb)
        
        if self.embedding_client:
            await self.embedding_client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def process_documents_for_rag(
        self, 
        documents: List[Dict[str, Any]]
    ) -> List[RagChunk]:
        """
        Process documents for RAG system ingestion.
        
        Args:
            documents: List of document dictionaries with 'content' and optional 'metadata'
            
        Returns:
            List of processed RAG chunks with embeddings
        """
        if not documents:
            return []
        
        logger.info(f"Processing {len(documents)} documents for RAG ingestion")
        
        # Convert documents to RAG chunks
        chunks = []
        for i, doc in enumerate(documents):
            chunk = RagChunk(
                id=f"chunk_{i}_{int(time.time())}",
                content=doc["content"],
                token_count=self.embedding_client._estimate_token_count(doc["content"]),
                metadata=doc.get("metadata", {}),
                created_at=time.time()
            )
            chunks.append(chunk)
        
        # Embed chunks
        embedded_chunks = await self.embedding_client.embed_chunks_for_rag(chunks)
        
        logger.info(f"Successfully processed {len(embedded_chunks)} chunks for RAG")
        
        return embedded_chunks
    
    async def retrieve_and_rerank(
        self,
        query: str,
        retrieval_candidates: List[RetrievalCandidate],
        use_sub_chunking: bool = True
    ) -> List[RerankingCandidate]:
        """
        Complete retrieval and reranking pipeline.
        
        Args:
            query: Query text
            retrieval_candidates: Candidates from vector similarity search
            use_sub_chunking: Whether to use sub-chunking for reranking
            
        Returns:
            Final reranked candidates
        """
        if not retrieval_candidates:
            return []
        
        logger.info(f"Processing query: '{query[:50]}...' with {len(retrieval_candidates)} candidates")
        
        if use_sub_chunking:
            # Create sub-chunks for more granular reranking
            chunks = [candidate.chunk for candidate in retrieval_candidates]
            sub_chunks = await self.embedding_client.create_sub_chunks(
                chunks, 
                self.sub_chunk_token_range
            )
            
            # Rerank sub-chunks
            reranked_sub_chunks = await self.reranking_client.rerank_sub_chunks(
                query=query,
                sub_chunks=sub_chunks,
                threshold=self.rerank_threshold
            )
            
            # Map back to original chunks and aggregate scores
            chunk_scores = {}
            for sub_chunk, score in reranked_sub_chunks:
                parent_id = sub_chunk.parent_chunk_id
                if parent_id not in chunk_scores:
                    chunk_scores[parent_id] = []
                chunk_scores[parent_id].append(score)
            
            # Create final candidates with aggregated scores
            final_candidates = []
            chunk_id_to_candidate = {candidate.chunk.id: candidate for candidate in retrieval_candidates}
            
            for chunk_id, scores in chunk_scores.items():
                if chunk_id in chunk_id_to_candidate:
                    original_candidate = chunk_id_to_candidate[chunk_id]
                    
                    # Use maximum sub-chunk score as the rerank score
                    max_rerank_score = max(scores)
                    final_score = (original_candidate.similarity_score * 0.3) + (max_rerank_score * 0.7)
                    
                    reranking_candidate = RerankingCandidate(
                        chunk=original_candidate.chunk,
                        similarity_score=original_candidate.similarity_score,
                        rerank_score=max_rerank_score,
                        final_score=final_score,
                        original_index=original_candidate.original_index,
                        reranked_index=len(final_candidates)
                    )
                    final_candidates.append(reranking_candidate)
            
            # Sort by final score
            final_candidates.sort(key=lambda x: x.final_score, reverse=True)
            
            # Update reranked indices
            for i, candidate in enumerate(final_candidates):
                candidate.reranked_index = i
        
        else:
            # Direct reranking without sub-chunking
            final_candidates = await self.reranking_client.rerank_retrieval_candidates(
                query=query,
                candidates=retrieval_candidates,
                threshold=self.rerank_threshold
            )
        
        # Apply final result limit
        if len(final_candidates) > self.max_final_results:
            final_candidates = final_candidates[:self.max_final_results]
        
        logger.info(f"Final pipeline result: {len(final_candidates)} reranked candidates")
        
        return final_candidates


# Convenience functions for backward compatibility
async def embed_documents_for_rag(
    documents: List[Dict[str, Any]], 
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Convenience function to embed documents for RAG system.
    
    Args:
        documents: List of document dictionaries
        api_key: NVIDIA API key
        
    Returns:
        List of embedded document dictionaries
    """
    async with RagIntegrationPipeline(api_key=api_key) as pipeline:
        embedded_chunks = await pipeline.process_documents_for_rag(documents)
        
        # Convert back to dictionaries
        result = []
        for chunk in embedded_chunks:
            doc_dict = {
                "id": chunk.id,
                "content": chunk.content,
                "embedding": chunk.embedding,
                "token_count": chunk.token_count,
                "metadata": chunk.metadata or {},
                "created_at": chunk.created_at
            }
            result.append(doc_dict)
        
        return result


async def rerank_with_sub_chunking(
    query: str,
    candidates: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """
    Convenience function to rerank candidates with sub-chunking.
    
    Args:
        query: Query text
        candidates: List of candidate dictionaries
        api_key: NVIDIA API key
        threshold: Reranking threshold
        
    Returns:
        List of reranked candidate dictionaries
    """
    # Convert to internal format
    retrieval_candidates = []
    for i, candidate in enumerate(candidates):
        chunk = RagChunk(
            id=candidate.get("id", f"chunk_{i}"),
            content=candidate["content"],
            embedding=candidate.get("embedding"),
            token_count=candidate.get("token_count", 0),
            metadata=candidate.get("metadata", {})
        )
        
        retrieval_candidate = RetrievalCandidate(
            chunk=chunk,
            similarity_score=candidate.get("similarity_score", 0.0),
            original_index=i
        )
        retrieval_candidates.append(retrieval_candidate)
    
    # Process with pipeline
    async with RagIntegrationPipeline(api_key=api_key, rerank_threshold=threshold) as pipeline:
        reranked_candidates = await pipeline.retrieve_and_rerank(
            query=query,
            retrieval_candidates=retrieval_candidates,
            use_sub_chunking=True
        )
        
        # Convert back to dictionaries
        result = []
        for candidate in reranked_candidates:
            result_dict = {
                "id": candidate.chunk.id,
                "content": candidate.chunk.content,
                "similarity_score": candidate.similarity_score,
                "rerank_score": candidate.rerank_score,
                "final_score": candidate.final_score,
                "original_index": candidate.original_index,
                "reranked_index": candidate.reranked_index,
                "metadata": candidate.chunk.metadata or {}
            }
            result.append(result_dict)
        
        return result


# Example usage and testing
if __name__ == "__main__":
    async def test_rag_integration():
        """Test RAG integration functionality."""
        try:
            # Sample documents
            documents = [
                {
                    "content": "The H100 GPU delivers exceptional performance with 3TB/s memory bandwidth for AI workloads.",
                    "metadata": {"source": "gpu_specs", "category": "hardware"}
                },
                {
                    "content": "NVIDIA's Grace CPU provides energy-efficient computing optimized for AI and HPC applications.",
                    "metadata": {"source": "cpu_specs", "category": "hardware"}
                },
                {
                    "content": "Memory hierarchy optimization is crucial for achieving peak performance in GPU computing.",
                    "metadata": {"source": "optimization_guide", "category": "performance"}
                }
            ]
            
            query = "What is the memory bandwidth of H100 GPU?"
            
            print("Testing RAG Integration Pipeline...")
            
            # Test document processing
            embedded_docs = await embed_documents_for_rag(documents)
            print(f"Embedded {len(embedded_docs)} documents")
            
            # Simulate retrieval candidates
            candidates = []
            for i, doc in enumerate(embedded_docs):
                candidate = {
                    "id": doc["id"],
                    "content": doc["content"],
                    "embedding": doc["embedding"],
                    "similarity_score": 0.8 - (i * 0.1),  # Decreasing scores
                    "metadata": doc["metadata"]
                }
                candidates.append(candidate)
            
            # Test reranking with sub-chunking
            reranked = await rerank_with_sub_chunking(query, candidates)
            print(f"Reranked to {len(reranked)} candidates")
            
            # Display results
            for i, result in enumerate(reranked):
                print(f"{i+1}. Score: {result['final_score']:.3f} - {result['content'][:60]}...")
            
            print("RAG integration test completed successfully!")
            
        except Exception as e:
            print(f"Test failed: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Run test
    asyncio.run(test_rag_integration())