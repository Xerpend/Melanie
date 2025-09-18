use melanie_rag::RagEngine;
use std::collections::HashMap;
use tokio;
use tracing::{info, error};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing
    melanie_rag::init_tracing();
    
    info!("Starting Melanie RAG Engine - Rust Implementation");
    
    // Create RAG engine with default configuration
    let engine = match RagEngine::with_default_config().await {
        Ok(engine) => {
            info!("RAG engine initialized successfully");
            engine
        }
        Err(e) => {
            error!("Failed to initialize RAG engine: {}", e);
            return Err(e.into());
        }
    };
    
    // Perform health check
    match engine.health_check().await {
        Ok(true) => info!("RAG engine health check passed"),
        Ok(false) => {
            error!("RAG engine health check failed");
            return Err("Health check failed".into());
        }
        Err(e) => {
            error!("Health check error: {}", e);
            return Err(e.into());
        }
    }
    
    // Demo: Ingest a sample document
    let sample_content = r#"
    Artificial Intelligence (AI) is a branch of computer science that aims to create intelligent machines 
    that can perform tasks that typically require human intelligence. These tasks include learning, 
    reasoning, problem-solving, perception, and language understanding.
    
    Machine Learning (ML) is a subset of AI that focuses on the development of algorithms and statistical 
    models that enable computers to improve their performance on a specific task through experience, 
    without being explicitly programmed for every scenario.
    
    Deep Learning is a subset of machine learning that uses neural networks with multiple layers 
    (hence "deep") to model and understand complex patterns in data. It has been particularly 
    successful in areas like image recognition, natural language processing, and speech recognition.
    
    Natural Language Processing (NLP) is a field of AI that focuses on the interaction between 
    computers and human language. It involves developing algorithms and models that can understand, 
    interpret, and generate human language in a valuable way.
    "#;
    
    let mut metadata = HashMap::new();
    metadata.insert("title".to_string(), "AI Overview".to_string());
    metadata.insert("category".to_string(), "technology".to_string());
    
    info!("Ingesting sample document...");
    let document_id = engine.ingest_document(sample_content.to_string(), metadata).await?;
    info!("Document ingested with ID: {}", document_id);
    
    // Demo: Retrieve context for different queries
    let queries = vec![
        "What is artificial intelligence?",
        "Tell me about machine learning",
        "How does deep learning work?",
        "What is natural language processing?",
    ];
    
    for query in queries {
        info!("Querying: '{}'", query);
        
        match engine.retrieve_context(query, melanie_rag::RetrievalMode::General).await {
            Ok(results) => {
                info!("Found {} relevant chunks", results.len());
                for (i, result) in results.iter().take(2).enumerate() {
                    info!(
                        "  Result {}: Score={:.3}, Content preview: '{}'",
                        i + 1,
                        result.final_score,
                        result.chunk.content.chars().take(100).collect::<String>()
                    );
                }
            }
            Err(e) => {
                error!("Query failed: {}", e);
            }
        }
    }
    
    // Display final statistics
    let stats = engine.get_stats().await;
    info!("Final RAG Engine Statistics:");
    info!("  Documents: {}", stats.document_count);
    info!("  Chunks: {}", stats.chunk_count);
    info!("  Embeddings: {}", stats.embedding_count);
    info!("  Average chunk size: {:.1} tokens", stats.avg_chunk_size);
    info!("  Cache hit rate: {:.1}%", stats.cache_hit_rate * 100.0);
    
    info!("Melanie RAG Engine demo completed successfully");
    Ok(())
}
