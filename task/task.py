"""Executes a task: initial LLM call + iterations until completion."""
from task.constants import NO_TEXT_RESPONSE
from task.execute_tools import ExecuteTools
from session.conversation_history import ConversationHistory
from llm.response import LLMResponse, ToolCall, ToolResult, SystemError, NoToolFound, RepetitionError


class Task:
    """Executes a task: initial LLM call + iterations until completion."""

    def __init__(self, execute_tools: ExecuteTools, max_iterations: int = 25):
        self.execute_tools = execute_tools
        self.max_iterations = max_iterations
        self.conversation = ConversationHistory()

    def run(self, prompt: str, system_prompt: str, consult_llm, provider) -> str:
        self._provider = provider
        self.conversation.add_user_message(prompt)

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            response = consult_llm(self.conversation.messages, system_prompt, self._provider)
            
            if response.error:
                return f"[Error: {response.error}]"
            
            # Add response to conversation (for potential tool calls in text format)
            tool_calls_dicts = [tc.to_dict() for tc in response.tool_calls]
            self.conversation.add_model_response(response.text, tool_calls=tool_calls_dicts)

            # Use execute_tools (dispatch or dispatch_with_text_parsing) to handle response
            # This properly handles both structured tool calls AND text-based tool calls
            result = self.execute_tools(response)
            
            if isinstance(result, SystemError):
                return f"[Error: {result}]"
            
            if isinstance(result, NoToolFound):
                # No tool call found - return the text response
                return response.text
            
            # Tool was executed - add result and continue loop
            self.conversation.add_tool_result(result)

        # Exit loop without final response - use last assistant message from history
        messages = self.conversation.messages
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if msg["role"] == "assistant" and msg["content"].strip():
                return msg["content"]
        
        return NO_TEXT_RESPONSE