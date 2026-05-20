
import subprocess


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
            
    return "[SYSTEM ERROR: Unknown command]"
