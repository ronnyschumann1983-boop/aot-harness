"""
aot_harness/core/chip_orchestrator.py
CHIP-Orchestrator: AoT-Harness + CHIP-Architektur (Vault, Spezialisten, QA, Bibliothekarin)

Vollständiger Flow:
  1. Vault-Check (Cache-Hit?)
  2. AoT-Decomposition → AtomGraph
  3. Spezialisten parallel starten (Research / Writing / Analysis)
  4. Sensor + Verifier Loop pro Atom
  5. QA-Agent → Score
  6. Output an Nutzer
  7. Bibliothekarin async → Obsidian

Usage:
    from aot_harness.core.chip_orchestrator import CHIPOrchestrator
    from aot_harness.integrations.claude_adapter import ClaudeAdapter
    from aot_harness.integrations.obsidian_adapter import ObsidianVault

    orch = CHIPOrchestrator(
        llm_client = ClaudeAdapter(api_key="..."),
        vault      = ObsidianVault(mcp_client=your_mcp),  # oder mock=True
    )
    result = orch.run("Erstelle IDD-Dokumentation für Kunde X")
"""
from __future__ import annotations
import json, logging, threading
from typing import Any

from .aot_reasoner  import AoTReasoner, AtomGraph, AtomStatus
from .memory        import Memory
from .sensors       import Sensor
from .verifier      import Verifier
from .tool_executor import ToolRegistry, get_default_registry
from .agents        import (
    ResearchAgent, WritingAgent, AnalysisAgent,
    QAAgent, QAResult, Bibliothekarin, AgentInput, AgentOutput
)

logger = logging.getLogger("chip_orchestrator")


# ── Atom → Spezialist Mapping ──────────────────────────────────────────────────

SPECIALIST_KEYWORDS = {
    "research":  ["recherch", "suche", "finde", "research", "daten", "quellen",
                  "informationen", "analyse des marktes"],
    "writing":   ["schreibe", "erstelle", "formuliere", "texte", "email",
                  "dokument", "bericht", "post", "idd"],
    "analysis":  ["analysiere", "bewerte", "vergleiche", "prüfe", "score",
                  "risiko", "klassifizier"],
}

def _detect_specialist(question: str) -> str:
    q = question.lower()
    scores = {sp: sum(1 for kw in kws if kw in q)
              for sp, kws in SPECIALIST_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "research"  # default: research


# ── CHIP Orchestrator ─────────────────────────────────────────────────────────

class CHIPOrchestrator:

    def __init__(
        self,
        llm_client,
        vault=None,
        tools:        ToolRegistry | None = None,
        session_id:   str                  = "chip-default",
        max_retries:  int                  = 3,
        max_qa_loops: int                  = 2,
        persist_path: str | None           = None,
        verbose:      bool                 = True,
    ):
        self.llm          = llm_client
        self.vault        = vault
        self.reasoner     = AoTReasoner(llm_client)
        self.memory       = Memory(session_id, persist_path=persist_path)
        self.tools        = tools or get_default_registry()
        self.sensor       = Sensor()
        self.verifier     = Verifier(max_retries=max_retries)
        self.qa_agent     = QAAgent(llm_client)
        self.bibliothek   = Bibliothekarin(llm_client, vault) if vault else None
        self.verbose      = verbose
        self.max_qa_loops = max_qa_loops

        self.research_agent = ResearchAgent(llm_client, vault)
        self.writing_agent  = WritingAgent(llm_client, vault)
        self.analysis_agent = AnalysisAgent(llm_client, vault)

    # ── Haupt-Einstiegspunkt ──────────────────────────────────────────────────

    def run(self, goal: str) -> dict:
        self._log(f"\n🎯 CHIP-Orchestrator | Goal: {goal}")
        self.memory.add("user", goal)

        # ── Schritt 1: Vault-Check ─────────────────────────────────────────
        cache = self._vault_check(goal)
        if cache["hit"] == "full":
            self._log(f"⚡ Cache-Hit ({cache['similarity']*100:.0f}% Ähnlichkeit) — Pattern geladen")
            # Trotzdem durch QA schicken
            mock_output = AgentOutput(agent="cache", result={"text": cache["pattern"]}, confidence=0.95)
            qa = self.qa_agent.run(goal, {"cache": mock_output})
            return self._finalize(goal, qa, ["cache_hit"], cache_hit=True)

        if cache["hit"] == "partial":
            self._log(f"📎 Partial-Hit ({cache['similarity']*100:.0f}%) — Pattern als Referenz geladen")
            self.memory.add("system", f"Referenz-Pattern: {str(cache['pattern'])[:500]}")

        # ── Schritt 2: AoT Decomposition ──────────────────────────────────
        self._log("🗂️  AoT-Decomposition...")
        graph = self.reasoner.decompose(goal, self.memory.atom_context())
        self._log(f"   → {len(graph.atoms)} Atoms | " +
                  ", ".join(f"{a.id}:{_detect_specialist(a.question)}"
                            for a in graph.atoms.values()))

        # ── Schritt 3: Atoms + Spezialisten ausführen ──────────────────────
        specialist_outputs: dict[str, AgentOutput] = {}
        qa_loops = 0

        while qa_loops < self.max_qa_loops:
            specialist_outputs = self._run_atoms(graph, specialist_outputs)

            # ── Schritt 4: QA ─────────────────────────────────────────────
            self._log("\n🔍 QA-Agent läuft...")
            qa = self.qa_agent.run(goal, specialist_outputs)
            self._log(f"   QA-Score: {qa.qa_score:.2f} | Bestanden: {qa.bestanden}")
            for note in qa.anmerkungen:
                self._log(f"   • {note}")

            if qa.bestanden or qa_loops >= self.max_qa_loops - 1:
                break

            # Retry: QA hat Verbesserungsvorschlag
            if qa.zurueck_an:
                self._log(f"   ↩️  Zurück an: {qa.zurueck_an} (Loop {qa_loops+1})")
                self.memory.add("system", f"QA-Feedback: {', '.join(qa.anmerkungen)}")
                # Nur die spezifischen Atom-IDs zurücksetzen die QA benannt hat.
                # Fallback: alle Atoms des Agent-Typs (altes Verhalten) wenn keine IDs.
                if qa.retry_atom_ids:
                    for atom_id in qa.retry_atom_ids:
                        if atom_id in graph.atoms:
                            graph.atoms[atom_id].status = AtomStatus.PENDING
                            graph.atoms[atom_id].result = None
                            self._log(f"   🔄 Reset atom {atom_id}")
                else:
                    for atom in graph.atoms.values():
                        if _detect_specialist(atom.question) == qa.zurueck_an:
                            atom.status = AtomStatus.PENDING
                            atom.result = None
            qa_loops += 1

        # ── Schritt 5: Output + Bibliothekarin async ───────────────────────
        atoms_used = [a.id for a in graph.atoms.values() if a.status == AtomStatus.DONE]
        result = self._finalize(goal, qa, atoms_used)

        # Bibliothekarin startet async — blockiert NICHT
        if self.bibliothek:
            self.bibliothek.run_async(
                task_typ=goal[:60],
                atome=[a.question[:80] for a in graph.atoms.values()],
                qa_score=qa.qa_score,
                output_auszug=qa.final_output[:200],
            )
            self._log("📚 Bibliothekarin gestartet (async)")

        return result

    # ── Atoms ausführen (parallel pro DAG-Ebene) ──────────────────────────────

    def _run_atoms(self, graph: AtomGraph,
                   existing: dict[str, AgentOutput]) -> dict[str, AgentOutput]:
        outputs = dict(existing)
        outputs_lock = threading.Lock()
        max_rounds = len(graph.atoms) * 3
        rounds = 0

        while not graph.is_complete() and rounds < max_rounds:
            rounds += 1
            ready = graph.ready_atoms()
            if not ready:
                break

            # Alle bereiten Atoms sofort als RUNNING markieren, dann parallel starten
            for atom in ready:
                atom.status = AtomStatus.RUNNING

            threads = [
                threading.Thread(
                    target=self._run_single_atom,
                    args=(atom, graph, outputs, outputs_lock),
                    daemon=True,
                )
                for atom in ready
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        return outputs

    def _run_single_atom(self, atom, graph: AtomGraph,
                         outputs: dict, lock: threading.Lock) -> None:
        """Führt einen einzelnen Atom durch — thread-safe."""
        specialist = _detect_specialist(atom.question)
        self._log(f"⚛️  [{atom.id}] → {specialist}: {atom.question[:55]}...")

        inp = AgentInput(
            atom_aufgabe=atom.question,
            kontext={dep: graph.atoms[dep].result
                     for dep in atom.depends_on if dep in graph.atoms}
        )

        attempt = 0
        while attempt <= atom.max_retries:
            if specialist == "research":
                out = self.research_agent.run(inp)
            elif specialist == "writing":
                input_mat = json.dumps(inp.kontext, ensure_ascii=False)
                out = self.writing_agent.run(inp, input_material=input_mat)
            else:
                out = self.analysis_agent.run(inp, daten=json.dumps(inp.kontext))

            raw_output = json.dumps(out.result, ensure_ascii=False)

            tool_result = self.tools.parse_and_execute(raw_output)
            if tool_result:
                raw_output = tool_result.output

            sensor_res = self.sensor.observe(raw_output)
            verdict    = self.verifier.evaluate(sensor_res, attempt)
            self._log(f"   [{atom.id}] attempt {attempt+1}: {verdict['action'].upper()}")

            if verdict["action"] == "accept":
                atom.result = out.result
                atom.status = AtomStatus.DONE
                with lock:
                    outputs[specialist] = out
                self.memory.store_atom_result(atom.id, raw_output)
                break
            elif verdict["action"] == "retry":
                attempt += 1
                self.memory.add("system",
                    f"Atom {atom.id} retry {attempt}: {verdict['feedback']}")
            else:
                atom.status = AtomStatus.FAILED
                atom.error  = verdict["reason"]
                self._log(f"   ❌ {atom.id} FAILED: {atom.error}")
                break

    # ── Vault-Check ───────────────────────────────────────────────────────────

    def _vault_check(self, goal: str) -> dict:
        if not self.vault:
            return {"hit": "none", "pattern": None, "similarity": 0.0}
        self._log("🔎 Vault-Check...")
        result = self.vault.cache_check(goal)
        self._log(f"   → {result['hit']} ({result['similarity']*100:.0f}%)")
        return result

    # ── Output zusammenstellen ────────────────────────────────────────────────

    def _finalize(self, goal: str, qa: QAResult, atoms_used: list[str],
                  cache_hit: bool = False) -> dict:
        self._log(f"\n{'✅' if qa.bestanden else '⚠️ '} Final | Score: {qa.qa_score:.2f}")
        return {
            "goal":       goal,
            "result":     qa.final_output,
            "qa_score":   qa.qa_score,
            "success":    qa.bestanden,
            "atoms_used": atoms_used,
            "cache_hit":  cache_hit,
            "notes":      qa.anmerkungen,
        }

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)
        logger.info(msg)
