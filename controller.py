import os
import re
from brain import call_llm
from tools import execute_tool, get_tools_instructions
from AGENT import AGENT_md_INGESTIOR
from terminal_history import terminal_history_upgrade
from provider import ProviderManager
from context import create_context_manager, ContextManager


PERSONAS_DIR = os.path.join(os.path.dirname(__file__), "personas")


def load_persona(persona_name: str = "default") -> str:
    """Load a persona definition from the personas directory.
    
    Args:
        persona_name: Name of the persona (directory name in personas/)
        
    Returns:
        Persona definition string to use in system prompt
        """
    persona_path = os.path.join(PERSONAS_DIR, persona_name, "persona.md")
    
    if not os.path.isfile(persona_path):
        print(f"[Harness: Persona '{persona_name}' not found, using default]")
        persona_path = os.path.join(PERSONAS_DIR, "default", "persona.md")
        if not os.path.isfile(persona_path):
            return "You are Bob, a helpful AI assistant."
    
    try:
        with open(persona_path, 'r') as f:
            content = f.read()
        print(f"[Harness: Loaded persona '{persona_name}']")
        return content
    except Exception as e:
        print(f"[Harness: Could not load persona: {e}]")
        return "You are Bob, a helpful AI assistant."


def load_persona_memory(persona_name: str) -> str:
    """Load persona memory file if it exists."""
    memory_path = os.path.join(PERSONAS_DIR, persona_name, "memory.md")
    if os.path.isfile(memory_path):
        try:
            with open(memory_path, 'r') as f:
                return f"\n\nYour memory:\n{f.read()}"
        except Exception:
            pass
    return ""


class HarnessController:
    """Agent controller with instance-based state for modularity and testability."""

    def __init__(self, provider_name: str = "cloud-pro", persona_name: str = "default", enable_context: bool = True):
        terminal_history_upgrade()

        # Initialize the Provider Manager and select the brain
        pm = ProviderManager()
        self.current_provider = pm.get_provider(provider_name)

        if not self.current_provider:
            raise RuntimeError(
                f"[CRITICAL ERROR: No LLM provider found for '{provider_name}']"
                "Check provider.py or providers.json"
            )

        self.persona_name = persona_name
        self.enable_context = enable_context
        self.context = create_context_manager() if enable_context else None
        self.system_prompt = self._build_system_prompt()
        self.conversation_history = []

    def _build_system_prompt(self) -> str:
        persona_text = load_persona(self.persona_name)
        memory_text = load_persona_memory(self.persona_name) if self.enable_context else ""
        context_info = self.context.get_context_summary() if self.context else ""
        return f"""
        {persona_text}{memory_text}
        Current Working Directory: {os.getcwd()}
        {context_info}
        You have access to a local file system via your Harness.
        {get_tools_instructions()}
        {AGENT_md_INGESTIOR()}
        """

    def run_task(self, prompt: str) -> str:
        """Execute a task with the given prompt. Returns the final response."""
        # Detect topic from prompt
        if self.context:
            words = prompt.split()
            topic = words[2] if len(words) > 2 else "general"
            self.context.set_topic(topic)

        self.conversation_history.append({"role": "user", "content": prompt})

        response = call_llm(
            self.conversation_history, self.system_prompt, self.current_provider
        )
        print(f"Bob: {response}")
        self.conversation_history.append({"role": "assistant", "content": response})

        # The Autonomous Tool Loop (ReAct) - serial execution
        while True:
            system_result, file_path = self._execute_next_tool(response)

            if system_result:
                print("\n[Harness feeding system result back to Bob...]")
                
                # If context enabled, check if a memory file was updated
                if self.context and self.enable_context:
                    memory_updated = self.context.check_memory_update(file_path)
                    if memory_updated:
                        self.context.add_memory_update(file_path)
                        # Don't add full result to history - persona manages memory
                        self.conversation_history.append(
                            {"role": "user", "content": "[Memory updated - see memory.md]"}
                        )
                    else:
                        self.conversation_history.append(
                            {"role": "user", "content": system_result}
                        )
                else:
                    self.conversation_history.append(
                        {"role": "user", "content": system_result}
                    )

                response = call_llm(
                    self.conversation_history, self.system_prompt, self.current_provider
                )
                print(f"Bob: {response}")
                self.conversation_history.append({"role": "assistant", "content": response})
            else:
                break

        return response

    def _execute_next_tool(self, response: str) -> tuple[str | None, str | None]:
        """
        Find and execute the first tool command in the response.
        Returns (result, file_path) tuple - file_path is the path argument used.
        """
        regex_map = {
            "!WRITE": r'^\s*!(WRITE)\s+(\S+)',
            "!EDIT":  r'^\s*!(EDIT)\s+(\S+)',
            "!READ":  r'^\s*!(READ)\s+(\S+)',
            "!BASH":  r'^\s*!(BASH)\s+(.+)',
            "!LS":    r'^\s*!(LS)\s+(\S+)'
        }

        matches = []
        for cmd_type, pattern in regex_map.items():
            flags = re.MULTILINE
            if "WRITE" in cmd_type or "EDIT" in cmd_type:
                flags |= re.DOTALL
            m = re.search(pattern, response, flags)
            if m:
                matches.append((m.start(), cmd_type, m))

        if not matches:
            return (None, None)

        matches.sort(key=lambda x: x[0])
        _, tool_cmd, match = matches[0]
        file_path = match.group(2)

        if tool_cmd in ["!WRITE", "!EDIT"]:
            return (execute_tool(tool_cmd, file_path, response), file_path)
        else:
            return (execute_tool(tool_cmd, file_path), None)

    def reset(self):
        """Clear conversation history to start fresh."""
        self.conversation_history = []
        if self.context:
            self.context.reset_session()


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