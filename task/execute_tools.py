"""Protocol for tool execution engines."""
from typing import Protocol

from response import LLMResponse, ToolResult, SystemError


class ExecuteTools(Protocol):
    """Protocol for tool execution."""
    def __call__(self, response: LLMResponse) -> ToolResult | SystemError: ...