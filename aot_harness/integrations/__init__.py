"""Integrations: external systems (LLM providers, vaults, MCP, n8n)."""
from .claude_adapter import ClaudeAdapter
from .litellm_adapter import LiteLLMAdapter, Provider, make_adapter, DEFAULT_MODELS

__all__ = [
    "ClaudeAdapter",
    "LiteLLMAdapter",
    "Provider",
    "make_adapter",
    "DEFAULT_MODELS",
]
