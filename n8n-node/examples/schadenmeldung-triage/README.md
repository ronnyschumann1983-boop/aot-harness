# Schadenmeldungs-Triage — Versicherungsmakler-Demo

**Aufwand alt:** 20–30 Min Textarbeit pro Schaden.
**Aufwand neu:** 2 Min Review + Approve.
**LLM-Kosten:** ~$0.005 pro Schaden.

Ein produktiver n8n-Workflow, der die Stärken des `aot-harness` Nodes an einem
realen Makler-Use-Case zeigt: AoT-Decomposition, Mixed-Provider (Kosten-Hebel),
QA-Loop, HITL-Fallback.

---

## Was er macht

```
Kundenmail + Police-Daten (Form)
      │
      ▼
AoT Harness Node
  ├─ a1: Schaden klassifizieren (Sparte, Dringlichkeit)
  ├─ a2: Sofort-Maßnahmen für Kunden
  ├─ a3: Mail-Entwurf an Kunden (empathisch, konkret)
  └─ a4: Mail-Entwurf an Versicherer (förmlich, mit Policennummer)
      │
      ▼
QA-Agent (Score 0–1)
  ├─ ≥ 0.75 → 2 Gmail-Drafts warten auf deinen Klick
  └─ < 0.75 → HITL-Mail an Makler mit Review-Kontext
```

---

## Mixed-Provider = Cost-Hebel

| Rolle       | Modell              | Warum                                    |
|-------------|---------------------|------------------------------------------|
| Decomposer  | Claude Sonnet 4.6   | Versteht Versicherungsfachdeutsch        |
| Executor    | Gemini 2.0 Flash    | Schreibt die Drafts — ~30× günstiger     |
| QA          | Gemini 2.0 Flash    | Bewertet eigenes Output-JSON             |

**Ein Lauf:** ~$0.003–$0.008.
**50 Schäden/Monat:** < $1 LLM-Kosten.

---

## Setup (10 Min)

### 1. n8n-Node installieren
```bash
npm install -g n8n-nodes-aot-harness
```
Danach n8n neu starten.

### 2. Credentials in n8n anlegen
- **AoT Harness — Anthropic** → dein `ANTHROPIC_API_KEY`
- **AoT Harness — Google Gemini** → dein `GEMINI_API_KEY` (Google AI Studio)
- **Gmail OAuth2** → Google-OAuth für Draft-Erstellung
  (Setup: https://docs.n8n.io/integrations/builtin/credentials/google/oauth-single-service/)

### 3. Workflow importieren
- n8n → **Workflows** → **Import from File** → `workflow.json`
- Jedem der 3 Kreditkarten-Icons die passende Credential zuweisen
- **Makler-E-Mail-Adresse** in der "HITL Notify"-Node setzen
  (Default-Platzhalter: `makler@dein-buero.de`)
- Save & Activate

### 4. Demo-Run
- Rechtsklick auf **Form Trigger** → **Open Form URL**
- Formular mit den Daten aus `beispielmail.md` ausfüllen
- Submit — ca. 60s später hast du 2 Gmail-Drafts im Ordner "Entwürfe"

---

## Rechnung für Makler

| Position                      | Aufwand            | Kosten/Monat  |
|-------------------------------|--------------------|--------------:|
| 50 Schäden × 25 Min (manuell) | 20,8 h × 80 €/h   | **1.667 €**   |
| Neu: 50 × 2 Min Review        |  1,7 h × 80 €/h   |     133 €     |
| LLM-Kosten                    | 50 × $0.005       |     < 1 $     |
| **Ersparnis / Jahr**          |                    | **~18.400 €** |

---

## Bonus: Automatische Police-Lookup via Supabase

Wer eine strukturierte Kundendatenbank hat, kann Schritt 2 (Police-Daten
manuell einfügen) automatisieren:

1. Supabase-Projekt anlegen (Free Tier reicht)
2. Schema + Seed-Daten einspielen: `seed.sql` enthält 5 Demo-Policen
3. Vor der "Build Goal"-Node einen **HTTP Request** einfügen:
   - `GET https://YOUR-PROJECT.supabase.co/rest/v1/vault_patterns?path=eq./policen/{{ $json['Policennummer'] }}&select=content`
   - Header: `apikey: YOUR_SUPABASE_KEY`
4. Das "Police-Daten"-Feld im Formular entfernen — wird nun aus Supabase gezogen

Der `aot-harness` Python-Core bringt zusätzlich einen **SupabaseAdapter** mit,
der dieselbe Tabelle als Vault nutzt — inkl. Cache-Check und Ingest.
Siehe [Pluggable Vaults](../../../README.md#whats-new-in-v040--pluggable-vaults--human-in-the-loop).

---

## Dateien

| Datei             | Zweck                                                   |
|-------------------|---------------------------------------------------------|
| `workflow.json`   | Importierbarer n8n-Workflow                             |
| `beispielmail.md` | Test-Schadenmail (Wasserschaden in Küche)               |
| `seed.sql`        | 5 Demo-Policen für Supabase (Bonus: Auto-Lookup)        |
| `README.md`       | Diese Datei                                             |

---

## Warum das verkauft

**Schadenmeldungen sind:**
- Täglich (jeder Makler hat ≥ 1/Tag)
- Zeitkritisch (Kunde wartet, Versicherer will schnell)
- Reaktiv (unterbricht den Arbeitstag)
- Hoher Textaufwand (doppelte Kommunikation: Kunde + Versicherer)

**Das sind die vier Merkmale, die KI-Automatisierung am besten lösen kann.**
Kein "nice to have" — ein konkreter Engpass im Makler-Alltag, quantifizierbar
in Euro pro Jahr.
