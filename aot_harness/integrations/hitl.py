"""
aot_harness.integrations.hitl
─────────────────────────────
Human-in-the-Loop notifier.

When the QA loop exhausts its retries and the score is still below threshold,
the orchestrator fires an HITL event → your webhook → n8n → Slack/Email/…

The notification is non-blocking (fire-and-forget thread). A failed webhook
logs a warning but never crashes the task: the partial result is still
returned to the caller.

Payload shape (stable contract):
    {
        "event":       "hitl_review_needed",
        "goal":        "<original user goal>",
        "qa_score":    0.62,
        "threshold":   0.75,
        "attempts":    2,
        "anmerkungen": ["QA feedback line 1", ...],
        "final_output":"<best-effort output>",
        "atoms_used":  ["a1", "a2", ...],
        "session_id":  "chip-default",
        "timestamp":   "2026-04-18T08:45:12Z"
    }
"""
from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("aot_harness.hitl")


class HITLNotifier:
    """Fire-and-forget webhook notifier for QA failures."""

    EVENT = "hitl_review_needed"

    def __init__(
        self,
        webhook_url: str,
        timeout: float = 10.0,
        extra_headers: dict[str, str] | None = None,
    ):
        if not webhook_url:
            raise ValueError("HITLNotifier needs a webhook_url")
        self.webhook_url   = webhook_url
        self.timeout       = timeout
        self.extra_headers = extra_headers or {}

    def notify(self, payload: dict[str, Any], *, block: bool = False) -> None:
        """
        Fire the webhook. By default runs in a daemon thread (non-blocking).
        Set block=True for synchronous delivery (useful in tests).
        """
        body = dict(payload)
        body.setdefault("event", self.EVENT)
        body.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

        if block:
            self._post(body)
        else:
            threading.Thread(target=self._post, args=(body,), daemon=True).start()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _post(self, body: dict[str, Any]) -> None:
        data = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json", **self.extra_headers}
        req = urllib.request.Request(
            self.webhook_url, data=data, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status >= 400:
                    logger.warning(
                        "HITL webhook returned %s: %s",
                        resp.status, resp.read()[:200],
                    )
        except (urllib.error.URLError, TimeoutError) as exc:
            logger.warning("HITL webhook failed: %s", exc)
        except Exception as exc:
            logger.warning("HITL webhook unexpected error: %s", exc)


def build_hitl_payload(
    *,
    goal: str,
    qa_score: float,
    threshold: float,
    attempts: int,
    anmerkungen: list[str],
    final_output: str,
    atoms_used: list[str],
    session_id: str,
) -> dict[str, Any]:
    """Helper: build the stable payload shape (keeps the contract in one place)."""
    return {
        "event":        HITLNotifier.EVENT,
        "goal":         goal,
        "qa_score":     round(float(qa_score), 4),
        "threshold":    round(float(threshold), 4),
        "attempts":     int(attempts),
        "anmerkungen":  list(anmerkungen),
        "final_output": final_output,
        "atoms_used":   list(atoms_used),
        "session_id":   session_id,
    }
