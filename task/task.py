"""Executes a task: initial LLM call + iterations until completion."""
from task.constants import NO_TEXT_RESPONSE
from task.execute_tools import ExecuteTools
from session.conversation_history import ConversationHistory


class Task:
    """Executes a task: initial LLM call + iterations until completion."""

    def __init__(self, execute_tools: ExecuteTools, max_iterations: int = 25):
        self.execute_tools = execute_tools
        self.max_iterations = max_iterations
        self.conversation = ConversationHistory()

    def run(self, prompt: str, system_prompt: str, consult_llm, provider) -> str:
        self._provider = provider
        self.conversation.add_user_message(prompt)

        while True:
            response = consult_llm(self.conversation.messages, system_prompt, self._provider)
            self.conversation.add_model_response(response.text)

            if not response.has_tool_calls:
                return response.text

            result = self.execute_tools(response)

            if not self.conversation.add_tool(result):
                break

        return response.text if response.text else NO_TEXT_RESPONSE