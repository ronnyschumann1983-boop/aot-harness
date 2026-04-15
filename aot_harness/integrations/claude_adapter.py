"""
aot_harness/integrations/claude_adapter.py
Claude API Adapter — wraps anthropic SDK for the Harness.
Includes: prompt caching for system prompt (reduces token cost on retries).
"""
from __future__ import annotations


class ClaudeAdapter:
    """
    Thin wrapper around the Anthropic SDK.
    Provides the .complete(prompt: str) -> str interface expected by AoTReasoner.

    Install: pip install anthropic>=0.40.0
    """

    DEFAULT_MODEL = "claude-opus-4-6"

    def __init__(
        self,
        api_key: str,
        model:   str  = DEFAULT_MODEL,
        max_tokens: int = 2048,
        system: str = "You are a precise, concise reasoning agent. Always respond in the requested format."
    ):
        try:
            import anthropic
        except ImportError:
            raise ImportError("Run: pip install anthropic>=0.40.0")

        self._client    = anthropic.Anthropic(api_key=api_key)
        self.model      = model
        self.max_tokens = max_tokens
        self.system     = system
        # System prompt as cacheable block — reused across all atom calls in a session
        self._system_block = [
            {
                "type": "text",
                "text": self.system,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def complete(self, prompt: str) -> str:
        """Send prompt to Claude with cached system prompt, return text response."""
        msg = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self._system_block,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text

    def complete_with_history(self, messages: list[dict], system: str | None = None) -> str:
        """Multi-turn conversation support with cached system prompt."""
        system_block = (
            [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
            if system
            else self._system_block
        )
        msg = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_block,
            messages=messages
        )
        return msg.content[0].text
