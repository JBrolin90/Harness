from brain import call_llm
from terminal_history import terminal_history_upgrade
from tools import ToolEngine
from provider import ProviderManager
from context import create_context_manager
from topic import Topic
from system_prompt import SystemPrompt
from persona import PersonaManager
from session import SessionManager


class HarnessController:
    """Agent controller with instance-based state for modularity and testability."""

    def __init__(self, provider_name: str = "cloud-pro", persona_name: str = "default", enable_context: bool = True):
        terminal_history_upgrade()

        # Initialize the Provider Manager and select the brain
        pm = ProviderManager()
        provider = pm.get_provider(provider_name)

        if not provider:
            raise RuntimeError(
                f"[CRITICAL ERROR: No LLM provider found for '{provider_name}']"
                "Check provider.py or providers.json"
            )

        # Type narrowed to non-None after RuntimeError
        self.current_provider = provider # type: ignore

        self.persona = PersonaManager(persona_name, enable_context)
        self.context = create_context_manager() if enable_context else None
        self.topic = Topic()
        self.session = SessionManager()
        self.system_prompt = SystemPrompt(
            persona_prompt_fn=self.persona.get_prompt_fragment,
            memory_prompt_fn=self.persona.get_memory_fragment,
            context_summary_fn=self.context.get_context_summary if self.context else None,
        )
        self.tool_engine = ToolEngine() # Instantiate the ToolEngine

    def run_task(self, prompt: str) -> str:
        """Execute a task with the given prompt. Returns the final response."""
        # Refresh system prompt to include latest project.md/memory.md state
        system_prompt = self.system_prompt.build()

        # Check if user explicitly stated a topic
        if not self.topic.is_set:
            detected = self.topic.detect_from_prompt(prompt)
            if detected and self.context:
                self.context.set_topic(detected)

        self.session.add_user_message(prompt)

        print(f"\n{self.session.get_stats()}")

        response = call_llm(
            self.session.conversation_history, system_prompt, self.current_provider
        )
        print(f"Bob: {response}")
        self.session.add_assistant_message(response)

        # Save session after initial exchange
        self.session.save()

        # The Autonomous Tool Loop (ReAct) - serial execution
        iteration = 0
        while True:
            tool_report = self.tool_engine.dispatch(response, self.current_provider.execution_mode)
            
            if tool_report.has_results:
                iteration += 1
                print(f"\n[Harness feeding system result back to Bob... {self.session.get_stats()}]")
                
                self.session.process_tool_execution_report(tool_report)

                response = call_llm(
                    self.session.conversation_history, system_prompt, self.current_provider
                )
                print(f"Bob: {response}")
                print(f"[Model: {self.current_provider.model}] {self.session.get_stats()} (iteration {iteration})")
                self.session.add_assistant_message(response) # Add the new response after tool execution

                # Save session after each iteration
                self.session.save()
            else:
                break

        return response # Return the final response from the LLM

    def reset(self):
        """Clear conversation history and topic to start fresh."""
        self.session.clear()
        self.topic.reset()
        if self.context:
            self.context.reset_session()

    def _execute_next_tool(self, response: str) -> tuple[str | None, str | None]:
        """Backward-compatible wrapper for tool execution."""
        report = self.tool_engine.dispatch(response, "serial")
        if report.has_results:
            # Return first result and determine file_path
            result = report.results[0]
            tool_cmd, _, file_path = report.executed_details[0]
            # Only WRITE/EDIT return file_path in original behavior
            return (result, file_path if tool_cmd in ["!WRITE", "!EDIT"] else None)
        return (None, None)


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
    # CLI entry point
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
