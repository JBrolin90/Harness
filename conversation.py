"""Conversation history management with statistics and text utilities."""
from typing import Any


class ConversationManager:
    """Manages conversation history and provides conversation utilities."""

    def __init__(self):
        self.history: list[dict[str, Any]] = []

    def add_user_message(self, content: str) -> None:
        """Add a user message to history."""
        self.history.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to history."""
        self.history.append({"role": "assistant", "content": content})

    def add_tool_result(self, result: str) -> None:
        """Add a tool result as a user message (Harness feedback)."""
        self.history.append({"role": "user", "content": result})

    def get_stats(self) -> str:
        """Return conversation stats string."""
        user_msgs = sum(1 for m in self.history if m["role"] == "user")
        assistant_msgs = sum(1 for m in self.history if m["role"] == "assistant")
        return f"[History: {user_msgs} user / {assistant_msgs} assistant msgs]"

    def clean_assistant_text(self, text: str | None) -> str:
        """Standardize cleaning of assistant response text."""
        content = str(text or "")
        if content.startswith("[Executed Action]:"):
            content = content[len("[Executed Action]:"):].strip()
        return content

    def reset(self) -> None:
        """Clear conversation history to start fresh."""
        self.history = []

    @property
    def messages(self) -> list[dict[str, Any]]:
        """Access the raw history for LLM calls."""
        return self.history