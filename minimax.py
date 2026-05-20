import os
import requests

# Set this in your LMDE 7 terminal before running: export MINIMAX_API_KEY="your_key"
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "your_hardcoded_key_if_you_prefer")

def call_minimax(prompt, context):
    """The Cloud Brain: Swapping Ollama for MiniMax API"""
    # Standard MiniMax API endpoint
    url = "https://api.minimax.io/v1/text/chatcompletion_v2"
    
    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "MiniMax-M2.7", # Replace with your specific MinMax 2.7 model ID
        "messages": [
            {"role": "system", "content": context},
            {"role": "user", "content": prompt}
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        # Cloud APIs nest their responses slightly deeper than Ollama
        return response.json()['choices'][0]['message']['content']
        
    except Exception as e:
        # Added extended debugging to catch API key/permission errors
        error_details = response.text if 'response' in locals() else "No response"
        return f"[API CONNECTION ERROR: {str(e)}\nDetails: {error_details}]"