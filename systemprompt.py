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


def _build_prompt(memory: "Memory | None" = None, provider_type: str = "minimax", attributes: dict | None = None) -> str:
    """Build system prompt dynamically from registered tools."""
    tools_section = _build_tools_section()
    additions = _build_system_prompt_additions()
    memory_section = _build_memory_section(memory)
    memory_instructions = _build_memory_instructions()
    
    enable_small_model_guidance = (attributes or {}).get("enable_small_model_guidance", False)
    
    response_format = """## IMPORTANT: Response Format
- When you call a tool, wait for the observation before responding with your final answer
- Provide substantive summaries of what you find - do NOT prefix responses with "[Executed Action]:" or similar placeholders
- Give direct, helpful answers without repetitive prefixes
- If you need to call multiple tools, wait for all observations first, then provide a consolidated summary"""
    
    code_review_instructions = """## Code Review Instructions
When reviewing a codebase:
1. First list the files to understand the structure
2. Read key files (brain.py, controller.py, AGENT.md, etc.)
3. Provide a summary of what each major component does
4. Identify relationships between components
5. Note any potential issues or areas for improvement"""
    
    parts = [
        "You are Bob, a helpful AI assistant specialized in code review and file operations.",
        f"Current Working Directory: {os.getcwd()}",
        "",
    ]
    
    if enable_small_model_guidance:
        parts.extend([
            response_format,
            "",
            code_review_instructions,
            "",
        ])
    
    parts.extend([
        tools_section,
        "",
        additions,
        "",
        _get_agent_py_cached(),
        memory_section,
        memory_instructions,
    ])
    
    return "\n".join(parts)


class SystemPromptManager:
    """Manages system prompt with caching and memory change detection.
    
    Owns memory lifecycle - fetches memory on first use and detects changes.
    """
    
    def __init__(self, provider_type: str = "minimax", attributes: dict | None = None):
        from memory import get_memory
        self.provider_type = provider_type
        self.attributes = attributes or {}
        self._memory = get_memory()
        self._cached_prompt: str = ""
        self._last_memory_content: str = ""
        self._preload()
    
    def _preload(self) -> None:
        """Pre-load system prompt at startup to cache AGENT.py and memory_instructions.md."""
        self._cached_prompt = _build_prompt(
            memory=self._memory,
            provider_type=self.provider_type,
            attributes=self.attributes
        )
        self._last_memory_content = str(self._memory.get_all())
    
    def get_system_prompt(self) -> str:
        """Get cached system prompt, rebuilding only if memory changed."""
        current = str(self._memory.get_all())
        if current != self._last_memory_content:
            self._cached_prompt = _build_prompt(
                memory=self._memory,
                provider_type=self.provider_type,
                attributes=self.attributes
            )
            self._last_memory_content = current
        return self._cached_prompt
    
    @property
    def memory(self):
        """Access the memory instance."""
        return self._memory