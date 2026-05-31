"""Bash execution tool with security enhancements."""
import subprocess
import shlex
import sys
from .base_tool import BaseTool

# Shell control characters that could be used for injection
SHELL_CONTROL_CHARS = set(';&|<>$`!')

# Commands that are pre-approved (don't need user confirmation)
APPROVED_COMMANDS = {
    "ls", "cd", "pwd", "cat", "grep", "find", "head", "tail", 
    "wc", "stat", "diff", "mkdir", "rmdir", "cp", "mv", "touch",
    "chmod", "chown", "tree", "du", "df", "free", "uptime"
}


def _contains_shell_control_chars(cmd: str) -> bool:
    """Check if command string contains shell control characters."""
    return any(c in SHELL_CONTROL_CHARS for c in cmd)


def _is_single_safe_command(cmd: str) -> bool:
    """Check if this is a single approved command with no arguments containing control chars."""
    try:
        parts = shlex.split(cmd)
        if not parts:
            return False
        first_word = parts[0]
        # Must be in approved list
        if first_word not in APPROVED_COMMANDS:
            return False
        # All remaining arguments must not contain control chars
        for arg in parts[1:]:
            if _contains_shell_control_chars(arg):
                return False
        return True
    except ValueError:
        # shlex.split failed (unbalanced quotes, etc.)
        return False


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

    def execute(self, command: str) -> str:  # type: ignore[override]
        """Execute a bash command with security checks."""
        # Parse command using shlex for proper handling of quoted args
        try:
            args = shlex.split(command)
        except ValueError as e:
            return f"[SYSTEM ERROR: Invalid command syntax - {e}]"
        
        if not args:
            return "[SYSTEM ERROR: Empty command]"
        
        # Use shell=False for security - no shell interpretation
        # Check for control characters in the original command
        if _contains_shell_control_chars(command):
            # This is a denial, not a system error that would continue the loop
            # The distinction matters for the dispatch loop behavior
            return "[ERROR: Command contains shell control characters (;, &&, |, >, <) which are not allowed]"
        
        # Check if it's a single safe command (pre-approved)
        if _is_single_safe_command(command):
            print(f"\n[🔧 Harness executing whitelisted bash: {command}]")
            try:
                # Use shell=False - pass args as list, no shell interpretation
                result = subprocess.run(
                    args, 
                    shell=False, 
                    capture_output=True, 
                    text=True,
                    cwd=None
                )
                output = result.stdout + result.stderr
                print(f"\n[SPYING ON DATA FED TO LLM]:\n\n{output}\n--------------------------")
                return f"[SYSTEM OUTPUT: Bash executed with code {result.returncode}]\n{output}"
            except Exception as e:
                return f"[SYSTEM ERROR: {str(e)}]"
        
        # Not in pre-approved list - need user confirmation
        print("\n⚠️  Bob REQUESTS SHELL EXECUTION ⚠️")
        print(f"Command:  {command}")
        print(f"Parsed:    {args}")
        
        # In non-interactive runs, deny by default
        if not sys.stdin.isatty():
            print("[❌ Execution denied - non-interactive mode]")
            return "[ERROR: Command requires user approval in interactive mode]"
        
        confirm = input("Allow this command? [y/N]: ")

        if confirm.lower() == 'y':
            try:
                result = subprocess.run(
                    args, 
                    shell=False, 
                    capture_output=True, 
                    text=True
                )
                output = result.stdout + result.stderr
                print(f"\n[SPYING ON DATA FED TO LLM]:\n\n{output}\n--------------------------")
                return f"[SYSTEM OUTPUT: Bash executed with code {result.returncode}]\n{output}"
            except Exception as e:
                return f"[SYSTEM ERROR: {str(e)}]"
        else:
            print("[❌ Execution denied by user]")
            return "[ERROR: Command denied by user]"