"""Agent controller with instance-based state for modularity and testability."""
from conversation import ConversationManager
from iteration_handler import IterationHandler
from tool_manager import ToolManager
from systemprompt import SystemPromptManager
from terminal_history import terminal_history_upgrade
from provider import ProviderManager
from tools.core_config import set_current_provider
from memory import get_memory


class HarnessController:
    """Agent controller with instance-based state for modularity and testability."""

    def __init__(self, provider_name: str = "cloud-pro", memory_path: str | None = None):
        terminal_history_upgrade()
        
        # Provider
        self.current_provider = ProviderManager().get_provider(provider_name)
        set_current_provider(self.current_provider)
        
        # Tools
        self.tool_manager = ToolManager()
        self.tool_manager.setup_for_provider(self.current_provider)
        
        # Memory & system prompt
        self.memory = get_memory()
        self.system_prompt_manager = SystemPromptManager(
            memory=self.memory,
            provider_type=self.current_provider.provider_type,
            attributes=self.current_provider.attributes
        )
        self.conversation_manager = ConversationManager()
        
        print("[Config preloaded]")

    def run_task(self, prompt: str, max_iterations: int = 25, call_llm=None) -> str:
        """Execute a task with the given prompt. Returns the final response."""
        from brain import call_llm as _call_llm
        call_llm_fn = call_llm or _call_llm

        self.system_prompt = self.system_prompt_manager.get_prompt()
        self.conversation_manager.add_user_message(prompt)

        print(f"\n[Task Started] {self.conversation_manager.get_stats()}")

        # Make LLM call
        print(f"[Thinking with {self.current_provider.name} / {self.current_provider.model}...]")
        response = call_llm_fn(
            self.conversation_manager.messages,
            self.system_prompt,
            self.current_provider
        )

        # Process and print response
        print(f"[Model response type: {'tool_call' if response.has_tool_calls else 'text'}]")
        full_text = self.conversation_manager.clean_assistant_text(response.text)
        if response.has_tool_calls:
            tool_names = ", ".join(tc.name for tc in response.tool_calls)
            print(f"Bob: {full_text} [🔧 Calling: {tool_names}]")
        else:
            print(f"Bob: {full_text}")

        self.conversation_manager.add_assistant_message(
            full_text if full_text.strip() else "[Thinking...]"
        )

        # Execute tool loop
        iteration_handler = IterationHandler(self.tool_manager.tool_engine, max_iterations)
        return iteration_handler.execute_loop(
            initial_response=response,
            call_llm=call_llm_fn,
            system_prompt_provider=self,
            conversation_manager=self.conversation_manager
        )

    def reset(self) -> None:
        """Clear conversation history to start fresh."""
        self.conversation_manager.reset()