import json
import os
from dataclasses import dataclass, asdict, field
from typing import List, Optional

@dataclass
class ProviderConfig:
    """Individual LLM Configuration."""
    name: str
    provider_type: str  # e.g., 'minimax', 'ollama'
    url: str
    model: str
    api_key_env_var: Optional[str] = None # Name of the environment variable holding the API key
    attributes: dict = field(default_factory=dict)
    tools: List[dict] = field(default_factory=list)  # Native function calling tools

def get_default_tools():
    """Return the default tool definitions for native function calling API."""
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a file from the file system.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "The path to the file to read, relative to the working directory."}
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write content to a new file. Use this to create new files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "The path to the file to write, relative to the working directory."},
                        "content": {"type": "string", "description": "The content to write to the file."}
                    },
                    "required": ["path", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "edit_file",
                "description": "Edit an existing file by replacing exact text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "The path to the file to edit, relative to the working directory."},
                        "oldText": {"type": "string", "description": "The exact text to find in the file."},
                        "newText": {"type": "string", "description": "The exact text to replace the oldText with."}
                    },
                    "required": ["path", "oldText", "newText"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files in a directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "The path to the directory, relative to the working directory."}
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "bash",
                "description": "Execute a bash command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The bash command to execute."}
                    },
                    "required": ["command"]
                }
            }
        }
    ]

class ProviderManager:
    def __init__(self, storage_path: str = "providers.json"):
        self.storage_path = storage_path
        self.providers: List[ProviderConfig] = []
        self._load_defaults()
        self.load_from_disk()

    def _load_defaults(self):
        """Built-in knowledge for MiniMax and Ollama."""
        self.add_provider(ProviderConfig(
            name="cloud-pro",
            provider_type="minimax",
            url="https://api.minimax.io/v1/text/chatcompletion_v2",
            model="MiniMax-M2.7", 
            api_key_env_var="MINIMAX_API_KEY",
            tools=get_default_tools()
        ))
        self.add_provider(ProviderConfig(
            name="local-coder",
            provider_type="ollama",
            url="http://localhost:11434/api/chat",
            model="qwen2.5-coder:7b",
            api_key_env_var="OLLAMA_DUMMY_KEY",
            tools=get_default_tools()
        ))

    def add_provider(self, config: ProviderConfig):
        """Add or update a provider configuration."""
        # Remove existing if name matches to allow updates
        self.providers = [p for p in self.providers if p.name != config.name]
        self.providers.append(config)
        self.save_to_disk()

    def get_provider(self, name: str) -> ProviderConfig:
        """Retrieve a provider by its unique name."""
        for p in self.providers:
            if p.name == name:
                return p
        raise RuntimeError(
            f"[CRITICAL ERROR: No LLM provider found for '{name}']"
            "Check provider.py or providers.json")

    def list_providers(self) -> List[str]:
        """Return a list of available provider names."""
        return [p.name for p in self.providers]

    def save_to_disk(self):
        """Persist configurations to a JSON file."""
        try:
            # Create a serializable version of providers, ensuring sensitive API keys are not saved
            serializable_providers = []
            for p in self.providers:
                serializable_providers.append(asdict(p))
            with open(self.storage_path, "w") as f:
                json.dump(serializable_providers, f, indent=4)
        except Exception as e:
            print(f"[PROVIDER STORAGE ERROR: {e}]")

    def load_from_disk(self):
        """Load configurations from disk if they exist."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                    for item in data:
                        # Convert dict back to Dataclass, avoiding duplicates
                        config = ProviderConfig(**item)
                        self.add_provider(config)
            except Exception as e:
                print(f"[PROVIDER LOAD ERROR: {e}]")