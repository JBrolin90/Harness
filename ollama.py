import requests

def call_ollama(history, system_prompt):
    """The Local Brain: Upgraded to the structured Chat endpoint"""
    url = "http://localhost:11434/api/chat"
    
    messages = [{"role": "system", "content": system_prompt}]
    messages += history
    
    payload = {
        "model": "qwen2.5-coder:7b",
        "messages": messages,
        "stream": False
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        return response.json()['message']['content']
        
    except Exception as e:
        return f"[API CONNECTION ERROR: {str(e)}]"

def call_ollama_simple(prompt, context):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen2.5-coder:1.5b",
        "prompt": f"{context}\n\n{prompt}",
        "stream": False
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()['response']
    except Exception as e:
        return f"[API CONNECTION ERROR: {str(e)}]"