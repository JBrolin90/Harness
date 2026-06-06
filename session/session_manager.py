"""Session manager - orchestrates task execution with LLM and tools."""
from task.task import Task
from tool_manager import ToolManager
from systemprompt import SystemPromptManager
from llm.provider import ProviderManager
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

    def run_task(self, prompt: str, max_iterations: int = 25, consult_llm=None) -> str:
        """Execute a task with the given prompt."""
        from llm.brain import consult_llm as _consult_llm
        consult_llm_fn = consult_llm or _consult_llm

        system_prompt = self.system_prompt_manager.get_system_prompt()

        tool_manager = ToolManager(self.current_provider.attributes)
        self.current_provider.tools = tool_manager.tools
        execute_tools = tool_manager.execute_tools
        
        task = Task(execute_tools, max_iterations)
        return task.run(
            prompt=prompt,
            system_prompt=system_prompt,
            consult_llm=consult_llm_fn,
            provider=self.current_provider
        )

    def reset(self) -> None:
        """No-op. Each run_task creates a fresh session."""
        pass