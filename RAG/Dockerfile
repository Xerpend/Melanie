# Multi-stage build for Rust RAG Engine
FROM rust:1.75 as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy Cargo files
COPY Cargo.toml Cargo.lock ./

# Create dummy main.rs to cache dependencies
RUN mkdir src && echo "fn main() {}" > src/main.rs
RUN cargo build --release
RUN rm src/main.rs

# Copy source code
COPY src ./src

# Build the application
RUN cargo build --release

# Runtime stage
FROM debian:bookworm-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    python3 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash melanie

# Copy binary from builder
COPY --from=builder /app/target/release/melanie-rag /usr/local/bin/melanie-rag

# Set ownership
RUN chown melanie:melanie /usr/local/bin/melanie-rag

# Switch to non-root user
USER melanie

# Set working directory
WORKDIR /app

# Create data directory
RUN mkdir -p rag_data

# Expose port (if needed for future HTTP interface)
EXPOSE 8001

# Run the application
CMD ["melanie-rag"]