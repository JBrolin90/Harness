"""
Topic Management for Harness - Single Responsibility Principle extraction.

This module handles topic detection and management independently of the controller.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass 
class Topic:
    """Holds topic state - name, lock status, and metadata.
    
    This is the main entry point for topic management.
    """
    _name: Optional[str] = None
    _locked: bool = False
    relevant_files: list[str] = field(default_factory=list)
    key_facts: list[str] = field(default_factory=list)
    
    # Common phrases to skip when detecting single-word topics
    SKIP_PHRASES = frozenset({
        "can you", "please", "i want", "i need", "help me", "now please",
        "hey there", "hi there", "hello there",
    })
    
    # Topics to skip during detection
    SKIP_WORDS = frozenset({
        "hey", "hi", "hello", "yo", "now", "just", "this", "that", "here", 
        "there", "going", "working", "helping",
    })

    @property
    def is_set(self) -> bool:
        """Check if a topic has been set."""
        return self._name is not None
    
    @property
    def name(self) -> Optional[str]:
        """Get current topic name."""
        return self._name
    
    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    @property
    def is_locked(self) -> bool:
        """Check if topic is locked (user-specified)."""
        return self._locked
    
    @is_locked.setter
    def is_locked(self, value: bool) -> None:
        self._locked = value

    def detect_from_prompt(self, prompt: str) -> Optional[str]:
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
        matched = self._match_patterns(prompt_lower, explicit_patterns)
        if matched:
            self.lock(matched)
            return matched
        
        # Pattern 2: single-word topic at start (if first 2 words aren't common phrases)
        words = prompt.split()
        if len(words) >= 2:
            first_two = ' '.join(words[:2]).lower()
            if first_two not in self.SKIP_PHRASES:
                topic_word = words[0].strip('.,!?').lower()
                if len(topic_word) > 2 and topic_word not in self.SKIP_WORDS:
                    self.lock(topic_word)
                    return topic_word
        
        return None

    def detect_from_response(self, response: str) -> None:
        """Update topic from agent response if user hasn't specified one."""
        if self._locked or not self.is_set:
            return
        
        patterns = [
            r'(?:topic|about|regarding):\s*(\w+)',
            r"(?:I'll|I will) (?:work on|focus on|address|help with)\s+(\w+)",
            r"(?:I'm|I am) (?:going to |about to )?(?:work on |focus on |help with )?(\w+)",
        ]
        
        matched = self._match_patterns(response, patterns, case_insensitive=True)
        if matched:
            self.set(matched)
            return
        
        # Fallback: extract first significant word from response
        words = response.split()
        for word in words[:10]:
            cleaned = re.sub(r'[^\w]', '', word).lower()
            if len(cleaned) > 3 and cleaned not in self.SKIP_WORDS:
                self.set(cleaned)
                return

    def set(self, topic_name: str) -> None:
        """Set or update the topic. Won't override locked topics."""
        if self._locked:
            return
        self._name = topic_name
        print(f"[Topic: Now tracking: {topic_name}]")

    def lock(self, topic_name: str) -> None:
        """Set topic as user-specified (locked)."""
        self._name = topic_name
        self._locked = True
        print(f"[Topic: User stated: {topic_name}]")

    def reset(self) -> None:
        """Reset all topic state."""
        self._name = None
        self._locked = False
        self.relevant_files = []
        self.key_facts = []

    def display(self) -> str:
        """Get formatted topic string for printing."""
        if self._name:
            lock_str = " [LOCKED]" if self._locked else ""
            return f"[Topic: {self._name}]{lock_str}"
        return ""

    def _match_patterns(
        self, text: str, patterns: list[str], *, case_insensitive: bool = False
    ) -> Optional[str]:
        """Match first pattern and return captured group."""
        flags = re.IGNORECASE if case_insensitive else 0
        for pattern in patterns:
            match = re.search(pattern, text, flags)
            if match:
                return match.group(1)
        return None
