"""Executes a task: initial LLM call + iterations until completion."""
from response import ToolResult, SystemError

from task.constants import THINKING_PLACEHOLDER, NO_TEXT_RESPONSE
from task.tool_engine import ToolEngine
from session.conversation_history import ConversationHistory
from task.repetition_detector import RepetitionDetector, StopReason


class Task:
    """Executes a task: initial LLM call + iterations until completion."""

    def __init__(self, tool_engine: ToolEngine, max_iterations: int = 25):
        self.tool_engine = tool_engine
        self.max_iterations = max_iterations
        self.conversation = ConversationHistory()

    def run(self, prompt: str, system_prompt: str, call_llm, provider) -> str:
        self._provider = provider
        self.conversation.add_user_message(prompt)
        return self._agent_loop(system_prompt, call_llm)

    def _agent_loop(self, system_prompt: str, call_llm) -> str:
        detector = RepetitionDetector()
        iteration = 0

        while True:
            iteration += 1
            response = call_llm(self.conversation.messages, system_prompt, self._provider)

            # Store assistant response
            clean_text = ConversationHistory.clean_assistant_text(response.text)
            self.conversation.add_assistant_message(
                clean_text if clean_text.strip() else THINKING_PLACEHOLDER
            )

            # Check if we should stop, record for next iteration
            stop = detector.evaluate(response, iteration, self.max_iterations)

            if stop == StopReason.NO_TOOL_CALL:
                return response.text
            elif stop == StopReason.MAX_ITERATIONS:
                break
            elif stop == StopReason.REPETITION:
                result = ToolResult(tool_name="system", output=detector.get_repetition_message())
            else:
                result = self.tool_engine(response)

            match result:
                case ToolResult() as r:
                    result_str = str(r.output) if r.tool_name == "system" else f"Observation: {str(r.output)}"
                case SystemError() as e:
                    result_str = str(e)

            self.conversation.add_tool_result(result_str)

        return response.text if response.text else NO_TEXT_RESPONSE

    @property
    def conversation_manager(self):
        """Backwards compat - return wrapped conversation state."""
        return self.conversation