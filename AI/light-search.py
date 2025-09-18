import os
import requests

def perplexity_light_search(prompt, model="sonar"):
    """
    Perform a quick search using Perplexity AI API with sonar model.

    Args:
        prompt (str): The search query or prompt to send to the API
        model (str): The model to use (default: "sonar")

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
    result = perplexity_light_search("What is the latest news in AI research?")
    print(result)