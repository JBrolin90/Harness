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

    def add_tool_result_message(self, content: str) -> None:
        """Add a tool result message to history."""
        self.history.append({"role": "tool", "content": content})

    def add_model_response(self, text: str) -> None:
        """Add model (assistant) response, stripping tool call artifacts."""
        cleaned = self._clean_text(text)
        # Only use placeholder if original text had content that got cleaned away
        # An empty text is a genuine empty response, not a placeholder situation
        if text.strip() and not cleaned:
            self.add_assistant_message(THINKING_PLACEHOLDER)
        else:
            self.add_assistant_message(cleaned if cleaned else "")

    def add_tool_result(self, result) -> None:
        """Add tool result to conversation history. Raises RepetitionError if LLM is repeating."""
        match result:
            case _ if hasattr(result, 'tool_name') and hasattr(result, 'output'):
                result_str = str(result.output) if result.tool_name == "system" else f"Observation: {str(result.output)}"
            case _ if hasattr(result, 'message'):
                result_str = str(result.message)
            case _:
                result_str = str(result)

        self.add_tool_result_message(result_str)
        
        # Check last assistant message for repetition
        last_msg = next((m for m in reversed(self.history) if m["role"] == "assistant"), None)
        if last_msg:
            if self._repetition_detector.check_after_tool_result(
                text=last_msg["content"],
                has_tool_calls=True
            ):
                from response import RepetitionError
                raise RepetitionError("LLM repetition detected")

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