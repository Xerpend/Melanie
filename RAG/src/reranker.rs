//! Reranking client for scoring and filtering retrieved chunks

use crate::config::RerankingConfig;
use crate::error::{RagError, RagResult};
use crate::types::{RetrievalResult, SubChunk};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tokio::time::timeout;

/// Request structure for reranking API
#[derive(Debug, Serialize)]
struct RerankingRequest {
    query: String,
    documents: Vec<String>,
    model: String,
    top_k: Option<usize>,
}

/// Response structure from reranking API
#[derive(Debug, Deserialize)]
struct RerankingResponse {
    results: Vec<RerankingResult>,
    usage: Option<Usage>,
}

#[derive(Debug, Deserialize)]
struct RerankingResult {
    index: usize,
    relevance_score: f32,
    document: Option<String>,
}

#[derive(Debug, Deserialize)]
struct Usage {
    total_tokens: usize,
}

/// Client for reranking operations
pub struct RerankingClient {
    /// HTTP client
    client: Client,
    /// Configuration
    config: RerankingConfig,
}

impl RerankingClient {
    /// Create a new reranking client
    pub fn new(config: RerankingConfig) -> RagResult<Self> {
        let client = Client::builder()
            .timeout(Duration::from_secs(config.timeout))
            .build()
            .map_err(|e| RagError::reranking(format!("Failed to create HTTP client: {}", e)))?;
        
        Ok(Self { client, config })
    }
    
    /// Rerank sub-chunks based on query relevance
    pub async fn rerank_sub_chunks(
        &self,
        query: &str,
        sub_chunks: &[SubChunk],
    ) -> RagResult<Vec<(SubChunk, f32)>> {
        if sub_chunks.is_empty() {
            return Ok(Vec::new());
        }
        
        // Extract documents for reranking
        let documents: Vec<String> = sub_chunks.iter()
            .map(|chunk| chunk.content.clone())
            .collect();
        
        // Get reranking scores
        let scores = self.rerank_documents(query, &documents).await?;
        
        // Combine sub-chunks with scores and filter by threshold
        let mut results: Vec<(SubChunk, f32)> = sub_chunks.iter()
            .zip(scores.into_iter())
            .filter(|(_, score)| *score >= self.config.threshold)
            .map(|(chunk, score)| (chunk.clone(), score))
            .collect();
        
        // Sort by score (descending)
        results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        
        Ok(results)
    }
    
    /// Rerank retrieval results
    pub async fn rerank_results(
        &self,
        query: &str,
        results: &mut [RetrievalResult],
    ) -> RagResult<()> {
        if results.is_empty() {
            return Ok(());
        }
        
        // Extract documents for reranking
        let documents: Vec<String> = results.iter()
            .map(|result| result.chunk.content.clone())
            .collect();
        
        // Get reranking scores
        let scores = self.rerank_documents(query, &documents).await?;
        
        // Update results with reranking scores
        for (result, score) in results.iter_mut().zip(scores.into_iter()) {
            result.set_rerank_score(score);
        }
        
        // Sort by final score (descending)
        results.sort_by(|a, b| b.final_score.partial_cmp(&a.final_score).unwrap_or(std::cmp::Ordering::Equal));
        
        Ok(())
    }
    
    /// Rerank documents and return scores
    async fn rerank_documents(&self, query: &str, documents: &[String]) -> RagResult<Vec<f32>> {
        if documents.is_empty() {
            return Ok(Vec::new());
        }
        
        // Split into batches if necessary
        let mut all_scores = Vec::new();
        
        for batch in documents.chunks(self.config.max_candidates) {
            let batch_scores = self.rerank_batch_internal(query, batch).await?;
            all_scores.extend(batch_scores);
        }
        
        Ok(all_scores)
    }
    
    /// Internal batch reranking with retries
    async fn rerank_batch_internal(&self, query: &str, documents: &[String]) -> RagResult<Vec<f32>> {
        let request = RerankingRequest {
            query: query.to_string(),
            documents: documents.to_vec(),
            model: self.config.model.clone(),
            top_k: Some(documents.len()), // Return scores for all documents
        };
        
        let mut last_error = None;
        
        for attempt in 0..=self.config.max_retries {
            match self.make_reranking_request(&request).await {
                Ok(scores) => return Ok(scores),
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
        
        Err(last_error.unwrap_or_else(|| RagError::reranking("Unknown error during reranking")))
    }
    
    /// Make the actual HTTP request for reranking
    async fn make_reranking_request(&self, request: &RerankingRequest) -> RagResult<Vec<f32>> {
        // Check if we should use Python integration client
        if self.config.endpoint.contains("python://") {
            return self.call_python_reranking_client(request).await;
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
        .map_err(|_| RagError::timeout("Reranking request timed out"))?
        .map_err(|e| RagError::reranking(format!("HTTP request failed: {}", e)))?;
        
        if !response.status().is_success() {
            let status = response.status();
            let error_text = response.text().await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(RagError::reranking(format!(
                "Reranking API returned error {}: {}", status, error_text
            )));
        }
        
        let reranking_response: RerankingResponse = response.json().await
            .map_err(|e| RagError::reranking(format!("Failed to parse response: {}", e)))?;
        
        // Sort by index to maintain order
        let mut results = reranking_response.results;
        results.sort_by_key(|r| r.index);
        
        let scores: Vec<f32> = results.into_iter()
            .map(|r| r.relevance_score)
            .collect();
        
        Ok(scores)
    }
    
    /// Call Python reranking client for integration
    async fn call_python_reranking_client(&self, request: &RerankingRequest) -> RagResult<Vec<f32>> {
        use std::process::Command;
        use serde_json;
        
        // Prepare request data for Python client
        let python_request = serde_json::json!({
            "query": request.query,
            "documents": request.documents,
            "model": request.model,
            "threshold": self.config.threshold,
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

from rag_integration_client import RagRerankingClient, SubChunk

async def main():
    request_data = json.loads('{}')
    
    # Create sub-chunks from documents
    sub_chunks = []
    for i, doc in enumerate(request_data['documents']):
        sub_chunk = SubChunk(
            parent_chunk_id=f'chunk_{{i}}',
            content=doc,
            start_offset=0,
            end_offset=len(doc),
            token_count=len(doc.split())
        )
        sub_chunks.append(sub_chunk)
    
    # Rerank sub-chunks
    async with RagRerankingClient(api_key=request_data.get('api_key')) as client:
        reranked = await client.rerank_sub_chunks(
            query=request_data['query'],
            sub_chunks=sub_chunks,
            threshold=request_data.get('threshold', 0.7)
        )
        
        # Extract scores in original order
        scores = [0.0] * len(request_data['documents'])
        for sub_chunk, score in reranked:
            # Find original index by matching content
            for i, doc in enumerate(request_data['documents']):
                if doc == sub_chunk.content:
                    scores[i] = score
                    break
        
        print(json.dumps(scores))

if __name__ == '__main__':
    asyncio.run(main())
"#, 
                std::env::current_dir()
                    .unwrap_or_else(|_| std::path::PathBuf::from("."))
                    .join("AI")
                    .to_string_lossy(),
                serde_json::to_string(&python_request)
                    .map_err(|e| RagError::reranking(format!("Failed to serialize request: {}", e)))?
            ))
            .output()
            .map_err(|e| RagError::reranking(format!("Failed to execute Python client: {}", e)))?;
        
        if !output.status.success() {
            let error_msg = String::from_utf8_lossy(&output.stderr);
            return Err(RagError::reranking(format!("Python client error: {}", error_msg)));
        }
        
        // Parse scores from output
        let output_str = String::from_utf8_lossy(&output.stdout);
        let scores: Vec<f32> = serde_json::from_str(&output_str)
            .map_err(|e| RagError::reranking(format!("Failed to parse Python client output: {}", e)))?;
        
        Ok(scores)
    }
    
    /// Filter results by reranking threshold
    pub fn filter_by_threshold(&self, results: &[RetrievalResult]) -> Vec<RetrievalResult> {
        results.iter()
            .filter(|result| result.meets_threshold(self.config.threshold))
            .cloned()
            .collect()
    }
    
    /// Calculate diversity score between two texts (simple implementation)
    pub fn calculate_diversity(&self, text1: &str, text2: &str) -> f32 {
        // Simple word-based diversity calculation
        let words1: std::collections::HashSet<&str> = text1.split_whitespace().collect();
        let words2: std::collections::HashSet<&str> = text2.split_whitespace().collect();
        
        let intersection = words1.intersection(&words2).count();
        let union = words1.union(&words2).count();
        
        if union == 0 {
            return 1.0; // Completely different (high diversity)
        }
        
        1.0 - (intersection as f32 / union as f32) // Jaccard distance
    }
    
    /// Ensure diversity in results by removing similar chunks
    pub fn ensure_diversity(&self, results: &[RetrievalResult], diversity_threshold: f32) -> Vec<RetrievalResult> {
        if results.is_empty() {
            return Vec::new();
        }
        
        let mut diverse_results = Vec::new();
        diverse_results.push(results[0].clone()); // Always include the top result
        
        for result in results.iter().skip(1) {
            let mut is_diverse = true;
            
            // Check diversity against all selected results
            for selected in &diverse_results {
                let diversity = self.calculate_diversity(&result.chunk.content, &selected.chunk.content);
                if diversity < diversity_threshold {
                    is_diverse = false;
                    break;
                }
            }
            
            if is_diverse {
                diverse_results.push(result.clone());
            }
        }
        
        diverse_results
    }
    
    /// Get reranking statistics
    pub fn get_stats(&self) -> RerankingConfig {
        self.config.clone()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{Chunk, DocumentId};
    use uuid::Uuid;
    
    #[test]
    fn test_diversity_calculation() {
        let config = RerankingConfig::default();
        let client = RerankingClient::new(config).unwrap();
        
        let text1 = "The quick brown fox jumps over the lazy dog";
        let text2 = "A fast brown fox leaps over a sleepy dog";
        let text3 = "Machine learning is a subset of artificial intelligence";
        
        let diversity_12 = client.calculate_diversity(text1, text2);
        let diversity_13 = client.calculate_diversity(text1, text3);
        
        // text1 and text2 should be more similar (lower diversity) than text1 and text3
        assert!(diversity_12 < diversity_13);
    }
    
    #[test]
    fn test_threshold_filtering() {
        let config = RerankingConfig {
            threshold: 0.5,
            ..Default::default()
        };
        let client = RerankingClient::new(config).unwrap();
        
        let document_id = Uuid::new_v4();
        let chunk1 = Chunk::new(document_id, "test content 1".to_string(), 0, 14, 3);
        let chunk2 = Chunk::new(document_id, "test content 2".to_string(), 0, 14, 3);
        
        let mut result1 = RetrievalResult::new(chunk1, 0.8);
        result1.set_rerank_score(0.6); // Above threshold
        
        let mut result2 = RetrievalResult::new(chunk2, 0.7);
        result2.set_rerank_score(0.3); // Below threshold
        
        let results = vec![result1, result2];
        let filtered = client.filter_by_threshold(&results);
        
        assert_eq!(filtered.len(), 1);
        assert!(filtered[0].meets_threshold(0.5));
    }
    
    #[tokio::test]
    async fn test_empty_reranking() {
        let config = RerankingConfig::default();
        let client = RerankingClient::new(config).unwrap();
        
        let result = client.rerank_sub_chunks("test query", &[]).await;
        assert!(result.is_ok());
        assert!(result.unwrap().is_empty());
    }
}