# n8n-nodes-aot-harness

> **CHIP + Atom of Thoughts (AoT) for n8n** — multi-provider agent harness with built-in cost tracking.

[![npm](https://img.shields.io/npm/v/n8n-nodes-aot-harness)](https://www.npmjs.com/package/n8n-nodes-aot-harness)
[![downloads](https://img.shields.io/npm/dt/n8n-nodes-aot-harness)](https://www.npmjs.com/package/n8n-nodes-aot-harness)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A community node that brings the **AoT-Harness** (atomic decomposition + QA loop) into n8n.
One node, one goal — the harness decomposes the task into atoms, runs them in parallel, QA-scores the result, and returns the polished output **plus a per-call cost breakdown**.

---

## What's new in v0.3.0 — Multi-Provider

- 🌐 **5 providers**: Anthropic, OpenAI, Google Gemini, **Mistral (EU/GDPR)**, OpenRouter (100+ models, 1 key)
- 🪙 **Mixed-Provider Mode** — let a smart model decompose, a cheap one execute. Typical saving: **60–80%** at comparable quality.
- 💰 **Cost tracking in node output** — every run reports `cost.total_usd`, tokens, breakdown by provider and by model
- 🇪🇺 **Mistral (la Plateforme)** — fully EU-hosted, GDPR-friendly, ideal for German/EU SMB workflows

> **⚠️ Breaking change** for existing v0.2.x users — see [Migration](#migration-from-v02x) below.

---

## Install

In n8n → **Settings → Community Nodes → Install**:

```
n8n-nodes-aot-harness
```

Then add the credential(s) for the provider(s) you want to use:
**AoT Harness — Anthropic / OpenAI / Google Gemini / Mistral / OpenRouter**.

---

## Quick Start

1. Drop **AoT Harness** into a workflow.
2. Pick a **Provider** (e.g. Anthropic) and a **Model** (e.g. `claude-sonnet-4-5`).
3. Attach the matching credential.
4. Set the **Goal** field to the task in plain language:
   ```
   Erstelle eine kurze IDD-Dokumentation für einen Kunden, 42 J., sucht private Haftpflicht…
   ```
5. Run.

The node returns:
```jsonc
{
  "goal":      "...",
  "result":    "polished final output",
  "qa_score":  0.92,
  "success":   true,
  "atoms_done": 4,
  "atoms_total": 4,
  "provider_used": "anthropic",
  "model_used":    "claude-sonnet-4-5",
  "cost": {
    "total_usd":         0.0143,
    "total_calls":       6,
    "prompt_tokens":     2480,
    "completion_tokens": 1120,
    "by_provider":       { "anthropic": { "cost_usd": 0.0143, "calls": 6, ... } },
    "by_model":          { "claude-sonnet-4-5": { "cost_usd": 0.0143, ... } }
  }
}
```

---

## 🪙 Mixed-Provider Mode (cost-saver)

Toggle **"Enable Mixed-Provider Mode"** in the node:

- **Decomposer** = the smart model that splits the goal into atoms (e.g. Claude Opus / Sonnet)
- **Executor** = the cheap model that solves each atom and runs QA (e.g. Gemini Flash)

Typical results on a German IDD-documentation task:

| Setup                                              | Cost / run | QA Score | Saving |
|----------------------------------------------------|-----------:|---------:|-------:|
| Single (Claude Sonnet only)                        |  ~$0.014   |  0.92    |   —    |
| Mixed (Claude Sonnet decompose + Gemini execute)   |  ~$0.003   |  0.88    |  **~78%** |

Annualized at 1k runs/month: **~$130/year saved per workflow.**

A ready-to-import demo workflow ships in [`examples/mixed-provider-cost-saver.json`](examples/mixed-provider-cost-saver.json) — runs both setups against the same goal and reports the delta in a Code node.

---

## Providers & default models

| Provider     | Default model                         | Best for                                  |
|--------------|---------------------------------------|-------------------------------------------|
| Anthropic    | `claude-sonnet-4-5`                   | Decomposer, complex reasoning             |
| OpenAI       | `gpt-4o`                              | General-purpose, structured output        |
| Google       | `gemini-2.0-flash`                    | Cheap, fast atom executor                 |
| Mistral (EU) | `mistral-large-latest`                | GDPR-sensitive workloads, EU residency    |
| OpenRouter   | `anthropic/claude-sonnet-4-5`         | One key for 100+ models, model A/B tests  |

Per-provider model dropdowns are pre-curated in the node UI.

---

## How it works

```
Goal
  │
  ▼
[Decomposer LLM]   AoT decomposition → AtomGraph (1–6 atoms, dependency-aware)
  │
  ▼
[Executor LLM]     Atoms run in parallel via Promise.all (where dependencies allow)
  │
  ▼
[Executor LLM]     QA-Agent scores 0–1 (retry on failure)
  │
  ▼
{ result, qa_score, success, atoms_used, cost }
```

In **single-provider mode** Decomposer = Executor.
In **mixed mode** they're independent — different provider, different model, different credential.

---

## Modes

| Mode               | Behavior                                                      |
|--------------------|---------------------------------------------------------------|
| **CHIP + AoT**     | Full pipeline: decompose → solve atoms → QA loop              |
| **AoT only**       | Decompose + solve, no QA (faster, less polished)              |
| **Webhook (Python)** | Forwards goal to a running [aot-harness Python server](https://github.com/ronnyschumann1983-boop/aot-harness). Use this when you want the full Vault/Obsidian pipeline. |

---

## Migration from v0.2.x

v0.3.0 is a **breaking change** because the node now requires a provider-specific credential.

After updating:

1. Open every workflow that uses **AoT Harness**.
2. Set **Provider** → `Anthropic` (matches the v0.2.x default behavior).
3. Attach the new **AoT Harness — Anthropic** credential. Re-enter your `ANTHROPIC_API_KEY`.
4. Pick a **Model** from the dropdown (default: `claude-sonnet-4-5`).
5. Save & test.

The legacy `aotHarnessApi` credential type is still registered so existing credential entries don't disappear from your n8n credentials list — but the new node doesn't read it. Delete it after migration if you like.

---

## Credentials

| Credential                          | Required env var      | Notes                               |
|-------------------------------------|-----------------------|-------------------------------------|
| AoT Harness — Anthropic             | `ANTHROPIC_API_KEY`   | Default provider                    |
| AoT Harness — OpenAI                | `OPENAI_API_KEY`      | Optional `OpenAI-Organization` header |
| AoT Harness — Google Gemini         | `GEMINI_API_KEY`      | Get one at aistudio.google.com      |
| AoT Harness — Mistral (EU)          | `MISTRAL_API_KEY`     | EU-hosted, GDPR-compliant           |
| AoT Harness — OpenRouter            | `OPENROUTER_API_KEY`  | Optional `HTTP-Referer` / `X-Title` |

You only need credentials for providers you actually use.

---

## Roadmap

- v0.3.1 — per-atom provider override (route specific atoms to specific models)
- v0.4   — Mistral self-hosted via Ollama, ReAct-style tool loops, prompt-cache visibility for non-Anthropic providers

---

## Based on

- **AoT Paper**: arXiv:2502.12018 (NeurIPS 2025) — MIT License
- **CHIP Architecture**: Ronny Schumann
- **Harness Concept**: Anthropic Engineering, Martin Fowler (2026)

---

## License

MIT
