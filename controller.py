from brain import call_llm
from tool_dispatch import tool_dispatch
from terminal_history import terminal_history_upgrade
from provider import ProviderManager
from systemprompt import build_system_prompt
from tools.core_config import set_current_provider
from tools.base_tool import BaseTool


class HarnessController:
    """Agent controller with instance-based state for modularity and testability."""

    def __init__(self, provider_name: str = "cloud-pro"):
        terminal_history_upgrade()

        self.current_provider = ProviderManager().get_provider(provider_name)
        set_current_provider(self.current_provider)
        self.tool_engine = tool_dispatch
        self.system_prompt = ""
        self.conversation_history = []
        self._setup_tools()

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

    def run_task(self, prompt: str, max_iterations: int = 10) -> str:
        """Execute a task with the given prompt. Returns the final response."""
        self.system_prompt = build_system_prompt()

        self.conversation_history.append({"role": "user", "content": prompt})

        print(f"\n{self._get_history_stats()}")

        response = call_llm(
            self.conversation_history, self.system_prompt, self.current_provider
        )
        print(f"Bob: {response}")
        self.conversation_history.append({"role": "assistant", "content": response})

        # The Autonomous Tool Loop (ReAct)
        iteration = 0
        while iteration < max_iterations:
            system_result = self.tool_engine(response)

            # None = no tool call found → exit loop
            # SystemError = fatal dispatch error → exit loop (stop)
            # ToolResult = tool executed → continue loop
            if not system_result:
                print(f"\n========================== End of task after {iteration} iterations ====================================\n")
                break

            iteration += 1
            result_str = str(system_result)
            print(f"\n[Harness feeding system result back to Bob... {self._get_history_stats()}]")
            print(f"Harness: {result_str}\n")
            self.conversation_history.append(
                {"role": "user", "content": result_str}
            )

            response = call_llm(
                self.conversation_history, self.system_prompt, self.current_provider
            )
            print(f"Bob: {response}")
            print(f"[Model: {self.current_provider.model}] {self._get_history_stats()} (iteration {iteration})")
            self.conversation_history.append({"role": "assistant", "content": response})
            print(f"\n================================ End of iteration {iteration} ==========================================\n")
        else:
            print("\n[WARNING: Task reached maximum iterations (" + str(max_iterations) + "). Stopping safety check.]")
            print("\n========================== Max Iterations Reached ====================================\n")

        return response

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
