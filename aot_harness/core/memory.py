"""
aot_harness/core/memory.py
Session Memory & Context Layer (AGENTS.md-compatible)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
import json, pathlib


@dataclass
class MemoryEntry:
    role:      str   # "user" | "agent" | "tool" | "system"
    content:   str
    timestamp: str   = field(default_factory=lambda: datetime.utcnow().isoformat())
    atom_id:   str | None = None


class Memory:
    """
    Rolling context window with AoT compression support.
    Compatible with AGENTS.md conventions.
    """

    def __init__(self, session_id: str, max_tokens: int = 4000, persist_path: str | None = None):
        self.session_id   = session_id
        self.max_tokens   = max_tokens
        self.persist_path = pathlib.Path(persist_path) if persist_path else None
        self._entries: list[MemoryEntry] = []
        self._atom_results: dict[str, str] = {}   # compressed AoT results
        self._load()

    def add(self, role: str, content: str, atom_id: str | None = None) -> None:
        self._entries.append(MemoryEntry(role=role, content=content, atom_id=atom_id))
        self._save()

    def store_atom_result(self, atom_id: str, result: str) -> None:
        """AoT contraction: store compressed atom result, drop reasoning chain."""
        self._atom_results[atom_id] = result
        self._save()

    def get_atom_result(self, atom_id: str) -> str | None:
        return self._atom_results.get(atom_id)

    def context_window(self, last_n: int = 20) -> list[dict]:
        """Return recent entries as {role, content} dicts for LLM prompts."""
        return [
            {"role": e.role, "content": e.content}
            for e in self._entries[-last_n:]
        ]

    def atom_context(self) -> list[dict]:
        """Return all compressed atom results for injection into prompts."""
        return [
            {"atom_id": k, "result": v}
            for k, v in self._atom_results.items()
        ]

    def clear_session(self) -> None:
        self._entries.clear()
        self._atom_results.clear()
        self._save()

    def _save(self) -> None:
        if not self.persist_path:
            return
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "session_id": self.session_id,
            "entries": [vars(e) for e in self._entries],
            "atom_results": self._atom_results
        }
        self.persist_path.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        if not self.persist_path or not self.persist_path.exists():
            return
        data = json.loads(self.persist_path.read_text())
        self._entries = [MemoryEntry(**e) for e in data.get("entries", [])]
        self._atom_results = data.get("atom_results", {})
