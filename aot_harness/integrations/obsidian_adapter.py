"""
aot_harness.integrations.obsidian_adapter
─────────────────────────────────────────
Backward-compat shim (v0.4.0+).

The real implementation moved to aot_harness.integrations.vault.obsidian.
This module re-exports the adapter under its legacy name so existing imports
keep working:

    from aot_harness.integrations.obsidian_adapter import ObsidianVault

New code should prefer:

    from aot_harness.integrations.vault import ObsidianAdapter
"""
from __future__ import annotations

from .vault.obsidian import ObsidianAdapter as _ObsidianAdapter


class ObsidianVault(_ObsidianAdapter):
    """Legacy name retained for backward compatibility. Prefer ObsidianAdapter."""

    # Legacy threshold constants kept as class attributes (same values).
    SIMILARITY_THRESHOLD_CACHE = _ObsidianAdapter.SIMILARITY_THRESHOLD_CACHE
    SIMILARITY_THRESHOLD_REF   = _ObsidianAdapter.SIMILARITY_THRESHOLD_REF


__all__ = ["ObsidianVault"]
