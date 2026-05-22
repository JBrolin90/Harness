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
            api_key_env_var="MINIMAX_API_KEY" # Reference to environment variable
        ))
        self.add_provider(ProviderConfig(
            name="local-coder",
            provider_type="ollama",
            url="http://localhost:11434/api/chat",
            model="qwen2.5-coder:7b",
            api_key_env_var="OLLAMA_DUMMY_KEY" # Reference to environment variable (can be dummy)
        ))

    def add_provider(self, config: ProviderConfig):
        """Add or update a provider configuration."""
        # Remove existing if name matches to allow updates
        self.providers = [p for p in self.providers if p.name != config.name]
        self.providers.append(config)
        self.save_to_disk()

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        """Retrieve a provider by its unique name."""
        for p in self.providers:
            if p.name == name:
                return p
        return None

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