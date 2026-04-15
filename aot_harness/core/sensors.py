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
        # Structural errors — only match in code/log context, not in prose
        (r"Traceback \(most recent call last\)",   "Python traceback detected"),
        (r'^Error:\s.+',                            "Explicit error message"),          # line-start only
        (r'"error"\s*:\s*true',                     "JSON error flag"),                 # JSON {"error": true}
        (r'\b(404|500|502|503)\b(?!\s*\w)',        "HTTP error status code"),
        # Avoid false positives on "failed to mention", "None of the clients", etc.
        (r'(?i)\b(FAILED|EXCEPTION)\b(?=\s*[:!\n])', "Failure/Exception keyword at sentence boundary"),
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
