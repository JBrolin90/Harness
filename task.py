import json
import re
from dataclasses import dataclass
from typing import Protocol

from response import LLMResponse, ToolResult, SystemError, NoToolFound
from tool_manager import ToolManager


# Constants for output messages
SYSTEM_MESSAGE_REPETITION = (
    "Observation: !!! REPETITION ERROR !!! "
    "You are repeating yourself. You already have this result in history. "
    "Look at previous Observations. Provide your Final Answer now or try a DIFFERENT approach."
)
THINKING_PLACEHOLDER = "[Thinking...]"
NO_TEXT_RESPONSE = "[Task completed but no text response received]"


class ToolEngine(Protocol):
    """Protocol for tool execution engines."""
    def __call__(self, response: LLMResponse) -> ToolResult | SystemError | NoToolFound: ...


@dataclass
class ActionSignature:
    """Represents a unique action signature for repetition detection."""
    signature: str | None
    assistant_text: str
    had_tool_call: bool


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


class Task:
    """Executes a task: initial LLM call + iterations until completion."""

    def __init__(self, provider, max_iterations: int = 25):
        tool_manager = ToolManager()
        tool_manager.setup(provider.attributes)
        provider.tools = tool_manager.tools
        self.tool_engine = tool_manager.tool_engine

        self.provider = provider
        self.max_iterations = max_iterations
        self.conversation = ConversationState()

    def run(self, prompt: str, system_prompt: str, call_llm) -> str:
        self.conversation.add_user_message(prompt)
        print(f"\n[Task Started] {self.conversation.get_stats()}")

        response = self._call_llm_and_process(
            self.conversation.messages,
            system_prompt,
            call_llm
        )

        if not response.has_tool_calls:
            return response.text

        return self._agent_loop(response, system_prompt, call_llm)

    def _call_llm_and_process(self, messages: list[dict], system_prompt: str, call_llm) -> LLMResponse:
        print(f"[Thinking with {self.provider.name} / {self.provider.model}...]")
        response = call_llm(messages, system_prompt, self.provider)

        print(f"[Model response type: {'tool_call' if response.has_tool_calls else 'text'}]")
        full_text = ConversationState.clean_assistant_text(response.text)
        if response.has_tool_calls:
            tool_names = ", ".join(tc.name for tc in response.tool_calls)
            print(f"Bob: {full_text} [🔧 Calling: {tool_names}]")
        else:
            print(f"Bob: {full_text}")

        self.conversation.add_assistant_message(
            full_text if full_text.strip() else THINKING_PLACEHOLDER
        )

        return response

    def _agent_loop(self, initial_response: LLMResponse, system_prompt: str, call_llm) -> str:
        response = initial_response
        repetition_detector = RepetitionDetector()

        for iteration in range(self.max_iterations):
            action_sig = self._compute_action_sig(response)

            if repetition_detector.is_repetitive(response, action_sig):
                result = ToolResult(tool_name="system", output=repetition_detector.get_repetition_message())
            else:
                result = self.tool_engine(response)

            if isinstance(result, NoToolFound):
                print(f"\n========================== End of task after {iteration} iterations ====================================\n")
                break

            if isinstance(result, SystemError):
                print(f"\n[SYSTEM ERROR] {result.message}")
                print("\n========================== Task stopped due to system error ====================================\n")
                break

            result_str = str(result.output) if result.tool_name == "system" else f"Observation: {str(result.output)}"
            print(f"\n[Harness feeding result back to Bob... {self.conversation.get_stats()}]")
            print(f"Harness: {result_str}\n")

            self.conversation.add_tool_result(result_str)

            response = self._call_llm_and_process(
                self.conversation.messages,
                system_prompt,
                call_llm
            )

            print(f"[Model: {self.provider.model}] {self.conversation.get_stats()} (iteration {iteration + 1})")
            print(f"\n================================ End of iteration {iteration + 1} ==========================================\n")

            repetition_detector.record(
                action_sig,
                ConversationState.clean_assistant_text(response.text),
                response.has_tool_calls
            )
        else:
            print(f"\n[WARNING: Task reached maximum iterations ({self.max_iterations}). Stopping safety check.]")
            print("\n========================== Max Iterations Reached ====================================\n")

        return response.text if response.text else NO_TEXT_RESPONSE

    def _compute_action_sig(self, response: LLMResponse) -> str | None:
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

    @property
    def conversation_manager(self):
        """Backwards compat - return wrapped conversation state."""
        return self.conversation