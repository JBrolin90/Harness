import os
import re
from brain import call_llm
from tools import execute_tool, get_tools_instructions
from AGENT import AGENT_md_INGESTIOR
from terminal_history import terminal_history_upgrade
from provider import ProviderManager

terminal_history_upgrade()

# Initialize the Provider Manager and select the brain
pm = ProviderManager()
current_provider = pm.get_provider("local-coder")  # Change to "cloud-pro" for MiniMax
#current_provider = pm.get_provider("cloud-pro")  # Change to "local-coder" for ollama

if not current_provider:
    print("[CRITICAL ERROR: No LLM provider found! Check provider.py or providers.json]")
    exit(1)

def get_persona_instructions():
    return """
    You are Bob, a Software and architect expert.
    """
# 1. System Prompt
system_prompt = f""" 
    {get_persona_instructions()}
    Current Working Directory: {os.getcwd()}
    You have access to a local file system via your Harness.
    {get_tools_instructions()}
    {AGENT_md_INGESTIOR()}
"""

conversation_history = []

print(f"Bob-Harness v1.4 initialized. Brain: {current_provider.name} ({current_provider.model})")
print("Type 'exit' to quit.")

while True:
    user_input = input("\nJoachim: ")
    if user_input.lower() == "exit": 
        break
    
    conversation_history.append( {"role": "user", "content": user_input} )
    
    response = call_llm(conversation_history, system_prompt, current_provider)
    print(f"Bob: {response}")
    
    conversation_history.append( {"role": "assistant", "content": response})
    
# 3. The Autonomous Tool Loop (ReAct)
    while True:
        system_result = None
        
        # Define regexes
        regex_map = {
            "!WRITE": r'^\s*!(WRITE)\s+(\S+)',
            "!EDIT":  r'^\s*!(EDIT)\s+(\S+)',
            "!READ":  r'^\s*!(READ)\s+(\S+)',
            "!BASH":  r'^\s*!(BASH)\s+(.+)',
            "!LS":    r'^\s*!(LS)\s+(\S+)'
        }

        # Find all matches and their starting positions
        matches = []
        for cmd_type, pattern in regex_map.items():
            # Use MULTILINE to allow ^ to match start of any line in the response
            flags = re.MULTILINE
            if "WRITE" in cmd_type or "EDIT" in cmd_type:
                flags |= re.DOTALL
            
            m = re.search(pattern, response, flags)
            if m:
                matches.append((m.start(), cmd_type, m))

        # Sort by occurrence in the text and pick the first one
        if matches:
            matches.sort(key=lambda x: x[0])
            _, tool_cmd, match = matches[0]
        
            if tool_cmd in ["!WRITE", "!EDIT"]:
                system_result = execute_tool(tool_cmd, match.group(2), response)
            else:
                system_result = execute_tool(tool_cmd, match.group(2))

        # Feed it back to the loop
        if system_result:
            print("\n[Harness feeding system result back to Bob...]")
            
            conversation_history.append({"role": "user", "content": system_result})
            
            response = call_llm(conversation_history, system_prompt, current_provider)
            print(f"Bob: {response}")
            
            conversation_history.append({"role": "assistant", "content": response})
        else:
            break