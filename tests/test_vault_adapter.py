"""
tests/test_vault_adapter.py
Contract tests — ObsidianAdapter and SupabaseAdapter must behave identically
against the VaultAdapter interface.

If a new adapter lands, add it to ADAPTERS and the whole contract re-runs
against it for free.
"""
from __future__ import annotations

import unittest

# Import the vault package directly so we don't drag in litellm/anthropic.
from aot_harness.integrations.vault import (
    VaultAdapter, ObsidianAdapter, SupabaseAdapter,
)


# ── Fake Supabase client (mimics the chaining API of supabase-py) ─────────────

class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    """Mimics supabase-py's chained query builder against an in-memory dict."""

    def __init__(self, store: dict[str, str]):
        self._store = store
        self._like_prefix: str | None = None
        self._ilike_terms: list[str] = []
        self._eq_path: str | None = None
        self._limit: int = 100

    def select(self, _cols): return self
    def limit(self, n): self._limit = n; return self

    def eq(self, col, val):
        if col == "path":
            self._eq_path = val
        return self

    def like(self, _col, pattern):
        self._like_prefix = pattern.rstrip("%")
        return self

    def or_(self, or_filter):
        # Parse "content.ilike.%term%,content.ilike.%term2%"
        for clause in or_filter.split(","):
            parts = clause.split(".")
            if len(parts) >= 3 and parts[1] == "ilike":
                self._ilike_terms.append(parts[2].strip("%").lower())
        return self

    def upsert(self, payload, on_conflict=None):
        self._store[payload["path"]] = payload["content"]
        return self

    def execute(self):
        if self._eq_path is not None:
            row = self._store.get(self._eq_path)
            return _FakeResult([{"path": self._eq_path, "content": row}] if row else [])
        if self._like_prefix is not None:
            rows = [{"path": p, "content": c} for p, c in self._store.items()
                    if p.startswith(self._like_prefix)]
            return _FakeResult(rows[: self._limit])
        if self._ilike_terms:
            rows = [{"path": p, "content": c} for p, c in self._store.items()
                    if any(t in c.lower() for t in self._ilike_terms)]
            return _FakeResult(rows[: self._limit])
        rows = [{"path": p, "content": c} for p, c in self._store.items()]
        return _FakeResult(rows[: self._limit])


class _FakeSupabase:
    def __init__(self):
        self._store: dict[str, str] = {}
    def table(self, _name):
        return _FakeQuery(self._store)


# ── Factory functions for each adapter ────────────────────────────────────────

def _make_obsidian() -> VaultAdapter:
    return ObsidianAdapter(mock=True)


def _make_supabase() -> VaultAdapter:
    return SupabaseAdapter(client=_FakeSupabase())


# ── Contract tests — mixin defines the tests, subclass picks the adapter ─────

class _VaultContractMixin:
    """Every adapter must satisfy these. Subclass + set _make_adapter."""

    def _make_adapter(self) -> VaultAdapter:  # pragma: no cover — overridden
        raise NotImplementedError

    def test_is_vault_adapter(self):
        self.assertIsInstance(self._make_adapter(), VaultAdapter)

    def test_ingest_then_read_round_trip(self):
        v = self._make_adapter()
        self.assertTrue(v.ingest("/patterns/test.md", "hello world from test"))
        self.assertEqual(v.read("/patterns/test.md"), "hello world from test")

    def test_read_missing_returns_none(self):
        self.assertIsNone(self._make_adapter().read("/nonexistent.md"))

    def test_search_finds_ingested_content(self):
        v = self._make_adapter()
        v.ingest("/a.md", "alpha beta gamma")
        v.ingest("/b.md", "delta epsilon")
        hits = v.search("alpha gamma")
        self.assertTrue(hits, "search must return at least one hit")
        self.assertEqual(hits[0]["path"], "/a.md")
        self.assertGreater(hits[0]["similarity"], 0.0)

    def test_search_orders_by_similarity_desc(self):
        v = self._make_adapter()
        v.ingest("/close.md", "pattern matching keyword")
        v.ingest("/far.md",   "pattern")
        hits = v.search("pattern matching keyword")
        sims = [h["similarity"] for h in hits]
        self.assertEqual(sims, sorted(sims, reverse=True))

    def test_cache_check_full_hit(self):
        v = self._make_adapter()
        text = "fully matching query phrase"
        v.ingest("/hit.md", text)
        result = v.cache_check(text)
        self.assertEqual(result["hit"], "full")
        self.assertGreaterEqual(result["similarity"], VaultAdapter.SIMILARITY_THRESHOLD_CACHE)
        self.assertEqual(result["pattern"], text)

    def test_cache_check_no_hit_on_empty_vault(self):
        v = self._make_adapter()
        result = v.cache_check("anything at all")
        self.assertEqual(result["hit"], "none")
        self.assertIsNone(result["pattern"])

    def test_ingest_updates_existing(self):
        v = self._make_adapter()
        v.ingest("/u.md", "version one")
        v.ingest("/u.md", "version two")
        self.assertEqual(v.read("/u.md"), "version two")


class TestObsidianAdapterContract(_VaultContractMixin, unittest.TestCase):
    def _make_adapter(self) -> VaultAdapter:
        return _make_obsidian()


class TestSupabaseAdapterContract(_VaultContractMixin, unittest.TestCase):
    def _make_adapter(self) -> VaultAdapter:
        return _make_supabase()


# ── SupabaseAdapter-specific: missing credentials must fail loudly ────────────

class TestSupabaseAdapterCredentials(unittest.TestCase):
    def test_raises_without_credentials(self):
        import os
        saved = {k: os.environ.pop(k, None)
                 for k in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_KEY")}
        try:
            with self.assertRaises(ValueError):
                SupabaseAdapter()
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
