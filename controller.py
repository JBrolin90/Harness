import re
import readline
import os
import atexit
from minimax import call_minimax
from ollama import call_ollama
from tools import execute_tool

# --- TERMINAL HISTORY UPGRADE ---
# Explicitly initialize key bindings to force the VS Code terminal to respect it
readline.parse_and_bind('tab: complete')

# Create a hidden history file in your home directory
histfile = os.path.join(os.path.expanduser("~"), ".Bob_harness_history")

# Load existing history if the file exists
try:
    readline.read_history_file(histfile)
    readline.set_history_length(1000) # Keep the last 1000 commands
except FileNotFoundError:
    pass

# Save the history automatically when you type 'exit' or close the script
atexit.register(readline.write_history_file, histfile)


call_llm = call_minimax


# 1. System Prompt
system_prompt = """You are Bob, a Software and architect expert.
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

print("Bob-Harness v1.3 initialized. Type 'exit' to quit.")

while True:
    user_input = input("\nJoachim: ")
    if user_input.lower() == "exit": 
        break
    
    conversation_history.append( {"role": "user", "content": user_input} )
    
    response = call_llm(conversation_history, system_prompt)
    print(f"Bob: {response}")
    
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
            print("\n[Harness feeding system result back to Bob...]")
            conversation_history += f"\n{system_result}\nBob: "
            
            response = call_llm(conversation_history, system_prompt)
            print(f"Bob: {response}")
            conversation_history += response
        else:
            break