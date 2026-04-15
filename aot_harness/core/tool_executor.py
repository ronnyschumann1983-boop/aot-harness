"""
aot_harness/core/tool_executor.py
Tool Registry & Executor — sandboxed, extensible.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Any
import json


@dataclass
class ToolResult:
    name:    str
    output:  str
    success: bool
    error:   str | None = None


class ToolRegistry:
    """
    Register callable tools; the Orchestrator dispatches to them by name.
    Tools receive a dict of arguments and return a string output.
    """

    def __init__(self):
        self._tools: dict[str, Callable] = {}
        self._schemas: dict[str, dict]   = {}

    def register(self, name: str, fn: Callable, schema: dict | None = None) -> None:
        self._tools[name] = fn
        self._schemas[name] = schema or {"name": name, "description": "No description"}

    def execute(self, name: str, args: dict) -> ToolResult:
        if name not in self._tools:
            return ToolResult(name=name, output="", success=False,
                              error=f"Tool '{name}' not registered")
        try:
            output = self._tools[name](**args)
            return ToolResult(name=name, output=str(output), success=True)
        except Exception as exc:
            return ToolResult(name=name, output="", success=False, error=str(exc))

    def available_tools(self) -> list[dict]:
        return list(self._schemas.values())

    def parse_and_execute(self, llm_output: str) -> ToolResult | None:
        """
        Parse a tool call from LLM output.
        Expected format:  TOOL: tool_name({"arg": "value"})
        """
        import re
        match = re.search(r"TOOL:\s*(\w+)\((.*)\)", llm_output, re.DOTALL)
        if not match:
            return None
        name = match.group(1)
        try:
            args = json.loads(match.group(2)) if match.group(2).strip() else {}
        except json.JSONDecodeError:
            args = {}
        return self.execute(name, args)


# ── Built-in default tools ────────────────────────────────────────────────────

def _builtin_echo(text: str = "") -> str:
    return text

def _builtin_format_json(data: str = "") -> str:
    try:
        return json.dumps(json.loads(data), indent=2)
    except Exception as e:
        return f"Error: {e}"

def get_default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register("echo",        _builtin_echo,        {"name": "echo", "description": "Echo text back"})
    reg.register("format_json", _builtin_format_json, {"name": "format_json", "description": "Pretty-print JSON"})
    return reg
