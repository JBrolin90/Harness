"""Memory management tool for long-term memory operations."""
from memory import Memory, get_memory
from .base_tool import BaseTool


class MemoryTool(BaseTool):
    """Manage the agent's long-term memory (memory.md)."""

    name = "memory"
    description = "Manage long-term memory. Use this tool to add, update, or delete items from memory sections."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "update", "delete"],
                "description": "Action to perform: 'add' (append item), 'update' (replace old item), 'delete' (remove item)."
            },
            "section": {
                "type": "string",
                "description": f"Memory section name. Valid sections: {', '.join(Memory.SECTIONS)}"
            },
            "item": {
                "type": "string",
                "description": "The item text to add (for 'add') or the new text (for 'update'). Required for 'add' and 'update'; ignored for 'delete'."
            },
            "old_item": {
                "type": "string",
                "description": "The existing item to update or delete. Required for 'update' and 'delete'; ignored for 'add'."
            }
        },
        "required": ["action", "section"]
    }

    def execute(self, action: str, section: str, item: str, old_item: str = "") -> str:  # type: ignore[override]
        memory = get_memory()
        
        if section not in Memory.SECTIONS:
            return f"[ERROR] Invalid section '{section}'. Valid sections: {', '.join(Memory.SECTIONS)}"
        
        if action == "add":
            memory.add(section, item)
            return f"[OK] Added to {section}: {item}"
        
        elif action == "update":
            if not old_item:
                return "[ERROR] 'old_item' is required for 'update' action."
            if memory.update(section, old_item, item):
                return f"[OK] Updated in {section}: '{old_item}' → '{item}'"
            else:
                return f"[ERROR] Item not found in {section}: {old_item}"
        
        elif action == "delete":
            if not old_item:
                return "[ERROR] 'old_item' is required for 'delete' action."
            if memory.remove(section, old_item):
                return f"[OK] Deleted from {section}: {old_item}"
            else:
                return f"[ERROR] Item not found in {section}: {old_item}"
        
        return f"[ERROR] Unknown action: {action}"


class MemoryReadTool(BaseTool):
    """Read the current memory content."""

    name = "memory_read"
    description = "Read all current memory entries organized by section."
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }

    def execute(self) -> str:  # type: ignore[override]
        memory = get_memory()
        all_memory = memory.get_all()
        
        if not memory.has_content():
            return "[EMPTY] Memory is empty."
        
        lines = ["=== CURRENT MEMORY ==="]
        for section, items in all_memory.items():
            if items:
                lines.append(f"\n## {section}")
                for item in items:
                    lines.append(f"- {item}")
        
        return "\n".join(lines)
