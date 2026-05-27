"""Bash execution tool."""
import subprocess
from .base_tool import BaseTool


class BashTool(BaseTool):
    """Execute a bash command with security checks."""

    name = "bash"
    description = "Execute a bash command. Use only whitelisted commands or get user approval."
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute."
            }
        },
        "required": ["command"]
    }

    def system_prompt_addition(self) -> str:
        return "\n- Use the exact tool name as specified in the schema\n- Wait for the system to confirm tool operations before concluding"

    def execute(self, command: str) -> str:
        clean_arg = command.strip().strip('"').strip("'")
        safe_commands = ["ls", "cd", "find", "cat", "grep", "pwd", "du", "head", "tail", "wc", "stat", "diff"]
        first_word = clean_arg.split(' ')[0]

        if first_word in safe_commands:
            print(f"\n[🔧 Harness executing whitelisted bash: {clean_arg}]")
            try:
                result = subprocess.run(clean_arg, shell=True, capture_output=True, text=True)
                output = (result.stdout + result.stderr).strip()
                print(f"\n[SPYING ON DATA FED TO LLM]:\n\n{output}\n--------------------------")
                return f"[SYSTEM OUTPUT: Bash executed with code {result.returncode}]\n{output}"
            except Exception as e:
                return f"[SYSTEM ERROR: {str(e)}]"
        else:
            print("\n⚠️  Bob REQUESTS SHELL EXECUTION ⚠️")
            print(f"Command:  {clean_arg}")
            confirm = input("Allow this command? [y/N]: ")

            if confirm.lower() == 'y':
                try:
                    result = subprocess.run(clean_arg, shell=True, capture_output=True, text=True)
                    output = (result.stdout + result.stderr).strip()
                    print(f"\n[SPYING ON DATA FED TO LLM]:\n\n{output}\n--------------------------")
                    return f"[SYSTEM OUTPUT: Bash executed with code {result.returncode}]\n{output}"
                except Exception as e:
                    return f"[SYSTEM ERROR: {str(e)}]"
            else:
                print("[❌ Execution denied by user.]")
                return "[SYSTEM ERROR: User denied permission.]"
