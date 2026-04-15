# 🧠 aot-harness

> **Agent = Model + Harness + CHIP** | AoT-powered, selbstlernendes Multi-Agent-System

Kombiniert **Atom of Thoughts (AoT)** Reasoning mit der **CHIP-Architektur**:
spezialisierte Subagenten, QA-Scoring und einem Obsidian-Vault der aus jedem Task lernt.

---

## Zwei Modi

### 1. Einfacher Orchestrator (`Orchestrator`)
AoT + Tool Execution + Sensor/Verifier Loop. Kein Vault, keine Spezialisten.

```python
from aot_harness.core import Orchestrator
from aot_harness.integrations.claude_adapter import ClaudeAdapter

orch = Orchestrator(llm_client=ClaudeAdapter(api_key="..."))
result = orch.run("Analysiere die Top 3 CRM-Systeme")
```

### 2. CHIP-Orchestrator (`CHIPOrchestrator`) — empfohlen
AoT + CHIP: Vault-Check, Spezialisten, QA-Agent, Bibliothekarin.

```python
from aot_harness.core.chip_orchestrator import CHIPOrchestrator
from aot_harness.integrations.obsidian_adapter import ObsidianVault

vault = ObsidianVault(mcp_client=your_mcp)  # oder mock=True
orch  = CHIPOrchestrator(llm_client=ClaudeAdapter(api_key="..."), vault=vault)
result = orch.run("Erstelle IDD-Dokumentation für Kunde X")
```

---

## Vollständiger Flow (CHIP-Modus)

```
User Goal
  └─► Vault-Check (kb_search) → Cache-Hit? ──────────────── ja ──► QA ──► Output
                                     │ nein
                                     ▼
                           AoT Decomposition → AtomGraph
                                     │
                          ┌──────────┴──────────┐
                    [Research]            [Writing] [Analysis]
                    Spezialist            Spezialist Spezialist
                          └──────────┬──────────┘
                               Sensor + Verifier Loop
                                     │
                                 QA-Agent (Score 0–1)
                                     │ Score < 0.75 → Retry
                                     │ Score ≥ 0.75
                                     ▼
                                Output an User
                                     │
                           Bibliothekarin (async)
                                     ▼
                            Obsidian Vault lernt
```

---

## Architektur-Komponenten

| Komponente | Datei | Funktion |
|---|---|---|
| CHIPOrchestrator | `core/chip_orchestrator.py` | Koordiniert alles |
| AoTReasoner | `core/aot_reasoner.py` | Zerlegt Goals in AtomGraph |
| Research/Writing/Analysis | `core/agents.py` | Spezialisierte Subagenten |
| QAAgent | `core/agents.py` | Qualitätsprüfung (Score 0–1) |
| Bibliothekarin | `core/agents.py` | Async Vault-Pflege |
| Memory | `core/memory.py` | Session-Context mit AoT-Kompression |
| ObsidianVault | `integrations/obsidian_adapter.py` | kb_* MCP-Tools Wrapper |
| ClaudeAdapter | `integrations/claude_adapter.py` | Anthropic SDK |
| n8n Webhook | `integrations/n8n_webhook.py` | POST /run Endpoint |

---

## Quick Start Demo

```bash
pip install anthropic
python -m aot_harness.examples.chip_idd_demo
```

---

## Basiert auf

- **AoT Paper**: arXiv:2502.12018 (NeurIPS 2025) — MIT License
- **CHIP-Architektur**: CLAUDE.md / AGENTS.md (Ronny Schumann)
- **Harness-Konzept**: Anthropic Engineering, Martin Fowler (2026)

---

## Lizenz

MIT
