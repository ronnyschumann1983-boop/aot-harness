"""
aot_harness/integrations/litellm_adapter.py
Multi-Provider LLM Adapter — wraps LiteLLM for unified access to:
  - Anthropic (with prompt caching)
  - OpenAI
  - Google (Gemini)
  - Mistral (la Plateforme)
  - OpenRouter (meta-provider for 100+ models)

Provides the .complete(prompt: str) -> str interface expected by AoTReasoner
and all CHIP agents — fully backward-compatible with ClaudeAdapter.

Install: pip install litellm>=1.50.0
"""
from __future__ import annotations
from typing import Literal, Any
import os


Provider = Literal["anthropic", "openai", "google", "mistral", "openrouter"]


# Default model per provider — sane choices, balance of cost/quality
DEFAULT_MODELS: dict[str, str] = {
    "anthropic":  "claude-sonnet-4-6",
    "openai":     "gpt-4o",
    "google":     "gemini/gemini-2.0-flash",
    "mistral":    "mistral/mistral-large-latest",
    "openrouter": "openrouter/anthropic/claude-sonnet-4-6",
}

# LiteLLM model-prefix per provider (for explicit routing)
PROVIDER_PREFIX: dict[str, str] = {
    "anthropic":  "anthropic/",
    "openai":     "",                  # OpenAI is LiteLLM default — no prefix needed
    "google":     "gemini/",
    "mistral":    "mistral/",
    "openrouter": "openrouter/",
}

# Env-var name per provider — auto-resolved if api_key not passed
ENV_KEYS: dict[str, str] = {
    "anthropic":  "ANTHROPIC_API_KEY",
    "openai":     "OPENAI_API_KEY",
    "google":     "GEMINI_API_KEY",
    "mistral":    "MISTRAL_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


class LiteLLMAdapter:
    """
    Unified multi-provider adapter using LiteLLM.

    Usage:
        # Single-provider
        adapter = LiteLLMAdapter(provider="openai", api_key="sk-...")
        adapter.complete("Hello")

        # With explicit model
        adapter = LiteLLMAdapter(provider="google", model="gemini/gemini-1.5-pro")

        # Per-call override (used by CHIPOrchestrator for per-atom routing)
        adapter.complete("Hello", provider="mistral", model="mistral/mistral-small-latest")
    """

    def __init__(
        self,
        provider:    Provider          = "anthropic",
        model:       str | None        = None,
        api_key:     str | None        = None,
        max_tokens:  int               = 4096,
        system:      str               = "You are a precise, concise reasoning agent. Always respond in the requested format.",
        temperature: float             = 0.7,
        extra:       dict[str, Any] | None = None,
    ):
        try:
            import litellm  # noqa: F401
        except ImportError:
            raise ImportError("Run: pip install litellm>=1.50.0")

        self.provider     = provider
        self.model        = model or DEFAULT_MODELS[provider]
        self.api_key      = api_key or os.environ.get(ENV_KEYS[provider])
        self.max_tokens   = max_tokens
        self.system       = system
        self.temperature  = temperature
        self.extra        = extra or {}

        # Track cumulative cost per provider — read via .cost_summary()
        self._cost_by_provider: dict[str, float] = {}
        self._tokens_by_provider: dict[str, dict[str, int]] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def complete(
        self,
        prompt:   str,
        provider: Provider | None = None,
        model:    str | None      = None,
    ) -> str:
        """
        Send prompt → return text response.
        Per-call provider/model override possible (used for per-atom routing).
        """
        return self.complete_with_history(
            messages=[{"role": "user", "content": prompt}],
            provider=provider,
            model=model,
        )

    def complete_with_history(
        self,
        messages: list[dict],
        system:   str | None      = None,
        provider: Provider | None = None,
        model:    str | None      = None,
    ) -> str:
        """Multi-turn conversation. System-prompt cached for Anthropic only."""
        import litellm

        eff_provider = provider or self.provider
        eff_model    = model or (self.model if eff_provider == self.provider else DEFAULT_MODELS[eff_provider])
        eff_system   = system or self.system
        eff_api_key  = self.api_key if eff_provider == self.provider else os.environ.get(ENV_KEYS[eff_provider])

        # Build messages with provider-aware system handling
        full_messages = self._build_messages(eff_provider, eff_system, messages)

        kwargs: dict[str, Any] = {
            "model":       eff_model,
            "messages":    full_messages,
            "max_tokens":  self.max_tokens,
            "temperature": self.temperature,
        }
        if eff_api_key:
            kwargs["api_key"] = eff_api_key
        kwargs.update(self.extra)

        response = litellm.completion(**kwargs)

        # Track cost + tokens for this call
        self._track_usage(eff_provider, eff_model, response)

        return response.choices[0].message.content

    # ── Cost / usage introspection ────────────────────────────────────────────

    def cost_summary(self) -> dict:
        """Return cumulative cost + token usage per provider."""
        return {
            "total_usd":       round(sum(self._cost_by_provider.values()), 6),
            "by_provider":     {k: round(v, 6) for k, v in self._cost_by_provider.items()},
            "tokens":          dict(self._tokens_by_provider),
        }

    def reset_cost(self) -> None:
        """Reset cost tracking (e.g. between orchestrator runs)."""
        self._cost_by_provider.clear()
        self._tokens_by_provider.clear()

    # ── Internal: provider-specific message building ──────────────────────────

    def _build_messages(self, provider: str, system: str, messages: list[dict]) -> list[dict]:
        """
        Build the messages list for LiteLLM.

        For Anthropic: use cache_control on system prompt to enable prompt caching
        (re-used across all atom calls in a session — major cost reduction).

        For other providers: standard system message, no caching (yet).
        """
        if provider == "anthropic":
            return [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": system,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                },
                *messages,
            ]
        else:
            return [
                {"role": "system", "content": system},
                *messages,
            ]

    # ── Internal: cost / token tracking ───────────────────────────────────────

    def _track_usage(self, provider: str, model: str, response: Any) -> None:
        try:
            import litellm
            cost = litellm.completion_cost(completion_response=response) or 0.0
        except Exception:
            cost = 0.0

        self._cost_by_provider[provider] = self._cost_by_provider.get(provider, 0.0) + cost

        usage = getattr(response, "usage", None)
        if usage:
            bucket = self._tokens_by_provider.setdefault(provider, {"prompt": 0, "completion": 0})
            bucket["prompt"]     += getattr(usage, "prompt_tokens", 0) or 0
            bucket["completion"] += getattr(usage, "completion_tokens", 0) or 0


# ── Convenience factory ───────────────────────────────────────────────────────

def make_adapter(
    provider: Provider = "anthropic",
    **kwargs,
) -> LiteLLMAdapter:
    """Shorthand for `LiteLLMAdapter(provider=..., **kwargs)`."""
    return LiteLLMAdapter(provider=provider, **kwargs)
