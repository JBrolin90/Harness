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
    locked: bool = False  # True if user explicitly stated the topic
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

    def set_topic(self, topic_name: str, locked: bool = False) -> None:
        """Set or update the current topic. If locked, topic cannot change."""
        if self.current_topic and self.current_topic.locked:
            return
        if self.current_topic is None or self.current_topic.name != topic_name:
            self.current_topic = Topic(name=topic_name, started=True, locked=locked)
            lock_str = " [LOCKED]" if locked else ""
            print(f"[Context: Now tracking topic: {topic_name}]{lock_str}")

    def set_user_topic(self, topic_name: str) -> None:
        """Set topic that user explicitly stated - always locks the topic."""
        self.current_topic = Topic(name=topic_name, started=True, locked=True)
        print(f"[Context: User stated topic: {topic_name}]")

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
        if file_path.endswith("memory.md") and ("personas" in file_path or ".bob" in file_path):
            return True
        
        # Check for other common memory file names
        memory_indicators = ["memory.md", "notes.md", "context.md"]
        return any(indicator in file_path for indicator in memory_indicators)

    def add_memory_update(self, file_path: str) -> None:
        """Record that a memory file was updated."""
        if file_path not in self.session_memory_updates:
            self.session_memory_updates.append(file_path)
            print(f"[Context: Memory file updated: {file_path}]")

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
        self.current_topic = None  # Allow new topic to be set after reset

    def get_topic_display(self) -> str:
        """Get formatted topic string for printing."""
        if self.current_topic:
            lock_str = " [LOCKED]" if self.current_topic.locked else ""
            return f"[Topic: {self.current_topic.name}]{lock_str}"
        return ""


def create_context_manager() -> ContextManager:
    """Factory function to create a ContextManager with correct paths."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    personas_dir = os.path.expanduser("~/.bob/personas")
    return ContextManager(project_root, personas_dir)