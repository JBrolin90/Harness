"""Tools module - re-exports for backward compatibility.

All tools are defined in the tools/ package:
- tools.base_tool: BaseTool ABC, ToolsManager, _validate_path, get_tools_instructions
- tools.standard_tools: ReadFileTool, WriteFileTool, EditFileTool, ListFilesTool
- tools.bash: BashTool
"""
# Import all tools to trigger registration (relative imports needed inside package)
from .standard_tools import ReadFileTool, WriteFileTool, EditFileTool, ListFilesTool
from .bash import BashTool
from .base_tool import BaseTool, ToolsManager, _validate_path, get_tools_instructions

# Backward compatibility exports
TOOLS = BaseTool.get_all_instructions()
TOOL_HANDLERS = {
    "read_file": lambda args: BaseTool.dispatch("read_file", args),
    "write_file": lambda args: BaseTool.dispatch("write_file", args),
    "edit_file": lambda args: BaseTool.dispatch("edit_file", args),
    "list_files": lambda args: BaseTool.dispatch("list_files", args),
    "bash": lambda args: BaseTool.dispatch("bash", args),
}

__all__ = [
    "BaseTool",
    "ToolsManager",
    "_validate_path",
    "TOOLS",
    "TOOL_HANDLERS",
    "get_tools_instructions",
]
