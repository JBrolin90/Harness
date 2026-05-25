"""Session management for the Harness framework.

Keeps conversation history short, focused, accurate, and deduplicated.
"""

import json
import os
import re
from datetime import datetime
from typing import Literal


Message = dict[Literal["role", "content"], str]


class SessionManager:
    """Manages conversation history with summarization and deduplication."""

    MAX_HISTORY_SIZE = 50  # Max turns before compression
    MAX_CONTENT_LENGTH = 15000  # Truncate READ results larger than this

    def __init__(self):
        self.conversation_history: list[Message] = []
        self.session_file = self._get_session_file_path()

    def _get_session_file_path(self) -> str:
        """Generate session file path: session-<date>-<cwd>.json"""
        date_str = datetime.now().strftime("%Y%m%d")
        cwd_safe = os.getcwd().replace("/", "_").lstrip("_")
        return f"session-{date_str}-{cwd_safe}.json"

    def add_user_message(self, content: str) -> None:
        """Add a user message to history."""
        self.conversation_history.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to history."""
        self.conversation_history.append({"role": "assistant", "content": content})

    def add_tool_result(self, result: str, file_path: str | None) -> str:
        """Process and add a tool result. Returns the summary to add to history."""
        summary = self._summarize_tool_result(result, file_path)
        self.conversation_history.append({"role": "user", "content": summary})
        return summary

    def save(self) -> None:
        """Persist conversation history to disk."""
        try:
            with open(self.session_file, 'w') as f:
                json.dump(self.conversation_history, f, indent=2)
        except Exception as e:
            print(f"[Harness: Warning - could not save session: {e}]")

    def clear(self) -> None:
        """Clear conversation history and remove session file."""
        self.conversation_history = []
        if os.path.exists(self.session_file):
            try:
                os.remove(self.session_file)
            except Exception:
                pass

    def get_stats(self) -> str:
        """Return conversation stats string."""
        user_msgs = sum(1 for m in self.conversation_history if m["role"] == "user")
        assistant_msgs = sum(1 for m in self.conversation_history if m["role"] == "assistant")
        return f"[History: {user_msgs} user / {assistant_msgs} assistant msgs]"

    def needs_compression(self) -> bool:
        """Check if history needs compression."""
        return len(self.conversation_history) > self.MAX_HISTORY_SIZE

    def _summarize_tool_result(self, result: str, file_path: str | None) -> str:
        """
        Summarize tool results to keep conversation history focused.
        
        Goals:
        - Keep errors (they're important and short)
        - Keep success confirmations
        - Truncate large file reads (model becomes blind otherwise)
        - Summarize directory listings and bash output
        - No duplications
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
        # Only truncate if the file is exceptionally large to prevent context crashing.
        if result.startswith("[SYSTEM OUTPUT: Content of"):
            if len(result) > self.MAX_CONTENT_LENGTH:
                match = re.search(r'Content of (.+?)\]\n', result)
                filename = os.path.basename(match.group(1)) if match else "file"
                return (
                    f"[Read {filename}: truncated due to size ({len(result)} chars)]\n"
                    + result[:2000]
                    + "\n...[TRUNCATED]..."
                )
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
