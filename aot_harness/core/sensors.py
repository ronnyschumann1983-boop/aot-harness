"""
aot_harness/core/sensors.py
Feedback Sensors — observe tool outputs and detect errors.
"""
from __future__ import annotations
from dataclasses import dataclass
import re


@dataclass
class SensorResult:
    passed:    bool
    signals:   list[str]   # human-readable feedback messages
    raw:       str         # raw tool output


class Sensor:
    """
    Inspects tool outputs after execution and generates structured feedback
    that the Verifier and Orchestrator can act on.
    """

    ERROR_PATTERNS = [
        (r"Traceback \(most recent call last\)",   "Python traceback detected"),
        (r"Error:\s.+",                              "Explicit error message"),
        (r"\bfailed\b",                             "Failure keyword"),
        (r"\bexception\b",                          "Exception keyword"),
        (r"\bnull\b|\bNone\b|\bundefined\b",   "Null/None value returned"),
        (r"\b(404|500|502|503)\b",                 "HTTP error status code"),
    ]

    SUCCESS_PATTERNS = [
        (r"\bsuccess\b|\bcompleted\b|\bdone\b", "Success keyword"),
        (r"\bOK\b|\b200\b",                       "HTTP OK"),
    ]

    def observe(self, output: str) -> SensorResult:
        signals = []
        passed  = True

        for pattern, msg in self.ERROR_PATTERNS:
            if re.search(pattern, output, re.IGNORECASE):
                signals.append(f"⚠️  {msg}")
                passed = False

        if passed:
            for pattern, msg in self.SUCCESS_PATTERNS:
                if re.search(pattern, output, re.IGNORECASE):
                    signals.append(f"✅ {msg}")

        if not signals:
            signals.append("ℹ️  Output received (no explicit signal)")

        return SensorResult(passed=passed, signals=signals, raw=output)
