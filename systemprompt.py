"""System prompt builder - dynamically generates prompts from registered tools."""
import os
from tools.base_tool import BaseTool
from AGENT import AGENT_md_INGESTIOR


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


def build_system_prompt() -> str:
    """Build system prompt dynamically from registered tools."""
    tools_section = _build_tools_section()
    additions = _build_system_prompt_additions()

    return f"""You are Bob, a helpful AI assistant.
Current Working Directory: {os.getcwd()}

{tools_section}

{additions}

{AGENT_md_INGESTIOR()}
"""
