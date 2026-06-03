"""Manages conversation history."""
import re


class ConversationState:
    """Manages conversation history."""

    _TOOL_CALL_BLOCK_PATTERN = re.compile(r'```tool_call\n[\s\S]*?\n```')
    _TOOL_CALL_TAG_PATTERN = re.compile(r'<tool_call>[\s\S]*?</tool_call>')

    def __init__(self):
        self.history: list[dict] = []

    def add_user_message(self, content: str) -> None:
        self.history.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        self.history.append({"role": "assistant", "content": content})

    def add_tool_result(self, content: str) -> None:
        self.history.append({"role": "tool", "content": content})

    @staticmethod
    def clean_assistant_text(text: str) -> str:
        if not text:
            return ""
        cleaned = ConversationState._TOOL_CALL_BLOCK_PATTERN.sub('', text)
        cleaned = ConversationState._TOOL_CALL_TAG_PATTERN.sub('', cleaned)
        return cleaned.strip()

    @property
    def messages(self) -> list[dict]:
        return self.history

    def get_stats(self) -> str:
        user = sum(1 for m in self.history if m["role"] == "user")
        assistant = sum(1 for m in self.history if m["role"] == "assistant")
        tool = sum(1 for m in self.history if m["role"] == "tool")
        return f"msgs: {len(self.history)} (u:{user} a:{assistant} t:{tool})"

    def reset(self) -> None:
        self.history = []