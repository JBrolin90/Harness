"""Agent controller with instance-based state for modularity and testability."""
from conversation import ConversationManager
from iteration_handler import IterationHandler
from tool_manager import ToolManager
from terminal_history import terminal_history_upgrade
from provider import ProviderManager
from systemprompt import build_system_prompt
from tools.core_config import set_current_provider
from memory import get_memory, load_memory_instructions
from response import LLMResponse


class HarnessController:
    """Agent controller with instance-based state for modularity and testability."""

    def __init__(self, provider_name: str = "cloud-pro", memory_path: str | None = None):
        terminal_history_upgrade()
        self._init_provider(provider_name)
        self._init_tools()
        self._init_system_prompt()

    def _init_provider(self, provider_name: str) -> None:
        """Initialize the provider."""
        self.current_provider = ProviderManager().get_provider(provider_name)
        set_current_provider(self.current_provider)

    def _init_tools(self) -> None:
        """Initialize tool manager and configure for provider."""
        self.tool_manager = ToolManager()
        self.tool_manager.setup_for_provider(self.current_provider)

    def _init_system_prompt(self) -> None:
        """Initialize memory and system prompt."""
        self.memory = get_memory()
        self._cached_system_prompt: str = ""
        self._last_memory_content: str = ""
        self._preload_system_prompt()
        self.conversation_manager = ConversationManager()
        print("[Config preloaded]")

    def _preload_system_prompt(self) -> None:
        """Pre-load system prompt at startup to cache AGENT.py and memory_instructions.md."""
        self.system_prompt = build_system_prompt(
            self.memory,
            provider_type=self.current_provider.provider_type,
            attributes=self.current_provider.attributes
        )
        self._cached_system_prompt = self.system_prompt
        self._last_memory_content = str(self.memory.get_all())

    def _get_cached_system_prompt(self) -> str:
        """Get cached system prompt, rebuilding only if memory changed."""
        current_memory = str(self.memory.get_all())
        if current_memory != self._last_memory_content:
            self._cached_system_prompt = build_system_prompt(
                self.memory,
                provider_type=self.current_provider.provider_type,
                attributes=self.current_provider.attributes
            )
            self._last_memory_content = current_memory
        return self._cached_system_prompt

    def run_task(self, prompt: str, max_iterations: int = 25, call_llm=None) -> str:
        """Execute a task with the given prompt. Returns the final response."""
        from brain import call_llm as _call_llm
        call_llm_fn = call_llm or _call_llm

        self.system_prompt = self._get_cached_system_prompt()
        self.conversation_manager.add_user_message(prompt)

        print(f"\n[Task Started] {self.conversation_manager.get_stats()}")

        # Get initial response
        response = self._get_llm_response(call_llm_fn)

        # Process response
        full_text = self.conversation_manager.clean_assistant_text(response.text)
        self._print_response(response, full_text)
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

    def _get_llm_response(self, call_llm_fn=None) -> LLMResponse:
        """Make an LLM call."""
        from brain import call_llm as _call_llm
        fn = call_llm_fn or _call_llm
        print(f"[Thinking with {self.current_provider.name} / {self.current_provider.model}...]")
        return fn(
            self.conversation_manager.messages,
            self.system_prompt,
            self.current_provider
        )

    def _print_response(self, response: LLMResponse, full_text: str) -> None:
        """Print model response with tool call info."""
        print(f"[Model response type: {'tool_call' if response.has_tool_calls else 'text'}]")
        if response.has_tool_calls:
            tool_names = ", ".join(tc.name for tc in response.tool_calls)
            print(f"Bob: {full_text} [🔧 Calling: {tool_names}]")
        else:
            print(f"Bob: {full_text}")

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

    def reset(self) -> None:
        """Clear conversation history to start fresh."""
        self.conversation_manager.reset()