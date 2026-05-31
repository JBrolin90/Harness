"""Agent controller with instance-based state for modularity and testability."""
from brain import call_llm
from tool_dispatch import dispatch, extract_json_string, parse_bash_command
from terminal_history import terminal_history_upgrade
from provider import ProviderManager
from systemprompt import build_system_prompt
from tools.core_config import set_current_provider
from tools.base_tool import BaseTool
from memory import get_memory, load_memory_instructions
from response import LLMResponse, ToolResult, SystemError, NoToolFound


class HarnessController:
    """Agent controller with instance-based state for modularity and testability."""

    def __init__(self, provider_name: str = "cloud-pro", memory_path: str | None = None):
        terminal_history_upgrade()

        self.current_provider = ProviderManager().get_provider(provider_name)
        set_current_provider(self.current_provider)
        self.tool_engine = dispatch
        self.system_prompt = ""
        self._cached_system_prompt: str = ""
        self._last_memory_content: str = ""
        self.conversation_history = []
        self.memory = get_memory(memory_path)
        self._setup_tools()
        self._preload_system_prompt()

    def _preload_system_prompt(self):
        """Pre-load system prompt at startup to cache AGENT.py and memory_instructions.md."""
        self.system_prompt = build_system_prompt(self.memory)
        self._cached_system_prompt = self.system_prompt
        self._last_memory_content = str(self.memory.get_all())
        print("[Config preloaded]")

    def _get_cached_system_prompt(self) -> str:
        """Get cached system prompt, rebuilding only if memory changed."""
        current_memory = str(self.memory.get_all())
        if current_memory != self._last_memory_content:
            # Memory changed, rebuild system prompt
            self._cached_system_prompt = build_system_prompt(self.memory)
            self._last_memory_content = current_memory
        return self._cached_system_prompt

    def _setup_tools(self):
        """Build tools list from registered BaseTool classes and attach to provider."""
        tools = []
        for tool_cls in BaseTool._registry.values():
            tool = tool_cls()
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            })
        self.current_provider.tools = tools

    def run_task(self, prompt: str, max_iterations: int = 25) -> str:
        """Execute a task with the given prompt. Returns the final response."""
        self.system_prompt = self._get_cached_system_prompt()

        self.conversation_history.append({"role": "user", "content": prompt})

        print(f"\n[Task Started] {self._get_history_stats()}")

        print(f"[Thinking with {self.current_provider.name} / {self.current_provider.model}...]")
        response: LLMResponse = call_llm(
            self.conversation_history, self.system_prompt, self.current_provider
        )
        print(f"[Model response type: {'tool_call' if response.has_tool_calls else 'text'}]")

        # Print and store assistant response (preserving thoughts)
        full_assistant_text = str(response.text or "")
        # Clean up any "[Executed Action]:" prefixes from assistant text
        if full_assistant_text.startswith("[Executed Action]:"):
            full_assistant_text = full_assistant_text[len("[Executed Action]:"):].strip()
        
        if response.has_tool_calls:
            tool_names = ", ".join(tc.name for tc in response.tool_calls)
            print(f"Bob: {full_assistant_text} [🔧 Calling: {tool_names}]")
        else:
            print(f"Bob: {full_assistant_text}")
        
        # Record assistant turn (ensure role sequence is preserved)
        self.conversation_history.append({"role": "assistant", "content": str(full_assistant_text)})

        # The Autonomous Tool Loop - now using structured responses
        iteration = 0
        last_action_sig = None
        last_assistant_text = ""
        while iteration < max_iterations:
            # Calculate action signature (valid tool or raw block) for loop detection
            current_tc = response.first_tool_call
            if current_tc:
                current_action_sig = f"{current_tc.name}({current_tc.arguments})"
            else:
                # Extract raw blocks even if parsing failed, to detect repetitive invalid attempts
                raw_json = extract_json_string(full_assistant_text)
                raw_bash = parse_bash_command(full_assistant_text)
                current_action_sig = raw_json or raw_bash

            # Detect immediate repetition to break loops in smaller models
            if (current_action_sig and current_action_sig == last_action_sig) or \
               (iteration > 0 and full_assistant_text.strip() == last_assistant_text.strip() and full_assistant_text.strip()):
                result_str = "Observation: !!! REPETITION ERROR !!! You are repeating yourself. You already have this result in history. Look at previous Observations. Provide your Final Answer now or try a DIFFERENT approach."
                result = ToolResult(tool_name="system", output=result_str)
            else:
                # Dispatch tool call from structured response
                result = self.tool_engine(response)
            
            last_assistant_text = str(full_assistant_text)
            last_action_sig = current_action_sig

            # SystemError = fatal dispatch error → exit loop
            # ToolResult = tool executed → continue loop
            if isinstance(result, NoToolFound):
                print(f"\n========================== End of task after {iteration} iterations ====================================\n")
                break
            
            if isinstance(result, SystemError):
                print(f"\n[SYSTEM ERROR] {result.message}")
                print("\n========================== Task stopped due to system error ====================================\n")
                break

            # ToolResult - tool executed successfully, continue loop
            iteration += 1
            result_str = str(result.output) if result.tool_name == "system" else f"Observation: {str(result.output)}"
            print(f"\n[Harness feeding result back to Bob... {self._get_history_stats()}]")
            print(f"Harness: {result_str}\n")
            
            # Append tool result as user message for next LLM call
            self.conversation_history.append(
                {"role": "user", "content": result_str}
            )

            print(f"[Thinking with {self.current_provider.name} / {self.current_provider.model}...]")
            response = call_llm(
                self.conversation_history, self.system_prompt, self.current_provider
            )
            print(f"[Model response type: {'tool_call' if response.has_tool_calls else 'text'}]")
            
            full_assistant_text = str(response.text or "")
            if response.has_tool_calls:
                tool_names = ", ".join(tc.name for tc in response.tool_calls)
                print(f"Bob: {full_assistant_text} [🔧 Calling: {tool_names}]")
            else:
                print(f"Bob: {full_assistant_text}")
                
            print(f"[Model: {self.current_provider.model}] {self._get_history_stats()} (iteration {iteration})")
            # Clean up any "[Executed Action]:" prefixes
            cleaned_text = full_assistant_text
            if cleaned_text.startswith("[Executed Action]:"):
                cleaned_text = cleaned_text[len("[Executed Action]:"):].strip()
            
            # Always append assistant turn if text exists OR tool calls were made to preserve turn order
            if cleaned_text.strip() or response.has_tool_calls:
                # If text is empty but tool calls exist, ensure we send a valid assistant message
                content = str(cleaned_text) if cleaned_text.strip() else "[Thinking...]"
                self.conversation_history.append({"role": "assistant", "content": content})
            print(f"\n================================ End of iteration {iteration} ==========================================\n")
        else:
            print(f"\n[WARNING: Task reached maximum iterations ({max_iterations}). Stopping safety check.]")
            print("\n========================== Max Iterations Reached ====================================\n")

        return response.text if not response.has_tool_calls else str(response.tool_calls)

    def remember(self, section: str, item: str) -> str:
        """Add an item to a memory section."""
        self.memory.add(section, item)
        return f"[Memory] Added to '{section}': {item}"

    def search_memory(self, query: str) -> list[tuple[str, str]]:
        """Search memory for items matching query."""
        return self.memory.find(query)

    def get_memory_section(self, section: str) -> list[str]:
        """Get all items in a memory section."""
        return self.memory.get(section)

    def get_memory_instructions(self) -> str | None:
        """Load memory instructions if available."""
        return load_memory_instructions()

    def _get_history_stats(self) -> str:
        """Return conversation stats string."""
        user_msgs = sum(1 for m in self.conversation_history if m["role"] == "user")
        assistant_msgs = sum(1 for m in self.conversation_history if m["role"] == "assistant")
        return f"[History: {user_msgs} user / {assistant_msgs} assistant msgs]"

    def reset(self):
        """Clear conversation history to start fresh."""
        self.conversation_history = []


# Module-level convenience for backward compatibility with existing CLI usage
_controller: HarnessController | None = None


def init(provider_name: str = "cloud-pro"):
    """Initialize the global controller instance."""
    global _controller
    _controller = HarnessController(provider_name)


def run_task(prompt: str) -> str:
    """Run task using the global controller instance."""
    if _controller is None:
        raise RuntimeError("Controller not initialized. Call init() first.")
    return _controller.run_task(prompt)


if __name__ == "__main__":
    init()
    while True:
        try:
            prompt = input("You: ")
            if prompt.lower() in ("exit", "quit"):
                break
            run_task(prompt)
        except KeyboardInterrupt:
            print("\n[Exiting]")
            break