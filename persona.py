"""Persona management for the Harness framework."""

import os


PERSONAS_DIR = os.path.join(os.path.dirname(__file__), "personas")

DEFAULT_FALLBACK = "You are Bob, a helpful AI assistant."


class PersonaManager:
    """Manages persona loading and memory for the agent."""

    def __init__(self, persona_name: str = "default", enable_context: bool = True):
        self.persona_name = persona_name
        self.enable_context = enable_context

    def get_prompt_fragment(self) -> str:
        """Load and return the persona definition for the system prompt."""
        persona_path = os.path.join(PERSONAS_DIR, self.persona_name, "persona.md")

        if not os.path.isfile(persona_path):
            print(f"[Harness: Persona '{self.persona_name}' not found, using default]")
            persona_path = os.path.join(PERSONAS_DIR, "default", "persona.md")
            if not os.path.isfile(persona_path):
                return DEFAULT_FALLBACK

        try:
            with open(persona_path, 'r') as f:
                content = f.read()
            print(f"[Harness: Loaded persona '{self.persona_name}']")
            return content
        except Exception as e:
            print(f"[Harness: Could not load persona: {e}]")
            return DEFAULT_FALLBACK

    def get_memory_fragment(self) -> str:
        """Load and return the persona memory file if it exists."""
        if not self.enable_context:
            return ""

        memory_path = os.path.join(PERSONAS_DIR, self.persona_name, "memory.md")
        if os.path.isfile(memory_path):
            try:
                with open(memory_path, 'r') as f:
                    return f"\n\nYour memory:\n{f.read()}"
            except Exception:
                pass
        return ""
