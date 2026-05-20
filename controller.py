import requests
import subprocess
import re

def call_ollama(prompt, context):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen2.5-coder:3b",
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

conversation_history = ""

print("Hazel-Harness v1.2 initialized. Type 'exit' to quit.")

while True:
    user_input = input("\nJoachim: ")
    if user_input.lower() == "exit": 
        break
    
    conversation_history += f"\nJoachim: {user_input}\nHazel: "
    
    current_response = call_ollama(conversation_history, system_prompt)
    print(f"Hazel: {current_response}")
    
    conversation_history += current_response
    
    # 3. The Autonomous Tool Loop (ReAct)
    while True:
        system_result = None
        
        read_match = re.search(r'!(READ)\s+([^\n]+)', current_response)
        bash_match = re.search(r'!(BASH)\s+([^\n]+)', current_response)
        write_match = re.search(r'!(WRITE)\s+([^\n]+)\n+~~~[^\n]*\n(.*?)~~~', current_response, re.DOTALL)
        
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
            
            current_response = call_ollama(conversation_history, system_prompt)
            print(f"Hazel: {current_response}")
            conversation_history += current_response
        else:
            break