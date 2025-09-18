//! Embedding client for converting text to vectors

use crate::config::EmbeddingConfig;
use crate::error::{RagError, RagResult};
use crate::types::{Chunk, Embedding};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tokio::time::timeout;

/// Request structure for embedding API
#[derive(Debug, Serialize)]
struct EmbeddingRequest {
    input: Vec<String>,
    model: String,
}

/// Response structure from embedding API
#[derive(Debug, Deserialize)]
struct EmbeddingResponse {
    data: Vec<EmbeddingData>,
    usage: Option<Usage>,
}

#[derive(Debug, Deserialize)]
struct EmbeddingData {
    embedding: Vec<f32>,
    index: usize,
}

#[derive(Debug, Deserialize)]
struct Usage {
    prompt_tokens: usize,
    total_tokens: usize,
}

/// Client for embedding operations
pub struct EmbeddingClient {
    /// HTTP client
    client: Client,
    /// Configuration
    config: EmbeddingConfig,
}

impl EmbeddingClient {
    /// Create a new embedding client
    pub fn new(config: EmbeddingConfig) -> RagResult<Self> {
        let client = Client::builder()
            .timeout(Duration::from_secs(config.timeout))
            .build()
            .map_err(|e| RagError::embedding(format!("Failed to create HTTP client: {}", e)))?;
        
        Ok(Self { client, config })
    }
    
    /// Embed a single text
    pub async fn embed_single(&self, text: &str) -> RagResult<Embedding> {
        let embeddings = self.embed_batch(&[text.to_string()]).await?;
        embeddings.into_iter().next()
            .ok_or_else(|| RagError::embedding("No embedding returned for single text"))
    }
    
    /// Embed multiple texts in batch
    pub async fn embed_batch(&self, texts: &[String]) -> RagResult<Vec<Embedding>> {
        if texts.is_empty() {
            return Ok(Vec::new());
        }
        
        // Split into batches if necessary
        let mut all_embeddings = Vec::new();
        
        for batch in texts.chunks(self.config.batch_size) {
            let batch_embeddings = self.embed_batch_internal(batch).await?;
            all_embeddings.extend(batch_embeddings);
        }
        
        Ok(all_embeddings)
    }
    
    /// Internal batch embedding with retries
    async fn embed_batch_internal(&self, texts: &[String]) -> RagResult<Vec<Embedding>> {
        let request = EmbeddingRequest {
            input: texts.to_vec(),
            model: self.config.model.clone(),
        };
        
        let mut last_error = None;
        
        for attempt in 0..=self.config.max_retries {
            match self.make_embedding_request(&request).await {
                Ok(embeddings) => return Ok(embeddings),
                Err(e) => {
                    last_error = Some(e);
                    if attempt < self.config.max_retries {
                        // Exponential backoff
                        let delay = Duration::from_millis(100 * (2_u64.pow(attempt as u32)));
                        tokio::time::sleep(delay).await;
                    }
                }
            }
        }
        
        Err(last_error.unwrap_or_else(|| RagError::embedding("Unknown error during embedding")))
    }
    
    /// Make the actual HTTP request for embeddings
    async fn make_embedding_request(&self, request: &EmbeddingRequest) -> RagResult<Vec<Embedding>> {
        // Check if we should use Python integration client
        if self.config.endpoint.contains("python://") {
            return self.call_python_embedding_client(request).await;
        }
        
        let mut req_builder = self.client
            .post(&self.config.endpoint)
            .json(request);
        
        // Add API key if configured
        if let Some(api_key) = &self.config.api_key {
            req_builder = req_builder.bearer_auth(api_key);
        }
        
        let response = timeout(
            Duration::from_secs(self.config.timeout),
            req_builder.send()
        ).await
        .map_err(|_| RagError::timeout("Embedding request timed out"))?
        .map_err(|e| RagError::embedding(format!("HTTP request failed: {}", e)))?;
        
        if !response.status().is_success() {
            let status = response.status();
            let error_text = response.text().await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(RagError::embedding(format!(
                "Embedding API returned error {}: {}", status, error_text
            )));
        }
        
        let embedding_response: EmbeddingResponse = response.json().await
            .map_err(|e| RagError::embedding(format!("Failed to parse response: {}", e)))?;
        
        // Sort by index to maintain order
        let mut data = embedding_response.data;
        data.sort_by_key(|d| d.index);
        
        let embeddings: Vec<Embedding> = data.into_iter()
            .map(|d| d.embedding)
            .collect();
        
        Ok(embeddings)
    }
    
    /// Call Python embedding client for integration
    async fn call_python_embedding_client(&self, request: &EmbeddingRequest) -> RagResult<Vec<Embedding>> {
        use std::process::Command;
        use serde_json;
        
        // Prepare request data for Python client
        let python_request = serde_json::json!({
            "texts": request.input,
            "model": request.model,
            "api_key": self.config.api_key
        });
        
        // Call Python script
        let output = Command::new("python3")
            .arg("-c")
            .arg(format!(r#"
import asyncio
import json
import sys
import os
sys.path.append('{}')

from rag_integration_client import RagEmbeddingClient, RagChunk

async def main():
    request_data = json.loads('{}')
    
    # Create chunks from texts
    chunks = []
    for i, text in enumerate(request_data['texts']):
        chunk = RagChunk(
            id=f'chunk_{{i}}',
            content=text,
            token_count=len(text.split())
        )
        chunks.append(chunk)
    
    # Embed chunks
    async with RagEmbeddingClient(api_key=request_data.get('api_key')) as client:
        embedded_chunks = await client.embed_chunks_for_rag(chunks)
        
        # Extract embeddings
        embeddings = [chunk.embedding for chunk in embedded_chunks]
        print(json.dumps(embeddings))

if __name__ == '__main__':
    asyncio.run(main())
"#, 
                std::env::current_dir()
                    .unwrap_or_else(|_| std::path::PathBuf::from("."))
                    .join("AI")
                    .to_string_lossy(),
                serde_json::to_string(&python_request)
                    .map_err(|e| RagError::embedding(format!("Failed to serialize request: {}", e)))?
            ))
            .output()
            .map_err(|e| RagError::embedding(format!("Failed to execute Python client: {}", e)))?;
        
        if !output.status.success() {
            let error_msg = String::from_utf8_lossy(&output.stderr);
            return Err(RagError::embedding(format!("Python client error: {}", error_msg)));
        }
        
        // Parse embeddings from output
        let output_str = String::from_utf8_lossy(&output.stdout);
        let embeddings: Vec<Vec<f32>> = serde_json::from_str(&output_str)
            .map_err(|e| RagError::embedding(format!("Failed to parse Python client output: {}", e)))?;
        
        Ok(embeddings)
    }
    
    /// Embed chunks and update them with embeddings
    pub async fn embed_chunks(&self, chunks: &mut [Chunk]) -> RagResult<()> {
        if chunks.is_empty() {
            return Ok(());
        }
        
        // Extract texts from chunks
        let texts: Vec<String> = chunks.iter()
            .map(|chunk| chunk.content.clone())
            .collect();
        
        // Get embeddings
        let embeddings = self.embed_batch(&texts).await?;
        
        // Update chunks with embeddings
        for (chunk, embedding) in chunks.iter_mut().zip(embeddings.into_iter()) {
            chunk.set_embedding(embedding);
        }
        
        Ok(())
    }
    
    /// Calculate cosine similarity between two embeddings
    pub fn cosine_similarity(a: &Embedding, b: &Embedding) -> f32 {
        if a.len() != b.len() {
            return 0.0;
        }
        
        let dot_product: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
        let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
        let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
        
        if norm_a == 0.0 || norm_b == 0.0 {
            return 0.0;
        }
        
        dot_product / (norm_a * norm_b)
    }
    
    /// Find most similar embeddings using cosine similarity
    pub fn find_similar(
        &self,
        query_embedding: &Embedding,
        candidate_embeddings: &[(usize, &Embedding)],
        top_k: usize,
    ) -> Vec<(usize, f32)> {
        let mut similarities: Vec<(usize, f32)> = candidate_embeddings
            .iter()
            .map(|(idx, embedding)| {
                let similarity = Self::cosine_similarity(query_embedding, embedding);
                (*idx, similarity)
            })
            .collect();
        
        // Sort by similarity (descending)
        similarities.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        
        // Take top k
        similarities.truncate(top_k);
        similarities
    }
    
    /// Get embedding statistics
    pub fn get_stats(&self) -> EmbeddingConfig {
        self.config.clone()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_cosine_similarity() {
        let a = vec![1.0, 0.0, 0.0];
        let b = vec![1.0, 0.0, 0.0];
        let similarity = EmbeddingClient::cosine_similarity(&a, &b);
        assert!((similarity - 1.0).abs() < 1e-6);
        
        let a = vec![1.0, 0.0, 0.0];
        let b = vec![0.0, 1.0, 0.0];
        let similarity = EmbeddingClient::cosine_similarity(&a, &b);
        assert!((similarity - 0.0).abs() < 1e-6);
    }
    
    #[test]
    fn test_find_similar() {
        let config = EmbeddingConfig::default();
        let client = EmbeddingClient::new(config).unwrap();
        
        let query = vec![1.0, 0.0, 0.0];
        let embeddings = vec![
            vec![1.0, 0.0, 0.0],  // Perfect match
            vec![0.8, 0.6, 0.0],  // Similar
            vec![0.0, 1.0, 0.0],  // Orthogonal
        ];
        let candidates: Vec<(usize, &Embedding)> = embeddings.iter().enumerate().collect();
        
        let results = client.find_similar(&query, &candidates, 2);
        
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].0, 0); // Perfect match should be first
        assert!(results[0].1 > results[1].1); // First should have higher similarity
    }
    
    #[tokio::test]
    async fn test_empty_batch() {
        let config = EmbeddingConfig::default();
        let client = EmbeddingClient::new(config).unwrap();
        
        let result = client.embed_batch(&[]).await;
        assert!(result.is_ok());
        assert!(result.unwrap().is_empty());
    }
}