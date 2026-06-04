"""Structured representation of LLM responses and tool calls."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """A single tool call with name and arguments."""
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Structured response from the LLM."""
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    error: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains any tool calls."""
        return len(self.tool_calls) > 0

    @property
    def first_tool_call(self) -> ToolCall | None:
        """Get the first tool call if any."""
        return self.tool_calls[0] if self.tool_calls else None


@dataclass
class ToolResult:
    """Result from executing a tool."""
    tool_name: str
    output: str
    is_error: bool = False

    def __bool__(self) -> bool:
        """Return True for successful execution, False if error (for loop continuation)."""
        return not self.is_error

    def __str__(self) -> str:
        """Return just the output string for convenience."""
        return self.output


@dataclass
class SystemError:
    """System-level error that should stop the loop."""
    message: str

    def __bool__(self) -> bool:
        """Return False to signal loop should stop."""
        return False

    def __str__(self) -> str:
        """Return the error message."""
        return self.message


class RepetitionError(Exception):
    """Raised when LLM repetition is detected - loop should stop."""
    pass


@dataclass
class NoToolFound:
    """No tool call found in response - loop should stop."""
    def __bool__(self) -> bool:
        """Return False since no tool was found."""
        return False