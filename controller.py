import requests
import subprocess
import re
import readline
import os
import atexit

# --- TERMINAL HISTORY UPGRADE ---
# Explicitly initialize key bindings to force the VS Code terminal to respect it
readline.parse_and_bind('tab: complete')

# Create a hidden history file in your home directory
histfile = os.path.join(os.path.expanduser("~"), ".hazel_harness_history")

# Load existing history if the file exists
try:
    readline.read_history_file(histfile)
    readline.set_history_length(1000) # Keep the last 1000 commands
except FileNotFoundError:
    pass

# Save the history automatically when you type 'exit' or close the script
atexit.register(readline.write_history_file, histfile)
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

def call_ollama(prompt, context):
    """The Local Brain: Upgraded to the structured Chat endpoint"""
    url = "http://localhost:11434/api/chat"
    
    payload = {
        "model": "qwen2.5-coder:7b",
        "messages": [
            {"role": "system", "content": context},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        # The chat endpoint nests the response under ['message']['content']
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

def execute_tool(command, arg, content=""):
    """The 'Hands': Executes local commands based on LLM requests."""
    
    if command == "!READ":
        print(f"\n[🔧 Harness executing: {command} on {arg}]")
        try:
            result = subprocess.run(["cat", arg.strip()], capture_output=True, text=True)
            if result.returncode == 0:
                return f"[SYSTEM OUTPUT: Content of {arg}]\n{result.stdout}"
            else:
                return f"[SYSTEM ERROR: Could not read {arg}]\n{result.stderr}"
        except Exception as e:
            return f"[SYSTEM ERROR: {str(e)}]"
            
    elif command == "!WRITE":
        print(f"\n[🔧 Harness executing: {command} on {arg}]")
        try:
            safe_path = arg.strip()
            with open(safe_path, 'w') as f:
                f.write(content.strip())
            return f"[SYSTEM OUTPUT: Successfully wrote {len(content)} characters to {safe_path}]"
        except Exception as e:
            return f"[SYSTEM ERROR: Could not write to {safe_path}: {str(e)}]"
            
    elif command == "!BASH":
        # Sanitize the input by stripping whitespace and quotation marks
        clean_arg = arg.strip().strip('"').strip("'")

        # HUMAN IN THE LOOP SECRETY GATE
        print("\n⚠️  HAZEL REQUESTS SHELL EXECUTION ⚠️")
        print(f"Command:  {clean_arg}")
        confirm = input("Allow this command? [y/N]: ")
        
        if confirm.lower() == 'y':
            try:
                # shell=True allows pipes and standard bash syntax
                result = subprocess.run(clean_arg, shell=True, capture_output=True, text=True)
                output = result.stdout if result.stdout else result.stderr

                print(f"\n[SPYING ON DATA FED TO LLM]:\n\n{output}\n--------------------------")

                return f"[SYSTEM OUTPUT: Bash executed with code {result.returncode}]\n{output}"
            except Exception as e:
                return f"[SYSTEM ERROR: Bash failed: {str(e)}]"
        else:
            print("[❌ Execution denied by user.]")
            return "[SYSTEM ERROR: The user denied permission to execute this bash command. You must try a different approach.]"
            
    return "[SYSTEM ERROR: Unknown command]"

def call_llm(prompt, context):
    return call_minimax(prompt, context)


# 1. System Prompt
system_prompt = """You are Hazel, a Home Assistant expert.
You have access to a local file system via your Harness. 


AVAILABLE TOOLS:
1. Read a file:
!READ /path/to/file

2. Write a file:
!WRITE /path/to/file
~~~yaml
[YOUR FILE CONTENT HERE]
~~~

3. Execute a bash command:
!BASH your_command_here

RULES:
- Do not use JSON to call tools. Use the exact text commands above.
- When using !WRITE, the file path must be on the same line, followed immediately by a block wrapped in ~~~ (tildes).
- Use !BASH for things like checking systemctl status, pinging devices, or validating YAML.
- Wait for the system to confirm tool operations before concluding.
"""

conversation_history = []

print("Hazel-Harness v1.3 initialized. Type 'exit' to quit.")

while True:
    user_input = input("\nJoachim: ")
    if user_input.lower() == "exit": 
        break
    
    conversation_history.append( {"role": "user", "content": user_input} )
    
    response = call_llm(conversation_history, system_prompt)
    print(f"Hazel: {response}")
    
    conversation_history.append( {"role": "assistant", "content": response})
    
    # 3. The Autonomous Tool Loop (ReAct)
    while True:
        system_result = None
        
        read_match = re.search(r'!(READ)\s+([^\n]+)', response)
        bash_match = re.search(r'!(BASH)\s+([^\n]+)', response)
        write_match = re.search(r'!(WRITE)\s+([^\n]+)\n+~~~[^\n]*\n(.*?)~~~', response, re.DOTALL)
        
        if write_match:
            system_result = execute_tool("!WRITE", write_match.group(2), write_match.group(3))
        elif read_match:
            system_result = execute_tool("!READ", read_match.group(2))
        elif bash_match:
            system_result = execute_tool("!BASH", bash_match.group(2))
            
        # Feed it back to the loop
        if system_result:
            print("\n[Harness feeding system result back to Hazel...]")
            conversation_history += f"\n{system_result}\nHazel: "
            
            response = call_llm(conversation_history, system_prompt)
            print(f"Hazel: {response}")
            conversation_history += response
        else:
            break