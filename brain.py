import requests
import json
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
    
    # Add tools if provider supports native function calling
    if config.tools:
        payload["tools"] = config.tools
    
    try:
        response = requests.post(config.url, headers=headers, json=payload, timeout=180) 
        response.raise_for_status()
        data = response.json()
        
        # Handle MiniMax/OpenAI vs Ollama formats
        if config.provider_type == "minimax" or 'choices' in data:
            # MiniMax / OpenAI style - check for tool calls
            message = data['choices'][0]['message']
            content = message.get('content', '')
            
            # Check if model made a tool call (OpenAI style)
            if 'tool_calls' in message and message['tool_calls']:
                tool_call = message['tool_calls'][0]
                tool_name = tool_call['function']['name']
                arguments = tool_call['function']['arguments']
                
                # Parse arguments if they're a JSON string
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)
                
                return json.dumps({"name": tool_name, "arguments": arguments})
            
            return content
        else:
            # Ollama style
            return data['message']['content']
        
    except Exception as e:
        print(f"Error processing request to {config.url}: {e}")
        error_details = str(e)
        return f"[BRAIN ERROR: {str(e)}\nDetails: {error_details}]"