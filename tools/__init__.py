"""Tools module - imports all tools to trigger auto-registration."""
from .standard_tools import ReadFileTool, WriteFileTool, EditFileTool, ListFilesTool
from .bash_tool import BashTool
from .modelName_tool import GetModelNameTool
from .config_reader_tool import ConfigReaderTool
from .memory_tool import MemoryTool, MemoryReadTool
from .base_tool import BaseTool, ToolsManager, _validate_path, get_tools_instructions

# Re-exports for backward compatibility
TOOLS = BaseTool.get_all_instructions()

__all__ = [
    "BaseTool",
    "ToolsManager",
    "_validate_path",
    "TOOLS",
    "get_tools_instructions",
    # Tool classes for direct imports
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "ListFilesTool",
    "BashTool",
    "GetModelNameTool",
    "ConfigReaderTool",
    "MemoryTool",
    "MemoryReadTool",
]
