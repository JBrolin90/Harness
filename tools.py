import subprocess
import os
import json


TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file from the file system.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to read, relative to the working directory."
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a new file. Use this to create new files.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to write, relative to the working directory."
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file."
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "edit_file",
        "description": "Edit an existing file by replacing exact text.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to edit, relative to the working directory."
                },
                "search": {
                    "type": "string",
                    "description": "The exact text to find in the file."
                },
                "replace": {
                    "type": "string",
                    "description": "The exact text to replace the search text with."
                }
            },
            "required": ["path", "search", "replace"]
        }
    },
    {
        "name": "list_files",
        "description": "List files in a directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the directory, relative to the working directory."
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "bash",
        "description": "Execute a bash command. Use only whitelisted commands or get user approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute."
                }
            },
            "required": ["command"]
        }
    }
]


def get_tools_instructions():
    """Return JSON schema for available tools."""
    return f"""
    AVAILABLE TOOLS:
    You have access to the following tools. To call a tool, respond with a JSON object.
    
    ```json
    {json.dumps(TOOLS, indent=2)}
    ```
    
    When using tools:
    - Use the exact tool name as specified in the schema
    - Provide all required parameters
    - Wait for the system to confirm tool operations before concluding
    - You are an AUTONOMOUS agent. Do not ask the user for confirmation
    """


def _validate_path(file_path: str) -> str:
    """Validate path is within working directory."""
    current_working_directory = os.getcwd()
    abs_path = os.path.abspath(os.path.join(current_working_directory, file_path))

    if not abs_path.startswith(current_working_directory):
        raise ValueError(f"Access denied: Path '{file_path}' is outside the allowed working directory.")

    return abs_path


def _execute_read(path: str) -> str:
    """Execute read_file tool."""
    try:
        validated_path = _validate_path(path)
        with open(validated_path, 'r') as f:
            content = f.read()
        return f"[SYSTEM OUTPUT: Content of {validated_path}]\n{content}"
    except Exception as e:
        return f"[SYSTEM ERROR: {str(e)}]"


def _execute_write(path: str, content: str) -> str:
    """Execute write_file tool."""
    try:
        validated_path = _validate_path(path)
        with open(validated_path, 'w') as f:
            f.write(content)
        return f"[SYSTEM OUTPUT: Successfully wrote {len(content)} characters to {validated_path}]"
    except Exception as e:
        return f"[SYSTEM ERROR: {str(e)}]"


def _execute_edit(path: str, search: str, replace: str) -> str:
    """Execute edit_file tool."""
    try:
        validated_path = _validate_path(path)
    except ValueError as e:
        return f"[SYSTEM ERROR: {str(e)}]"

    try:
        if not os.path.exists(validated_path):
            return f"[SYSTEM ERROR: File {validated_path} not found.]"

        with open(validated_path, 'r') as f:
            file_content = f.read()

        if search not in file_content:
            return "[SYSTEM ERROR: Search text not found in file. Edit aborted.]"

        new_content = file_content.replace(search, replace, 1)

        with open(validated_path, 'w') as f:
            f.write(new_content)

        return f"[SYSTEM OUTPUT: Successfully edited {validated_path}]"
    except Exception as e:
        return f"[SYSTEM ERROR: {str(e)}]"


def _execute_ls(path: str) -> str:
    """Execute list_files tool."""
    try:
        validated_path = _validate_path(path)
        if not os.path.exists(validated_path):
            return f"[SYSTEM ERROR: Directory {validated_path} not found.]"
        files = os.listdir(validated_path)
        files.sort()
        return f"[SYSTEM OUTPUT: Files in {validated_path}]\n" + "\n".join(files)
    except Exception as e:
        return f"[SYSTEM ERROR: {str(e)}]"


def _execute_bash(command: str) -> str:
    """Execute bash tool with security checks."""
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


TOOL_HANDLERS = {
    "read_file": lambda args: _execute_read(args["path"]),
    "write_file": lambda args: _execute_write(args["path"], args["content"]),
    "edit_file": lambda args: _execute_edit(args["path"], args["search"], args["replace"]),
    "list_files": lambda args: _execute_ls(args["path"]),
    "bash": lambda args: _execute_bash(args["command"]),
}


class ToolEngine:
    """Parses JSON tool calls and executes them."""

    def dispatch(self, response: str) -> str | None:
        """Parse response for JSON tool call and execute it."""
        try:
            # Parse the response as JSON
            call = json.loads(response.strip())
            
            if "name" not in call:
                return None
            tool_name = call["name"]
            arguments = call.get("arguments") or {}
            
            if tool_name not in TOOL_HANDLERS:
                return f"[SYSTEM ERROR: Unknown tool '{tool_name}']"
            
            print(f"\n[🔧 Harness executing: {tool_name}]")
            handler = TOOL_HANDLERS[tool_name]
            return handler(arguments)
            
        except json.JSONDecodeError:
            return None
        except KeyError as e:
            return f"[SYSTEM ERROR: Missing parameter {e}]"
        except Exception as e:
            return f"[SYSTEM ERROR: {str(e)}]"