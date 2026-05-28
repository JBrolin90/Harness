"""BaseTool ABC and ToolsManager metaclass."""
from __future__ import annotations

import os
from abc import ABCMeta
from typing import ClassVar, Any


class ToolsManager(ABCMeta):
    """Metaclass that auto-registers tools on subclass creation."""
    _registry: ClassVar[dict[str, type]] = {}

    def __new__(mcs, name: str, bases: tuple, namespace: dict) -> ToolsManager:
        cls = super().__new__(mcs, name, bases, namespace)
        # Register concrete subclasses (those with 'name' attribute)
        cls_name: str | None = getattr(cls, 'name', None)  # type: ignore[assignment]
        if cls_name:
            mcs._registry[cls_name] = cls
        return cls


class BaseTool(metaclass=ToolsManager):
    """Abstract base class for all tools."""

    name: str = ""
    description: str = ""
    parameters: ClassVar[dict] = {"type": "object", "properties": {}, "required": []}

    # Subclasses override with their own signature. Type checker suppressed because
    # we always dispatch via **kwargs unpacking (see dispatch method below)
    def execute(self, **kwargs: Any) -> str:  # type: ignore[override]
        """Execute the tool with given kwargs."""
        raise NotImplementedError

    def get_instruction(self, name: str, description: str, parameters: dict) -> dict:
        """Return the JSON instruction object for LLM tool calling."""
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
        return [t().get_instruction(t.name, t.description, t.parameters) for t in cls._registry.values()]  # type: ignore[misc]

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
    abs_path = os.path.realpath(os.path.join(current_working_directory, file_path))

    if os.path.commonpath([current_working_directory, abs_path]) != current_working_directory:
        raise ValueError(f"Access denied: Path '{file_path}' is outside the allowed working directory.")

    return abs_path


def get_tools_instructions():
    """Return JSON schema for available tools."""
    import json
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
