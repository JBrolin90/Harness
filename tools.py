"""Tool infrastructure - BaseTool ABC, ToolsManager, and built-in tools."""
from __future__ import annotations
import subprocess
import os
import json
from abc import ABCMeta, abstractmethod
from typing import ClassVar, Callable, Any


class ToolsManager(ABCMeta):
    """Metaclass that auto-registers tools on subclass creation."""
    _registry: ClassVar[dict[str, type]] = {}

    def __new__(mcs, name: str, bases: tuple, namespace: dict) -> ToolsManager:
        cls = super().__new__(mcs, name, bases, namespace)
        # Register concrete subclasses (those with 'name' attribute)
        if hasattr(cls, 'name') and cls.name:
            mcs._registry[cls.name] = cls
        return cls


class BaseTool(metaclass=ToolsManager):
    """Abstract base class for all tools."""

    name: str = ""
    description: str = ""
    parameters: dict = {"type": "object", "properties": {}, "required": []}

    # Subclasses override with their own signature. Type checker suppressed because
    # we always dispatch via **kwargs unpacking (see BaseTool.dispatch)
    def execute(self, **kwargs: Any) -> str:  # type: ignore[override]
        """Execute the tool with given kwargs."""
        raise NotImplementedError

    def get_instruction(
        self,
        name: str,
        description: str,
        parameters: dict,
    ) -> dict:
        """"Return the JSON instruction object for LLM tool calling."""
        return {
            "name": name,
            "description": description,
            "parameters": parameters,
        }

    def system_prompt_addition(self) -> str:
        """Return additional instructions for the system prompt."""
        return ""


    @classmethod
    def get_all_instructions(cls) -> list[dict]:
        """Get instructions for all registered tools."""
        return [t().get_instruction(t.name, t.description, t.parameters) for t in cls._registry.values()]

    @classmethod
    def dispatch(cls, tool_name: str, arguments: dict) -> str:
        """Dispatch a tool call to the appropriate handler."""
        if tool_name not in cls._registry:
            return f"[SYSTEM ERROR: Unknown tool '{tool_name}']"
        tool = cls._registry[tool_name]()
        return tool.execute(**arguments)


def _validate_path(file_path: str) -> str:
    """Validate path is within working directory."""
    current_working_directory = os.getcwd()
    abs_path = os.path.abspath(os.path.join(current_working_directory, file_path))

    if not abs_path.startswith(current_working_directory):
        raise ValueError(f"Access denied: Path '{file_path}' is outside the allowed working directory.")

    return abs_path


class ReadFileTool(BaseTool):
    """Read the contents of a file from the file system."""

    name = "read_file"
    description = "Read the contents of a file from the file system."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path to the file to read, relative to the working directory."
            }
        },
        "required": ["path"]
    }

    def execute(self, path: str) -> str:
        try:
            validated_path = _validate_path(path)
            with open(validated_path, 'r') as f:
                content = f.read()
            return f"[SYSTEM OUTPUT: Content of {validated_path}]\n{content}"
        except Exception as e:
            return f"[SYSTEM ERROR: {str(e)}]"


class WriteFileTool(BaseTool):
    """Create or overwrite a file with given content."""

    name = "write_file"
    description = "Write content to a new file. Use this to create new files."
    parameters = {
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

    def execute(self, path: str, content: str) -> str:
        try:
            validated_path = _validate_path(path)
            with open(validated_path, 'w') as f:
                f.write(content)
            return f"[SYSTEM OUTPUT: Successfully wrote {len(content)} characters to {validated_path}]"
        except Exception as e:
            return f"[SYSTEM ERROR: {str(e)}]"


class EditFileTool(BaseTool):
    """Edit an existing file by replacing exact text."""

    name = "edit_file"
    description = "Edit an existing file by replacing exact text."
    parameters = {
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

    def execute(self, path: str, search: str, replace: str) -> str:
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


class ListFilesTool(BaseTool):
    """List files in a directory."""

    name = "list_files"
    description = "List files in a directory."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path to the directory, relative to the working directory."
            }
        },
        "required": ["path"]
    }

    def execute(self, path: str) -> str:
        try:
            validated_path = _validate_path(path)
            if not os.path.exists(validated_path):
                return f"[SYSTEM ERROR: Directory {validated_path} not found.]"
            files = os.listdir(validated_path)
            files.sort()
            return f"[SYSTEM OUTPUT: Files in {validated_path}]\n" + "\n".join(files)
        except Exception as e:
            return f"[SYSTEM ERROR: {str(e)}]"


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

    @staticmethod
    def system_prompt_addition() -> str:
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


def get_tools_instructions():
    """Return JSON schema for available tools."""
    tools = BaseTool.get_all_instructions()
    return f"""
    AVAILABLE TOOLS:
    You have access to the following tools. To call a tool, respond with a JSON object.
    
    ```json
    {json.dumps(tools, indent=2)}
    ```
    
    When using tools:
    [System uses individual tool system_prompt_addition() for additional instructions]
    """


# Backward compatibility exports
TOOLS = BaseTool.get_all_instructions()
TOOL_HANDLERS = {
    "read_file": lambda args: BaseTool.dispatch("read_file", args),
    "write_file": lambda args: BaseTool.dispatch("write_file", args),
    "edit_file": lambda args: BaseTool.dispatch("edit_file", args),
    "list_files": lambda args: BaseTool.dispatch("list_files", args),
    "bash": lambda args: BaseTool.dispatch("bash", args),
}
