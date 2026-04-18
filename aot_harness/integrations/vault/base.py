"""
aot_harness.integrations.vault.base
───────────────────────────────────
VaultAdapter — abstract base class for knowledge-base backends.

The CHIP Orchestrator depends on this interface, not on any concrete adapter.
To add a new backend (Notion, Weaviate, Qdrant, …) subclass VaultAdapter and
implement the three abstract methods; cache_check() comes for free.

Return-shape contract for search():
    [{"path": str, "content": str, "similarity": float}, ...]
    sorted by similarity descending. similarity ∈ [0.0, 1.0].
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class VaultAdapter(ABC):
    """Abstract knowledge-base backend. Subclass to add a new vault."""

    # Cache thresholds (override in subclass only when backend semantics require it).
    SIMILARITY_THRESHOLD_CACHE: float = 0.85   # full hit → reuse pattern verbatim
    SIMILARITY_THRESHOLD_REF:   float = 0.50   # partial hit → load as reference

    # ── Abstract surface ──────────────────────────────────────────────────────

    @abstractmethod
    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """Return up to top_k matches sorted by similarity descending."""

    @abstractmethod
    def read(self, path: str) -> str | None:
        """Load a single note by path. Return None if not found."""

    @abstractmethod
    def ingest(self, path: str, content: str) -> bool:
        """Write or update a note. Return True on success."""

    # ── Optional surface (backends may override) ──────────────────────────────

    def list_folder(self, folder: str) -> list[str]:
        """List paths under a folder. Default: empty (not all backends support folders)."""
        return []

    # ── Derived behaviour (concrete, uses abstract methods) ───────────────────

    def cache_check(self, task: str) -> dict:
        """
        Three-tier cache lookup using the abstract search()/read() primitives.

        Returns:
            {"hit": "full"|"partial"|"none",
             "pattern": str|None,
             "similarity": float,
             "path": str|None}
        """
        hits = self.search(task)
        if not hits:
            return {"hit": "none", "pattern": None, "similarity": 0.0, "path": None}

        top = hits[0]
        sim = float(top.get("similarity", 0.0))
        path = top.get("path")

        if sim >= self.SIMILARITY_THRESHOLD_CACHE:
            return {"hit": "full",    "pattern": self.read(path), "similarity": sim, "path": path}
        if sim >= self.SIMILARITY_THRESHOLD_REF:
            return {"hit": "partial", "pattern": self.read(path), "similarity": sim, "path": path}
        return {"hit": "none", "pattern": None, "similarity": sim, "path": None}
