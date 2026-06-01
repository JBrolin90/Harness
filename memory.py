"""Long-term memory management for the agent."""
from pathlib import Path
from typing import Optional, Union


class Memory:
    """Manages long-term memory storage and retrieval."""
    
    SECTIONS = ["Personal", "Voice", "Process", "Active Projects", "Preferences", "Knowledge Base"]
    
    def __init__(self, memory_path: Union[str, Path, None] = None):
        """Initialize memory with path to memory file.
        
        Args:
            memory_path: Path to memory.md file. Defaults to memory.md in cwd.
        """
        self.memory_path = Path(memory_path) if memory_path else Path.cwd() / "memory.md"
        self._memory: dict[str, list[str]] = {section: [] for section in self.SECTIONS}
        self._load()
    
    def _load(self) -> None:
        """Load memory from file, parsing existing content."""
        if not self.memory_path.exists():
            return
        
        content = self.memory_path.read_text()
        current_section = None
        
        for line in content.split("\n"):
            stripped = line.strip()
            
            # Check for section header (## Section)
            if stripped.startswith("## ") and not stripped.startswith("###"):
                current_section = stripped[3:].strip()
                if current_section not in self._memory:
                    self._memory[current_section] = []
            
            # Check for bullet point
            elif stripped.startswith("- ") and current_section:
                self._memory[current_section].append(stripped[2:])
    
    def _save(self) -> None:
        """Save memory to file."""
        lines = ["# Memory\n"]
        
        for section in self.SECTIONS:
            if self._memory[section]:  # Only add section if it has content
                lines.append(f"## {section}\n")
                for item in self._memory[section]:
                    lines.append(f"- {item}\n")
                lines.append("\n")
        
        # Remove trailing newlines
        while lines and lines[-1] == "\n":
            lines.pop()
        
        self.memory_path.write_text("".join(lines))
    
    def get(self, section: str) -> list[str]:
        """Get all items in a section.
        
        Args:
            section: Section name (e.g., "Personal", "Preferences")
            
        Returns:
            List of items in the section
        """
        return self._memory.get(section, []).copy()
    
    def add(self, section: str, item: str) -> None:
        """Add an item to a section.
        
        Args:
            section: Section name
            item: Item to add (without the leading "- ")
        """
        if section not in self._memory:
            self._memory[section] = []
        if item not in self._memory[section]:
            self._memory[section].append(item)
            self._save()
    
    def update(self, section: str, old_item: str, new_item: str) -> bool:
        """Update an existing item in a section.
        
        Args:
            section: Section name
            old_item: Item to replace
            new_item: Replacement item
            
        Returns:
            True if item was found and updated, False otherwise
        """
        if section not in self._memory:
            return False
        
        try:
            index = self._memory[section].index(old_item)
            self._memory[section][index] = new_item
            self._save()
            return True
        except ValueError:
            return False
    
    def remove(self, section: str, item: str) -> bool:
        """Remove an item from a section.
        
        Args:
            section: Section name
            item: Item to remove
            
        Returns:
            True if item was found and removed, False otherwise
        """
        if section not in self._memory:
            return False
        
        try:
            self._memory[section].remove(item)
            self._save()
            return True
        except ValueError:
            return False
    
    def get_all(self) -> dict[str, list[str]]:
        """Get all memory as a dictionary.
        
        Returns:
            Copy of all memory sections and their items
        """
        return {section: items.copy() for section, items in self._memory.items()}
    
    def find(self, query: str) -> list[tuple[str, str]]:
        """Search for a query across all sections.
        
        Args:
            query: Search term (case-insensitive substring match)
            
        Returns:
            List of (section, item) tuples matching the query
        """
        results = []
        query_lower = query.lower()
        
        for section, items in self._memory.items():
            for item in items:
                if query_lower in item.lower():
                    results.append((section, item))
        
        return results
    
    def clear_section(self, section: str) -> bool:
        """Clear all items from a section.
        
        Args:
            section: Section name
            
        Returns:
            True if section existed and was cleared, False otherwise
        """
        if section not in self._memory:
            return False
        
        self._memory[section] = []
        self._save()
        return True
    
    def has_content(self) -> bool:
        """Check if memory has any content stored.
        
        Returns:
            True if any section has items, False otherwise
        """
        return any(items for items in self._memory.values())


def load_memory_instructions(path: Union[str, Path, None] = None) -> Optional[str]:
    """Load memory instructions file content.
    
    Args:
        path: Path to memory_instructions.md. Defaults to cwd.
        
    Returns:
        File content or None if not found
    """
    instructions_path = Path(path) if path else Path.cwd() / "memory_instructions.md"
    if instructions_path.exists():
        return instructions_path.read_text()
    return None


# Module-level default instance for convenience
_default_memory: Optional[Memory] = None


def get_memory(path: Union[str, Path, None] = None) -> Memory:
    """Get or create a Memory instance.
    
    CAUTION: This function caches a single default Memory instance globally.
    Calling get_memory(path=None) after get_memory(some_path) will return
    the cached instance, not a new one for the default path.
    
    To get a fresh Memory instance with a different path, either:
    1. Pass path on every call to use it consistently
    2. Create Memory instances directly: Memory(path)
    
    Args:
        path: Optional path to memory.md. If None and no cached instance
              exists, uses memory.md in cwd.
        
    Returns:
        Memory instance (cached after first call)
    """
    global _default_memory
    if _default_memory is None or path is not None:
        _default_memory = Memory(path)
    return _default_memory