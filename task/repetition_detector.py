"""Detects repetitive behavior by tracking action signatures."""
import json
from enum import StrEnum

from response import LLMResponse

from task.constants import SYSTEM_MESSAGE_REPETITION
from task.action_signature import ActionSignature
from session.conversation_history import ConversationHistory


class StopReason(StrEnum):
    NO_TOOL_CALL = "no_tool_call"
    MAX_ITERATIONS = "max_iterations"
    REPETITION = "repetition"


class RepetitionDetector:
    """Detects repetitive behavior by tracking action signatures."""

    def __init__(self):
        self._previous: ActionSignature | None = None
        self._has_recorded_action: bool = False

    def evaluate(self, response: LLMResponse, iteration: int, max_iterations: int) -> StopReason | None:
        """Evaluate response, record state for next iteration, return stop reason."""
        action_sig = self.compute_signature(response)

        # Check if we should stop
        if iteration >= max_iterations:
            return StopReason.MAX_ITERATIONS

        if not response.has_tool_calls:
            return StopReason.NO_TOOL_CALL

        if self.is_repetitive(response, action_sig):
            return StopReason.REPETITION

        # Record for repetition detection on next iteration
        self.record(
            action_sig,
            ConversationHistory._clean_text(response.text),
            response.has_tool_calls
        )

        return None

    def record(self, action_sig: str | None, assistant_text: str, had_tool_call: bool) -> None:
        """Record current response state for repetition detection on next iteration."""
        self._previous = ActionSignature(action_sig, assistant_text, had_tool_call)
        self._has_recorded_action = True

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

    def get_repetition_message(self) -> str:
        return SYSTEM_MESSAGE_REPETITION

    @staticmethod
    def compute_signature(response: LLMResponse) -> str | None:
        """Compute unique signature for a response to detect repetition."""
        if response.first_tool_call:
            tc = response.first_tool_call
            return f"{tc.name}({json.dumps(tc.arguments, sort_keys=True)})"

        from tool_dispatch import extract_json_string, parse_bash_command
        raw_json = extract_json_string(response.text or "")
        raw_bash = parse_bash_command(response.text or "")

        result = raw_json or raw_bash
        if result:
            return json.dumps(result)
        return None