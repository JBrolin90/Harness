"""LLM provider configuration management."""
import json
import os
from dataclasses import dataclass, asdict, field
from typing import List, Optional
from enum import Enum


class ProviderType(Enum):
    """Supported LLM provider types."""
    OLLAMA = "ollama"
    MINIMAX = "minimax"
    OPENAI = "openai"
    OPENROUTER = "openrouter"

    @classmethod
    def from_string(cls, value: str) -> "ProviderType":
        """Create from string, defaulting to OPENAI for unknown providers."""
        try:
            return cls(value.lower())
        except ValueError:
            return cls.OPENAI

    @property
    def is_local(self) -> bool:
        """Check if this is a local provider (doesn't need API key)."""
        return self == self.OLLAMA

    @property
    def supports_function_calling(self) -> bool:
        """Check if provider supports native function calling."""
        return self != self.OLLAMA


@dataclass
class ProviderConfig:
    """Individual LLM Configuration."""
    name: str
    provider_type: ProviderType  # ProviderType enum instead of raw string
    url: str
    model: str
    api_key_env_var: Optional[str] = None  # Name of the environment variable holding the API key
    attributes: dict = field(default_factory=dict)
    tools: List[dict] = field(default_factory=list)  # Native function calling tools

    def __post_init__(self):
        """Convert string provider_type to ProviderType enum if needed."""
        if isinstance(self.provider_type, str):
            self.provider_type = ProviderType.from_string(self.provider_type)


class ProviderManager:
    """Manages LLM provider configurations."""

    DEFAULT_PROVIDERS: List[str] = ["cloud-pro", "local-coder"]

    def __init__(self, storage_path: str = None):
        if storage_path is None:
            # Default to providers.json in the project root (same dir as provider.py)
            module_dir = os.path.dirname(os.path.abspath(__file__))
            storage_path = os.path.join(module_dir, "providers.json")
        self.storage_path = storage_path
        self.providers: List[ProviderConfig] = []
        self._load_defaults()
        self.load_from_disk()

    def _load_defaults(self):
        """Built-in provider configurations (not saved to disk)."""
        # Load recommendations from provider-recommendations.json
        recommendations = self._load_recommendations()

        # cloud-pro - MiniMax-M2.7 cloud model
        cloud_pro_attrs = recommendations.get("cloud-pro", {}).get("attributes", {})
        self.providers.append(ProviderConfig(
            name="cloud-pro",
            provider_type=ProviderType.MINIMAX,
            url="https://api.minimax.io/v1/text/chatcompletion_v2",
            model="MiniMax-M2.7",
            api_key_env_var="MINIMAX_API_KEY",
            attributes=cloud_pro_attrs,
        ))

        # local-coder - qwen2.5-coder:7b ollama model
        local_coder_attrs = recommendations.get("local-coder", {}).get("attributes", {})
        self.providers.append(ProviderConfig(
            name="local-coder",
            provider_type=ProviderType.OLLAMA,
            url="http://localhost:11434/api/chat",
            model="qwen2.5-coder:7b",
            api_key_env_var="OLLAMA_DUMMY_KEY",
            attributes=local_coder_attrs,
        ))

    def _load_recommendations(self) -> dict:
        """Load provider recommendations from provider-recommendations.json.
        
        Returns:
            Dict mapping provider name -> {notes, attributes}
        """
        recommendations_path = "provider-recommendations.json"
        if os.path.exists(recommendations_path):
            try:
                with open(recommendations_path, "r") as f:
                    data = json.load(f)
                    return {item["name"]: item for item in data}
            except Exception as e:
                print(f"[PROVIDER RECOMMENDATIONS WARNING: {e}]")
        return {}

    def add_provider(self, config: ProviderConfig, persist: bool = True):
        """Add or update a provider configuration.
        
        Args:
            config: Provider configuration to add/update
            persist: If True, saves to disk. If False, only updates in-memory.
                     Note: Default providers (cloud-pro, local-coder) are not
                     persisted by default to avoid overwriting built-in configs.
        """
        # Remove existing if name matches to allow updates
        self.providers = [p for p in self.providers if p.name != config.name]
        self.providers.append(config)
        if persist:
            self.save_to_disk()

    def update_provider(self, name: str, **kwargs) -> bool:
        """Update a provider's configuration in memory and persist if possible.
        
        Args:
            name: Provider name to update
            **kwargs: Fields to update (provider_type, url, model, api_key_env_var, attributes, tools)
        
        Returns:
            True if provider was found and updated, False otherwise.
        
        Note:
            Default providers (cloud-pro, local-coder) cannot be persisted via this method.
            To persist changes to default providers, add a new provider with a different name
            or manually edit providers.json.
        """
        for i, p in enumerate(self.providers):
            if p.name == name:
                # Update fields
                for key, value in kwargs.items():
                    if hasattr(p, key):
                        setattr(p, key, value)
                    else:
                        print(f"[WARNING: Unknown provider field '{key}'")
                
                # Only persist if not a default provider
                if name not in self.DEFAULT_PROVIDERS:
                    self.save_to_disk()
                else:
                    print(f"[NOTE: Changes to default provider '{name}' are not persisted.]")
                    print(f"       Use add_provider() with a custom name to persist changes.")
                return True
        return False

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
