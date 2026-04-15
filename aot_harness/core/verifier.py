"""
aot_harness/core/verifier.py
Verification Loop — decides retry, fix, or accept based on sensor feedback.
"""
from __future__ import annotations
from .sensors import SensorResult


class Verifier:
    """
    Evaluates SensorResults and produces a structured verdict.
    Feeds into the Orchestrator retry-loop.
    """

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def evaluate(self, sensor_result: SensorResult, attempt: int) -> dict:
        """
        Returns:
            {"action": "accept" | "retry" | "abort", "reason": str, "feedback": str}
        """
        if sensor_result.passed:
            return {
                "action":   "accept",
                "reason":   "All sensors passed",
                "feedback": "\n".join(sensor_result.signals)
            }

        if attempt >= self.max_retries:
            return {
                "action":   "abort",
                "reason":   f"Max retries ({self.max_retries}) reached",
                "feedback": "\n".join(sensor_result.signals)
            }

        return {
            "action":   "retry",
            "reason":   "Sensor detected issues — retrying",
            "feedback": "\n".join(sensor_result.signals)
        }
