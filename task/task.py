"""Executes a task: initial LLM call + iterations until completion."""
from task.constants import NO_TEXT_RESPONSE
from task.execute_tools import ExecuteTools
from session.conversation_history import ConversationHistory
from llm.response import LLMResponse, ToolResult, SystemError, NoToolFound, RepetitionError


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
        broke_due_to_repetition = False
        while iteration < self.max_iterations:
            iteration += 1
            response = consult_llm(self.conversation.messages, system_prompt, self._provider)
            
            if response.error:
                return f"[Error: {response.error}]"
            
            # Add response to conversation (for potential tool calls in text format)
            tool_calls_dicts = [tc.to_dict() for tc in response.tool_calls]
            self.conversation.add_model_response(response.text, tool_calls=tool_calls_dicts)

            # Check for repetition BEFORE executing the tool
            # This prevents executing the same tool call twice
            last_msg = next((m for m in reversed(self.conversation.messages) if m["role"] == "assistant"), None)
            if last_msg:
                if self.conversation._repetition_detector.check_after_tool_result(
                    text=last_msg.get("content", ""),
                    has_tool_calls=bool(response.tool_calls)
                ):
                    # Repetition detected - break without executing the tool
                    broke_due_to_repetition = True
                    break

            # Use execute_tools (dispatch or dispatch_with_text_parsing) to handle response
            # This properly handles both structured tool calls AND text-based tool calls
            result = self.execute_tools(response)
            
            if isinstance(result, SystemError):
                return f"[Error: {result}]"
            
            if isinstance(result, NoToolFound):
                # No tool call found - return the text response
                return response.text
            
            # Tool was executed - add result and continue loop
            # skip_check=True because we already did the repetition check pre-execution
            # This avoids double-recording in the repetition detector
            self.conversation.add_tool_result(result, has_tool_calls=bool(response.tool_calls), skip_check=True)

        # Exit loop - handle repetition case specially
        if broke_due_to_repetition:
            # When repetition detected, the last assistant message is the repeated tool call
            # which is not useful content. Remove it and return a repetition message.
            if self.conversation.history and self.conversation.history[-1]["role"] == "assistant":
                self.conversation.history.pop()
            return "[Repetition detected - model repeated the same tool call. Please try again with a different approach.]"

        # Exit loop without final response - use last assistant message from history
        messages = self.conversation.messages
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if msg["role"] == "assistant" and msg["content"].strip():
                return msg["content"]
        
        return NO_TEXT_RESPONSE