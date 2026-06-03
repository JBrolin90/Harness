"""Detects repetitive behavior by tracking action signatures."""
import json

from task.constants import SYSTEM_MESSAGE_REPETITION
from task.action_signature import ActionSignature


class RepetitionDetector:
    """Detects repetitive behavior by tracking action signatures."""

    def __init__(self):
        self._previous: ActionSignature | None = None
        self._has_recorded_action: bool = False

    def record(self, action_sig: str | None, assistant_text: str, had_tool_call: bool) -> None:
        """Record current response state for repetition detection on next iteration."""
        self._previous = ActionSignature(action_sig, assistant_text, had_tool_call)
        self._has_recorded_action = True

    def is_repetitive(self, response, action_sig: str | None = None) -> bool:
        """Check if response is repetitive compared to previous recorded response."""
        if not self._has_recorded_action or self._previous is None:
            return False

        prev = self._previous
        current_had_tool_call = getattr(response, 'has_tool_calls', False)

        # Different tool call patterns are not repetition
        if prev.had_tool_call != current_had_tool_call:
            return False

        # Check for repeated tool call signature
        if current_had_tool_call and action_sig and prev.signature:
            if action_sig == prev.signature:
                return True

        # Check for repeated text response (no tool calls)
        if not current_had_tool_call and prev.assistant_text and getattr(response, 'text', None):
            current_text = response.text.strip()
            if current_text and current_text == prev.assistant_text.strip():
                return True

        return False

    def check_after_tool_result(self, text: str, has_tool_calls: bool) -> bool:
        """Check if the current action is repetitive after a tool result."""
        action_sig = self._compute_signature_from_text(text, has_tool_calls)
        
        # Check if repetitive
        is_rep = False
        if self._has_recorded_action and self._previous is not None:
            prev = self._previous
            if prev.had_tool_call == has_tool_calls:
                if has_tool_calls and action_sig and prev.signature == action_sig:
                    is_rep = True
                elif not has_tool_calls and prev.assistant_text and text:
                    if text.strip() == prev.assistant_text.strip():
                        is_rep = True
        
        # Record current
        self._previous = ActionSignature(action_sig, text, has_tool_calls)
        self._has_recorded_action = True
        
        return is_rep

    def _compute_signature_from_text(self, text: str, has_tool_calls: bool) -> str | None:
        """Compute signature from text (for already-cleaned messages)."""
        if not text:
            return None
        
        # If text looks like JSON, use it as signature
        if has_tool_calls:
            import re
            json_match = re.search(r'\{[^}]+\}', text)
            if json_match:
                try:
                    return json.dumps(json.loads(json_match.group()))
                except json.JSONDecodeError:
                    pass
        
        return None

    def get_repetition_message(self) -> str:
        return SYSTEM_MESSAGE_REPETITION