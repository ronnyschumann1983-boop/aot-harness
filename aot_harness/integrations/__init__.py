"""Integrations: external systems (LLM providers, vaults, MCP, n8n)."""
from .claude_adapter import ClaudeAdapter
from .litellm_adapter import LiteLLMAdapter, Provider, make_adapter, DEFAULT_MODELS
from .vault import VaultAdapter, ObsidianAdapter, SupabaseAdapter
from .hitl import HITLNotifier, build_hitl_payload

__all__ = [
    "ClaudeAdapter",
    "LiteLLMAdapter",
    "Provider",
    "make_adapter",
    "DEFAULT_MODELS",
    "VaultAdapter",
    "ObsidianAdapter",
    "SupabaseAdapter",
    "HITLNotifier",
    "build_hitl_payload",
]
