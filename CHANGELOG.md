# Changelog

All notable changes to **aot-harness** (Python core + `n8n-nodes-aot-harness`).
Format inspired by [Keep a Changelog](https://keepachangelog.com/), versioning is [SemVer](https://semver.org/).

---

## [0.4.0] — 2026-04-18 — Pluggable Vaults + Human-in-the-Loop

### Added — Python core

- `aot_harness/integrations/vault/` — new package with a formal `VaultAdapter` ABC (abstract surface: `search`, `read`, `ingest`; derived `cache_check` concrete on the base).
- `ObsidianAdapter` — Obsidian via MCP kb_* tools (behaviour preserved from the legacy `ObsidianVault`, now inheriting from `VaultAdapter`). Mock mode still works for tests.
- `SupabaseAdapter` — Postgres-backed vault against a `vault_patterns` table. Keyword-match candidate retrieval + Jaccard re-ranking; pgvector is the drop-in replacement planned for v0.4.1 (swap `_candidate_rows`, public surface unchanged).
- `aot_harness/integrations/hitl.py` — `HITLNotifier` (fire-and-forget webhook POST) + `build_hitl_payload()` helper with a stable payload contract.
- `CHIPOrchestrator` — new kwargs `qa_threshold` (default 0.75) and `hitl_notifier`. When QA retries exhaust and `qa_score < qa_threshold`, the orchestrator emits a single `hitl_review_needed` webhook with `goal`, `qa_score`, `threshold`, `attempts`, `anmerkungen`, `final_output`, `atoms_used`, `session_id`.
- 25 new tests: a `_VaultContractMixin` re-runs identical assertions against every adapter (contract tests — new backends inherit coverage automatically); dedicated HITL tests cover payload shape, blocking POST, webhook failure handling, and orchestrator gating logic.

### Changed

- `integrations/__init__.py` now exports `VaultAdapter`, `ObsidianAdapter`, `SupabaseAdapter`, `HITLNotifier`, `build_hitl_payload`.
- `obsidian_adapter.py` becomes a backward-compat shim: `ObsidianVault` now inherits from the new `ObsidianAdapter`. Existing imports (`from aot_harness.integrations.obsidian_adapter import ObsidianVault`) continue to work unchanged.

### Backward compatibility

- No breaking changes. v0.3.x call sites keep working without modification — vault backends are opt-in per orchestrator instance, HITL is opt-in via `hitl_notifier=...`.

### Known limitations (will land in v0.4.1)

- `SupabaseAdapter.search` uses keyword-match + Jaccard on the returned rows. Semantic search via pgvector is queued — adapter surface will not change.
- n8n node does not yet expose vault-backend selection in the UI (workaround: use Webhook mode to call a Python orchestrator that uses the new vaults).

### Strategic context

v0.3.0 broadened provider coverage. v0.4.0 broadens memory coverage: Obsidian-only locked out teams without a filesystem-vault workflow. Supabase is the natural second backend for most n8n self-hosters (they often already run it). HITL closes the "silent bad output" gap — at scale, QA failures must page a human, not disappear into logs.

---

## [0.3.0] — 2026-04-17 — Multi-Provider

### ⚠️ Breaking changes (n8n node)

- The n8n node now requires a **provider-specific credential** instead of the legacy `aotHarnessApi` credential.
- Existing workflows must be re-configured: pick **Provider** → attach the matching credential (e.g. `AoT Harness — Anthropic`) → pick a **Model** from the dropdown.
- The legacy `aotHarnessApi` credential type is still registered (so existing entries don't disappear) but the new node does not read from it. See [Migration guide](n8n-node/README.md#migration-from-v02x).

The Python API is **not** breaking — `ClaudeAdapter` and the existing `CHIPOrchestrator(llm_client=...)` constructor continue to work exactly as before.

### Added — Python core

- `aot_harness/integrations/litellm_adapter.py` — `LiteLLMAdapter` covering 5 providers via [LiteLLM](https://github.com/BerriAI/litellm):
  Anthropic, OpenAI, Google Gemini, Mistral (la Plateforme, EU-hosted), OpenRouter (100+ models with one key).
- `CHIPOrchestrator.from_provider(provider, model, api_key, ...)` — single-provider factory.
- `CHIPOrchestrator.from_mixed(executor_provider, executor_model, decomposer_provider, decomposer_model, ...)` — mixed-provider factory: smart decomposer + cheap executor (typical 60–80% cost saving).
- Per-call cost tracking via `adapter.cost_summary()` + thread-local `last_call_info()` (safe under parallel atom execution).
- Per-atom cost log line in `CHIPOrchestrator` (`💰 [{atom_id}] {model}: ${cost:.4f} ({pt}+{ct} tok)`).
- Anthropic-only prompt caching (`cache_control: ephemeral` on the system message) — transparent fallback for the other 4 providers.
- `aot_harness/examples/mixed_provider_demo.py` — runs the same goal twice (single vs mixed) and prints the cost delta + annualized savings.
- 31 new unit tests across 4 files covering provider routing, per-call cost tracking, atom-override fields, and backward compatibility with `ClaudeAdapter`.

### Added — n8n node

- 5 new credential types: `AnthropicAotApi`, `OpenAiAotApi`, `GoogleGeminiAotApi`, `MistralAotApi`, `OpenRouterAotApi`.
- Provider dropdown + per-provider Model dropdown (curated options) in the node UI.
- 🪙 **Enable Mixed-Provider Mode** toggle exposing decomposer Provider/Model/credential.
- `nodes/AotHarness/llm.router.ts` — provider-agnostic HTTP caller with native handling for each provider's request/response format and token-usage shape.
- Per-call cost calculator (`PRICING_PER_1M`, `calcCost`) covering all listed models.
- Cost aggregator in node output:
  ```jsonc
  "cost": {
    "total_usd":         0.0143,
    "total_calls":       6,
    "prompt_tokens":     2480,
    "completion_tokens": 1120,
    "by_provider":       { "anthropic": { ... } },
    "by_model":          { "claude-sonnet-4-5": { ... } }
  }
  ```
- `n8n-node/examples/mixed-provider-cost-saver.json` — importable demo workflow comparing single-provider vs mixed-provider cost on the same goal.

### Changed

- `requirements.txt`, `setup.py`, `aot_harness/__init__.py` — version `0.3.0`, added `litellm>=1.50.0`.
- `n8n-node/package.json` — version `0.3.0`, all 6 credentials registered (5 new + legacy `aotHarnessApi` for migration safety).
- `aot_harness/core/aot_reasoner.py` — `Atom` dataclass gains optional `provider` / `model` fields (foundation for v0.3.1 per-atom routing; **stored but not yet applied** — see Known limitations).
- `CHIPOrchestrator` — accepts an optional `decomposer_llm` distinct from `llm_client`; `_collect_cost_summary()` aggregates both without double-counting when they share an instance.

### Known limitations (will land in v0.3.1)

- Per-atom provider/model overrides (atom-level routing) are **stored** in the AtomGraph but not yet **applied** during execution — this needs a thread-safe per-call adapter swap and is queued for v0.3.1.
- Mistral self-hosting via Ollama deferred to v0.4 (only the API-hosted `la Plateforme` is supported in v0.3.0).
- Prompt caching only on Anthropic (other providers don't yet expose a comparable cache-control surface).

### Strategic context

Anthropic-only locked out a majority of n8n self-hosters (existing OpenAI/Gemini/Mistral keys, GDPR-sensitive EU SMBs). The mixed-provider mode is the v0.3.0 hero feature: at 600 npm downloads and the first GitHub star, broadening provider coverage was the highest-ROI move before adding new patterns (BoT/ReAct/CoA).

---

## [0.2.2] — 2026-04-15

### Added / Changed

- ⚡ Parallel atom execution via `Promise.all` (independent atoms now run concurrently — typical 2–3× speedup).
- 📄 `max_tokens` raised to 4096 (no more silent truncation on long outputs).
- 🎯 Smart retry — QA returns `retry_atom_ids`, only failed atoms are recomputed.
- 🔇 Sensor: reduced false positives on empty-field outputs ("None of the clients…").

---

## [0.2.1] — 2026-04-15

- First public release on npm + GitHub. n8n community node + Python CHIP/AoT package.

---

[0.4.0]: https://github.com/ronnyschumann1983-boop/aot-harness/releases/tag/v0.4.0
[0.3.0]: https://github.com/ronnyschumann1983-boop/aot-harness/releases/tag/v0.3.0
[0.2.2]: https://github.com/ronnyschumann1983-boop/aot-harness/releases/tag/v0.2.2
[0.2.1]: https://github.com/ronnyschumann1983-boop/aot-harness/releases/tag/v0.2.1
