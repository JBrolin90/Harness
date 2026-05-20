import re
import readline
import os
import atexit
from minimax import call_minimax
from ollama import call_ollama
from tools import execute_tool, get_tools_instructions

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

def get_persona_instructions():
    return """
    You are Bob, a Software and architect expert.
    """
# 1. System Prompt
system_prompt = f""" 
    {get_persona_instructions()}
    You have access to a local file system via your Harness.
    {get_tools_instructions()}
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
        
        # More forgiving regexes (using .+? to handle stray spaces before the newline)
        read_match = re.search(r'!(READ)\s+(.+)', response)
        bash_match = re.search(r'!(BASH)\s+(.+)', response)
        write_match = re.search(r'!(WRITE)\s+(.+?)\n~~~.*?\n(.*?)~~~', response, re.DOTALL)
        edit_match = re.search(r'!(EDIT)\s+(.+?)\n~~~.*?\n(.*?)~~~', response, re.DOTALL)
        
        if write_match:
            system_result = execute_tool("!WRITE", write_match.group(2), write_match.group(3))
        elif edit_match:
            system_result = execute_tool("!EDIT", edit_match.group(2), edit_match.group(3))
        elif read_match:
            system_result = execute_tool("!READ", read_match.group(2))
        elif bash_match:
            system_result = execute_tool("!BASH", bash_match.group(2))
            
        # --- THE SYNTAX CATCHERS ---
        # If Bob tried to use a tool but the regex failed, tell him to fix it!
        elif "!EDIT" in response and not edit_match:
            system_result = "[SYSTEM ERROR: You attempted to use !EDIT but the syntax was invalid. Ensure the file path is on the first line, followed by ~~~, then the search block, then ===, then the replace block, then ~~~.]"
        elif "!WRITE" in response and not write_match:
            system_result = "[SYSTEM ERROR: You attempted to use !WRITE but the syntax was invalid. Ensure you wrap the code block in ~~~.]"
        # ---------------------------

        # Feed it back to the loop
        if system_result:
            print("\n[Harness feeding system result back to Bob...]")
            
            conversation_history.append({"role": "user", "content": system_result})
            
            response = call_llm(conversation_history, system_prompt)
            print(f"Bob: {response}")
            
            conversation_history.append({"role": "assistant", "content": response})
        else:
            break