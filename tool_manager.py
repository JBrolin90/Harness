"""Tool management - builds tools list and selects appropriate dispatch engine."""
from typing import Callable

from tools.base_tool import BaseTool
from tool_dispatch import dispatch, dispatch_with_text_parsing
from response import LLMResponse, ToolResult, SystemError, NoToolFound


# Type alias for the tool engine function signature
ToolEngine = Callable[[LLMResponse], ToolResult | SystemError | NoToolFound]


class ToolManager:
    """Manages tool registry and dispatch engine selection."""

    def __init__(self):
        self._tools: list[dict] = []
        self.tool_engine: ToolEngine = dispatch

    def build_tools_list(self) -> list[dict]:
        """Build tools list from registered BaseTool classes."""
        self._tools = []
        for tool_cls in BaseTool._registry.values():
            tool = tool_cls()
            self._tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            })
        return self._tools

    def select_dispatch_engine(self, provider_attributes: dict | None = None) -> ToolEngine:
        """Select appropriate dispatch engine based on provider text parsing flags."""
        attrs = provider_attributes or {}
        text_parsing_flags = [
            "text_parse_json_codeblock", "text_parse_json_raw", "text_parse_bash",
            "text_parse_xml", "text_parse_colon_xml", "text_parse_plain_xml"
        ]
        has_text_parsing = any(attrs.get(flag) for flag in text_parsing_flags)
        
        self.tool_engine = dispatch_with_text_parsing if has_text_parsing else dispatch
        return self.tool_engine

    def setup_for_provider(self, provider) -> None:
        """Configure tool manager for a given provider.
        
        Builds tools list and attaches to provider, then selects dispatch engine.
        """
        self.build_tools_list()
        provider.tools = self._tools
        self.select_dispatch_engine(provider.attributes)

    @property
    def tools(self) -> list[dict]:
        """Get the current tools list."""
        return self._tools

    def reload_tools(self) -> list[dict]:
        """Reload tools from registry (useful if tools are registered after init)."""
        return self.build_tools_list()