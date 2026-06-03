"""Iteration handler - manages the autonomous tool loop."""
import json
from typing import Protocol

from response import LLMResponse, ToolResult, SystemError, NoToolFound
from tool_manager import ToolManager


class ToolEngine(Protocol):
    """Protocol for tool execution engines."""
    def __call__(self, response: LLMResponse) -> ToolResult | SystemError | NoToolFound: ...


class LoopDetection:
    """Tracks action signatures to detect repetitive behavior."""

    def __init__(self):
        self.last_action_sig: str | None = None
        self.last_assistant_text: str = ""
        self.last_had_tool_call: bool = False
        self._has_recorded_action: bool = False

    def check_repetition(self, response: LLMResponse, action_sig: str | None) -> bool:
        if not self._has_recorded_action:
            return False

        current_had_tool_call = response.has_tool_calls

        if self.last_had_tool_call != current_had_tool_call:
            return False

        if current_had_tool_call and action_sig and self.last_action_sig:
            if action_sig == self.last_action_sig:
                return True

        if not current_had_tool_call and self.last_assistant_text and response.text:
            current_text = response.text.strip()
            if current_text and current_text == self.last_assistant_text.strip():
                return True

        return False

    def update(self, action_sig: str | None, assistant_text: str, had_tool_call: bool) -> None:
        self.last_action_sig = action_sig
        self.last_assistant_text = assistant_text
        self.last_had_tool_call = had_tool_call
        self._has_recorded_action = True

    def build_repetition_message(self) -> str:
        return (
            "Observation: !!! REPETITION ERROR !!! "
            "You are repeating yourself. You already have this result in history. "
            "Look at previous Observations. Provide your Final Answer now or try a DIFFERENT approach."
        )


class ConversationState:
    """Manages conversation history."""

    def __init__(self):
        self.history: list[dict] = []

    def add_user_message(self, content: str) -> None:
        self.history.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        self.history.append({"role": "assistant", "content": content})

    def add_tool_result(self, content: str) -> None:
        self.history.append({"role": "tool", "content": content})

    def clean_assistant_text(self, text: str) -> str:
        if not text:
            return ""
        import re
        cleaned = re.sub(r'```tool_call\n[\s\S]*?\n```', '', text)
        cleaned = re.sub(r'<tool_call>[\s\S]*?</tool_call>', '', cleaned)
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


class IterationHandler:
    """Executes the tool loop: initial LLM call + iterations until completion."""

    def __init__(self, provider, max_iterations: int = 25):
        tool_manager = ToolManager()
        tool_manager.setup(provider.attributes)
        provider.tools = tool_manager.tools
        self.tool_engine = tool_manager.tool_engine

        self.provider = provider
        self.max_iterations = max_iterations
        self.conversation = ConversationState()

    def execute(self, prompt: str, system_prompt: str, call_llm) -> str:
        self.conversation.add_user_message(prompt)
        print(f"\n[Task Started] {self.conversation.get_stats()}")

        response = self._call_llm_and_process(
            self.conversation.messages,
            system_prompt,
            call_llm
        )

        if not response.has_tool_calls:
            return response.text

        return self._execute_loop(response, system_prompt, call_llm)

    def _call_llm_and_process(self, messages: list[dict], system_prompt: str, call_llm) -> LLMResponse:
        print(f"[Thinking with {self.provider.name} / {self.provider.model}...]")
        response = call_llm(messages, system_prompt, self.provider)

        print(f"[Model response type: {'tool_call' if response.has_tool_calls else 'text'}]")
        full_text = self.conversation.clean_assistant_text(response.text)
        if response.has_tool_calls:
            tool_names = ", ".join(tc.name for tc in response.tool_calls)
            print(f"Bob: {full_text} [🔧 Calling: {tool_names}]")
        else:
            print(f"Bob: {full_text}")

        self.conversation.add_assistant_message(
            full_text if full_text.strip() else "[Thinking...]"
        )

        return response

    def _execute_loop(self, initial_response: LLMResponse, system_prompt: str, call_llm) -> str:
        response = initial_response
        loop_detection = LoopDetection()

        for iteration in range(self.max_iterations):
            action_sig = self._compute_action_sig(response)

            if loop_detection.check_repetition(response, action_sig):
                result = ToolResult(tool_name="system", output=loop_detection.build_repetition_message())
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

            loop_detection.update(action_sig, self.conversation.clean_assistant_text(response.text), response.has_tool_calls)
        else:
            print(f"\n[WARNING: Task reached maximum iterations ({self.max_iterations}). Stopping safety check.]")
            print("\n========================== Max Iterations Reached ====================================\n")

        return response.text if response.text else "[Task completed but no text response received]"

    def _compute_action_sig(self, response: LLMResponse) -> str | None:
        if response.first_tool_call:
            tc = response.first_tool_call
            return f"{tc.name}({json.dumps(tc.arguments, sort_keys=True)})"

        from tool_dispatch import extract_json_string, parse_bash_command
        raw_json = extract_json_string(response.text or "")
        raw_bash = parse_bash_command(response.text or "")
        return raw_json or raw_bash

    @property
    def conversation_manager(self):
        """Backwards compat - return wrapped conversation state."""
        return self.conversation