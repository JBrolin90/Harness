"""Executes a task: initial LLM call + iterations until completion."""
import json

from response import LLMResponse, ToolResult, SystemError

from task.constants import THINKING_PLACEHOLDER, NO_TEXT_RESPONSE
from task.tool_engine import ToolEngine
from session.conversation_history import ConversationHistory
from task.repetition_detector import RepetitionDetector


class Task:
    """Executes a task: initial LLM call + iterations until completion."""

    def __init__(self, tool_engine: ToolEngine, max_iterations: int = 25):
        self.tool_engine = tool_engine
        self.max_iterations = max_iterations
        self.conversation = ConversationHistory()

    def run(self, prompt: str, system_prompt: str, call_llm, provider) -> str:
        self._provider = provider
        self.conversation.add_user_message(prompt)
        print(f"\n[Task Started] {self.conversation.get_stats()}")
        return self._agent_loop(system_prompt, call_llm)

    def _call_llm_and_process(self, messages: list[dict], system_prompt: str, call_llm) -> LLMResponse:
        print(f"[Thinking with {self._provider.name} / {self._provider.model}...]")
        response = call_llm(messages, system_prompt, self._provider)

        print(f"[Model response type: {'tool_call' if response.has_tool_calls else 'text'}]")
        full_text = ConversationHistory.clean_assistant_text(response.text)
        if response.has_tool_calls:
            tool_names = ", ".join(tc.name for tc in response.tool_calls)
            print(f"Bob: {full_text} [🔧 Calling: {tool_names}]")
        else:
            print(f"Bob: {full_text}")

        self.conversation.add_assistant_message(
            full_text if full_text.strip() else THINKING_PLACEHOLDER
        )

        return response

    def _agent_loop(self, system_prompt: str, call_llm) -> str:
        repetition_detector = RepetitionDetector()
        iteration = 0

        while True:
            iteration += 1
            response = self._call_llm_and_process(
                self.conversation.messages,
                system_prompt,
                call_llm
            )

            if not response.has_tool_calls:
                return response.text

            action_sig = self._compute_action_sig(response)

            if repetition_detector.is_repetitive(response, action_sig):
                result = ToolResult(tool_name="system", output=repetition_detector.get_repetition_message())
            else:
                result = self.tool_engine(response)

            match result:
                case ToolResult() as r:
                    result_str = str(r.output) if r.tool_name == "system" else f"Observation: {str(r.output)}"
                case SystemError() as e:
                    result_str = str(e)

            print(f"\n[Harness feeding result back to Bob... {self.conversation.get_stats()}]")
            print(f"Harness: {result_str}\n")

            self.conversation.add_tool_result(result_str)

            print(f"[Model: {self._provider.model}] {self.conversation.get_stats()} (iteration {iteration})")
            print(f"\n================================ End of iteration {iteration} ==========================================\n")

            if iteration >= self.max_iterations:
                print(f"\n[WARNING: Task reached maximum iterations ({self.max_iterations}). Stopping safety check.]")
                print("\n========================== Max Iterations Reached ====================================\n")
                break

            repetition_detector.record(
                action_sig,
                ConversationHistory.clean_assistant_text(response.text),
                response.has_tool_calls
            )

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