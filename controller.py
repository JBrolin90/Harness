import re
from brain import call_llm
from tools import execute_tool
from terminal_history import terminal_history_upgrade
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
        self.current_provider = provider

        # Define regexes for tool detection once
        self._tool_regex_map = {
            "!WRITE": r'^\s*!(WRITE)\s+(\S+)',
            "!EDIT":  r'^\s*!(EDIT)\s+(\S+)',
            "!READ":  r'^\s*!(READ)\s+(\S+)',
            "!BASH":  r'^\s*!(BASH)\s+(.+)',
            "!LS":    r'^\s*!(LS)\s+(\S+)'
        }

        self.persona = PersonaManager(persona_name, enable_context)
        self.context = create_context_manager() if enable_context else None
        self.topic = Topic()
        self.session = SessionManager()
        self.system_prompt = SystemPrompt(
            persona_prompt_fn=self.persona.get_prompt_fragment,
            memory_prompt_fn=self.persona.get_memory_fragment,
            context_summary_fn=self.context.get_context_summary if self.context else None,
        )

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
            combined_system_results = []
            executed_tools_details = [] # Stores (tool_cmd, result, file_path) for compaction

            if self.current_provider.execution_mode == "parallel":
                combined_system_results, executed_tools_details = self._execute_tools_parallel(response)
            else: # serial mode
                system_result, file_path, tool_cmd = self._execute_tool_serial(response)
                if system_result:
                    combined_system_results.append(system_result)
                    executed_tools_details.append((tool_cmd, system_result, file_path))

            if combined_system_results:
                iteration += 1
                print(f"\n[Harness feeding system result back to Bob... {self.session.get_stats()}]")

                full_result_text = "\n\n".join(combined_system_results)
                self.session.add_tool_result(full_result_text, None) # file_path is handled by summarizer

                # History Compaction for any successful writes/edits in this batch
                for tool_cmd, res, file_path_for_compaction in executed_tools_details:
                    if tool_cmd in ["!WRITE", "!EDIT"] and "Successfully" in res:
                        # Find the last assistant message that contains the original tool call
                        # This assumes the tool call was in the immediately preceding assistant message
                        # A more robust solution might involve tracking message IDs or more complex parsing
                        for i in range(len(self.session.conversation_history) - 2, -1, -1):
                            msg = self.session.conversation_history[i]
                            if msg["role"] == "assistant" and (tool_cmd in msg["content"] and file_path_for_compaction in msg["content"]):
                                compacted = re.sub(r'<<<.*?>>>', '[BLOCK CONTENT SAVED TO DISK]', msg["content"], flags=re.DOTALL)
                                self.session.conversation_history[i]["content"] = compacted
                                break

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

    def _execute_tool_serial(self, response: str) -> tuple[str | None, str | None, str | None]:
        """
        Find and execute the first tool command in the response.
        Returns (result, file_path, tool_cmd) tuple.
        """
        matches = []
        for cmd_type, pattern in self._tool_regex_map.items():
            flags = re.MULTILINE
            if "WRITE" in cmd_type or "EDIT" in cmd_type:
                flags |= re.DOTALL
            m = re.search(pattern, response, flags)
            if m:
                matches.append((m.start(), cmd_type, m))

        if not matches:
            return (None, None, None)

        matches.sort(key=lambda x: x[0])
        _, tool_cmd, match = matches[0]
        file_path = match.group(2)

        if tool_cmd in ["!WRITE", "!EDIT"]:
            return (execute_tool(tool_cmd, file_path, response), file_path, tool_cmd)
        else:
            return (execute_tool(tool_cmd, file_path), file_path, tool_cmd)

    def _execute_next_tool(self, response: str) -> tuple[str | None, str | None]:
        """Backward-compatible wrapper returning 2-tuple for non-WRITE/EDIT tools."""
        result, file_path, tool_cmd = self._execute_tool_serial(response)
        # Original behavior: only WRITE/EDIT returned file_path
        return (result, file_path if tool_cmd in ["!WRITE", "!EDIT"] else None)


    def _execute_tools_parallel(self, response: str) -> tuple[list[str], list[tuple[str, str, str]]]:
        """
        Find and execute ALL tool commands in the response.
        Returns (list of results, list of (tool_cmd, result, file_path) for compaction).
        """
        all_matches = []
        for cmd_type, pattern in self._tool_regex_map.items():
            flags = re.MULTILINE
            if "WRITE" in cmd_type or "EDIT" in cmd_type:
                flags |= re.DOTALL
            
            # Use finditer to catch multiple calls of the same type
            for m in re.finditer(pattern, response, flags):
                all_matches.append((m.start(), cmd_type, m))

        if not all_matches:
            return ([], [])

        # Sort by occurrence in the text
        all_matches.sort(key=lambda x: x[0])

        combined_system_results = []
        executed_tools_details = [] # (tool_cmd, result, file_path)

        for _, tool_cmd, match in all_matches:
            file_path = match.group(2)
            if tool_cmd in ["!WRITE", "!EDIT"]:
                result = execute_tool(tool_cmd, file_path, response)
            else:
                result = execute_tool(tool_cmd, file_path)
            
            combined_system_results.append(result)
            executed_tools_details.append((tool_cmd, result, file_path))

        return (combined_system_results, executed_tools_details)

    def reset(self):
        """Clear conversation history and topic to start fresh."""
        self.session.clear()
        self.topic.reset()
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
