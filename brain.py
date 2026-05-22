import requests
import os
from provider import ProviderConfig

def call_llm(history, system_prompt, config: ProviderConfig):
    """Unified LLM request handler using a ProviderConfig object."""
    
    # Resolve API key from environment variable if specified
    resolved_api_key = os.environ.get(config.api_key_env_var, "") if config.api_key_env_var else ""
    if not resolved_api_key and config.provider_type != "ollama": # Ollama might not need a real key, but others do
        print(f"[WARNING: API key for {config.name} not found in environment variable '{config.api_key_env_var}']")

    headers = {
        "Authorization": f"Bearer {resolved_api_key}",
        "Content-Type": "application/json"
    }
    
    messages = [{"role": "system", "content": system_prompt}]
    messages += history
    
    payload = {
        "model": config.model,
        "messages": messages,
        "stream": config.attributes.get("stream", False)
    }
    
    try:
        response = requests.post(config.url, headers=headers, json=payload, timeout=180) 
        response.raise_for_status()
        data = response.json()
        
        # Handle MiniMax/OpenAI vs Ollama formats
        if config.provider_type == "minimax" or 'choices' in data:
            # MiniMax / OpenAI style
            return data['choices'][0]['message']['content']
        else:
            # Ollama style
            return data['message']['content']
        
    except Exception as e:
        error_details = response.text if 'response' in locals() else "Connection failed"
        return f"[BRAIN ERROR: {str(e)}\nDetails: {error_details}]"