"""Agent controller with instance-based state for modularity and testability."""
from iteration_handler import IterationHandler
from systemprompt import SystemPromptManager
from provider import ProviderManager
from tools.core_config import set_current_provider


class HarnessController:
    """Agent controller - thin orchestrator delegating to specialized components.
    
    Responsibilities:
    - Provider setup
    - System prompt management
    - Delegating to IterationHandler for task execution
    """

    def __init__(self, provider_name: str = "cloud-pro", memory_path: str | None = None):
        # Provider
        self.current_provider = ProviderManager().get_provider(provider_name)
        set_current_provider(self.current_provider)
        
        # System prompt (owns memory internally)
        self.system_prompt_manager = SystemPromptManager(
            provider_type=self.current_provider.provider_type,
            attributes=self.current_provider.attributes
        )
        
        print("[Config preloaded]")

    def run_task(self, prompt: str, max_iterations: int = 25, call_llm=None) -> str:
        """Execute a task with the given prompt. Returns the final response."""
        from brain import call_llm as _call_llm
        call_llm_fn = call_llm or _call_llm

        system_prompt = self.system_prompt_manager.get_system_prompt()

        # Delegate to IterationHandler which encapsulates:
        # - Tool management
        # - LLM calls
        # - Conversation state
        # - Loop detection
        iteration_handler = IterationHandler(self.current_provider, max_iterations)
        return iteration_handler.execute(
            prompt=prompt,
            system_prompt=system_prompt,
            call_llm=call_llm_fn
        )

    def reset(self) -> None:
        """Clear conversation history to start fresh."""
        # Controller doesn't own conversation state anymore
        # Each run_task creates a fresh IterationHandler
        pass