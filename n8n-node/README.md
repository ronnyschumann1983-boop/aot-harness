# n8n-nodes-aot-harness

> **CHIP + Atom of Thoughts (AoT) for n8n** — multi-provider agent harness with built-in cost tracking, plus a **Process Analyst Worker** for operational case triage.

[![npm](https://img.shields.io/npm/v/n8n-nodes-aot-harness)](https://www.npmjs.com/package/n8n-nodes-aot-harness)
[![downloads](https://img.shields.io/npm/dt/n8n-nodes-aot-harness)](https://www.npmjs.com/package/n8n-nodes-aot-harness)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A community node that brings the **AoT-Harness** (atomic decomposition + QA loop) into n8n.
One node, one goal — the harness decomposes the task into atoms, runs them in parallel, QA-scores the result, and returns the polished output **plus a per-call cost breakdown**.

---

## What's new in v0.5.0 — Process Analyst Worker

> The **Process Analyst Worker** turns unstructured operational input into structured next-step decisions for n8n workflows: classification, missing information, urgency, automation potential, risk flags, human review and draft response.
>
> *Der Process Analyst Worker übersetzt unstrukturierte operative Eingaben in strukturierte nächste Schritte für n8n-Workflows: Klassifikation, fehlende Informationen, Dringlichkeit, Automatisierungspotenzial, Risiken, Human Review und Antwortentwurf.*

- 🆕 **New mode** `Process Analyst` — single-call structured triage of one operational case (email, document, support ticket, workshop request, internal note)
- 🧠 **4 process profiles** — `generic`, `email_support`, `document_intake`, `automotive_service`
- 🔒 **Read-only by design** — produces analysis + draft response, never sends. Human-in-the-Loop is part of the contract.
- ⚙️ **Deterministic HITL gate** — `human_review_required` is forced true whenever confidence falls below the threshold, missing facts exist, risk flags appear, or input is too short to be reliable
- 📦 **Structured JSON output** — drop directly into Switch / Set / Gmail / Supabase nodes downstream

See the [Process Analyst Worker](#-process-analyst-worker) section below.

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
2. Pick a **Provider** (e.g. Anthropic) and a **Model** (e.g. `claude-sonnet-4-6`).
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
  "model_used":    "claude-sonnet-4-6",
  "cost": {
    "total_usd":         0.0143,
    "total_calls":       6,
    "prompt_tokens":     2480,
    "completion_tokens": 1120,
    "by_provider":       { "anthropic": { "cost_usd": 0.0143, "calls": 6, ... } },
    "by_model":          { "claude-sonnet-4-6": { "cost_usd": 0.0143, ... } }
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

## 🛡️ Production demo: Insurance-broker claim triage

A full Versicherungsmakler-use-case lives in [`examples/schadenmeldung-triage/`](examples/schadenmeldung-triage/):

- **Goal:** incoming claim email → 2 ready-to-send Gmail drafts (to customer + to insurer) in ~60s
- **Features shown:** AoT decomposition (4 atoms), Mixed-Provider cost saving, QA gate with HITL fallback (Makler gets review email if `qa_score < 0.75`)
- **Economics:** ~20.000€/year savings for a broker handling 50 claims/month — full math in the folder's `README.md`
- **Includes:** importable workflow, test mail, Supabase seed SQL for automatic policy lookup

This is the workflow to show an interested broker.

---

## Providers & default models

| Provider     | Default model                         | Best for                                  |
|--------------|---------------------------------------|-------------------------------------------|
| Anthropic    | `claude-sonnet-4-6`                   | Decomposer, complex reasoning             |
| OpenAI       | `gpt-4o`                              | General-purpose, structured output        |
| Google       | `gemini-2.5-flash`                    | Cheap, fast atom executor                 |
| Mistral (EU) | `mistral-large-latest`                | GDPR-sensitive workloads, EU residency    |
| OpenRouter   | `anthropic/claude-sonnet-4-6`         | One key for 100+ models, model A/B tests  |

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

| Mode                  | Behavior                                                      |
|-----------------------|---------------------------------------------------------------|
| **CHIP + AoT**        | Full pipeline: decompose → solve atoms → QA loop              |
| **AoT only**          | Decompose + solve, no QA (faster, less polished)              |
| **Webhook (Python)**  | Forwards goal to a running [aot-harness Python server](https://github.com/ronnyschumann1983-boop/aot-harness). Use this when you want the full Vault/Obsidian pipeline. |
| **Process Analyst**   | Single-call triage of one operational case → structured JSON with classification, entities, urgency, missing info, risk flags, automation potential, draft response, and a Human-Review flag. |

---

## 🛠️ Process Analyst Worker

A focused mode for **operational case triage**. Pick `Mode → Process Analyst`, paste one inbound case (email, support ticket, document excerpt, workshop request, internal note), and the worker returns a single structured JSON payload that the rest of the n8n workflow can branch on.

### When to use it

- Inbound email needs to be classified, scored, and possibly answered (or escalated)
- A scanned document arrives and you need to know: which type, what's missing, what to do next
- A workshop / car-dealership receives a service request and you want a structured intake before a human picks it up
- Any process where an unstructured input must become a deterministic next step

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `Operational Input`        | string (multi-line, required) | — | The case to analyze. |
| `Process Profile`          | options | `generic` | Biases what the analyst pays attention to: `generic` / `email_support` / `document_intake` / `automotive_service`. |
| `Output Language`          | options | `de` | Language for `summary`, `next_best_action`, `draft_response`, `missing_information`, `risk_flags`. Field names + enum values stay in English. |
| `Human Review Threshold`   | number 0–1 | `0.7` | Below this confidence the case is flagged for review. Missing info or risk flags also trigger review independent of confidence. |
| `Include Draft Response`   | boolean | `true` | If false, `draft_response` is `null`. The worker never sends — drafts are read-only. |
| `Strict JSON`              | boolean | `true` | On parser failure, returns a safe empty analysis with `human_review_required = true` instead of throwing. |

The active **Provider + Model** at the top of the node is reused as the analyst LLM (no separate decomposer needed — this is a single call).

### Example: automotive service request

**Operational Input:**

```
Sehr geehrte Damen und Herren,

mein Golf macht beim Bremsen seit ein paar Tagen ein schleifendes Geräusch.
Können Sie mir nächste Woche einen Termin anbieten?

Viele Grüße
Max Mustermann
```

**Profile:** `automotive_service` · **Language:** `de` · **Threshold:** `0.7`

**Output:**

```jsonc
{
  "mode":    "process_analyst",
  "profile": "automotive_service",
  "analysis": {
    "process_type":  "terminanfrage",
    "business_area": "service",
    "summary":       "Kunde fragt nach einem Werkstatttermin für nächste Woche wegen Bremsgeräuschen am VW Golf.",
    "detected_entities": {
      "customer_name":   "Max Mustermann",
      "company":         null,
      "email":           null,
      "phone":           null,
      "vehicle":         "VW Golf",
      "license_plate":   null,
      "requested_date":  "nächste Woche",
      "topic":           "Bremsgeräusch / Werkstatttermin"
    },
    "urgency":     "medium",
    "confidence":  0.82,
    "missing_information": [
      "Telefonnummer",
      "Kennzeichen",
      "konkreter Wunschtermin"
    ],
    "next_best_action":      "Rückfrage an Kunden mit Bitte um Kennzeichen, Telefonnummer und zwei mögliche Zeitfenster für nächste Woche vorbereiten.",
    "automation_potential":  "high",
    "human_review_required": true,
    "risk_flags": [
      "Terminwunsch unklar",
      "Fahrzeugdaten unvollständig"
    ],
    "recommended_workflow_tags": [
      "service_intake",
      "appointment_request",
      "human_review"
    ],
    "draft_response": "Hallo Herr Mustermann, vielen Dank für Ihre Anfrage. Damit wir Ihnen einen passenden Werkstatttermin anbieten können, senden Sie uns bitte noch Ihr Kennzeichen, eine Telefonnummer und zwei mögliche Zeitfenster für nächste Woche.",
    "_profile":         "automotive_service",
    "_trigger_reasons": ["3 missing fact(s)", "2 risk flag(s)"]
  },
  "provider_used": "anthropic",
  "model_used":    "claude-sonnet-4-6",
  "cost": { "total_usd": 0.0021, "total_calls": 1, "prompt_tokens": 480, "completion_tokens": 220 }
}
```

The downstream Switch node branches on `analysis.human_review_required` → either send the draft via Gmail or route to a Makler/Service-Annahme inbox.

### Logic guarantees

- **Read-only.** No mailing, no DB writes, no decisions on legal / monetary topics.
- **`human_review_required` is deterministic** — set in code (not just by the model) whenever any of these is true:
  - `confidence < humanReviewThreshold`
  - `missing_information.length > 0`
  - `risk_flags.length > 0`
  - input is shorter than 20 characters
- **`_trigger_reasons`** lists exactly which of the above fired — useful for explainability + debugging.
- **`recommended_workflow_tags` always contains `human_review`** when the gate fires, so a Switch node can match on a single tag.

### Profile cheatsheet

| Profile | Pays attention to |
|---|---|
| `generic`             | Process type, business area, missing info, next step. Branch-neutral. |
| `email_support`       | Customer concern, urgency, missing info, draft reply, escalation, support category. |
| `document_intake`     | Document type, mandatory fields, missing fields, plausibility, extraction hints. |
| `automotive_service`  | Vehicle, license plate, requested date, service topic, callback need, missing vehicle info, next workshop step. |

---

---

## Migration from v0.2.x

v0.3.0 is a **breaking change** because the node now requires a provider-specific credential.

After updating:

1. Open every workflow that uses **AoT Harness**.
2. Set **Provider** → `Anthropic` (matches the v0.2.x default behavior).
3. Attach the new **AoT Harness — Anthropic** credential. Re-enter your `ANTHROPIC_API_KEY`.
4. Pick a **Model** from the dropdown (default: `claude-sonnet-4-6`).
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

- v0.5.1 — Process Analyst: per-profile entity-schema overrides, optional batch-mode for multi-case analysis
- v0.6   — additional profiles (legal_intake, finance_intake, hr_intake), webhook-mode parity for the analyst worker
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
