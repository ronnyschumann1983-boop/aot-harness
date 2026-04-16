"""
tests/test_backward_compat.py
Ensure existing v0.2.x usage patterns still work after the multi-provider refactor.
"""
from __future__ import annotations
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


# Mock anthropic so the test runs without the real SDK installed
mock_anthropic = types.ModuleType("anthropic")


class _FakeAnthropic:
    def __init__(self, *args, **kwargs):
        self.messages = MagicMock()
        msg = MagicMock()
        msg.content = [MagicMock(text="hello")]
        self.messages.create = MagicMock(return_value=msg)


mock_anthropic.Anthropic = _FakeAnthropic
sys.modules["anthropic"] = mock_anthropic

# Mock litellm too (imported via integrations/__init__.py)
mock_litellm = types.ModuleType("litellm")
mock_litellm.completion = MagicMock()
mock_litellm.completion_cost = MagicMock(return_value=0.0)
sys.modules["litellm"] = mock_litellm


def setUpModule():
    sys.modules["anthropic"] = mock_anthropic
    sys.modules["litellm"]   = mock_litellm


from aot_harness.integrations.claude_adapter import ClaudeAdapter  # noqa: E402
from aot_harness.core.chip_orchestrator import CHIPOrchestrator  # noqa: E402


class TestBackwardCompat(unittest.TestCase):

    def test_claude_adapter_still_works(self):
        adapter = ClaudeAdapter(api_key="sk-test", model="claude-sonnet-4-6")
        result = adapter.complete("hello")
        self.assertEqual(result, "hello")

    def test_orchestrator_with_claude_adapter(self):
        """v0.2.x usage pattern: pass ClaudeAdapter directly."""
        adapter = ClaudeAdapter(api_key="sk-test")
        orch = CHIPOrchestrator(llm_client=adapter)
        # Single-LLM mode: decomposer falls back to llm
        self.assertIs(orch.llm, adapter)
        self.assertIs(orch.decomposer_llm, adapter)

    def test_cost_summary_safe_with_claude_adapter(self):
        """ClaudeAdapter has no cost_summary() — _collect_cost_summary must not crash."""
        adapter = ClaudeAdapter(api_key="sk-test")
        orch = CHIPOrchestrator(llm_client=adapter)
        cost = orch._collect_cost_summary()
        self.assertEqual(cost["total_usd"], 0.0)
        self.assertEqual(cost["by_provider"], {})


if __name__ == "__main__":
    unittest.main()
