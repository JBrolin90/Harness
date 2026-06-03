"""Session manager - orchestrates task execution with LLM and tools."""
from task import Task
from systemprompt import SystemPromptManager
from provider import ProviderManager
from tools.core_config import set_current_provider


class SessionManager:
    """Manages a session for running tasks with an LLM."""

    def __init__(self, provider_name: str = "cloud-pro", memory_path: str | None = None):
        self.current_provider = ProviderManager().get_provider(provider_name)
        set_current_provider(self.current_provider)
        self.system_prompt_manager = SystemPromptManager(
            provider_type=self.current_provider.provider_type,
            attributes=self.current_provider.attributes
        )
        print("[Config preloaded]")

    def run_task(self, prompt: str, max_iterations: int = 25, call_llm=None) -> str:
        """Execute a task with the given prompt."""
        from brain import call_llm as _call_llm
        call_llm_fn = call_llm or _call_llm

        system_prompt = self.system_prompt_manager.get_system_prompt()

        task = Task(self.current_provider, max_iterations)
        return task.run(
            prompt=prompt,
            system_prompt=system_prompt,
            call_llm=call_llm_fn
        )

    def reset(self) -> None:
        """No-op. Each run_task creates a fresh session."""
        pass