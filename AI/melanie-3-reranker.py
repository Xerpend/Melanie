import os
import requests

def rerank_passages(query, passages, model="nvidia/nv-rerankqa-mistral-4b-v3", truncate="NONE"):
    """
    Rerank passages based on relevance to a query using NVIDIA's reranking API.

    Args:
        query (str): The query text to rank passages against
        passages (list): List of passage dictionaries with 'text' key, or list of strings
        model (str): NVIDIA model to use (default: "nvidia/nv-rerankqa-mistral-4b-v3")
        truncate (str): Truncation strategy (default: "NONE")

    Returns:
        dict: The reranking response containing ranked passages with scores
    """
    invoke_url = "https://ai.api.nvidia.com/v1/retrieval/nvidia/nv-rerankqa-mistral-4b-v3/reranking"

    headers = {
        "Authorization": f"Bearer {os.getenv('NVIDIA_API_KEY')}",
        "Accept": "application/json",
    }

    # Convert passages to proper format if they're just strings
    formatted_passages = []
    for passage in passages:
        if isinstance(passage, str):
            formatted_passages.append({"text": passage})
        elif isinstance(passage, dict) and "text" in passage:
            formatted_passages.append(passage)
        else:
            raise ValueError("Each passage must be a string or dict with 'text' key")

    payload = {
        "model": model,
        "query": {
            "text": query
        },
        "passages": formatted_passages,
        "truncate": truncate,
        "messages": [
            {
                "role": "user",
                "content": ""
            }
        ]
    }

    # Re-use connections for efficiency
    session = requests.Session()
    response = session.post(invoke_url, headers=headers, json=payload)

    response.raise_for_status()
    return response.json()

# Example usage
if __name__ == "__main__":
    try:
        # Example with string passages
        query = "What is the GPU memory bandwidth of H100 SXM?"
        passages = [
            "The Hopper GPU is paired with the Grace CPU using NVIDIA's ultra-fast chip-to-chip interconnect, delivering 900GB/s of bandwidth, 7X faster than PCIe Gen5.",
            "A100 provides up to 20X higher performance over the prior generation and can be partitioned into seven GPU instances to dynamically adjust to shifting demands.",
            "Accelerated servers with H100 deliver the compute power—along with 3 terabytes per second (TB/s) of memory bandwidth per GPU and scalability with NVLink and NVSwitch™."
        ]

        result = rerank_passages(query, passages)
        print("Reranking Results:")
        print(result)

        # Show rankings if available
        if "rankings" in result:
            print("\nPassage Rankings:")
            for i, ranking in enumerate(result["rankings"]):
                print(f"Rank {i+1}: Score {ranking.get('score', 'N/A')} - Passage {ranking.get('index', 'N/A')}")

    except Exception as e:
        print(f"Reranking failed: {e}")