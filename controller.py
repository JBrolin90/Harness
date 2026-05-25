import os
import re
import json
from datetime import datetime
from typing import Optional
from brain import call_llm
from tools import execute_tool, get_tools_instructions
from AGENT import AGENT_md_INGESTIOR
from terminal_history import terminal_history_upgrade
from provider import ProviderManager
from context import create_context_manager
from persona import PersonaManager


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

        self.persona = PersonaManager(persona_name, enable_context)
        self.context = create_context_manager() if enable_context else None
        self.user_specified_topic: Optional[str] = None
        self.system_prompt = self._build_system_prompt()
        self.conversation_history = []
        self.session_file = self._get_session_file_path()

    def _get_session_file_path(self) -> str:
        """Generate session file path: session-<date>-<cwd>.json"""
        date_str = datetime.now().strftime("%Y%m%d")
        cwd_safe = os.getcwd().replace("/", "_").lstrip("_")
        return f"session-{date_str}-{cwd_safe}.json"

    def _save_session(self) -> None:
        """Save conversation history to session file."""
        try:
            with open(self.session_file, 'w') as f:
                json.dump(self.conversation_history, f, indent=2)
        except Exception as e:
            print(f"[Harness: Warning - could not save session: {e}]")

    def _build_system_prompt(self) -> str:
        persona_text = self.persona.get_prompt_fragment()
        memory_text = self.persona.get_memory_fragment()

        # Load project.md from CWD as the shared source of truth
        project_text = ""
        project_path = os.path.join(os.getcwd(), "project.md")
        if os.path.isfile(project_path):
            try:
                with open(project_path, 'r') as f:
                    project_text = f"\n\nProject Context (project.md):\n{f.read()}"
            except Exception:
                pass

        context_info = self.context.get_context_summary() if self.context else ""

        return f"""
        {persona_text}{memory_text}{project_text}
        Current Working Directory: {os.getcwd()}
        {context_info}
        You have access to a local file system via your Harness.
        {get_tools_instructions()}
        {AGENT_md_INGESTIOR()}
        """

    def _summarize_tool_result(self, result: str, file_path: str | None) -> str:
        """
        Summarize tool results to keep conversation history small.
        For small models, we don't need full outputs - just what changed.
        """
        if not result:
            return "[No output]"
        
        # Error messages - keep them (they're short and important)
        if result.startswith("[SYSTEM ERROR"):
            return result
        
        # Memory updates - persona manages this
        if "[Memory updated" in result:
            return "[Memory updated - see memory.md]"
        
        # WRITE success - already compact
        if "Successfully wrote" in result:
            return result
        
        # EDIT success - already compact  
        if "Successfully edited" in result:
            return result
        
        # READ - Do NOT summarize file content entirely, or the model becomes "blind".
        # We only truncate if the file is exceptionally large to prevent context crashing.
        if result.startswith("[SYSTEM OUTPUT: Content of"):
            if len(result) > 15000:
                match = re.search(r'Content of (.+?)\\]\\n', result)
                filename = os.path.basename(match.group(1)) if match else "file"
                return f"[Read {filename}: truncated due to size ({len(result)} chars)]\n" + result[:2000] + "\n...[TRUNCATED]..."
            return result

        # LS - summarize directory listing
        if result.startswith("[SYSTEM OUTPUT: Files in"):
            lines = result.split('\n')
            if len(lines) > 1:
                count = len(lines) - 1
                return f"[Listed directory: {count} items]"
            return "[Empty directory]"
        
        # BASH - summarize command output
        if result.startswith("[SYSTEM OUTPUT: Bash executed"):
            # Extract exit code and output
            match = re.search(r'exited with code (\d+)\]\n(.*)', result, re.DOTALL)
            if match:
                exit_code = match.group(1)
                output = match.group(2).strip()
                if output:
                    output_lines = output.count('\n') + 1
                    return f"[Bash exited {exit_code}: {output_lines} lines output]"
                return f"[Bash exited {exit_code}: no output]"
            return result
        
        # Fallback - truncate very long results
        if len(result) > 500:
            return result[:500] + f"\n...[truncated, {len(result) - 500} more chars]"
        
        return result

    def run_task(self, prompt: str) -> str:
        """Execute a task with the given prompt. Returns the final response."""
        # Refresh system prompt to include latest project.md/memory.md state
        self.system_prompt = self._build_system_prompt()

        # Check if user explicitly stated a topic
        if self.user_specified_topic is None:
            detected = self._detect_user_topic(prompt)
            if detected:
                self.user_specified_topic = detected
                if self.context:
                    self.context.set_topic(detected)

        self.conversation_history.append({"role": "user", "content": prompt})

        print(f"\n{self._get_history_stats()}")

        response = call_llm(
            self.conversation_history, self.system_prompt, self.current_provider
        )
        print(f"Bob: {response}")
        self.conversation_history.append({"role": "assistant", "content": response})

        # Save session after initial exchange
        self._save_session()

        # The Autonomous Tool Loop (ReAct) - serial execution
        iteration = 0
        while True:
            system_result, file_path = self._execute_next_tool(response)

            if system_result:
                iteration += 1
                print(f"\n[Harness feeding system result back to Bob... {self._get_history_stats()}]")
                
                # Summarize tool results to keep history small
                summary = self._summarize_tool_result(system_result, file_path)
                self.conversation_history.append(
                    {"role": "user", "content": summary}
                )

                response = call_llm(
                    self.conversation_history, self.system_prompt, self.current_provider
                )
                print(f"Bob: {response}")
                print(f"[Model: {self.current_provider.model}] {self._get_history_stats()} (iteration {iteration})")
                self.conversation_history.append({"role": "assistant", "content": response})

                # Save session after each iteration
                self._save_session()
            else:
                break

        return response

    def _detect_user_topic(self, prompt: str) -> Optional[str]:
        """
        Try to detect if the user explicitly stated a topic.
        Looks for patterns like: 'topic: foo', 'about: foo', 'the topic is foo', etc.
        Returns the topic string or None if not detected.
        """
        prompt_lower = prompt.lower()
        
        # Pattern 1: explicit topic markers
        explicit_patterns = [
            r'topic:\s*(\w+)',
            r'about:\s*(\w+)',
            r'regarding:\s*(\w+)',
            r'the topic (?:is|should be)\s+(\w+)',
        ]
        for pattern in explicit_patterns:
            match = re.search(pattern, prompt_lower)
            if match:
                return match.group(1)
        
        # Pattern 2: single-word topic at start (if first 2 words aren't common phrases)
        words = prompt.split()
        if len(words) >= 2:
            first_two = ' '.join(words[:2]).lower()
            if first_two not in ("can you", "please", "i want", "i need", "help me", "now please"):
                topic_word = words[0].strip('.,!?').lower()
                if len(topic_word) > 2 and topic_word not in ("hey", "hi", "hello", "yo", "now", "just"):
                    return topic_word
        
        return None

    def _update_topic_from_response(self, response: str) -> None:
        """Update topic from agent response if user hasn't specified one."""
        if self.user_specified_topic is not None or not self.context:
            return
        
        patterns = [
            r'(?:topic|about|regarding):\s*(\w+)',
            r"(?:I'll|I will) (?:work on|focus on|address|help with)\s+(\w+)",
            r"(?:I'm|I am) (?:going to |about to )?(?:work on |focus on |help with )?(\w+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                topic = match.group(1).lower()
                self.context.set_topic(topic)
                return
        
        # Fallback: extract first significant word from response
        words = response.split()
        for word in words[:10]:
            cleaned = re.sub(r'[^\w]', '', word).lower()
            if len(cleaned) > 3 and cleaned not in ("this", "that", "here", "there", "going", "working", "helping"):
                self.context.set_topic(cleaned)
                return

    def _print_topic(self) -> None:
        """Print the current topic if set."""
        if self.context:
            topic = self.context.get_topic()
            if topic:
                lock_indicator = " [LOCKED]" if self.user_specified_topic else ""
                print(f"[Topic: {topic}]{lock_indicator}")

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

    def _get_history_stats(self) -> str:
        """Return conversation stats string."""
        user_msgs = sum(1 for m in self.conversation_history if m["role"] == "user")
        assistant_msgs = sum(1 for m in self.conversation_history if m["role"] == "assistant")
        return f"[History: {user_msgs} user / {assistant_msgs} assistant msgs]"

    def reset(self):
        """Clear conversation history to start fresh."""
        self.conversation_history = []
        if self.context:
            self.context.reset_session()
        # Remove session file on reset
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