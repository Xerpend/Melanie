import os
from xai_sdk import Client
from xai_sdk.chat import user, system

def ask_grok_code(prompt, system_prompt="You are Melanie, a helpful AI assistant."):
    """
    Ask Grok-Code-Fast a question with customizable prompts.
    
    Args:
        prompt (str): The user prompt/question
        system_prompt (str): The system prompt to set context
    
    Returns:
        str: The response content from Grok
    """
    client = Client(
        api_key=os.getenv("XAI_API_KEY"),
        timeout=3600  # Override default timeout with longer timeout for reasoning models
    )
    
    chat = client.chat.create(model="grok-code-fast")
    chat.append(system(system_prompt))
    chat.append(user(prompt))
    
    response = chat.sample()
    return response.content

if __name__ == "__main__":
    # Example usage
    result = ask_grok_code("What is 2 + 2?", "You are Melanie, a PhD-level mathematician.")
    print(result)