"""Tool management - builds tools list and selects appropriate dispatch engine."""
from tools.base_tool import BaseTool
from tool_dispatch import dispatch, dispatch_with_text_parsing
from task.execute_tools import ExecuteTools
from llm.response import LLMResponse, ToolResult, SystemError, NoToolFound
from logger import debug, info, warning

# Text parsing flag names for logging
TEXT_PARSING_FLAGS = [
    "text_parse_json_codeblock", "text_parse_json_raw", "text_parse_bash",
    "text_parse_xml", "text_parse_colon_xml", "text_parse_plain_xml"
]


class ToolManager:
    """Manages tool registry and dispatch engine selection."""

    def __init__(self, provider_attributes: dict | None = None):
        self._tools: list[dict] = []
        self.build_tools_list()
        self.execute_tools = self.select_dispatch_engine(provider_attributes)

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

    def select_dispatch_engine(self, provider_attributes: dict | None = None) -> ExecuteTools:
        """Select appropriate dispatch engine based on provider text parsing flags.
        
        Logs the decision and which text parsing flags are enabled.
        """
        attrs = provider_attributes or {}
        
        # Check which text parsing flags are enabled
        enabled_flags = [flag for flag in TEXT_PARSING_FLAGS if attrs.get(flag)]
        has_text_parsing = bool(enabled_flags)
        
        if has_text_parsing:
            self.execute_tools = dispatch_with_text_parsing
            info(f"Text parsing ENABLED - using dispatch_with_text_parsing", module="tool_manager")
            info(f"  Enabled flags: {enabled_flags}", module="tool_manager")
        else:
            self.execute_tools = dispatch
            info(f"Text parsing DISABLED - using dispatch (structured tool_calls only)", module="tool_manager")
            info(f"  Provider attributes: {attrs}", module="tool_manager")
        
        return self.execute_tools

    @property
    def tools(self) -> list[dict]:
        """Get the current tools list."""
        return self._tools

    def reload_tools(self) -> list[dict]:
        """Reload tools from registry (useful if tools are registered after init)."""
        return self.build_tools_list()