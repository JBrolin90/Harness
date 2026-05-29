"""System prompt builder - dynamically generates prompts from registered tools."""
import os
from typing import TYPE_CHECKING
from tools.base_tool import BaseTool
from AGENT import AGENT_md_INGESTIOR

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
    from memory import load_memory_instructions
    instructions = load_memory_instructions()
    if instructions:
        return f"\n=== MEMORY SYSTEM INSTRUCTIONS ===\n{instructions}\n==================================="
    return ""


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

{AGENT_md_INGESTIOR()}
{memory_section}
{memory_instructions}
"""
