"""Executes a task: initial LLM call + iterations until completion."""
from task.constants import NO_TEXT_RESPONSE
from task.tool_engine import ToolEngine
from session.conversation_history import ConversationHistory


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
        while True:
            response = call_llm(self.conversation.messages, system_prompt, self._provider)
            self.conversation.add_model_response(response.text)

            if not response.has_tool_calls:
                return response.text

            result = self.tool_engine(response)

            if self.conversation.add_tool_response(result):
                break

        return response.text if response.text else NO_TEXT_RESPONSE

    @property
    def conversation_manager(self):
        """Backwards compat - return wrapped conversation state."""
        return self.conversation