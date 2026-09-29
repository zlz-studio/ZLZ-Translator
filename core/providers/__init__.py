from core.providers.anthropic_api import AnthropicProvider
from core.providers.base import Provider, ProviderCancelled, ProviderError
from core.providers.claude_code import ClaudeCodeProvider
from core.providers.gemini import GeminiProvider
from core.providers.ollama import OllamaProvider

PROVIDERS: dict[str, type[Provider]] = {
    ClaudeCodeProvider.name: ClaudeCodeProvider,
    GeminiProvider.name: GeminiProvider,
    AnthropicProvider.name: AnthropicProvider,
    OllamaProvider.name: OllamaProvider,
}

__all__ = ["PROVIDERS", "Provider", "ProviderCancelled", "ProviderError"]
