"""
tests/test_orchestrator_multi_provider.py
Tests CHIPOrchestrator factory methods (from_provider, from_mixed) and
verifies the decomposer/executor LLM separation works correctly.
"""
from __future__ import annotations
import sys
import types
import unittest
from unittest.mock import MagicMock

# Mock litellm before any aot_harness import
mock_litellm = types.ModuleType("litellm")
mock_litellm.completion = MagicMock()
mock_litellm.completion_cost = MagicMock(return_value=0.001)
sys.modules["litellm"] = mock_litellm


def setUpModule():
    sys.modules["litellm"] = mock_litellm


def _resp(text="ok"):
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = text
    r.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
    return r


from aot_harness.core.chip_orchestrator import CHIPOrchestrator  # noqa: E402
from aot_harness.integrations.litellm_adapter import LiteLLMAdapter  # noqa: E402


class TestFactoryConstructors(unittest.TestCase):

    def test_from_provider_single(self):
        orch = CHIPOrchestrator.from_provider(provider="openai", api_key="sk-test")
        self.assertIsInstance(orch.llm, LiteLLMAdapter)
        self.assertEqual(orch.llm.provider, "openai")
        # Single-provider mode: decomposer == executor
        self.assertIs(orch.decomposer_llm, orch.llm)

    def test_from_mixed_separate_llms(self):
        orch = CHIPOrchestrator.from_mixed(
            executor_provider="google",
            decomposer_provider="anthropic",
        )
        self.assertEqual(orch.llm.provider, "google")
        self.assertEqual(orch.decomposer_llm.provider, "anthropic")
        self.assertIsNot(orch.decomposer_llm, orch.llm)

    def test_decomposer_routes_to_separate_llm(self):
        """AoTReasoner should hold the decomposer_llm, not the executor."""
        executor   = LiteLLMAdapter(provider="google",    api_key="test")
        decomposer = LiteLLMAdapter(provider="anthropic", api_key="sk-test")
        orch = CHIPOrchestrator(llm_client=executor, decomposer_llm=decomposer)
        self.assertIs(orch.reasoner.llm, decomposer)
        self.assertIs(orch.research_agent.llm, executor)
        self.assertIs(orch.writing_agent.llm, executor)
        self.assertIs(orch.analysis_agent.llm, executor)

    def test_no_decomposer_falls_back_to_executor(self):
        executor = LiteLLMAdapter(provider="mistral", api_key="test")
        orch = CHIPOrchestrator(llm_client=executor)
        self.assertIs(orch.decomposer_llm, executor)
        self.assertIs(orch.reasoner.llm, executor)


class TestCostAggregation(unittest.TestCase):

    def setUp(self):
        mock_litellm.completion.reset_mock()
        mock_litellm.completion.return_value = _resp("ok")
        mock_litellm.completion_cost.return_value = 0.01

    def test_mixed_cost_sums_both_providers(self):
        executor   = LiteLLMAdapter(provider="google",    api_key="test")
        decomposer = LiteLLMAdapter(provider="anthropic", api_key="sk-test")
        orch = CHIPOrchestrator(llm_client=executor, decomposer_llm=decomposer)

        executor.complete("a")
        decomposer.complete("b")

        cost = orch._collect_cost_summary()
        self.assertAlmostEqual(cost["total_usd"], 0.02, places=4)
        self.assertIn("google", cost["by_provider"])
        self.assertIn("anthropic", cost["by_provider"])

    def test_single_provider_no_double_count(self):
        """When decomposer_llm IS llm (default), cost counted once."""
        executor = LiteLLMAdapter(provider="openai", api_key="sk-test")
        orch = CHIPOrchestrator(llm_client=executor)

        executor.complete("a")
        executor.complete("b")

        cost = orch._collect_cost_summary()
        self.assertAlmostEqual(cost["total_usd"], 0.02, places=4)


if __name__ == "__main__":
    unittest.main()
