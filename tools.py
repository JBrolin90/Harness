
import subprocess
import os

def get_tools_instructions():
    return """
        AVAILABLE TOOLS:
        1. Read a file:
        !READ /path/to/file

        2. Write a file:
        !WRITE /path/to/file
        ~~~
        [YOUR FILE CONTENT HERE]
        ~~~

        3. Execute a bash command:
        !BASH your_command_here

        4. Edit an existing file:
        !EDIT /path/to/file
        ~~~
        [EXACT TEXT TO MATCH IN THE FILE]
        ===
        [NEW TEXT TO REPLACE IT WITH]
        ~~~
    
        RULES:
        - Do not use JSON to call tools. Use the exact text commands above.
        - When using !WRITE or !EDIT, the file path must be on the same line, followed immediately by a block wrapped in ~~~ (tildes).
        - Use !BASH for things like checking systemctl status, pinging devices, or validating YAML.
        - Wait for the system to confirm tool operations before concluding.
    """

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
        print("\n⚠️  Bob REQUESTS SHELL EXECUTION ⚠️")
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
            
    elif command == "!EDIT":
        print(f"\n[🔧 Harness executing: {command} on {arg}]")
        try:
            safe_path = arg.strip()
            if not os.path.exists(safe_path):
                return f"[SYSTEM ERROR: File {safe_path} not found.]"
            
            # Split content into search and replace blocks using the === delimiter
            parts = content.split('\n===\n')
            if len(parts) != 2:
                return "[SYSTEM ERROR: Invalid edit format. Must contain exactly one '===' separator on its own line.]"
            
            search_block = parts[0]
            replace_block = parts[1]
            
            with open(safe_path, 'r') as f:
                file_content = f.read()
            
            if search_block not in file_content:
                return "[SYSTEM ERROR: Search block not found in file. Edit aborted to prevent data corruption. Ensure the text matches exactly.]"
            
            # Replace only the first occurrence for safety
            new_content = file_content.replace(search_block, replace_block, 1)
            
            with open(safe_path, 'w') as f:
                f.write(new_content)
                
            return f"[SYSTEM OUTPUT: Successfully edited {safe_path}]"
        except Exception as e:
            return f"[SYSTEM ERROR: Could not edit {safe_path}: {str(e)}]"
    return "[SYSTEM ERROR: Unknown command]"


