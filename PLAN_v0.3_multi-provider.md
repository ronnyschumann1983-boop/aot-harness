# Plan: aot-harness v0.3.0 — Multi-Provider Support

**Erstellt:** 2026-04-16
**Ziel-Release:** v0.3.0
**Status:** Planning

---

## Goal

Den AoT-Harness von Anthropic-only auf 5 Provider erweitern, um Adoption zu vergrößern und ein DSGVO-Sales-Argument für die deutsche KMU-Zielgruppe zu schaffen.

**Provider:**
1. **Anthropic** (mit Prompt-Caching, bestehend)
2. **OpenAI** (GPT-4o, GPT-4o-mini, o1)
3. **Google** (Gemini 2.0 Flash, Gemini 1.5 Pro)
4. **Mistral** (API-hosted via la Plateforme — Mistral Large, Small, Codestral)
5. **OpenRouter** (Meta-Provider: 100+ Modelle inkl. DeepSeek, Llama, Qwen via eine Credential)

---

## Strategische Begründung

- **Adoption-Hebel:** 600 Downloads nur mit Anthropic. Multi-Provider öffnet den Node für alle n8n-User mit existierenden Credentials (3-4× Downloads erwartet).
- **DSGVO-Sales-Argument:** Mistral = europäisches Hosting → harter Verkaufs-Hebel für Steuerberater/Versicherungsmakler-Zielgruppe.
- **Cost-Optimization als Killer-Feature:** Per-Atom Provider-Override ermöglicht Mixed-Provider Workflows (Sonnet für Decomposition, Haiku/Gemini Flash/Mistral Small für Atom-Execution → 70-80% Kosten-Ersparnis bei gleicher Qualität).
- **Fundament für ReAct (v0.4.0):** Provider-Abstraction macht spätere Tool-Use-Integration sauberer.

---

## Entscheidungen (festgelegt)

| # | Entscheidung | Wahl | Begründung |
|---|---|---|---|
| 1 | Caching-Strategie | Anthropic-only Caching, transparent abschalten bei anderen Providern | Komplexität niedrig halten; provider-spezifisches Caching später |
| 2 | Mistral-Hosting | Nur API-hosted (la Plateforme) | Self-hosted via Ollama als v0.4+ Feature |
| 3 | Abstraction-Layer | LiteLLM | Industriestandard, alle 5 Provider out-of-the-box, normalisiert Token-Counting & Errors |

---

## Phase 1 — Python Core (aot_harness/)

### 1.1 Provider-Abstraction

- Neue Datei: `aot_harness/providers.py`
- LiteLLM als Dependency: `litellm>=1.50.0` in `requirements.txt`
- Provider-Enum: `Provider = Literal["anthropic", "openai", "google", "mistral", "openrouter"]`
- Unified Call: `llm_call(provider, model, messages, **kwargs) -> Response`
- Token-Counting normalisiert via `litellm.token_counter()`

### 1.2 Atom-Schema Erweiterung

```python
class Atom:
    provider: Provider | None = None        # None → orchestrator default
    model: str | None = None                # None → provider default
    # ... existing fields
```

### 1.3 Orchestrator-Defaults

- `CHIPOrchestrator(default_provider="anthropic", default_model="claude-sonnet-4-6", decomposer_provider=None, decomposer_model=None)`
- Wenn `decomposer_provider` gesetzt → Decomposition-Phase nutzt diesen Provider, Atoms nutzen `default_provider`
- Per-Atom Override hat höchste Priorität

### 1.4 Caching-Layer Update

- `aot_harness/cache.py`: Prompt-Cache nur aktivieren wenn `provider == "anthropic"`
- Bei anderen Providern: existing deterministic file-cache bleibt aktiv (kein API-side caching)

### 1.5 Error-Handling

- Unified Exception: `ProviderError(provider, original_exception, retry_able)`
- LiteLLM mappt provider-specific Errors → wir mappen auf unsere Sensor-Verifier-Layer
- Existing granular retry funktioniert weiter

### 1.6 Tests

- `tests/test_providers.py`: Mock-Calls für alle 5 Provider
- `tests/test_mixed_provider.py`: Decomposer=Anthropic + Atoms=Google
- Smoke-Tests gegen echte APIs (optional, nur mit ENV-Vars)

---

## Phase 2 — n8n Node (n8n-node/)

### 2.1 Credentials-Picker

- Neue UI-Property `provider`: Dropdown mit 5 Optionen
- Conditional Credential-Field je nach Provider:
  - `anthropic` → `anthropicApi` (existing n8n credential type)
  - `openai` → `openAiApi`
  - `google` → `googlePalmApi` oder `googleGeminiApi`
  - `mistral` → `mistralCloudApi`
  - `openrouter` → custom `openRouterApi` (eigener Credential-Type, da n8n keinen hat)

### 2.2 Custom OpenRouter Credential-Type

- Neue Datei: `n8n-node/credentials/OpenRouterApi.credentials.ts`
- Felder: `apiKey` (string, password)
- Test-Endpoint: GET `https://openrouter.ai/api/v1/models` mit Auth-Header

### 2.3 Workflow-Level Defaults

- Top-Level Properties am CHIP-Node: `defaultProvider`, `defaultModel`
- Optional: `decomposerProvider`, `decomposerModel` (für Mixed-Mode)

### 2.4 Per-Atom Override

- Atom-Schema im UI bekommt optional `provider` + `model` Field
- Wenn gesetzt → Override; sonst Workflow-Default

### 2.5 Validation

- Bei Node-Execution: prüfe ob Credential für gewählten Provider vorhanden ist
- Klare Error-Message bei fehlender Credential

---

## Phase 3 — Mixed-Provider Killer-Feature

### 3.1 Demo-Workflow

- `examples/mixed-provider-cost-saver.json`
- Decomposer: `anthropic/claude-sonnet-4-6` (Qualität)
- Atoms: `google/gemini-2.0-flash` (Geschwindigkeit + Kosten)
- README-Vergleich: Single-Provider Cost vs Mixed Cost

### 3.2 Cost-Tracking

- Pro Atom: Track tokens × provider-rate
- Orchestrator-Output enthält `cost_breakdown: {provider: usd_amount}`
- Logs: `[atom_3] gemini-2.0-flash: 0.0012 USD`

---

## Phase 4 — Release 0.3.0

### 4.1 Documentation

- README.md Top-Section: "Multi-Provider Support" mit Provider-Tabelle
- Mistral besonders highlighten:
  > **🇪🇺 Built for European Compliance** — Mistral hosting in EU data centers, GDPR-compliant by default.
- README_final.md: Mixed-Provider Beispiel
- AGENTS.md: Update Provider-Referenzen

### 4.2 Changelog

- `CHANGELOG.md` neu anlegen wenn nicht vorhanden
- v0.3.0 Eintrag: 5 Provider, Mixed-Mode, Cost-Tracking, Breaking Changes (falls API verändert)

### 4.3 Versioning

- `setup.py`: `version="0.3.0"`
- `n8n-node/package.json`: `"version": "0.3.0"`
- TypeScript Build: `npm run build` im n8n-node Ordner
- npm publish: `npm publish` (n8n-node)
- PyPI publish (optional, wenn Python-Package public): `python setup.py sdist bdist_wheel && twine upload dist/*`

### 4.4 GitHub Release

- Tag `v0.3.0`
- Release Notes mit Highlights, Migration-Guide (falls Breaking)
- Demo-GIF oder Screenshot Mixed-Provider-Workflow

---

## Phase-Reihenfolge & Aufwand-Schätzung

| Phase | Aufwand | Reihenfolge |
|---|---|---|
| 1.1 Provider-Abstraction | 0,5 Tag | Zuerst |
| 1.2-1.5 Atom-Schema, Orchestrator, Cache, Errors | 1 Tag | Sequenziell |
| 1.6 Tests | 0,5 Tag | Mit Phase 1 |
| 2.1-2.5 n8n Node | 1,5 Tage | Nach Phase 1 |
| 3.1-3.2 Mixed-Provider + Cost-Tracking | 0,5 Tag | Nach Phase 2 |
| 4.1-4.4 Release | 0,5 Tag | Zuletzt |
| **Gesamt** | **~4,5 Tage** | |

---

## Risiken (akzeptiert)

1. **Token-Counting-Drift:** LiteLLM normalisiert, aber kleine Abweichungen pro Provider möglich → akzeptiert, Cost-Schätzungen sind ±5% genau, das reicht.
2. **OpenRouter-Latenz:** OpenRouter ist Meta-Layer, +50-200ms vs direct API → akzeptiert, User wählt bewusst.
3. **Provider-spezifische Features verloren:** Z.B. Anthropic Tool-Use, OpenAI Structured Outputs → erst mit ReAct (v0.4) relevant, jetzt nicht.

---

## Out of Scope (für v0.3.0)

- Mistral Self-Hosting (Ollama) → v0.4+
- ReAct Execution-Mode → v0.4
- BoT (Buffer of Thoughts) → v0.5
- Chain of Agents → v0.6
- Provider-spezifisches Caching (OpenAI/Gemini) → v0.5+
