"""LLM provider configuration management."""
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
    api_key_env_var: Optional[str] = None  # Name of the environment variable holding the API key
    attributes: dict = field(default_factory=dict)
    tools: List[dict] = field(default_factory=list)  # Native function calling tools


class ProviderManager:
    """Manages LLM provider configurations."""

    DEFAULT_PROVIDERS: List[str] = ["cloud-pro", "local-coder"]

    def __init__(self, storage_path: str = "providers.json"):
        self.storage_path = storage_path
        self.providers: List[ProviderConfig] = []
        self._load_defaults()
        self.load_from_disk()

    def _load_defaults(self):
        """Built-in provider configurations (not saved to disk)."""
        self.providers.append(ProviderConfig(
            name="cloud-pro",
            provider_type="minimax",
            url="https://api.minimax.io/v1/text/chatcompletion_v2",
            model="MiniMax-M2.7",
            api_key_env_var="MINIMAX_API_KEY",
        ))
        self.providers.append(ProviderConfig(
            name="local-coder",
            provider_type="ollama",
            url="http://localhost:11434/api/chat",
            model="qwen2.5-coder:7b",
            api_key_env_var="OLLAMA_DUMMY_KEY",
        ))

    def add_provider(self, config: ProviderConfig):
        """Add or update a provider configuration in memory."""
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
            "Check provider.py or providers.json"
        )

    def list_providers(self) -> List[str]:
        """Return a list of available provider names."""
        return [p.name for p in self.providers]

    def save_to_disk(self):
        """Persist only user-added (non-default) providers to disk."""
        try:
            # Only save providers that are not in DEFAULT_PROVIDERS
            user_providers = [p for p in self.providers if p.name not in self.DEFAULT_PROVIDERS]
            serializable_providers = [asdict(p) for p in user_providers]
            with open(self.storage_path, "w") as f:
                json.dump(serializable_providers, f, indent=4)
        except Exception as e:
            print(f"[PROVIDER STORAGE ERROR: {e}]")

    def load_from_disk(self):
        """Load user-added configurations from disk (not defaults)."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                    for item in data:
                        if item.get("name") not in self.DEFAULT_PROVIDERS:
                            config = ProviderConfig(**item)
                            self.providers.append(config)
            except Exception as e:
                print(f"[PROVIDER LOAD ERROR: {e}]")
