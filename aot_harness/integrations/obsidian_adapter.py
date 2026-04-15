"""
aot_harness/integrations/obsidian_adapter.py
Obsidian Vault Adapter — wraps MCP kb_* Tools für den Harness.
Kompatibel mit CLAUDE.md Vault-Struktur.

Vault-Tools (via MCP):
  kb_search(query)       → semantische Suche
  kb_read(path)          → Note lesen
  kb_ingest(path, cont.) → Note schreiben / updaten
  kb_list(folder)        → Ordner auflisten
"""
from __future__ import annotations
import json


class ObsidianVault:
    """
    Wrapper um die kb_* MCP-Tools.
    Kann als Mock (für Tests) oder mit echtem MCP-Client verwendet werden.

    Echt:  ObsidianVault(mcp_client=your_mcp_client)
    Mock:  ObsidianVault(mock=True)
    """

    SIMILARITY_THRESHOLD_CACHE = 0.85   # Cache-Hit: direkt verwenden
    SIMILARITY_THRESHOLD_REF   = 0.50   # Referenz: als Vorlage laden

    def __init__(self, mcp_client=None, mock: bool = False):
        self._mcp  = mcp_client
        self._mock = mock
        self._store: dict[str, str] = {}  # nur für Mock-Modus

    # ── Öffentliche API ───────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """Semantische Suche im Vault. Gibt [{path, content, similarity}] zurück."""
        if self._mock:
            return self._mock_search(query)
        return self._call("kb_search", {"query": query, "top_k": top_k})

    def read(self, path: str) -> str | None:
        """Einzelne Note lesen."""
        if self._mock:
            return self._store.get(path)
        result = self._call("kb_read", {"path": path})
        return result.get("content") if result else None

    def ingest(self, path: str, content: str) -> bool:
        """Note schreiben oder updaten."""
        if self._mock:
            self._store[path] = content
            return True
        result = self._call("kb_ingest", {"path": path, "content": content})
        return bool(result)

    def list_folder(self, folder: str) -> list[str]:
        """Alle Notes in einem Ordner auflisten."""
        if self._mock:
            return [k for k in self._store if k.startswith(folder)]
        result = self._call("kb_list", {"folder": folder})
        return result.get("paths", []) if result else []

    def cache_check(self, task: str) -> dict:
        """
        Prüft Vault auf Cache-Hits.
        Returns: {"hit": "full"|"partial"|"none", "pattern": dict|None, "similarity": float}
        """
        hits = self.search(task)
        if not hits:
            return {"hit": "none", "pattern": None, "similarity": 0.0}

        top = hits[0]
        sim = top.get("similarity", 0.0)

        if sim >= self.SIMILARITY_THRESHOLD_CACHE:
            content = self.read(top["path"])
            return {"hit": "full", "pattern": content, "similarity": sim, "path": top["path"]}
        elif sim >= self.SIMILARITY_THRESHOLD_REF:
            content = self.read(top["path"])
            return {"hit": "partial", "pattern": content, "similarity": sim, "path": top["path"]}
        else:
            return {"hit": "none", "pattern": None, "similarity": sim}

    # ── Interner MCP-Aufruf ───────────────────────────────────────────────────

    def _call(self, tool: str, args: dict) -> dict:
        if self._mcp is None:
            raise RuntimeError("Kein MCP-Client gesetzt. Nutze mock=True für Tests.")
        try:
            return self._mcp.call_tool(tool, args)
        except Exception as e:
            print(f"[ObsidianVault] MCP-Fehler bei {tool}: {e}")
            return {}

    # ── Mock-Implementierung (für Tests ohne Obsidian) ────────────────────────

    def _mock_search(self, query: str) -> list[dict]:
        """Jaccard similarity on word sets — better than simple word-count overlap."""
        results = []
        query_words = set(query.lower().split())
        for path, content in self._store.items():
            content_words = set(content.lower().split())
            intersection = query_words & content_words
            union = query_words | content_words
            similarity = len(intersection) / len(union) if union else 0.0
            if similarity > 0:
                results.append({"path": path, "content": content[:200],
                                 "similarity": round(similarity, 2)})
        return sorted(results, key=lambda x: x["similarity"], reverse=True)[:3]
