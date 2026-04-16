"""
tests/test_litellm_adapter.py
Mock-based tests for the LiteLLMAdapter — covers all 5 providers,
Anthropic prompt-caching, per-call override, and cost tracking.
"""
from __future__ import annotations
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


# ── Mock litellm before importing the adapter ────────────────────────────────
# This lets the test suite run without litellm installed.

mock_litellm = types.ModuleType("litellm")
mock_litellm.completion = MagicMock()
mock_litellm.completion_cost = MagicMock(return_value=0.001)
sys.modules["litellm"] = mock_litellm


def setUpModule():
    """Re-bind sys.modules['litellm'] when this file's tests start running.
    Other test files also patch sys.modules['litellm'] at import time —
    last write wins. This restores OUR mock right before our tests run."""
    sys.modules["litellm"] = mock_litellm


from aot_harness.integrations.litellm_adapter import (  # noqa: E402
    LiteLLMAdapter, Provider, DEFAULT_MODELS, make_adapter,
)


def _mock_response(text: str = "ok", prompt_tokens: int = 10, completion_tokens: int = 5):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = text
    response.usage = MagicMock(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return response


class TestProviderRouting(unittest.TestCase):
    """Each provider should resolve to the correct model + send messages correctly."""

    def setUp(self):
        mock_litellm.completion.reset_mock()
        mock_litellm.completion.return_value = _mock_response("hello")

    def test_anthropic_default_model(self):
        adapter = LiteLLMAdapter(provider="anthropic", api_key="sk-test")
        self.assertEqual(adapter.model, DEFAULT_MODELS["anthropic"])
        adapter.complete("hi")
        kwargs = mock_litellm.completion.call_args.kwargs
        self.assertEqual(kwargs["model"], DEFAULT_MODELS["anthropic"])

    def test_openai_default_model(self):
        adapter = LiteLLMAdapter(provider="openai", api_key="sk-test")
        adapter.complete("hi")
        self.assertEqual(mock_litellm.completion.call_args.kwargs["model"], DEFAULT_MODELS["openai"])

    def test_google_default_model(self):
        adapter = LiteLLMAdapter(provider="google", api_key="test")
        adapter.complete("hi")
        self.assertEqual(mock_litellm.completion.call_args.kwargs["model"], DEFAULT_MODELS["google"])

    def test_mistral_default_model(self):
        adapter = LiteLLMAdapter(provider="mistral", api_key="test")
        adapter.complete("hi")
        self.assertEqual(mock_litellm.completion.call_args.kwargs["model"], DEFAULT_MODELS["mistral"])

    def test_openrouter_default_model(self):
        adapter = LiteLLMAdapter(provider="openrouter", api_key="test")
        adapter.complete("hi")
        self.assertEqual(mock_litellm.completion.call_args.kwargs["model"], DEFAULT_MODELS["openrouter"])

    def test_explicit_model_overrides_default(self):
        adapter = LiteLLMAdapter(provider="openai", model="gpt-4o-mini", api_key="sk-test")
        adapter.complete("hi")
        self.assertEqual(mock_litellm.completion.call_args.kwargs["model"], "gpt-4o-mini")


class TestAnthropicPromptCaching(unittest.TestCase):
    """Anthropic should send system prompt with cache_control. Other providers should not."""

    def setUp(self):
        mock_litellm.completion.reset_mock()
        mock_litellm.completion.return_value = _mock_response("ok")

    def test_anthropic_uses_cache_control(self):
        adapter = LiteLLMAdapter(provider="anthropic", api_key="sk-test", system="SYS")
        adapter.complete("hi")
        msgs = mock_litellm.completion.call_args.kwargs["messages"]
        sys_msg = msgs[0]
        self.assertEqual(sys_msg["role"], "system")
        self.assertIsInstance(sys_msg["content"], list)
        self.assertEqual(sys_msg["content"][0]["cache_control"], {"type": "ephemeral"})

    def test_openai_no_cache_control(self):
        adapter = LiteLLMAdapter(provider="openai", api_key="sk-test", system="SYS")
        adapter.complete("hi")
        msgs = mock_litellm.completion.call_args.kwargs["messages"]
        sys_msg = msgs[0]
        self.assertEqual(sys_msg["content"], "SYS")  # plain string, no cache_control

    def test_google_no_cache_control(self):
        adapter = LiteLLMAdapter(provider="google", api_key="test", system="SYS")
        adapter.complete("hi")
        sys_msg = mock_litellm.completion.call_args.kwargs["messages"][0]
        self.assertEqual(sys_msg["content"], "SYS")


class TestPerCallOverride(unittest.TestCase):
    """complete() should accept provider/model overrides for per-atom routing."""

    def setUp(self):
        mock_litellm.completion.reset_mock()
        mock_litellm.completion.return_value = _mock_response("ok")

    def test_provider_override(self):
        adapter = LiteLLMAdapter(provider="anthropic", api_key="sk-test")
        adapter.complete("hi", provider="openai")
        # Override → uses openai default model
        self.assertEqual(mock_litellm.completion.call_args.kwargs["model"], DEFAULT_MODELS["openai"])

    def test_model_override_with_provider(self):
        adapter = LiteLLMAdapter(provider="anthropic", api_key="sk-test")
        adapter.complete("hi", provider="google", model="gemini/gemini-1.5-pro")
        self.assertEqual(mock_litellm.completion.call_args.kwargs["model"], "gemini/gemini-1.5-pro")

    def test_no_override_uses_instance_defaults(self):
        adapter = LiteLLMAdapter(provider="mistral", api_key="test")
        adapter.complete("hi")
        self.assertEqual(mock_litellm.completion.call_args.kwargs["model"], DEFAULT_MODELS["mistral"])


class TestCostTracking(unittest.TestCase):

    def setUp(self):
        mock_litellm.completion.reset_mock()
        mock_litellm.completion_cost.reset_mock()
        mock_litellm.completion.return_value = _mock_response("ok", 100, 50)
        mock_litellm.completion_cost.return_value = 0.0042

    def test_cumulative_cost(self):
        adapter = LiteLLMAdapter(provider="openai", api_key="sk-test")
        adapter.complete("a")
        adapter.complete("b")
        adapter.complete("c")
        summary = adapter.cost_summary()
        self.assertAlmostEqual(summary["total_usd"], 0.0042 * 3, places=4)
        self.assertAlmostEqual(summary["by_provider"]["openai"], 0.0042 * 3, places=4)

    def test_token_aggregation(self):
        adapter = LiteLLMAdapter(provider="openai", api_key="sk-test")
        adapter.complete("a")
        adapter.complete("b")
        summary = adapter.cost_summary()
        self.assertEqual(summary["tokens"]["openai"]["prompt"], 200)
        self.assertEqual(summary["tokens"]["openai"]["completion"], 100)

    def test_per_call_provider_split(self):
        adapter = LiteLLMAdapter(provider="anthropic", api_key="sk-test")
        adapter.complete("a")                          # → anthropic
        adapter.complete("b", provider="google")        # → google
        summary = adapter.cost_summary()
        self.assertIn("anthropic", summary["by_provider"])
        self.assertIn("google", summary["by_provider"])

    def test_reset_cost(self):
        adapter = LiteLLMAdapter(provider="openai", api_key="sk-test")
        adapter.complete("a")
        adapter.reset_cost()
        self.assertEqual(adapter.cost_summary()["total_usd"], 0.0)


class TestFactoryAndInit(unittest.TestCase):

    def test_make_adapter(self):
        adapter = make_adapter(provider="mistral", api_key="test")
        self.assertIsInstance(adapter, LiteLLMAdapter)
        self.assertEqual(adapter.provider, "mistral")

    def test_api_key_from_env(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "env-key"}):
            adapter = LiteLLMAdapter(provider="openai")
            self.assertEqual(adapter.api_key, "env-key")


if __name__ == "__main__":
    unittest.main()
