"""
Context Manager for Harness - Topic tracking for conversation context.

This module handles:
- Topic tracking across conversations
- Detecting when memory files are updated (to avoid redundancy in history)
"""

import os
from typing import Optional
from topic import Topic


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
        self.topic = Topic()
        self.session_memory_updates: list[str] = []  # Tracks what memory was updated this session

    def get_context(self, prompt: str) -> bool:
        """
        Detect and set topic from prompt if not already set.
        Returns True if a topic was detected and set.
        """
        if not self.topic.is_set:
            detected = self.topic.detect_from_prompt(prompt)
            if detected:
                return True
        return False

    def set_topic(self, topic_name: str, locked: bool = False) -> None:
        """Set or update the current topic. If locked, topic cannot change."""
        self.topic.set(topic_name)
        if locked:
            self.topic.lock(topic_name)

    def get_topic(self) -> Optional[str]:
        """Get current topic name."""
        return self.topic.name

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
        if self.topic.is_set:
            for fact in facts:
                if fact not in self.topic.key_facts:
                    self.topic.key_facts.append(fact)

    def get_context_summary(self) -> str:
        """Get a summary of current context for system prompt."""
        parts = []
        
        if self.topic.is_set:
            parts.append(f"Topic: {self.topic.name}")
            if self.topic.key_facts:
                parts.append(f"Known facts: {'; '.join(self.topic.key_facts[:3])}")
            if self.topic.relevant_files:
                parts.append(f"Relevant files: {', '.join(self.topic.relevant_files[:3])}")
        
        if self.session_memory_updates:
            files = [os.path.basename(f) for f in self.session_memory_updates[:2]]
            parts.append(f"Memory updates this session: {', '.join(files)}")
        
        return " | ".join(parts) if parts else ""

    def reset_session(self) -> None:
        """Reset session-only state (keeps persistent config)."""
        self.session_memory_updates = []
        self.topic.reset()  # Allow new topic to be set after reset

    def get_topic_display(self) -> str:
        """Get formatted topic string for printing."""
        return self.topic.display()


def create_context_manager() -> ContextManager:
    """Factory function to create a ContextManager with correct paths."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    personas_dir = os.path.expanduser("~/.bob/personas")
    return ContextManager(project_root, personas_dir)
