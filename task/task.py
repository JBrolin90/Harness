"""Executes a task: initial LLM call + iterations until completion."""
from task.constants import NO_TEXT_RESPONSE
from task.execute_tools import ExecuteTools
from session.conversation_history import ConversationHistory
from response import LLMResponse, ToolCall, ToolResult, SystemError, RepetitionError


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
            
            self.conversation.add_model_response(response.text)

            if not response.has_tool_calls:
                return response.text

            # Execute tool(s) and continue loop
            try:
                self._handle_tools(response)
            except RepetitionError:
                break

        # Exit loop without final response - use last assistant message from history
        messages = self.conversation.messages
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if msg["role"] == "assistant" and msg["content"].strip():
                return msg["content"]
        
        return NO_TEXT_RESPONSE
    
    def _handle_tools(self, response: LLMResponse) -> None:
        """Handle all tool call(s) from LLM response. Raises RepetitionError if detected."""
        for tc in response.tool_calls:
            result = self._execute_tool(tc)
            if isinstance(result, SystemError):
                break
            self.conversation.add_tool_result(result)
    
    def _execute_tool(self, tc: ToolCall) -> ToolResult | SystemError:
        """Execute a single tool call and return the result."""
        print(f"\n[🔧 Harness executing: {tc.name}]")
        try:
            from tools.base_tool import BaseTool
            output = BaseTool.dispatch(tc.name, tc.arguments)
        except (TypeError, KeyError, ValueError) as e:
            return SystemError(f"[SYSTEM ERROR: Invalid arguments for '{tc.name}': {e}]")
        except Exception as e:
            return SystemError(f"[SYSTEM ERROR: Unexpected error in '{tc.name}': {e}]")
        
        if output.startswith("[SYSTEM ERROR"):
            return SystemError(output)
        
        return ToolResult(tool_name=tc.name, output=output)