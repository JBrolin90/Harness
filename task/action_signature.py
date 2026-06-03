"""Represents a unique action signature for repetition detection."""
from dataclasses import dataclass


@dataclass
class ActionSignature:
    """Represents a unique action signature for repetition detection."""
    signature: str | None
    assistant_text: str
    had_tool_call: bool