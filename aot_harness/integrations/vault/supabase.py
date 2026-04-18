"""
aot_harness.integrations.vault.supabase
───────────────────────────────────────
Supabase-backed knowledge base.

Schema (run once per project):
    create table if not exists vault_patterns (
        path        text primary key,
        content     text not null,
        tags        jsonb default '[]'::jsonb,
        created_at  timestamptz default now(),
        updated_at  timestamptz default now()
    );
    create index if not exists idx_vault_patterns_content_trgm
        on vault_patterns using gin (content gin_trgm_ops);

v0.4.0 uses keyword match (ilike) + Jaccard re-ranking on the returned rows.
pgvector-backed semantic search is queued for v0.4.1 (drop-in replacement of
the _candidate_rows method — adapter public surface stays identical).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from .base import VaultAdapter


class SupabaseAdapter(VaultAdapter):
    """
    Supabase Postgres adapter.

    Usage:
        SupabaseAdapter(url="https://xxx.supabase.co", key="service-role-key")
        SupabaseAdapter()   # falls back to SUPABASE_URL + SUPABASE_KEY env vars
        SupabaseAdapter(client=existing_supabase_client)   # e.g. for tests
    """

    TABLE = "vault_patterns"

    def __init__(
        self,
        url: str | None = None,
        key: str | None = None,
        client: Any | None = None,
        table: str | None = None,
    ):
        self.table = table or self.TABLE
        if client is not None:
            self._client = client
            return

        url = url or os.environ.get("SUPABASE_URL")
        key = key or os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise ValueError(
                "SupabaseAdapter needs url+key, or SUPABASE_URL+SUPABASE_KEY env vars, "
                "or an existing client=... (for tests)."
            )

        try:
            from supabase import create_client
        except ImportError as exc:
            raise ImportError(
                "SupabaseAdapter requires the `supabase` package. "
                "Install with: pip install supabase>=2.0.0"
            ) from exc

        self._client = create_client(url, key)

    # ── VaultAdapter surface ──────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        rows = self._candidate_rows(query, limit=max(top_k * 5, 10))
        if not rows:
            return []

        q_words = set(query.lower().split())
        scored: list[dict] = []
        for row in rows:
            content = row.get("content") or ""
            c_words = set(content.lower().split())
            union = q_words | c_words
            sim = len(q_words & c_words) / len(union) if union else 0.0
            if sim > 0:
                scored.append({
                    "path":       row["path"],
                    "content":    content[:200],
                    "similarity": round(sim, 2),
                })
        return sorted(scored, key=lambda x: x["similarity"], reverse=True)[:top_k]

    def read(self, path: str) -> str | None:
        res = (self._client.table(self.table)
                           .select("content")
                           .eq("path", path)
                           .limit(1)
                           .execute())
        data = getattr(res, "data", None) or []
        return data[0]["content"] if data else None

    def ingest(self, path: str, content: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "path":       path,
            "content":    content,
            "updated_at": now,
        }
        try:
            (self._client.table(self.table)
                         .upsert(payload, on_conflict="path")
                         .execute())
            return True
        except Exception as exc:
            print(f"[SupabaseAdapter] ingest failed for {path}: {exc}")
            return False

    def list_folder(self, folder: str) -> list[str]:
        prefix = folder.rstrip("/") + "/"
        res = (self._client.table(self.table)
                           .select("path")
                           .like("path", f"{prefix}%")
                           .execute())
        rows = getattr(res, "data", None) or []
        return [r["path"] for r in rows]

    # ── Internals ─────────────────────────────────────────────────────────────

    def _candidate_rows(self, query: str, limit: int) -> list[dict]:
        """
        Keyword-match candidate retrieval. Swap this method for a pgvector RPC
        call in v0.4.1 without touching the public adapter surface.
        """
        terms = [t for t in query.lower().split() if len(t) >= 3]
        if not terms:
            res = (self._client.table(self.table)
                               .select("path, content")
                               .limit(limit)
                               .execute())
            return getattr(res, "data", None) or []

        # OR across terms via ilike — Supabase's .or_() takes a comma-joined filter list.
        or_filter = ",".join(f"content.ilike.%{t}%" for t in terms)
        res = (self._client.table(self.table)
                           .select("path, content")
                           .or_(or_filter)
                           .limit(limit)
                           .execute())
        return getattr(res, "data", None) or []
