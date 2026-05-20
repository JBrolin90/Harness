import requests
# import json

def call_ollama(prompt, context):
    url = "http://lmde:11434/api/generate"
    payload = {
        "model": "qwen2.5-coder:7b",
        "prompt": f"Context: {context}\n\nUser: {prompt}",
        "stream": False
    }
    response = requests.post(url, json=payload)
    return response.json()['response']

# Basic loop for your terminal
context = "You are Hazel, Home Assistant expert."
while True:
    user_input = input("Joachim: ")
    if user_input.lower() == "exit": 
        break
    
    # 1. Send prompt
    response = call_ollama(user_input, context)
    print(f"Hazel: {response}")