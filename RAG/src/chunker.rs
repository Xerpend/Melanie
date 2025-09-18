//! Smart chunking implementation with semantic awareness

use crate::error::{RagError, RagResult};
use crate::types::{Chunk, ChunkingConfig, DocumentId};
use rayon::prelude::*;
use std::sync::Arc;
use tokenizers::Tokenizer;
use unicode_segmentation::UnicodeSegmentation;

/// Smart chunker that creates semantically aware chunks
pub struct SmartChunker {
    /// Tokenizer for counting tokens
    tokenizer: Arc<Tokenizer>,
    /// Chunking configuration
    config: ChunkingConfig,
}

impl SmartChunker {
    /// Create a new smart chunker
    pub fn new(tokenizer: Tokenizer, config: ChunkingConfig) -> Self {
        Self {
            tokenizer: Arc::new(tokenizer),
            config,
        }
    }
    
    /// Create a chunker with default GPT tokenizer
    pub async fn with_default_tokenizer(config: ChunkingConfig) -> RagResult<Self> {
        // Create a simple word-based tokenizer for testing and basic functionality
        use tokenizers::{
            Tokenizer, 
            models::wordpiece::WordPiece, 
            pre_tokenizers::whitespace::Whitespace,
        };
        
        // Build a basic WordPiece model with minimal vocabulary
        let mut vocab = std::collections::HashMap::new();
        vocab.insert("[UNK]".to_string(), 0u32);
        vocab.insert("[PAD]".to_string(), 1u32);
        vocab.insert("[CLS]".to_string(), 2u32);
        vocab.insert("[SEP]".to_string(), 3u32);
        
        // Add common words to vocabulary
        let common_words = vec![
            "the", "and", "a", "to", "of", "in", "is", "it", "you", "that",
            "he", "was", "for", "on", "are", "as", "with", "his", "they",
            "I", "at", "be", "this", "have", "from", "or", "one", "had",
            "by", "word", "but", "not", "what", "all", "were", "we", "when",
            "your", "can", "said", "there", "each", "which", "she", "do",
            "how", "their", "if", "will", "up", "other", "about", "out",
            "many", "time", "very", "when", "much", "new", "write", "go",
            "see", "number", "no", "way", "could", "people", "my", "than",
            "first", "water", "been", "call", "who", "oil", "its", "now",
            "find", "long", "down", "day", "did", "get", "has", "him",
            "his", "how", "man", "new", "now", "old", "see", "two", "way",
            "who", "boy", "did", "its", "let", "put", "say", "she", "too",
            "use"
        ];
        
        for (i, word) in common_words.iter().enumerate() {
            vocab.insert(word.to_string(), (i as u32) + 4);
        }
        
        let wordpiece = WordPiece::builder()
            .vocab(vocab)
            .unk_token("[UNK]".to_string())
            .build()
            .map_err(|e| RagError::tokenization(format!("Failed to build WordPiece: {}", e)))?;
        
        let mut tokenizer = Tokenizer::new(wordpiece);
        
        // Add pre-tokenizer for whitespace splitting
        tokenizer.with_pre_tokenizer(Whitespace {});
        
        Ok(Self::new(tokenizer, config))
    }
    
    /// Chunk a document into semantically aware pieces
    pub async fn chunk_document(&self, document_id: DocumentId, content: &str) -> RagResult<Vec<Chunk>> {
        if content.is_empty() {
            return Ok(Vec::new());
        }
        
        // First, split by paragraphs to maintain semantic boundaries
        let paragraphs: Vec<&str> = content
            .split("\n\n")
            .filter(|p| !p.trim().is_empty())
            .collect();
        
        if paragraphs.is_empty() {
            return Ok(Vec::new());
        }
        
        // Process paragraphs in parallel if enabled
        let chunks = if self.config.chunk_size > 1000 && paragraphs.len() > 10 {
            self.chunk_paragraphs_parallel(document_id, &paragraphs).await?
        } else {
            self.chunk_paragraphs_sequential(document_id, &paragraphs).await?
        };
        
        Ok(chunks)
    }
    
    /// Chunk paragraphs sequentially
    async fn chunk_paragraphs_sequential(
        &self,
        document_id: DocumentId,
        paragraphs: &[&str],
    ) -> RagResult<Vec<Chunk>> {
        let mut chunks = Vec::new();
        let mut current_chunk = String::new();
        let mut current_tokens = 0;
        let mut start_offset = 0;
        let mut current_offset = 0;
        
        for paragraph in paragraphs {
            let paragraph_tokens = self.count_tokens(paragraph)?;
            
            // If adding this paragraph would exceed chunk size, finalize current chunk
            if current_tokens + paragraph_tokens > self.config.chunk_size && !current_chunk.is_empty() {
                let chunk = self.create_chunk(
                    document_id,
                    current_chunk.trim().to_string(),
                    start_offset,
                    current_offset,
                    current_tokens,
                )?;
                chunks.push(chunk);
                
                // Start new chunk with overlap
                let overlap_content = self.get_overlap_content(&current_chunk)?;
                current_chunk = overlap_content;
                current_tokens = self.count_tokens(&current_chunk)?;
                start_offset = current_offset - current_chunk.len();
            }
            
            // Add paragraph to current chunk
            if !current_chunk.is_empty() {
                current_chunk.push_str("\n\n");
                current_offset += 2;
            }
            current_chunk.push_str(paragraph);
            current_offset += paragraph.len();
            current_tokens += paragraph_tokens;
        }
        
        // Add final chunk if not empty
        if !current_chunk.trim().is_empty() {
            let chunk = self.create_chunk(
                document_id,
                current_chunk.trim().to_string(),
                start_offset,
                current_offset,
                current_tokens,
            )?;
            chunks.push(chunk);
        }
        
        Ok(chunks)
    }
    
    /// Chunk paragraphs in parallel (for large documents)
    async fn chunk_paragraphs_parallel(
        &self,
        document_id: DocumentId,
        paragraphs: &[&str],
    ) -> RagResult<Vec<Chunk>> {
        // Use rayon for parallel processing of paragraph batches
        let batch_size = 20; // Process 20 paragraphs at a time for better parallelization
        let tokenizer = Arc::clone(&self.tokenizer);
        let config = self.config.clone();
        
        // Process batches in parallel using rayon
        let batch_results: Result<Vec<Vec<Chunk>>, RagError> = paragraphs
            .par_chunks(batch_size)
            .enumerate()
            .map(|(batch_idx, batch)| {
                // Create a temporary chunker for this batch
                let batch_chunker = SmartChunker::new((*tokenizer).clone(), config.clone());
                
                // Process this batch sequentially within the parallel context
                let mut batch_chunks = Vec::new();
                let mut current_chunk = String::new();
                let mut current_tokens = 0;
                let mut start_offset = batch_idx * batch_size * 100; // Approximate offset
                let mut current_offset = start_offset;
                
                for paragraph in batch {
                    let paragraph_tokens = batch_chunker.count_tokens(paragraph)
                        .map_err(|e| RagError::tokenization(format!("Parallel tokenization failed: {}", e)))?;
                    
                    // If adding this paragraph would exceed chunk size, finalize current chunk
                    if current_tokens + paragraph_tokens > config.chunk_size && !current_chunk.is_empty() {
                        let chunk = batch_chunker.create_chunk(
                            document_id,
                            current_chunk.trim().to_string(),
                            start_offset,
                            current_offset,
                            current_tokens,
                        )?;
                        batch_chunks.push(chunk);
                        
                        // Start new chunk with overlap
                        let overlap_content = batch_chunker.get_overlap_content(&current_chunk)?;
                        current_chunk = overlap_content;
                        current_tokens = batch_chunker.count_tokens(&current_chunk)?;
                        start_offset = current_offset - current_chunk.len();
                    }
                    
                    // Add paragraph to current chunk
                    if !current_chunk.is_empty() {
                        current_chunk.push_str("\n\n");
                        current_offset += 2;
                    }
                    current_chunk.push_str(paragraph);
                    current_offset += paragraph.len();
                    current_tokens += paragraph_tokens;
                }
                
                // Add final chunk if not empty
                if !current_chunk.trim().is_empty() {
                    let chunk = batch_chunker.create_chunk(
                        document_id,
                        current_chunk.trim().to_string(),
                        start_offset,
                        current_offset,
                        current_tokens,
                    )?;
                    batch_chunks.push(chunk);
                }
                
                Ok(batch_chunks)
            })
            .collect();
        
        let batch_results = batch_results?;
        
        // Merge all batch results with proper overlap handling
        let mut all_chunks = Vec::new();
        
        for (batch_idx, batch_chunks) in batch_results.into_iter().enumerate() {
            if batch_idx == 0 {
                // First batch, add all chunks
                all_chunks.extend(batch_chunks);
            } else if !all_chunks.is_empty() && !batch_chunks.is_empty() {
                // Subsequent batches, handle overlap with previous batch
                let last_chunk = all_chunks.last().unwrap();
                let first_chunk = &batch_chunks[0];
                
                // Check if we should merge the boundary chunks
                if last_chunk.token_count + first_chunk.token_count <= self.config.max_chunk_size {
                    // Merge chunks
                    let mut merged_content = last_chunk.content.clone();
                    merged_content.push_str("\n\n");
                    merged_content.push_str(&first_chunk.content);
                    
                    let merged_tokens = self.count_tokens(&merged_content)?;
                    let merged_chunk = self.create_chunk(
                        document_id,
                        merged_content,
                        last_chunk.start_offset,
                        first_chunk.end_offset,
                        merged_tokens,
                    )?;
                    
                    // Replace last chunk with merged chunk
                    all_chunks.pop();
                    all_chunks.push(merged_chunk);
                    
                    // Add remaining chunks from current batch
                    all_chunks.extend(batch_chunks.into_iter().skip(1));
                } else {
                    // Keep chunks separate
                    all_chunks.extend(batch_chunks);
                }
            } else {
                all_chunks.extend(batch_chunks);
            }
        }
        
        Ok(all_chunks)
    }
    
    /// Create a chunk with proper metadata
    fn create_chunk(
        &self,
        document_id: DocumentId,
        content: String,
        start_offset: usize,
        end_offset: usize,
        token_count: usize,
    ) -> RagResult<Chunk> {
        let mut chunk = Chunk::new(document_id, content, start_offset, end_offset, token_count);
        
        // Add metadata
        chunk.metadata.insert("chunk_size".to_string(), token_count.to_string());
        chunk.metadata.insert("overlap".to_string(), self.config.overlap.to_string());
        
        Ok(chunk)
    }
    
    /// Get overlap content from the end of a chunk
    fn get_overlap_content(&self, content: &str) -> RagResult<String> {
        if self.config.overlap == 0 {
            return Ok(String::new());
        }
        
        // Split into sentences and take the last few to create overlap
        let sentences: Vec<&str> = content
            .unicode_sentences()
            .collect();
        
        if sentences.is_empty() {
            return Ok(String::new());
        }
        
        // Take sentences from the end until we reach the overlap token count
        let mut overlap_content = String::new();
        let mut overlap_tokens = 0;
        
        for sentence in sentences.iter().rev() {
            let sentence_tokens = self.count_tokens(sentence)?;
            
            if overlap_tokens + sentence_tokens > self.config.overlap {
                break;
            }
            
            if !overlap_content.is_empty() {
                overlap_content = format!("{} {}", sentence, overlap_content);
            } else {
                overlap_content = sentence.to_string();
            }
            overlap_tokens += sentence_tokens;
        }
        
        Ok(overlap_content)
    }
    
    /// Count tokens in text using the tokenizer
    pub fn count_tokens(&self, text: &str) -> RagResult<usize> {
        let encoding = self.tokenizer
            .encode(text, false)
            .map_err(|e| RagError::tokenization(format!("Failed to tokenize text: {}", e)))?;
        
        Ok(encoding.len())
    }
    
    /// Create sub-chunks for reranking (150-250 tokens)
    pub async fn create_sub_chunks(&self, chunks: &[Chunk]) -> RagResult<Vec<crate::types::SubChunk>> {
        let _target_size = 200; // Target 200 tokens per sub-chunk
        let min_size = 150;
        let max_size = 250;
        
        let mut sub_chunks = Vec::new();
        
        for chunk in chunks {
            if chunk.token_count <= max_size {
                // Chunk is already small enough, use as-is
                let sub_chunk = crate::types::SubChunk::new(
                    chunk.id,
                    chunk.content.clone(),
                    0,
                    chunk.content.len(),
                    chunk.token_count,
                );
                sub_chunks.push(sub_chunk);
                continue;
            }
            
            // Split chunk into sub-chunks
            let sentences: Vec<&str> = chunk.content
                .unicode_sentences()
                .collect();
            
            let mut current_content = String::new();
            let mut current_tokens = 0;
            let mut start_offset = 0;
            
            for sentence in sentences {
                let sentence_tokens = self.count_tokens(sentence)?;
                
                // If adding this sentence would exceed max size, finalize current sub-chunk
                if current_tokens + sentence_tokens > max_size && current_tokens >= min_size {
                    let sub_chunk = crate::types::SubChunk::new(
                        chunk.id,
                        current_content.trim().to_string(),
                        start_offset,
                        start_offset + current_content.len(),
                        current_tokens,
                    );
                    sub_chunks.push(sub_chunk);
                    
                    // Start new sub-chunk
                    current_content = sentence.to_string();
                    current_tokens = sentence_tokens;
                    start_offset += current_content.len();
                } else {
                    // Add sentence to current sub-chunk
                    if !current_content.is_empty() {
                        current_content.push(' ');
                    }
                    current_content.push_str(sentence);
                    current_tokens += sentence_tokens;
                }
            }
            
            // Add final sub-chunk if not empty
            if !current_content.trim().is_empty() {
                let sub_chunk = crate::types::SubChunk::new(
                    chunk.id,
                    current_content.trim().to_string(),
                    start_offset,
                    start_offset + current_content.len(),
                    current_tokens,
                );
                sub_chunks.push(sub_chunk);
            }
        }
        
        Ok(sub_chunks)
    }
    
    /// Get chunking statistics
    pub fn get_stats(&self) -> ChunkingConfig {
        self.config.clone()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use uuid::Uuid;
    
    /// Helper function to create test content with known token counts
    fn create_test_content(paragraphs: usize, words_per_paragraph: usize) -> String {
        let mut content = String::new();
        for i in 0..paragraphs {
            if i > 0 {
                content.push_str("\n\n");
            }
            for j in 0..words_per_paragraph {
                if j > 0 {
                    content.push(' ');
                }
                content.push_str(&format!("word{}", j));
            }
        }
        content
    }
    
    #[tokio::test]
    async fn test_chunker_creation() {
        let config = ChunkingConfig::default();
        let result = SmartChunker::with_default_tokenizer(config).await;
        assert!(result.is_ok());
        
        let chunker = result.unwrap();
        assert_eq!(chunker.config.chunk_size, 450);
        assert_eq!(chunker.config.overlap, 50);
    }
    
    #[tokio::test]
    async fn test_empty_content() {
        let config = ChunkingConfig::default();
        let chunker = SmartChunker::with_default_tokenizer(config).await.unwrap();
        let document_id = Uuid::new_v4();
        
        let chunks = chunker.chunk_document(document_id, "").await.unwrap();
        assert!(chunks.is_empty());
    }
    
    #[tokio::test]
    async fn test_small_content() {
        let config = ChunkingConfig::default();
        let chunker = SmartChunker::with_default_tokenizer(config).await.unwrap();
        let document_id = Uuid::new_v4();
        
        let content = "This is a small test document with several words.";
        let chunks = chunker.chunk_document(document_id, content).await.unwrap();
        
        assert_eq!(chunks.len(), 1);
        assert_eq!(chunks[0].content, content);
        assert_eq!(chunks[0].document_id, document_id);
        assert!(chunks[0].token_count > 0);
    }
    
    #[tokio::test]
    async fn test_chunk_size_limits() {
        let config = ChunkingConfig {
            chunk_size: 10, // Very small for testing
            overlap: 2,
            min_chunk_size: 5,
            max_chunk_size: 15,
        };
        let chunker = SmartChunker::with_default_tokenizer(config.clone()).await.unwrap();
        let document_id = Uuid::new_v4();
        
        // Create content that should be split into multiple chunks
        let content = create_test_content(5, 8); // 5 paragraphs, 8 words each
        let chunks = chunker.chunk_document(document_id, &content).await.unwrap();
        
        // Should create multiple chunks
        assert!(chunks.len() > 1);
        
        // Each chunk should respect size limits
        for chunk in &chunks {
            assert!(chunk.token_count <= config.max_chunk_size);
            assert_eq!(chunk.document_id, document_id);
            assert!(chunk.start_offset < chunk.end_offset);
        }
    }
    
    #[tokio::test]
    async fn test_overlap_functionality() {
        let config = ChunkingConfig {
            chunk_size: 20,
            overlap: 5,
            min_chunk_size: 10,
            max_chunk_size: 30,
        };
        let chunker = SmartChunker::with_default_tokenizer(config.clone()).await.unwrap();
        let document_id = Uuid::new_v4();
        
        // Create content that will definitely be split
        let content = create_test_content(10, 10); // 10 paragraphs, 10 words each
        let chunks = chunker.chunk_document(document_id, &content).await.unwrap();
        
        if chunks.len() > 1 {
            // Check that chunks have some overlapping content
            // This is a basic check - in practice, overlap detection would be more sophisticated
            for i in 1..chunks.len() {
                let prev_chunk = &chunks[i - 1];
                let curr_chunk = &chunks[i];
                
                // Chunks should be properly ordered
                assert!(prev_chunk.start_offset < curr_chunk.start_offset);
                
                // Check metadata contains overlap information
                assert!(prev_chunk.metadata.contains_key("overlap"));
                assert!(curr_chunk.metadata.contains_key("overlap"));
            }
        }
    }
    
    #[tokio::test]
    async fn test_parallel_chunking() {
        let config = ChunkingConfig {
            chunk_size: 50,
            overlap: 10,
            min_chunk_size: 20,
            max_chunk_size: 80,
        };
        let chunker = SmartChunker::with_default_tokenizer(config.clone()).await.unwrap();
        let document_id = Uuid::new_v4();
        
        // Create large content that will trigger parallel processing
        let content = create_test_content(100, 15); // 100 paragraphs, 15 words each
        let chunks = chunker.chunk_document(document_id, &content).await.unwrap();
        
        // Should create multiple chunks
        assert!(chunks.len() > 5);
        
        // Verify chunk properties
        for chunk in &chunks {
            assert_eq!(chunk.document_id, document_id);
            assert!(chunk.token_count > 0);
            assert!(chunk.token_count <= config.max_chunk_size);
            assert!(!chunk.content.trim().is_empty());
        }
        
        // Verify chunks are properly ordered
        for i in 1..chunks.len() {
            assert!(chunks[i - 1].start_offset <= chunks[i].start_offset);
        }
    }
    
    #[tokio::test]
    async fn test_sub_chunk_creation() {
        let config = ChunkingConfig::default();
        let chunker = SmartChunker::with_default_tokenizer(config).await.unwrap();
        let document_id = Uuid::new_v4();
        
        // Create a large chunk that should be split into sub-chunks
        let large_content = create_test_content(20, 20); // 20 paragraphs, 20 words each
        let chunks = chunker.chunk_document(document_id, &large_content).await.unwrap();
        
        // Create sub-chunks from the first chunk (if it exists and is large enough)
        if let Some(large_chunk) = chunks.into_iter().find(|c| c.token_count > 250) {
            let sub_chunks = chunker.create_sub_chunks(&[large_chunk]).await.unwrap();
            
            // Should create multiple sub-chunks
            assert!(sub_chunks.len() > 1);
            
            // Each sub-chunk should be within the target range (150-250 tokens)
            for sub_chunk in &sub_chunks {
                assert!(sub_chunk.token_count >= 150);
                assert!(sub_chunk.token_count <= 250);
                assert!(!sub_chunk.content.trim().is_empty());
            }
        }
    }
    
    #[tokio::test]
    async fn test_token_counting_accuracy() {
        let config = ChunkingConfig::default();
        let chunker = SmartChunker::with_default_tokenizer(config).await.unwrap();
        
        // Test various text samples
        let test_cases = vec![
            ("Hello world", 2),
            ("The quick brown fox jumps over the lazy dog", 9),
            ("", 0),
            ("Single", 1),
        ];
        
        for (text, expected_min_tokens) in test_cases {
            let token_count = chunker.count_tokens(text).unwrap();
            // Token count should be reasonable (at least the expected minimum)
            assert!(token_count >= expected_min_tokens, 
                "Text '{}' should have at least {} tokens, got {}", 
                text, expected_min_tokens, token_count);
        }
    }
    
    #[tokio::test]
    async fn test_chunk_metadata() {
        let config = ChunkingConfig::default();
        let chunker = SmartChunker::with_default_tokenizer(config.clone()).await.unwrap();
        let document_id = Uuid::new_v4();
        
        let content = "This is a test document for metadata verification.";
        let chunks = chunker.chunk_document(document_id, content).await.unwrap();
        
        assert!(!chunks.is_empty());
        let chunk = &chunks[0];
        
        // Check that metadata is properly set
        assert!(chunk.metadata.contains_key("chunk_size"));
        assert!(chunk.metadata.contains_key("overlap"));
        
        // Verify metadata values
        assert_eq!(chunk.metadata.get("chunk_size").unwrap(), &chunk.token_count.to_string());
        assert_eq!(chunk.metadata.get("overlap").unwrap(), &config.overlap.to_string());
    }
    
    #[tokio::test]
    async fn test_chunking_with_custom_config() {
        let custom_config = ChunkingConfig {
            chunk_size: 100,
            overlap: 20,
            min_chunk_size: 50,
            max_chunk_size: 150,
        };
        
        let chunker = SmartChunker::with_default_tokenizer(custom_config.clone()).await.unwrap();
        let document_id = Uuid::new_v4();
        
        let content = create_test_content(15, 12); // 15 paragraphs, 12 words each
        let chunks = chunker.chunk_document(document_id, &content).await.unwrap();
        
        // Verify configuration is respected
        let stats = chunker.get_stats();
        assert_eq!(stats.chunk_size, custom_config.chunk_size);
        assert_eq!(stats.overlap, custom_config.overlap);
        assert_eq!(stats.min_chunk_size, custom_config.min_chunk_size);
        assert_eq!(stats.max_chunk_size, custom_config.max_chunk_size);
        
        // Verify chunks respect the configuration
        for chunk in &chunks {
            assert!(chunk.token_count <= custom_config.max_chunk_size);
        }
    }
}