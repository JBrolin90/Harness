"""Bash execution tool with security enhancements."""
import subprocess
import shlex
import sys
from .base_tool import BaseTool

# Shell control characters that are BLOCKED entirely (even with user approval)
# These are dangerous because they can chain commands or redirect output
DANGEROUS_CONTROL_CHARS = set(';&|<>$`!')

# Characters that may appear safely in quoted arguments (not at command level)
# None currently - all have potential for abuse if at top level

# Commands that are pre-approved (don't need user confirmation)
APPROVED_COMMANDS = {
    "ls", "cd", "pwd", "cat", "grep", "find", "head", "tail", 
    "wc", "stat", "diff", "mkdir", "rmdir", "cp", "mv", "touch",
    "chmod", "chown", "tree", "du", "df", "free", "uptime",
    "sort", "uniq", "rm", "echo", "mkdir", "git"
}


def _contains_dangerous_control_chars(cmd: str) -> bool:
    """Check if command string contains dangerous control characters.
    
    Note: Since we use shell=False, only characters at the top level
    (before any quoted section) are checked. Quoted arguments are safe.
    """
    return any(c in DANGEROUS_CONTROL_CHARS for c in cmd)


class BashTool(BaseTool):
    """Execute a bash command with security checks.
    
    Security features:
    - Uses subprocess.run with shell=False to prevent command injection
    - Blocks dangerous shell metacharacters (;, &&, |, >, <, $, `)
    - Pre-approved commands don't need user confirmation
    - Non-interactive mode: denies commands requiring approval
    - Uses shlex.split for proper argument parsing
    """

    name = "bash"
    description = """Execute a bash command. Use only whitelisted commands or get user approval.
    
    Security: Uses shell=False with argument parsing. Dangerous characters (;, &&, |, >, <, $, `)
    are blocked. In non-interactive mode, commands requiring approval are denied."""
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute. Avoid using shell metacharacters (;, &&, |, >, <, $, `)."
            }
        },
        "required": ["command"]
    }

    def system_prompt_addition(self) -> str:
        return "\n- Use the exact tool name as specified in the schema\n- Wait for the system to confirm tool operations before concluding"

    def execute(self, command: str) -> str:  # type: ignore[override]
        """Execute a bash command with security checks.
        
        In non-interactive mode (cron, CI, etc.), commands that require
        user approval will be DENIED. Only pre-approved commands work.
        """
        # Parse command using shlex for proper handling of quoted args
        try:
            args = shlex.split(command)
        except ValueError as e:
            return f"[SYSTEM ERROR: Invalid command syntax - {e}]"
        
        if not args:
            return "[SYSTEM ERROR: Empty command]"
        
        # Check for dangerous control characters (blocked entirely)
        if _contains_dangerous_control_chars(command):
            return ("[ERROR: Command contains blocked shell characters (;, &&, |, >, <, $, `) "
                    "which are not allowed]")
        
        # Check if it's a single pre-approved command
        if self._is_preapproved_command(args):
            return self._execute_command(args, command)
        
        # Not pre-approved - requires user confirmation
        return self._request_approval(command, args)

    def _is_preapproved_command(self, args: list) -> bool:
        """Check if command is in the pre-approved list."""
        return args[0] in APPROVED_COMMANDS

    def _execute_command(self, args: list, original_command: str) -> str:
        """Execute a pre-approved command."""
        print(f"\n[🔧 Harness executing whitelisted bash: {original_command}]")
        try:
            result = subprocess.run(
                args, 
                shell=False, 
                capture_output=True, 
                text=True,
                timeout=30
            )
            output = result.stdout + result.stderr
            print(f"\n[SPYING ON DATA FED TO LLM]:\n\n{output}\n--------------------------")
            return f"[SYSTEM OUTPUT: Bash executed with code {result.returncode}]\n{output}"
        except Exception as e:
            return f"[SYSTEM ERROR: {str(e)}]"

    def _request_approval(self, command: str, args: list) -> str:
        """Request user approval for non-pre-approved commands.
        
        In non-interactive mode (sys.stdin.isatty() is False), 
        commands are denied because user confirmation is not possible.
        """
        print("\n⚠️  Bob REQUESTS SHELL EXECUTION ⚠️")
        print(f"Command:  {command}")
        print(f"Parsed:   {args}")
        
        if not sys.stdin.isatty():
            # Non-interactive: cannot prompt for approval
            print("[❌ Execution denied - non-interactive mode]")
            print("    To allow this command, run in an interactive terminal.")
            return "[ERROR: Command requires user approval in interactive mode]"
        
        confirm = input("Allow this command? [y/N]: ")

        if confirm.lower() == 'y':
            return self._execute_command(args, command)
        else:
            print("[❌ Execution denied by user]")
            return "[ERROR: Command denied by user]"