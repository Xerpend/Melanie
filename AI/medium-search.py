import os
import requests

def perplexity_reasoning_search(prompt, model="sonar-reasoning"):
    """
    Perform a detailed search using Perplexity AI API with reasoning model.

    Args:
        prompt (str): The search query or prompt to send to the API
        model (str): The model to use (default: "sonar-reasoning")

    Returns:
        dict: The API response as a JSON object
    """
    url = "https://api.perplexity.ai/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    headers = {
        "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    return response.json()

# Example usage
if __name__ == "__main__":
    result = perplexity_reasoning_search("Provide an in-depth analysis of the impact of AI on global job markets over the next decade.")
    print(result)