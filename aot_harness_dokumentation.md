# aot-harness — Vollständige Dokumentation
## CHIP + Atom of Thoughts + Harness Architecture
**Version 0.2.1 | Ronny Schumann | April 2026**

---

# TEIL 1 — INSTALLATIONSANLEITUNG

## Voraussetzungen

| Komponente       | Mindestversion | Zweck                          |
|------------------|---------------|--------------------------------|
| Python           | 3.11+         | Laufzeitumgebung               |
| anthropic SDK    | 0.40.0+       | Claude API Zugriff             |
| Obsidian         | beliebig      | Vault (optional, Mock möglich) |
| n8n              | beliebig      | Webhook-Integration (optional) |
| mcp SDK          | 1.0.0+        | Claude Code Integration (opt.) |

---

## Schritt 1 — Repository klonen

```bash
git clone https://github.com/YOUR_USERNAME/aot-harness.git
cd aot-harness
```

## Schritt 2 — Abhängigkeiten installieren

```bash
# Basis-Installation (nur Claude API)
pip install anthropic>=0.40.0

# Mit MCP-Support (Claude Code Integration)
pip install anthropic mcp

# Empfohlen: virtuelle Umgebung
python -m venv venv
source venv/bin/activate        # Linux / Mac
venv\Scripts\activate           # Windows
pip install -r requirements.txt
```

## Schritt 3 — API Key konfigurieren

```bash
# Option A: Umgebungsvariable (empfohlen)
export ANTHROPIC_API_KEY="sk-ant-api03-..."

# Option B: In .env Datei (niemals committen!)
echo "ANTHROPIC_API_KEY=sk-ant-api03-..." > .env

# Option C: Direkt im Code (nur für Tests)
ClaudeAdapter(api_key="sk-ant-api03-...")
```

## Schritt 4 — Installation prüfen

```bash
# Demo ohne API-Key (Mock-Modus)
python -m aot_harness.examples.chip_idd_demo

# Erwartete Ausgabe:
# 🎯 CHIP-Orchestrator | Goal: ...
# 🔎 Vault-Check...
# 🗂️ AoT-Decomposition...
# ⚛️ [a1] → research: ...
# ✅ Final | Score: 0.91
```

## Schritt 5 — Obsidian Vault verbinden (optional)

```bash
# MCP-Server für Obsidian starten
# (Obsidian-MCP-Plugin vorher installieren)
python -m aot_harness.integrations.mcp_server

# Vault-Struktur anlegen (einmalig)
# /system/CLAUDE.md    ← deine CLAUDE.md
# /system/AGENTS.md    ← deine AGENTS.md
# /patterns/           ← wird automatisch befüllt
# /atoms/              ← wiederverwendbare Bausteine
# /pending/            ← Tasks mit Score < 0.75
```

## Schritt 6 — n8n Webhook starten (optional)

```bash
python -m aot_harness.integrations.n8n_webhook
# → Server läuft auf http://localhost:8765/run

# In n8n: HTTP Request Node
# Method: POST
# URL: http://localhost:8765/run
# Body: { "goal": "dein Task hier" }
```

---

# TEIL 2 — BETRIEBSANLEITUNG

## Grundlegende Nutzung

### Einfacher Orchestrator (ohne Vault)

```python
from aot_harness.core import Orchestrator
from aot_harness.integrations.claude_adapter import ClaudeAdapter
import os

orch = Orchestrator(
    llm_client  = ClaudeAdapter(api_key=os.environ["ANTHROPIC_API_KEY"]),
    session_id  = "mein-projekt",
    max_retries = 2,
    verbose     = True,
)

result = orch.run("Dein Task hier als natürlicher Satz")
print(result["result"])
```

### CHIP-Orchestrator (mit Vault, empfohlen)

```python
from aot_harness.core.chip_orchestrator import CHIPOrchestrator
from aot_harness.integrations.claude_adapter import ClaudeAdapter
from aot_harness.integrations.obsidian_adapter import ObsidianVault
import os

# Vault verbinden (Mock für Tests, MCP für Produktion)
vault = ObsidianVault(mock=True)                  # Test
# vault = ObsidianVault(mcp_client=mcp_client)    # Produktion

orch = CHIPOrchestrator(
    llm_client   = ClaudeAdapter(api_key=os.environ["ANTHROPIC_API_KEY"]),
    vault        = vault,
    session_id   = "mein-projekt",
    max_retries  = 2,
    max_qa_loops = 2,
    verbose      = True,
)

result = orch.run("Dein Task hier")

# Rückgabe-Objekt:
# result["result"]      → fertiger Output (Text)
# result["qa_score"]    → Qualitätsscore 0.0 - 1.0
# result["success"]     → True / False
# result["cache_hit"]   → True wenn Vault-Treffer
# result["atoms_used"]  → ["a1", "a2", "a3", ...]
# result["notes"]       → QA-Hinweise
```

## Eigene Tools registrieren

```python
from aot_harness.core.tool_executor import get_default_registry

reg = get_default_registry()

# Jede Funktion die einen String zurückgibt ist ein Tool
def mein_crm_tool(customer_id: str = "") -> str:
    # echte CRM-Abfrage hier
    return f"Kunde {customer_id}: Max Mustermann, 42J."

def mein_produkt_tool(kategorie: str = "") -> str:
    # echte DB-Abfrage hier
    return f"Produkte: Basis 180€, Premium 340€"

reg.register("crm_abfrage",    mein_crm_tool,    {"name": "crm_abfrage"})
reg.register("produkt_suche",  mein_produkt_tool, {"name": "produkt_suche"})

# Im Orchestrator übergeben
orch = CHIPOrchestrator(llm_client=..., tools=reg, vault=vault)
```

## Vault mit Start-Patterns befüllen

```python
vault = ObsidianVault(mock=True)  # oder echter MCP-Client

vault.ingest("/patterns/IDD_Beratung.md", """---
task_typ: IDD Beratungsdokumentation
qa_score_avg: 0.90
durchlaeufe: 1
---
## Atom-Struktur
- Atom 1: Kundendaten abrufen (Research)
- Atom 2: Produkte recherchieren (Research)
- Atom 3: Risikoklasse bestimmen (Analysis)
- Atom 4: IDD-Dokument erstellen (Writing)
## Besonderheiten
Immer § 61 VVG referenzieren.
""")
```

## Konfigurationsparameter

| Parameter      | Default         | Beschreibung                              |
|----------------|-----------------|-------------------------------------------|
| max_retries    | 3               | Max. Versuche pro Atom bei Sensor-Fehler  |
| max_qa_loops   | 2               | Max. QA-Retry-Loops                       |
| session_id     | "default"       | ID für Memory-Persistenz                  |
| persist_path   | None            | Pfad für JSON-Memory (z.B. ./memory.json) |
| verbose        | True            | Konsolenausgabe an/aus                    |

## QA-Score verstehen

| Score      | Bedeutung                          | Aktion des Systems               |
|------------|------------------------------------|----------------------------------|
| 0.90 - 1.0 | Exzellent                         | Direkt in Vault gespeichert      |
| 0.75 - 0.89| Gut                               | In Vault gespeichert             |
| 0.50 - 0.74| Verbesserungswürdig               | Retry + in /pending/ abgelegt    |
| 0.00 - 0.49| Fehlgeschlagen                    | Abort, Error-Logging             |

## Fehlerbehandlung

```python
result = orch.run("mein task")

if not result["success"]:
    print(f"Fehler! QA-Score: {result['qa_score']}")
    print(f"Hinweise: {result['notes']}")
    # Task mit mehr Kontext nochmal versuchen
    result2 = orch.run("mein task — bitte auf X achten")
```

---

# TEIL 3 — ANWENDUNGSBEISPIELE

---

## Beispiel 1: IDD-Dokumentation (Versicherungsmakler)

**Anwendungsfall:** Automatische Erstellung gesetzeskonformer
Beratungsdokumentation nach § 61 VVG / IDD-Richtlinie

```python
import os
from aot_harness.core.chip_orchestrator import CHIPOrchestrator
from aot_harness.integrations.claude_adapter import ClaudeAdapter
from aot_harness.integrations.obsidian_adapter import ObsidianVault
from aot_harness.core.tool_executor import get_default_registry

# CRM + Produktdatenbank einbinden
reg = get_default_registry()

def kundendaten_abrufen(customer_id: str = "") -> str:
    # Hier: echte CRM-API
    return f"Kunde {customer_id}: Sabine Weber, 38J., Berlin, Risiko niedrig"

def produktkatalog(kategorie: str = "haftpflicht") -> str:
    return "Basis 180€ (5 Mio.), Premium 340€ (15 Mio., Miete inkl.)"

reg.register("kundendaten", kundendaten_abrufen)
reg.register("produktkatalog", produktkatalog)

vault = ObsidianVault(mock=True)
orch = CHIPOrchestrator(
    llm_client=ClaudeAdapter(api_key=os.environ["ANTHROPIC_API_KEY"]),
    tools=reg, vault=vault,
    session_id="idd-makler-001"
)

# Aufruf: ein natürlicher Satz genügt
result = orch.run(
    "Erstelle vollständige IDD-Beratungsdokumentation für "
    "Kundin Weber #KD-0815, Interesse an Privathaftpflicht."
)

print(result["result"])
# → Fertige IDD-Dokumentation mit Kundendaten, Produktempfehlung,
#   Risikoklasse, § 61 VVG Referenz, QA-Score 0.91
```

**Was das System automatisch macht:**
- a1: Kundendaten per CRM-Tool abrufen
- a2: Passende Produkte recherchieren
- a3: Risikoklasse analysieren
- a4: IDD-konformes Dokument schreiben
- QA: Vollständigkeit + rechtliche Grundlage prüfen
- Bibliothekarin: Pattern für nächste IDD-Docs speichern

---

## Beispiel 2: LinkedIn Content-Erstellung

**Anwendungsfall:** Automatische Erstellung von
LinkedIn-Posts zu KI/Automation-Themen

```python
vault = ObsidianVault(mock=True)

# Ton-Beispiele vorab laden
vault.ingest("/atoms/linkedin_ton.md", """
Stil: direkt, professionell, keine Buzzwords
Struktur: Hook (1 Satz) → Problem → Lösung → CTA
Max. Zeichen: 1200
Zielgruppe: Entscheider in KMU, nicht technisch
""")

orch = CHIPOrchestrator(
    llm_client=ClaudeAdapter(api_key=os.environ["ANTHROPIC_API_KEY"]),
    vault=vault,
    session_id="linkedin-content"
)

result = orch.run(
    "Schreibe einen LinkedIn-Post über den ROI von "
    "KI-Automatisierung für Versicherungsmakler. "
    "Konkrete Zahlen, kein Fachjargon, CTA am Ende."
)

print(result["result"])
# → Fertiger LinkedIn-Post, QA-geprüft auf Ton, Format, Vollständigkeit
# → Nächstes Mal: Vault-Hit beschleunigt Erstellung
```

**Was das System automatisch macht:**
- a1: Vault nach ähnlichen Posts durchsuchen
- a2: ROI-Daten für Versicherungsbranche recherchieren
- a3: Zielgruppen-Analyse (KMU-Entscheider)
- a4: Post im definierten Stil schreiben
- QA: Ton, Format, Zeichenanzahl prüfen

---

## Beispiel 3: Lead-Scoring und Akquise-Automatisierung

**Anwendungsfall:** Automatisches Scoring eingehender
B2B-Leads + personalisierte Erst-Email

```python
reg = get_default_registry()

def website_analyse(url: str = "") -> str:
    # Hier: Scraper oder SerpAPI
    return f"Firma auf {url}: 45 Mitarbeiter, Versicherungsbranche, kein CRM sichtbar"

def email_validator(email: str = "") -> str:
    return f"{email}: valid, MX-Record vorhanden"

def crm_lookup(firma: str = "") -> str:
    return f"{firma}: noch kein Kontakt im CRM"

reg.register("website_analyse", website_analyse)
reg.register("email_validator", email_validator)
reg.register("crm_lookup", crm_lookup)

vault = ObsidianVault(mock=True)
orch = CHIPOrchestrator(
    llm_client=ClaudeAdapter(api_key=os.environ["ANTHROPIC_API_KEY"]),
    tools=reg, vault=vault,
    session_id="lead-scoring"
)

result = orch.run(
    "Analysiere Lead: Makler GmbH, kontakt@makler-gmbh.de, "
    "www.makler-gmbh.de — Lead-Score berechnen und "
    "personalisierte Erst-Akquise-Email schreiben."
)

print(result["result"])
# → Lead-Score (0-100) + Begründung + fertige Email
# score["qa_score"]  → Qualität der Email geprüft
```

**Was das System automatisch macht:**
- a1: Website analysieren (Firmengröße, Branche, Tech-Stack)
- a2: CRM prüfen (Duplikat-Check)
- a3: Lead-Score berechnen (Branche, Größe, Bedarf)
- a4: Personalisierte Email schreiben (mit Vault-Ton-Beispielen)
- QA: Email auf Ton, Personalisierung, CTA prüfen
- Bibliothekarin: Erfolgreiche Lead-Patterns speichern

---

## Beispiel 4: WhatsApp-Nachfass-Automatisierung (n8n)

**Anwendungsfall:** n8n Workflow triggert das System
automatisch wenn ein Kunde antwortet

```
n8n Workflow:
  WhatsApp-Nachricht empfangen
      → HTTP Request POST http://localhost:8765/run
          Body: {
            "goal": "Kunde Müller fragt nach Kündigung seiner KFZ-Police. 
                     Erstelle passende Antwort und prüfe Kündigungsfristen."
          }
      → Response verarbeiten
      → WhatsApp-Antwort senden
```

```python
# Server starten
from aot_harness.integrations.n8n_webhook import init, serve
from aot_harness.core.chip_orchestrator import CHIPOrchestrator

orch = CHIPOrchestrator(
    llm_client=ClaudeAdapter(api_key=os.environ["ANTHROPIC_API_KEY"]),
    vault=ObsidianVault(mcp_client=mcp_client),
)

init(orch)
serve(host="0.0.0.0", port=8765)
# → n8n kann jetzt POST /run aufrufen
```

---

# ANHANG

## Dateistruktur

```
aot-harness/
├── aot_harness/
│   ├── core/
│   │   ├── orchestrator.py       ← Einfacher Orchestrator
│   │   ├── chip_orchestrator.py  ← CHIP-Orchestrator (empfohlen)
│   │   ├── aot_reasoner.py       ← AoT Decomposition
│   │   ├── agents.py             ← Research/Writing/Analysis/QA/Biblio
│   │   ├── memory.py             ← Session-Memory
│   │   ├── sensors.py            ← Feedback-Detektion
│   │   ├── verifier.py           ← Retry-Entscheidung
│   │   └── tool_executor.py      ← Tool-Registry
│   ├── integrations/
│   │   ├── claude_adapter.py     ← Anthropic SDK Wrapper
│   │   ├── obsidian_adapter.py   ← Obsidian MCP Tools
│   │   ├── n8n_webhook.py        ← HTTP Webhook für n8n
│   │   └── mcp_server.py         ← MCP für Claude Code
│   └── examples/
│       ├── insurance_idd.py      ← IDD-Demo (einfach)
│       └── chip_idd_demo.py      ← IDD-Demo (CHIP, vollständig)
├── AGENTS.md                     ← Harness-Konfiguration
├── README.md                     ← GitHub Startseite
└── requirements.txt
```

## Häufige Fehler

| Fehler | Ursache | Lösung |
|--------|---------|--------|
| `anthropic.AuthenticationError` | API Key fehlt/falsch | `ANTHROPIC_API_KEY` prüfen |
| `Tool 'xyz' not registered` | Tool nicht registriert | `reg.register("xyz", fn)` |
| QA-Score immer < 0.75 | Prompt zu vage | Goal-Satz präziser formulieren |
| Vault-Check schlägt fehl | MCP nicht gestartet | Mock-Modus testen: `mock=True` |
| Atom FAILED nach max Retries | Tool gibt Fehler zurück | Tool-Funktion debuggen |

## Support & Weiterentwicklung

- GitHub Issues: https://github.com/ronnyschumann1983-boop/aot-harness/issues
- Basiert auf: arXiv:2502.12018 (AoT, MIT License)
- CHIP-Architektur: Ronny Schumann (2026)
