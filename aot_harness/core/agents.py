"""
aot_harness/core/agents.py
CHIP Spezialisierte Subagenten: Research, Writing, Analysis, QA, Bibliothekarin
Basiert auf: AGENTS.md / CHIP-Agent-Architektur
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import json, threading, datetime


# ── Basis-Datenstrukturen ─────────────────────────────────────────────────────

@dataclass
class AgentInput:
    atom_aufgabe: str
    kontext:      dict = field(default_factory=dict)
    output_format: str = "json"

@dataclass
class AgentOutput:
    agent:      str
    result:     dict
    confidence: float = 1.0
    error:      str | None = None


# ── Spezialist: Research ──────────────────────────────────────────────────────

class ResearchAgent:
    PROMPT = """Du bist ein präziser Research-Spezialist.
Du bekommst NUR dein eigenes Atom — keinen anderen Kontext.

Atom-Aufgabe: {atom_aufgabe}
Kontext: {kontext}

Recherchiere gründlich. Wenn du unsicher bist, setze confidence niedrig.
Erfinde NIEMALS Fakten.

Antworte NUR mit gültigem JSON:
{{
  "findings": ["...", "..."],
  "sources": ["..."],
  "confidence": 0.0-1.0,
  "gaps": ["Was noch fehlt, falls relevant"]
}}"""

    def __init__(self, llm_client, vault=None):
        self.llm   = llm_client
        self.vault = vault

    def run(self, inp: AgentInput) -> AgentOutput:
        # Vault-Check für ähnliche Recherchen
        vault_context = ""
        if self.vault:
            hits = self.vault.search(inp.atom_aufgabe)
            if hits:
                vault_context = f"\nVault-Treffer: {json.dumps(hits[:2], ensure_ascii=False)}"

        prompt = self.PROMPT.format(
            atom_aufgabe=inp.atom_aufgabe,
            kontext=json.dumps(inp.kontext, ensure_ascii=False) + vault_context
        )
        raw = self.llm.complete(prompt)
        try:
            result = json.loads(raw)
        except Exception:
            result = {"findings": [raw], "sources": [], "confidence": 0.5, "gaps": []}
        return AgentOutput(agent="research", result=result,
                           confidence=result.get("confidence", 0.5))


# ── Spezialist: Writing ───────────────────────────────────────────────────────

class WritingAgent:
    PROMPT = """Du bist ein präziser Writing-Spezialist.
Du bekommst NUR dein eigenes Atom und das Input-Material.

Atom-Aufgabe: {atom_aufgabe}
Input-Material: {input_material}
Ton: {ton}
Format: {format}
Max. Zeichen: {max_zeichen}

Schreibe NUR auf Basis des Input-Materials. Keine eigenen Fakten hinzufügen.

Antworte NUR mit gültigem JSON:
{{
  "text": "...",
  "zeichen": 0,
  "ton_einhalten": true,
  "abweichungen": ""
}}"""

    def __init__(self, llm_client, vault=None):
        self.llm   = llm_client
        self.vault = vault

    def run(self, inp: AgentInput, input_material: str = "",
            ton: str = "professionell", format: str = "text",
            max_zeichen: int = 2000) -> AgentOutput:
        prompt = self.PROMPT.format(
            atom_aufgabe=inp.atom_aufgabe,
            input_material=input_material,
            ton=ton, format=format, max_zeichen=max_zeichen
        )
        raw = self.llm.complete(prompt)
        try:
            result = json.loads(raw)
        except Exception:
            result = {"text": raw, "zeichen": len(raw), "ton_einhalten": True, "abweichungen": ""}
        return AgentOutput(agent="writing", result=result, confidence=0.8)


# ── Spezialist: Analysis ──────────────────────────────────────────────────────

class AnalysisAgent:
    PROMPT = """Du bist ein präziser Analysis-Spezialist.
Du bekommst NUR dein eigenes Atom.

Atom-Aufgabe: {atom_aufgabe}
Daten: {daten}
Output-Format: {output_format}

Antworte NUR mit gültigem JSON:
{{
  "analyse": "...",
  "score": null,
  "empfehlung": "...",
  "konfidenz": 0.0-1.0
}}"""

    def __init__(self, llm_client, vault=None):
        self.llm   = llm_client
        self.vault = vault

    def run(self, inp: AgentInput, daten: str = "", output_format: str = "Bewertung") -> AgentOutput:
        prompt = self.PROMPT.format(
            atom_aufgabe=inp.atom_aufgabe,
            daten=daten, output_format=output_format
        )
        raw = self.llm.complete(prompt)
        try:
            result = json.loads(raw)
        except Exception:
            result = {"analyse": raw, "score": None, "empfehlung": "", "konfidenz": 0.5}
        return AgentOutput(agent="analysis", result=result,
                           confidence=result.get("konfidenz", 0.5))


# ── QA-Agent ──────────────────────────────────────────────────────────────────

@dataclass
class QAResult:
    final_output:  str
    qa_score:      float
    bestanden:     bool
    anmerkungen:   list[str]
    zurueck_an:    str | None = None   # "writing" | "research" | "analysis" | None


class QAAgent:
    PROMPT = """Du bist ein strenger QA-Agent.
Prüfe ob der Output den Original-Task vollständig erfüllt.

Original-Task: {original_task}

Spezialisten-Outputs:
{spezialisten_outputs}

Prüfe:
1. Vollständigkeit — Wurde der Task vollständig erfüllt?
2. Faktentreue — Stimmt Writing mit Research überein?
3. Ton — Passt der Text zur gewünschten Zielgruppe?
4. Format — Werden alle Format-Vorgaben eingehalten?

Antworte NUR mit gültigem JSON:
{{
  "final_output": "Fertiger, geprüfter Text oder Ergebnis",
  "qa_score": 0.0-1.0,
  "bestanden": true/false,
  "anmerkungen": ["...", "..."],
  "zurueck_an": null
}}

Regel: qa_score < 0.75 → bestanden=false, zurueck_an = der schlechteste Agent
Füge NIEMALS eigene Fakten hinzu. Schreibe NICHTS in den Vault."""

    def __init__(self, llm_client):
        self.llm = llm_client

    def run(self, original_task: str, outputs: dict[str, AgentOutput]) -> QAResult:
        outputs_dict = {k: v.result for k, v in outputs.items()}
        prompt = self.PROMPT.format(
            original_task=original_task,
            spezialisten_outputs=json.dumps(outputs_dict, indent=2, ensure_ascii=False)
        )
        raw = self.llm.complete(prompt)
        try:
            data = json.loads(raw)
        except Exception:
            data = {"final_output": str(outputs_dict), "qa_score": 0.6,
                    "bestanden": False, "anmerkungen": ["JSON parse error"], "zurueck_an": None}
        return QAResult(
            final_output=data.get("final_output", ""),
            qa_score=data.get("qa_score", 0.0),
            bestanden=data.get("bestanden", False),
            anmerkungen=data.get("anmerkungen", []),
            zurueck_an=data.get("zurueck_an")
        )


# ── Bibliothekarin (async) ────────────────────────────────────────────────────

class Bibliothekarin:
    PATTERN_TEMPLATE = """---
task_typ: {task_typ}
erstellt: {datum}
letzter_einsatz: {datum}
qa_score_avg: {qa_score}
durchlaeufe: 1
branche: {branche}
tags: {tags}
---

## Atom-Struktur
{atome}

## Output-Beispiel
{output_auszug}

## Besonderheiten
Automatisch eingepflegt via aot-harness Bibliothekarin.
"""

    def __init__(self, llm_client, vault):
        self.llm   = llm_client
        self.vault = vault

    def run_async(self, task_typ: str, atome: list[str], qa_score: float,
                  output_auszug: str, branche: str = "", tags: list[str] = None) -> None:
        """Startet async — blockiert keinen Output an den Nutzer."""
        thread = threading.Thread(
            target=self._run,
            args=(task_typ, atome, qa_score, output_auszug, branche, tags or []),
            daemon=True
        )
        thread.start()

    def _run(self, task_typ: str, atome: list[str], qa_score: float,
             output_auszug: str, branche: str, tags: list[str]) -> None:
        if qa_score < 0.75:
            # Pending — noch nicht gut genug für Patterns
            pending_path = f"/pending/{task_typ.replace(' ', '_')}.md"
            self.vault.ingest(pending_path,
                f"# PENDING: {task_typ}\nQA-Score: {qa_score}\n{output_auszug[:200]}")
            return

        # Duplikat-Check
        hits = self.vault.search(task_typ)
        similarity = hits[0].get("similarity", 0) if hits else 0

        datum = datetime.date.today().isoformat()
        atome_str = "\n".join(f"- {a}" for a in atome)
        pattern = self.PATTERN_TEMPLATE.format(
            task_typ=task_typ, datum=datum, qa_score=round(qa_score, 2),
            branche=branche, tags=json.dumps(tags, ensure_ascii=False),
            atome=atome_str, output_auszug=output_auszug[:300]
        )

        path = f"/patterns/{task_typ.replace(' ', '_')}.md"
        if similarity > 0.85:
            # Merge: Update bestehenden Eintrag
            existing = self.vault.read(hits[0].get("path", path)) or ""
            self.vault.ingest(hits[0].get("path", path), existing + "\n---\n" + pattern)
        else:
            # Neuer Eintrag
            self.vault.ingest(path, pattern)
