"""Manages conversation history."""
import re

from task.constants import THINKING_PLACEHOLDER
from task.repetition_detector import RepetitionDetector


class ConversationHistory:
    """Manages conversation history."""

    _TOOL_CALL_BLOCK_PATTERN = re.compile(r'```tool_call\n[\s\S]*?\n```')
    _TOOL_CALL_TAG_PATTERN = re.compile(r'<tool_call>[\s\S]*?</tool_call>')

    def __init__(self):
        self.history: list[dict] = []
        self._repetition_detector = RepetitionDetector()

    def add_user_message(self, content: str) -> None:
        self.history.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        self.history.append({"role": "assistant", "content": content})

    def add_tool_result(self, content: str) -> None:
        self.history.append({"role": "tool", "content": content})

    def add_model_response(self, text: str) -> None:
        """Add model (assistant) response, stripping tool call artifacts."""
        cleaned = self._clean_text(text)
        self.add_assistant_message(cleaned if cleaned.strip() else THINKING_PLACEHOLDER)

    def add_tool(self, result) -> bool:
        """Add tool result. Returns True if added successfully (no repetition), False to stop."""
        match result:
            case _ if hasattr(result, 'tool_name') and hasattr(result, 'output'):
                result_str = str(result.output) if result.tool_name == "system" else f"Observation: {str(result.output)}"
            case _ if hasattr(result, 'message'):
                result_str = str(result.message)
            case _:
                result_str = str(result)

        self.add_tool_result(result_str)
        
        # Check last assistant message for repetition
        last_msg = next((m for m in reversed(self.history) if m["role"] == "assistant"), None)
        if last_msg:
            return not self._repetition_detector.check_after_tool_result(
                text=last_msg["content"],
                has_tool_calls=True
            )
        return True

    @staticmethod
    def _clean_text(text: str) -> str:
        if not text:
            return ""
        cleaned = ConversationHistory._TOOL_CALL_BLOCK_PATTERN.sub('', text)
        cleaned = ConversationHistory._TOOL_CALL_TAG_PATTERN.sub('', cleaned)
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
        self._repetition_detector = RepetitionDetector()