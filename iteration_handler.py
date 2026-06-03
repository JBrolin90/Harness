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
        """Detect if the model is repeating itself."""
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
        """Update tracking state after each iteration."""
        self.last_action_sig = action_sig
        self.last_assistant_text = assistant_text
        self.last_had_tool_call = had_tool_call
        self._has_recorded_action = True

    def build_repetition_message(self) -> str:
        """Build a message to guide the model out of repetition."""
        return (
            "Observation: !!! REPETITION ERROR !!! "
            "You are repeating yourself. You already have this result in history. "
            "Look at previous Observations. Provide your Final Answer now or try a DIFFERENT approach."
        )


class IterationHandler:
    """Manages the autonomous tool loop execution and tool dispatch."""

    def __init__(self, provider, max_iterations: int = 25):
        # Tool management
        tool_manager = ToolManager()
        tool_manager.setup(provider.attributes)
        provider.tools = tool_manager.tools
        self.tool_engine = tool_manager.tool_engine
        
        self.provider = provider
        self.max_iterations = max_iterations

    def execute_loop(
        self,
        initial_response: LLMResponse,
        call_llm,
        system_prompt,
        conversation_manager
    ) -> str:
        """Execute the tool-calling loop until completion or max iterations.
        
        Args:
            initial_response: The first LLM response to process
            call_llm: Callable that takes (history, system_prompt, config) and returns LLMResponse
            system_prompt: Current system prompt string
            conversation_manager: ConversationManager instance for history access
            
        Returns:
            Final response text from the model
        """
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

            iteration += 1
            result_str = str(result.output) if result.tool_name == "system" else f"Observation: {str(result.output)}"
            print(f"\n[Harness feeding result back to Bob... {conversation_manager.get_stats()}]")
            print(f"Harness: {result_str}\n")

            conversation_manager.add_tool_result(result_str)

            print(f"[Thinking with {self.provider.name} / {self.provider.model}...]")
            response = call_llm(
                conversation_manager.messages,
                system_prompt,
                self.provider
            )

            full_text = conversation_manager.clean_assistant_text(response.text)
            if response.has_tool_calls:
                tool_names = ", ".join(tc.name for tc in response.tool_calls)
                print(f"Bob: {full_text} [🔧 Calling: {tool_names}]")
            else:
                print(f"Bob: {full_text}")

            print(f"[Model: {self.provider.model}] {conversation_manager.get_stats()} (iteration {iteration + 1})")

            if full_text.strip() or response.has_tool_calls:
                content = full_text if full_text.strip() else "[Thinking...]"
                conversation_manager.add_assistant_message(content)

            print(f"\n================================ End of iteration {iteration + 1} ==========================================\n")

            loop_detection.update(action_sig, full_text, response.has_tool_calls)
        else:
            print(f"\n[WARNING: Task reached maximum iterations ({self.max_iterations}). Stopping safety check.]")
            print("\n========================== Max Iterations Reached ====================================\n")

        return response.text if response.text else "[Task completed but no text response received]"

    def _compute_action_sig(self, response: LLMResponse) -> str | None:
        """Compute action signature for loop detection."""
        if response.first_tool_call:
            tc = response.first_tool_call
            return f"{tc.name}({json.dumps(tc.arguments, sort_keys=True)})"

        from tool_dispatch import extract_json_string, parse_bash_command
        raw_json = extract_json_string(response.text or "")
        raw_bash = parse_bash_command(response.text or "")
        return raw_json or raw_bash