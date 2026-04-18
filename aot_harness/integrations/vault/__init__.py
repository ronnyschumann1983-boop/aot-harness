"""
aot_harness.integrations.vault
──────────────────────────────
Pluggable knowledge-base backends for the CHIP Orchestrator.

Public API:
    VaultAdapter       — abstract base class, the contract
    ObsidianAdapter    — Obsidian vault via MCP kb_* tools (filesystem-backed)
    SupabaseAdapter    — Supabase Postgres table (pgvector-ready)
"""
from .base import VaultAdapter
from .obsidian import ObsidianAdapter
from .supabase import SupabaseAdapter

__all__ = ["VaultAdapter", "ObsidianAdapter", "SupabaseAdapter"]
