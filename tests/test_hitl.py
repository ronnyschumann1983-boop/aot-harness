"""
tests/test_hitl.py
Covers the HITL notifier + orchestrator integration:
  1. Webhook payload shape is stable and contains required fields.
  2. notify(block=True) actually POSTs to the webhook URL.
  3. _maybe_fire_hitl fires only when QA ultimately failed.
  4. A failing webhook does not raise (fire-and-forget semantics).
"""
from __future__ import annotations

import json
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from aot_harness.integrations.hitl import HITLNotifier, build_hitl_payload


# ── Pure payload + notifier tests (no orchestrator needed) ────────────────────

class TestHITLPayload(unittest.TestCase):

    def test_payload_has_required_fields(self):
        p = build_hitl_payload(
            goal="test goal", qa_score=0.42, threshold=0.75, attempts=2,
            anmerkungen=["too short"], final_output="partial",
            atoms_used=["a1"], session_id="sess-1",
        )
        for key in ("event", "goal", "qa_score", "threshold", "attempts",
                    "anmerkungen", "final_output", "atoms_used", "session_id"):
            self.assertIn(key, p)
        self.assertEqual(p["event"], "hitl_review_needed")
        self.assertEqual(p["qa_score"], 0.42)


class TestHITLNotifier(unittest.TestCase):

    def test_rejects_empty_webhook_url(self):
        with self.assertRaises(ValueError):
            HITLNotifier(webhook_url="")

    def test_blocking_notify_posts_to_webhook(self):
        captured = {}

        class _FakeResp:
            status = 200
            def read(self): return b""
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def _fake_urlopen(req, timeout):
            captured["url"]  = req.full_url
            captured["body"] = json.loads(req.data.decode())
            captured["ct"]   = req.headers.get("Content-type")
            return _FakeResp()

        notifier = HITLNotifier(webhook_url="https://example.test/hook")
        with patch("urllib.request.urlopen", _fake_urlopen):
            notifier.notify({"goal": "t", "qa_score": 0.4}, block=True)

        self.assertEqual(captured["url"], "https://example.test/hook")
        self.assertEqual(captured["body"]["goal"], "t")
        self.assertEqual(captured["body"]["event"], "hitl_review_needed")
        self.assertIn("timestamp", captured["body"])
        self.assertEqual(captured["ct"], "application/json")

    def test_webhook_failure_does_not_raise(self):
        import urllib.error
        def _boom(req, timeout):
            raise urllib.error.URLError("connection refused")

        notifier = HITLNotifier(webhook_url="https://bad.test/hook")
        with patch("urllib.request.urlopen", _boom):
            # Must complete without raising — fire-and-forget semantics
            notifier.notify({"goal": "t"}, block=True)


# ── Orchestrator integration — mock LLM/QA, inspect HITL calls ────────────────

# Minimal provider mocks so we can import CHIPOrchestrator
mock_anthropic = types.ModuleType("anthropic")
class _FakeAnthropic:
    def __init__(self, *a, **kw):
        self.messages = MagicMock()
        msg = MagicMock(); msg.content = [MagicMock(text="{}")]
        self.messages.create = MagicMock(return_value=msg)
mock_anthropic.Anthropic = _FakeAnthropic
sys.modules["anthropic"] = mock_anthropic

mock_litellm = types.ModuleType("litellm")
mock_litellm.completion = MagicMock()
mock_litellm.completion_cost = MagicMock(return_value=0.0)
sys.modules["litellm"] = mock_litellm

from aot_harness.core.chip_orchestrator import CHIPOrchestrator  # noqa: E402
from aot_harness.core.agents import QAResult  # noqa: E402


class _MiniOrchestrator(CHIPOrchestrator):
    """Bypass the full __init__ — we only need _maybe_fire_hitl."""
    def __init__(self, *, qa_threshold=0.75, hitl_notifier=None):
        self.qa_threshold = qa_threshold
        self.hitl         = hitl_notifier
        self.verbose      = False
        self.memory       = MagicMock(session_id="sess-test")


class TestOrchestratorHITLGate(unittest.TestCase):

    def _qa(self, score: float, bestanden: bool) -> QAResult:
        return QAResult(
            final_output = "some output",
            qa_score     = score,
            bestanden    = bestanden,
            anmerkungen  = ["note"],
            zurueck_an   = None,
        )

    def test_fires_when_qa_failed_after_retries(self):
        notifier = MagicMock(spec=HITLNotifier)
        orch = _MiniOrchestrator(qa_threshold=0.75, hitl_notifier=notifier)
        orch._maybe_fire_hitl("goal X", self._qa(0.60, bestanden=False),
                              atoms_used=["a1"], attempts=2)
        notifier.notify.assert_called_once()
        payload = notifier.notify.call_args[0][0]
        self.assertEqual(payload["qa_score"], 0.60)
        self.assertEqual(payload["threshold"], 0.75)
        self.assertEqual(payload["attempts"], 2)
        self.assertEqual(payload["goal"], "goal X")

    def test_does_not_fire_when_qa_passed(self):
        notifier = MagicMock(spec=HITLNotifier)
        orch = _MiniOrchestrator(qa_threshold=0.75, hitl_notifier=notifier)
        orch._maybe_fire_hitl("goal Y", self._qa(0.88, bestanden=True),
                              atoms_used=["a1"], attempts=1)
        notifier.notify.assert_not_called()

    def test_noop_when_hitl_not_configured(self):
        orch = _MiniOrchestrator(qa_threshold=0.75, hitl_notifier=None)
        # Must not raise
        orch._maybe_fire_hitl("goal Z", self._qa(0.30, bestanden=False),
                              atoms_used=[], attempts=2)

    def test_fires_when_bestanden_true_but_score_below_threshold(self):
        # Defensive: even if QAAgent says 'bestanden' but score is below threshold,
        # HITL should fire. This enforces the threshold as ground truth.
        notifier = MagicMock(spec=HITLNotifier)
        orch = _MiniOrchestrator(qa_threshold=0.75, hitl_notifier=notifier)
        orch._maybe_fire_hitl("goal W", self._qa(0.50, bestanden=True),
                              atoms_used=["a1"], attempts=2)
        notifier.notify.assert_called_once()


if __name__ == "__main__":
    unittest.main()
