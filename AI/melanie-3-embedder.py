import os
from openai import OpenAI

def get_embeddings(texts, model="nvidia/nv-embedqa-mistral-7b-v2", input_type="query"):
    """
    Generate embeddings for text using NVIDIA's embedding API.

    Args:
        texts (str or list): Text(s) to embed. Can be a single string or list of strings.
        model (str): NVIDIA model to use (default: "nvidia/nv-embedqa-mistral-7b-v2")
        input_type (str): Type of input - "query" or "passage" (default: "query")

    Returns:
        list: List of embeddings (one for each input text)
    """
    client = OpenAI(
        api_key=os.getenv("NVIDIA_API_KEY"),
        base_url="https://integrate.api.nvidia.com/v1"
    )

    # Ensure texts is a list
    if isinstance(texts, str):
        texts = [texts]

    response = client.embeddings.create(
        input=texts,
        model=model,
        encoding_format="float",
        extra_body={"input_type": input_type, "truncate": "NONE"}
    )

    # Return embeddings for all inputs
    return [data.embedding for data in response.data]

def get_single_embedding(text, model="nvidia/nv-embedqa-mistral-7b-v2", input_type="query"):
    """
    Generate a single embedding for text using NVIDIA's embedding API.

    Args:
        text (str): Text to embed
        model (str): NVIDIA model to use (default: "nvidia/nv-embedqa-mistral-7b-v2")
        input_type (str): Type of input - "query" or "passage" (default: "query")

    Returns:
        list: Single embedding vector
    """
    embeddings = get_embeddings([text], model, input_type)
    return embeddings[0] if embeddings else []

# Example usage
if __name__ == "__main__":
    try:
        # Single text embedding
        embedding = get_single_embedding("What is the capital of France?")
        print(f"Single embedding length: {len(embedding)}")
        print(f"First 5 values: {embedding[:5]}")

        # Multiple texts embedding
        texts = [
            "What is the capital of France?",
            "Paris is the capital of France.",
            "The weather in Paris is nice."
        ]
        embeddings = get_embeddings(texts)
        print(f"Multiple embeddings count: {len(embeddings)}")
        print(f"Each embedding length: {len(embeddings[0]) if embeddings else 0}")

    except Exception as e:
        print(f"Embedding generation failed: {e}")
