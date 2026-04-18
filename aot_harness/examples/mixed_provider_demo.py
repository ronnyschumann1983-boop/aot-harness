"""
aot_harness/examples/mixed_provider_demo.py

Demonstrates the v0.3.0 Mixed-Provider killer feature:
runs the SAME goal twice and compares cost.

  Run A: Single-provider (Anthropic Sonnet for everything)
  Run B: Mixed (Anthropic Sonnet decomposes, Google Gemini Flash executes)

Expected: Run B is ~70-80% cheaper at comparable quality.

Required env vars:
  ANTHROPIC_API_KEY   (for both runs)
  GEMINI_API_KEY      (for Run B)

Usage:
  python -m aot_harness.examples.mixed_provider_demo
"""
from __future__ import annotations
import os
import sys
import time

from aot_harness.core.chip_orchestrator import CHIPOrchestrator


GOAL = (
    "Erstelle eine kurze IDD-Dokumentation (Beratungsprotokoll) für einen Kunden, "
    "42 Jahre, sucht private Haftpflichtversicherung. "
    "Beratungsanlass: Auszug aus Elternhaus, jetzt eigener Hausstand."
)


def _check_keys() -> tuple[bool, bool]:
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_gemini    = bool(os.environ.get("GEMINI_API_KEY"))
    return has_anthropic, has_gemini


def _run(label: str, orch: CHIPOrchestrator, goal: str) -> dict:
    print(f"\n{'='*72}\n▶ {label}\n{'='*72}")
    t0 = time.time()
    result = orch.run(goal)
    elapsed = time.time() - t0
    cost = result.get("cost", {}).get("total_usd", 0.0)
    print(f"\n• Time:    {elapsed:.1f}s")
    print(f"• Cost:    ${cost:.4f} USD")
    print(f"• QA:      {result.get('qa_score', 0):.2f} (passed={result.get('success')})")
    return result


def main() -> int:
    has_anth, has_gem = _check_keys()
    if not has_anth:
        print("✗ Missing env var: ANTHROPIC_API_KEY", file=sys.stderr)
        return 1
    if not has_gem:
        print("✗ Missing env var: GEMINI_API_KEY", file=sys.stderr)
        return 1

    print("aot-harness v0.3.0 — Mixed-Provider Cost Comparison Demo")
    print(f"Goal: {GOAL[:90]}...")

    # ── Run A: single-provider (Anthropic for everything) ───────────────────
    orch_single = CHIPOrchestrator.from_provider(
        provider="anthropic",
        model="claude-sonnet-4-6",
        verbose=False,  # suppress per-step logs to keep demo output readable
    )
    res_a = _run("RUN A — Single-provider (Anthropic Sonnet)", orch_single, GOAL)

    # ── Run B: mixed (Anthropic decomposes, Gemini Flash executes) ──────────
    orch_mixed = CHIPOrchestrator.from_mixed(
        executor_provider="google",
        executor_model="gemini-2.0-flash",
        decomposer_provider="anthropic",
        decomposer_model="claude-sonnet-4-6",
        verbose=False,
    )
    res_b = _run("RUN B — Mixed (Anthropic decomposer + Gemini Flash executor)",
                 orch_mixed, GOAL)

    # ── Compare ─────────────────────────────────────────────────────────────
    cost_a = res_a.get("cost", {}).get("total_usd", 0.0)
    cost_b = res_b.get("cost", {}).get("total_usd", 0.0)
    saving = (cost_a - cost_b) / cost_a * 100 if cost_a > 0 else 0.0

    print(f"\n{'='*72}\n📊 COMPARISON\n{'='*72}")
    print(f"  Single (Anthropic only):  ${cost_a:.4f}")
    print(f"  Mixed  (Anth + Gemini):    ${cost_b:.4f}")
    print(f"  Savings:                   {saving:.0f}% ({(cost_a - cost_b):.4f} USD per run)")
    print(f"\n  → Annualized at 1k runs/month: {(cost_a - cost_b) * 12_000:.2f} USD/year saved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
