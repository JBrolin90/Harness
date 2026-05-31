"""Standard file manipulation tools."""
import os
from .base_tool import BaseTool, _validate_path


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

    def execute(self, path: str) -> str:  # type: ignore[override]
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

    def execute(self, path: str, content: str) -> str:  # type: ignore[override]
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

    def execute(self, path: str, search: str, replace: str) -> str:  # type: ignore[override]
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
                return f"[SYSTEM ERROR: Search text not found in {path}. Ensure the 'search' string matches the file content exactly, including whitespace and indentation.]"

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

    def execute(self, path: str) -> str:  # type: ignore[override]
        try:
            validated_path = _validate_path(path)
            if not os.path.exists(validated_path):
                return f"[SYSTEM ERROR: Directory {validated_path} not found.]"
            files = os.listdir(validated_path)
            files.sort()
            return f"[SYSTEM OUTPUT: Files in {validated_path}]\n" + "\n".join(files)
        except Exception as e:
            return f"[SYSTEM ERROR: {str(e)}]"
