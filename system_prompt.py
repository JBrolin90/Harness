"""
System Prompt Management for Harness - Single Responsibility Principle extraction.

This module handles building and refreshing the system prompt.
"""

import os
from tools import get_tools_instructions
from AGENT import AGENT_md_INGESTIOR


class SystemPrompt:
    """
    System prompt builder and manager.
    
    Responsibilities:
    - Compose system prompt from persona, memory, project context, and tools
    - Refresh prompt to capture latest state from dynamic sources
    """

    def __init__(
        self,
        persona_prompt_fn,
        memory_prompt_fn,
        context_summary_fn=None,
    ):
        """
        Initialize with dependency injection for flexible composition.
        
        Args:
            persona_prompt_fn: Callable returning persona fragment
            memory_prompt_fn: Callable returning memory fragment
            context_summary_fn: Callable returning context summary (optional)
        """
        self._persona_prompt = persona_prompt_fn
        self._memory_prompt = memory_prompt_fn
        self._context_summary = context_summary_fn
        self._cached = ""

    def build(self) -> str:
        """Build the system prompt with current dynamic content."""
        persona_text = self._persona_prompt()
        memory_text = self._memory_prompt()

        # Load project.md from CWD as the shared source of truth
        project_text = ""
        project_path = os.path.join(os.getcwd(), "project.md")
        if os.path.isfile(project_path):
            try:
                with open(project_path, 'r') as f:
                    project_text = f"\n\nProject Context (project.md):\n{f.read()}"
            except Exception:
                pass

        context_info = self._context_summary() if self._context_summary else ""

        prompt = f"""
        {persona_text}{memory_text}{project_text}
        Current Working Directory: {os.getcwd()}
        {context_info}
        You have access to a local file system via your Harness.
        {get_tools_instructions()}
        {AGENT_md_INGESTIOR()}
        """
        self._cached = prompt
        return prompt

    @property
    def current(self) -> str:
        """Get the last built prompt, building if needed."""
        return self._cached or self.build()
