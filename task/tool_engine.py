"""Protocol for tool execution engines."""
from typing import Protocol

from response import LLMResponse, ToolResult, SystemError


class ToolEngine(Protocol):
    """Protocol for tool execution engines."""
    def __call__(self, response: LLMResponse) -> ToolResult | SystemError: ...