"""
aot_harness.integrations.vault.obsidian
───────────────────────────────────────
Obsidian backend via MCP kb_* tools (filesystem-backed markdown vault).

Tools expected on the injected MCP client:
    kb_search(query, top_k)  → {"results": [{path, content, similarity}, ...]}
                                (or list directly — both shapes handled)
    kb_read(path)            → {"content": str}
    kb_ingest(path, content) → {"ok": bool}
    kb_list(folder)          → {"paths": [str, ...]}

Also offers a mock mode for tests (mock=True) — no MCP client needed.
"""
from __future__ import annotations

from .base import VaultAdapter


class ObsidianAdapter(VaultAdapter):
    """Obsidian vault adapter. Pass an MCP client, or use mock=True for tests."""

    def __init__(self, mcp_client=None, mock: bool = False):
        self._mcp = mcp_client
        self._mock = mock
        self._store: dict[str, str] = {}   # in-memory store for mock mode
        if not mock and mcp_client is None:
            raise ValueError("ObsidianAdapter needs mcp_client=... or mock=True")

    # ── VaultAdapter surface ──────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        if self._mock:
            return self._mock_search(query, top_k)
        raw = self._call("kb_search", {"query": query, "top_k": top_k})
        # Normalise: MCP may return dict with "results" or a bare list
        if isinstance(raw, dict):
            raw = raw.get("results", [])
        return raw if isinstance(raw, list) else []

    def read(self, path: str) -> str | None:
        if self._mock:
            return self._store.get(path)
        result = self._call("kb_read", {"path": path})
        return result.get("content") if isinstance(result, dict) else None

    def ingest(self, path: str, content: str) -> bool:
        if self._mock:
            self._store[path] = content
            return True
        result = self._call("kb_ingest", {"path": path, "content": content})
        return bool(result)

    def list_folder(self, folder: str) -> list[str]:
        if self._mock:
            return [k for k in self._store if k.startswith(folder)]
        result = self._call("kb_list", {"folder": folder})
        return result.get("paths", []) if isinstance(result, dict) else []

    # ── Internals ─────────────────────────────────────────────────────────────

    def _call(self, tool: str, args: dict) -> dict:
        try:
            return self._mcp.call_tool(tool, args) or {}
        except Exception as exc:
            print(f"[ObsidianAdapter] MCP error on {tool}: {exc}")
            return {}

    def _mock_search(self, query: str, top_k: int) -> list[dict]:
        """Jaccard similarity on lowercased word sets — good enough for tests."""
        q_words = set(query.lower().split())
        hits: list[dict] = []
        for path, content in self._store.items():
            c_words = set(content.lower().split())
            union = q_words | c_words
            if not union:
                continue
            sim = len(q_words & c_words) / len(union)
            if sim > 0:
                hits.append({
                    "path": path,
                    "content": content[:200],
                    "similarity": round(sim, 2),
                })
        return sorted(hits, key=lambda x: x["similarity"], reverse=True)[:top_k]
