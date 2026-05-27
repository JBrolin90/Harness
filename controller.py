import os
import re
import json
from datetime import datetime
from brain import call_llm
from tools import execute_tool, get_tools_instructions
from AGENT import AGENT_md_INGESTIOR
from terminal_history import terminal_history_upgrade
from provider import ProviderManager


class HarnessController:
    """Agent controller with instance-based state for modularity and testability."""

    def __init__(self, provider_name: str = "cloud-pro"):
        terminal_history_upgrade()

        pm = ProviderManager()
        provider = pm.get_provider(provider_name)

        if not provider:
            raise RuntimeError(
                f"[CRITICAL ERROR: No LLM provider found for '{provider_name}']"
                "Check provider.py or providers.json"
            )

        self.current_provider = provider
        self.system_prompt = self._build_system_prompt()
        self.conversation_history = []
        self.session_file = self._get_session_file_path()

    def _get_session_file_path(self) -> str:
        """Generate session file path."""
        session_dir = os.path.join(os.getcwd(), ".bob", "sessions")
        os.makedirs(session_dir, exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        cwd_safe = os.getcwd().replace("/", "_").lstrip("_")
        return os.path.join(session_dir, f"session-{date_str}-{cwd_safe}.json")

    def _save_session(self) -> None:
        """Save conversation history to session file."""
        try:
            os.makedirs(os.path.dirname(self.session_file), exist_ok=True)
            with open(self.session_file, 'w') as f:
                json.dump(self.conversation_history, f, indent=2)
        except Exception as e:
            print(f"[Harness: Warning - could not save session: {e}]")

    def _build_system_prompt(self) -> str:
        """Build system prompt from project.md."""
        project_text = ""
        project_path = os.path.join(os.getcwd(), "project.md")
        if os.path.isfile(project_path):
            try:
                with open(project_path, 'r') as f:
                    project_text = f"\n\nProject Context (project.md):\n{f.read()}"
            except Exception:
                pass

        return f"""
        You are Bob, a helpful AI assistant.{project_text}
        Current Working Directory: {os.getcwd()}
        You have access to a local file system via your Harness.
        {get_tools_instructions()}
        {AGENT_md_INGESTIOR()}
        """

    def run_task(self, prompt: str) -> str:
        """Execute a task with the given prompt. Returns the final response."""
        self.system_prompt = self._build_system_prompt()

        self.conversation_history.append({"role": "user", "content": prompt})

        print(f"\n{self._get_history_stats()}")

        response = call_llm(
            self.conversation_history, self.system_prompt, self.current_provider
        )
        print(f"Bob: {response}")
        self.conversation_history.append({"role": "assistant", "content": response})

        self._save_session()

        # The Autonomous Tool Loop (ReAct) - serial execution
        iteration = 0
        while True:
            system_result, _ = self._execute_next_tool(response)

            if system_result:
                iteration += 1
                print(f"\n[Harness feeding system result back to Bob... {self._get_history_stats()}]")

                self.conversation_history.append(
                    {"role": "user", "content": system_result}
                )

                response = call_llm(
                    self.conversation_history, self.system_prompt, self.current_provider
                )
                print(f"Bob: {response}")
                print(f"[Model: {self.current_provider.model}] {self._get_history_stats()} (iteration {iteration})")
                self.conversation_history.append({"role": "assistant", "content": response})

                self._save_session()
            else:
                break

        return response

    def _execute_next_tool(self, response: str) -> tuple[str | None, str | None]:
        """Find and execute the first tool command in the response."""
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

    def _get_history_stats(self) -> str:
        """Return conversation stats string."""
        user_msgs = sum(1 for m in self.conversation_history if m["role"] == "user")
        assistant_msgs = sum(1 for m in self.conversation_history if m["role"] == "assistant")
        return f"[History: {user_msgs} user / {assistant_msgs} assistant msgs]"

    def reset(self):
        """Clear conversation history to start fresh."""
        self.conversation_history = []
        if os.path.exists(self.session_file):
            try:
                os.remove(self.session_file)
            except Exception:
                pass


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
