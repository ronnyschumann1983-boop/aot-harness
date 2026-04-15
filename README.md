# 🧠 aot-harness

> **Agent = Model + Harness + CHIP** | AoT-powered, self-learning Multi-Agent System

Combines **Atom of Thoughts (AoT)** reasoning with the **CHIP architecture**:
specialized sub-agents, QA scoring, and an Obsidian Vault that learns from every task.

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
                                     │
                                 QA-Agent (Score 0–1)
                                     │ Score < 0.75 → Retry
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
| QAAgent | `core/agents.py` | Quality check (Score 0–1) |
| Librarian | `core/agents.py` | Async Vault maintenance |
| Memory | `core/memory.py` | Session context with AoT compression |
| ObsidianVault | `integrations/obsidian_adapter.py` | kb_* MCP-Tools Wrapper |
| ClaudeAdapter | `integrations/claude_adapter.py` | Anthropic SDK |
| n8n Webhook | `integrations/n8n_webhook.py` | POST /run Endpoint |

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
