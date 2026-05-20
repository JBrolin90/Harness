import os
import requests

MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "your_hardcoded_key_if_you_prefer")

def call_minimax(history, system_prompt):
    """The Cloud Brain: Swapping Ollama for MiniMax API"""
    url = "https://api.minimax.io/v1/text/chatcompletion_v2"
    
    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Concatenate the system prompt with the history list
    messages = [{"role": "system", "content": system_prompt}] + history
    
    payload = {
        "model": "MiniMax-M2.7", 
        "messages": messages
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        return response.json()['choices'][0]['message']['content']
        
    except Exception as e:
        error_details = response.text if 'response' in locals() else "No response"
        return f"[API CONNECTION ERROR: {str(e)}\nDetails: {error_details}]"