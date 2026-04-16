# 🧠 aot-harness

> **Agent = Model + Harness + CHIP** | AoT-powered, self-learning Multi-Agent System

Combines **Atom of Thoughts (AoT)** reasoning with the **CHIP architecture**:
specialized sub-agents, QA scoring, and an Obsidian Vault that learns from every task.

![npm](https://img.shields.io/npm/v/n8n-nodes-aot-harness)
![downloads](https://img.shields.io/npm/dt/n8n-nodes-aot-harness)
![license](https://img.shields.io/badge/license-MIT-green)

---

## Two Modes

### 1. Simple Orchestrator (`Orchestrator`)
AoT + Tool Execution + Sensor/Verifier Loop. No Vault, no specialists.

```python
from aot_harness.core import Orchestrator
from aot_harness.integrations.claude_adapter import ClaudeAdapter

orch = Orchestrator(llm_client=ClaudeAdapter(api_key="..."))
result = orch.run("Analyze the top 3 CRM systems")
```

### 2. CHIP-Orchestrator (`CHIPOrchestrator`) — recommended
AoT + CHIP: Vault-Check, specialists, QA-Agent, Librarian.

```python
from aot_harness.core.chip_orchestrator import CHIPOrchestrator
from aot_harness.integrations.obsidian_adapter import ObsidianVault

vault = ObsidianVault(mcp_client=your_mcp)  # or mock=True
orch  = CHIPOrchestrator(llm_client=ClaudeAdapter(api_key="..."), vault=vault)
result = orch.run("Create IDD documentation for Client X")
```

---

## Full Flow (CHIP Mode)

```
User Goal
  └─► Vault-Check (kb_search) → Cache-Hit? ──────────────── yes ──► QA ──► Output
                                     │ no
                                     ▼
                           AoT Decomposition → AtomGraph
                                     │
                          ┌──────────┴──────────┐
                    [Research]            [Writing] [Analysis]
                    Specialist            Specialist Specialist
                          └──────────┬──────────┘
                          Sensor + Verifier Loop
                          (parallel via Promise.all)
                                     │
                                 QA-Agent (Score 0–1)
                                     │ Score < 0.75 → Retry failed atoms only
                                     │ Score ≥ 0.75
                                     ▼
                                Output to User
                                     │
                           Librarian (async)
                                     ▼
                            Obsidian Vault learns
```

---

## Architecture Components

| Component | File | Function |
|---|---|---|
| CHIPOrchestrator | `core/chip_orchestrator.py` | Coordinates everything |
| AoTReasoner | `core/aot_reasoner.py` | Decomposes goals into AtomGraph |
| Research/Writing/Analysis | `core/agents.py` | Specialized sub-agents |
| QAAgent | `core/agents.py` | Quality check (Score 0–1), retry failed atoms only |
| Librarian | `core/agents.py` | Async Vault maintenance |
| Memory | `core/memory.py` | Session context with AoT compression |
| ObsidianVault | `integrations/obsidian_adapter.py` | kb_* MCP-Tools Wrapper |
| ClaudeAdapter | `integrations/claude_adapter.py` | Anthropic SDK (max_tokens 4096) |
| n8n Webhook | `integrations/n8n_webhook.py` | POST /run Endpoint |

---

## What's New in v0.3.0 — Multi-Provider

- 🌐 **5 LLM providers**: Anthropic, OpenAI, Google Gemini, **Mistral (EU/GDPR)**, OpenRouter
- 🪙 **Mixed-Provider Mode** — separate decomposer (smart) + executor (cheap) → typical **60–80% cost saving** at comparable QA score
- 💰 **Per-call cost tracking** — `cost_summary()` on the adapter, `cost.total_usd` + breakdown in n8n node output
- 🇪🇺 **Mistral (la Plateforme)** — fully EU-hosted for GDPR-sensitive workflows
- 🔌 **LiteLLM** under the hood — switch providers in one line:
  ```python
  CHIPOrchestrator.from_provider(provider="google", model="gemini-2.0-flash")
  CHIPOrchestrator.from_mixed(decomposer_provider="anthropic", executor_provider="google")
  ```
- 🧪 **31 tests** covering provider routing, cost tracking, backward compat
- 🪶 **n8n node v0.3.0** with provider dropdown + mixed-mode toggle (breaking change — see [n8n-node/README.md](n8n-node/README.md#migration-from-v02x))

> Full Python demo: `python -m aot_harness.examples.mixed_provider_demo`

### Previously in v0.2.2

- ⚡ **Parallel Atoms** — independent atoms run concurrently via `Promise.all`: 2–3x faster
- 📄 **max_tokens 4096** — no more truncation on long outputs
- 🎯 **Smart Retry** — QA returns `retry_atom_ids`, only failed atoms are recomputed
- 🔇 **Sensor Fix** — reduced false positives on empty fields like "None of the clients..."

---

## Quick Start

```bash
git clone https://github.com/ronnyschumann1983-boop/aot-harness
cd aot-harness
pip install -r requirements.txt
python -m aot_harness.examples.chip_idd_demo
```

---

## Based on

- **AoT Paper**: arXiv:2502.12018 (NeurIPS 2025) — MIT License
- **CHIP Architecture**: CLAUDE.md / AGENTS.md (Ronny Schumann)
- **Harness Concept**: Anthropic Engineering, Martin Fowler (2026)

---

## License

MIT
