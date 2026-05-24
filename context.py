"""
Context Manager for Harness - Topic tracking for conversation context.

This module handles:
- Topic tracking across conversations
- Detecting when memory files are updated (to avoid redundancy in history)
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Topic:
    """Represents a conversation topic."""
    name: str
    started: bool = True
    relevant_files: list[str] = field(default_factory=list)
    key_facts: list[str] = field(default_factory=list)


class ContextManager:
    """
    Manages conversation context and topic tracking.
    
    Flow:
    1. Track current topic during conversation
    2. Detect when memory files are updated (to avoid redundancy)
    3. Provide context summary for system prompt
    """

    def __init__(self, project_root: str, personas_dir: str):
        self.project_root = project_root
        self.personas_dir = personas_dir
        self.current_topic: Optional[Topic] = None
        self.session_memory_updates: list[str] = []  # Tracks what memory was updated this session

    def set_topic(self, topic_name: str) -> None:
        """Set or update the current topic."""
        if self.current_topic is None or self.current_topic.name != topic_name:
            self.current_topic = Topic(name=topic_name, started=True)
            print(f"[Context: Now tracking topic: {topic_name}]")

    def get_topic(self) -> Optional[str]:
        """Get current topic name."""
        return self.current_topic.name if self.current_topic else None

    def check_memory_update(self, file_path: str) -> bool:
        """
        Check if a file that looks like a memory file was updated.
        Returns True if this is a memory file that the persona is managing.
        """
        if not file_path:
            return False
        
        # Check if this is a memory.md file in a persona directory
        if file_path.endswith("memory.md") and "personas" in file_path:
            return True
        
        # Check for other common memory file names
        memory_indicators = ["memory.md", "notes.md", "context.md"]
        return any(indicator in file_path for indicator in memory_indicators)

    def add_memory_update(self, file_path: str) -> None:
        """Record that a memory file was updated."""
        if file_path not in self.session_memory_updates:
            self.session_memory_updates.append(file_path)
            print(f"[Context: Memory file updated: {file_path}]")

    def should_add_to_history(self, tool_result: str, memory_updated: bool = False) -> tuple[bool, Optional[str]]:
        """
        Determine if a tool result should be added to conversation history.
        
        Returns:
            (should_add, summary_or_none)
            - If should_add=True and summary=None: add full result
            - If should_add=True and summary="...": add summary only
            - If should_add=False: don't add to history (memory was updated)
        """
        # If a memory file was updated, don't add full result to history
        # The persona will reference the memory file directly
        if memory_updated:
            return (True, "[Memory updated - see memory.md for details]")
        
        return (True, None)

    def add_key_facts(self, facts: list[str]) -> None:
        """Add key facts to the current topic."""
        if self.current_topic:
            for fact in facts:
                if fact not in self.current_topic.key_facts:
                    self.current_topic.key_facts.append(fact)

    def get_context_summary(self) -> str:
        """Get a summary of current context for system prompt."""
        parts = []
        
        if self.current_topic:
            parts.append(f"Topic: {self.current_topic.name}")
            if self.current_topic.key_facts:
                parts.append(f"Known facts: {'; '.join(self.current_topic.key_facts[:3])}")
            if self.current_topic.relevant_files:
                parts.append(f"Relevant files: {', '.join(self.current_topic.relevant_files[:3])}")
        
        if self.session_memory_updates:
            files = [os.path.basename(f) for f in self.session_memory_updates[:2]]
            parts.append(f"Memory updates this session: {', '.join(files)}")
        
        return " | ".join(parts) if parts else ""

    def reset_session(self) -> None:
        """Reset session-only state (keeps persistent config)."""
        self.session_memory_updates = []


def create_context_manager() -> ContextManager:
    """Factory function to create a ContextManager with correct paths."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    personas_dir = os.path.join(project_root, "personas")
    return ContextManager(project_root, personas_dir)