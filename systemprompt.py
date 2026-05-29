"""System prompt builder - dynamically generates prompts from registered tools."""
import os
from typing import TYPE_CHECKING
from tools.base_tool import BaseTool
from agent import get_agent_py

# Cached content loaded via config
_cached_agent_py: str | None = None
_cached_memory_instructions: str | None = None


def _get_agent_py_cached() -> str:
    """Get cached AGENT.py content."""
    global _cached_agent_py
    if _cached_agent_py is None:
        _cached_agent_py = get_agent_py()
    return _cached_agent_py

if TYPE_CHECKING:
    from memory import Memory


def _build_memory_section(memory: "Memory | None") -> str:
    """Build memory section for system prompt if memory has content."""
    if memory is None or not memory.has_content():
        return ""
    
    lines = ["\nLONG-TERM MEMORY:"]
    for section, items in memory.get_all().items():
        if items:
            lines.append(f"## {section}")
            lines.extend(f"- {item}" for item in items)
            lines.append("")
    return "\n".join(lines)


def _build_memory_instructions() -> str:
    """Build memory instructions section if memory_instructions.md exists."""
    global _cached_memory_instructions
    if _cached_memory_instructions is None:
        import config
        instructions = config.load("memory_instructions.md")
        if instructions:
            _cached_memory_instructions = f"\n=== MEMORY SYSTEM INSTRUCTIONS ===\n{instructions}\n==================================="
        else:
            _cached_memory_instructions = ""
    return _cached_memory_instructions


def _build_tools_section() -> str:
    """Build AVAILABLE TOOLS section from registered tools."""
    tools = BaseTool.get_all_instructions()
    lines = ["AVAILABLE TOOLS:"]
    for tool in tools:
        name = tool["name"]
        desc = tool["description"]
        lines.append(f"- {name}: {desc}")
    return "\n".join(lines)


def _build_system_prompt_additions() -> str:
    """Build additional instructions from tool system_prompt_addition() methods."""
    additions = []
    for tool_cls in BaseTool._registry.values():
        tool = tool_cls()
        addition = tool.system_prompt_addition()
        if addition:
            additions.append(addition)
    return "\n".join(additions) if additions else ""


def build_system_prompt(memory: "Memory | None" = None) -> str:
    """Build system prompt dynamically from registered tools."""
    tools_section = _build_tools_section()
    additions = _build_system_prompt_additions()
    memory_section = _build_memory_section(memory)
    memory_instructions = _build_memory_instructions()

    return f"""You are Bob, a helpful AI assistant.
Current Working Directory: {os.getcwd()}

{tools_section}

{additions}

{_get_agent_py_cached()}
{memory_section}
{memory_instructions}
"""
