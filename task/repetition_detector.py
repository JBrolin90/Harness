"""Detects repetitive behavior by tracking action signatures."""
from response import LLMResponse

from task.constants import SYSTEM_MESSAGE_REPETITION
from task.action_signature import ActionSignature


class RepetitionDetector:
    """Detects repetitive behavior by tracking action signatures."""

    def __init__(self):
        self._previous: ActionSignature | None = None
        self._has_recorded_action: bool = False

    def is_repetitive(self, response: LLMResponse, action_sig: str | None) -> bool:
        if not self._has_recorded_action or self._previous is None:
            return False

        prev = self._previous
        current_had_tool_call = response.has_tool_calls

        # Different tool call patterns are not repetition
        if prev.had_tool_call != current_had_tool_call:
            return False

        # Check for repeated tool call signature
        if current_had_tool_call and action_sig and prev.signature:
            if action_sig == prev.signature:
                return True

        # Check for repeated text response (no tool calls)
        if not current_had_tool_call and prev.assistant_text and response.text:
            current_text = response.text.strip()
            if current_text and current_text == prev.assistant_text.strip():
                return True

        return False

    def record(self, action_sig: str | None, assistant_text: str, had_tool_call: bool) -> None:
        self._previous = ActionSignature(action_sig, assistant_text, had_tool_call)
        self._has_recorded_action = True

    def get_repetition_message(self) -> str:
        return SYSTEM_MESSAGE_REPETITION