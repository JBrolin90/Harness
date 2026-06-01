"""Tools module - imports all tools to trigger auto-registration.

Optional tools are wrapped in try/except to handle missing dependencies gracefully.
Use load_optional_tools() to attempt loading tools that failed import.
"""
import sys
import logging

# Configure logging for optional tool loading
logger = logging.getLogger(__name__)

# Track successfully loaded tools
_loaded_tools: list[type] = []
_failed_imports: dict[str, str] = {}  # tool_name -> error_message


def _safe_import(module_name: str, *tool_classes) -> list[type]:
    """Import tool classes from a module, logging failures gracefully.
    
    Returns list of successfully imported tool classes.
    """
    loaded = []
    try:
        module = __import__(module_name, fromlist=tool_classes)
        for cls in tool_classes:
            if hasattr(module, cls.__name__):
                loaded.append(getattr(module, cls.__name__))
                logger.debug(f"Loaded {cls.__name__} from {module_name}")
    except ImportError as e:
        logger.warning(f"[TOOLS] Could not import {tool_classes} from {module_name}: {e}")
        _failed_imports[module_name] = str(e)
    except Exception as e:
        logger.warning(f"[TOOLS] Unexpected error importing {tool_classes} from {module_name}: {e}")
        _failed_imports[module_name] = str(e)
    return loaded


def load_optional_tools() -> dict[str, type]:
    """Retry loading tools that previously failed to import.
    
    Returns dict of tool_name -> tool_class for successfully loaded tools.
    """
    global _failed_imports
    
    results = {}
    for tool_name, error in list(_failed_imports.items()):
        logger.info(f"[TOOLS] Retrying import for {tool_name} (previous error: {error})")
        # Re-import based on tool name
        if tool_name == "tools.bash_tool":
            result = _safe_import("tools.bash_tool", type('BashTool', (), {}))
            # Would need actual class reference
        # Add more specific retry logic as needed
    
    return results


# Import standard tools (required)
from .standard_tools import ReadFileTool, WriteFileTool, EditFileTool, ListFilesTool
_loaded_tools.extend([ReadFileTool, WriteFileTool, EditFileTool, ListFilesTool])

# Import optional tools with graceful failure handling
_bash = _safe_import("tools.bash_tool", type('BashTool', (), {}))
if _bash:
    BashTool = _bash[0]
else:
    BashTool = None

_model = _safe_import("tools.modelName_tool", type('GetModelNameTool', (), {}))
if _model:
    GetModelNameTool = _model[0]
else:
    GetModelNameTool = None

_config = _safe_import("tools.config_reader_tool", type('ConfigReaderTool', (), {}))
if _config:
    ConfigReaderTool = _config[0]
else:
    ConfigReaderTool = None

_memory = _safe_import("tools.memory_tool", type('MemoryTool', (), {}), type('MemoryReadTool', (), {}))
if _memory:
    MemoryTool, MemoryReadTool = _memory[0], _memory[1] if len(_memory) > 1 else (None, None)
else:
    MemoryTool, MemoryReadTool = None, None

# Import base components (required)
from .base_tool import BaseTool, ToolsManager, _validate_path, get_tools_instructions

# Re-exports for backward compatibility - only include successfully loaded tools
TOOLS = BaseTool.get_all_instructions()

__all__ = [
    "BaseTool",
    "ToolsManager",
    "_validate_path",
    "TOOLS",
    "get_tools_instructions",
    "load_optional_tools",
    "get_loaded_tools",
    # Tool classes (may be None if import failed)
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


def get_loaded_tools() -> list[type]:
    """Return list of successfully loaded tool classes."""
    return _loaded_tools.copy()


def get_failed_imports() -> dict[str, str]:
    """Return dict of tool module -> error message for failed imports."""
    return _failed_imports.copy()