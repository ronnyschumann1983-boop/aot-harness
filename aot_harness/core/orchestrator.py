"""
aot_harness/core/orchestrator.py
Central Harness Orchestrator — combines AoT + Memory + Tools + Sensors + Verifier
"""
from __future__ import annotations
from typing import Any
import time, logging

from .aot_reasoner import AoTReasoner, AtomGraph, AtomStatus
from .memory       import Memory
from .sensors      import Sensor
from .verifier     import Verifier
from .tool_executor import ToolRegistry, get_default_registry

logger = logging.getLogger("aot_harness")


class Orchestrator:
    """
    The Harness core.
    Takes a user goal, decomposes it via AoT, executes each Atom with
    tool support, feedback sensors, and a retry/verify loop.

    Usage:
        orch  = Orchestrator(llm_client=ClaudeAdapter(...))
        result = orch.run("Erstelle eine IDD-Dokumentation für Kunde X")
    """

    def __init__(
        self,
        llm_client,
        tools:       ToolRegistry | None = None,
        session_id:  str                  = "default",
        max_retries: int                  = 3,
        persist_path: str | None          = None,
        verbose:     bool                 = True,
    ):
        self.reasoner  = AoTReasoner(llm_client)
        self.memory    = Memory(session_id, persist_path=persist_path)
        self.tools     = tools or get_default_registry()
        self.sensor    = Sensor()
        self.verifier  = Verifier(max_retries=max_retries)
        self.verbose   = verbose

    def run(self, goal: str) -> dict:
        """
        Main entry point.
        Returns: {"goal": str, "result": str, "graph": dict, "success": bool}
        """
        self._log(f"🎯 Goal: {goal}")
        self.memory.add("user", goal)

        # 1. AoT Decomposition
        self._log("🗂️  Decomposing goal into atoms...")
        graph = self.reasoner.decompose(goal, self.memory.atom_context())
        self._log(f"   → {len(graph.atoms)} atoms created")

        # 2. Execute atoms in dependency order
        max_rounds = len(graph.atoms) * 3
        rounds = 0

        while not graph.is_complete() and rounds < max_rounds:
            rounds += 1
            ready = graph.ready_atoms()

            if not ready:
                if graph.has_failed():
                    self._log("💥 Unresolvable failures — aborting")
                    break
                self._log("⏳ No atoms ready — waiting for dependencies...")
                time.sleep(0.1)
                continue

            for atom in ready:
                self._log(f"⚛️  Solving atom [{atom.id}]: {atom.question[:60]}...")
                atom.status = AtomStatus.RUNNING
                attempt = 0

                while attempt <= atom.max_retries:
                    # Solve atom
                    raw_result = self.reasoner.solve_atom(atom, graph)

                    # Check for tool calls
                    tool_result = self.tools.parse_and_execute(raw_result)
                    output = tool_result.output if tool_result else raw_result

                    # Sensor feedback
                    sensor_result = self.sensor.observe(output)
                    verdict = self.verifier.evaluate(sensor_result, attempt)

                    self._log(f"   attempt {attempt+1}: {verdict['action'].upper()} — {verdict['reason']}")

                    if verdict["action"] == "accept":
                        atom.result = output
                        atom.status = AtomStatus.DONE
                        self.memory.store_atom_result(atom.id, output)
                        self.memory.add("agent", output, atom_id=atom.id)
                        break

                    elif verdict["action"] == "retry":
                        attempt += 1
                        atom.retry_count += 1
                        # Inject sensor feedback into memory for next attempt
                        self.memory.add("system",
                            f"Atom {atom.id} retry {attempt}: {verdict['feedback']}",
                            atom_id=atom.id)
                        continue

                    else:  # abort
                        atom.status = AtomStatus.FAILED
                        atom.error  = verdict["reason"]
                        self._log(f"   ❌ Atom {atom.id} FAILED: {atom.error}")
                        break

        # 3. Build final answer
        success = graph.is_complete() and not graph.has_failed()
        final_atoms = [
            a for a in graph.atoms.values()
            if a.status == AtomStatus.DONE
        ]
        # The last done atom is typically the synthesis atom
        result = final_atoms[-1].result if final_atoms else "No result produced."

        self._log(f"\n{'✅' if success else '⚠️ '} Completed — {len(final_atoms)}/{len(graph.atoms)} atoms done")

        return {
            "goal":    goal,
            "result":  result,
            "graph":   graph.to_dict(),
            "success": success,
            "atoms_done": len(final_atoms),
            "atoms_total": len(graph.atoms),
        }

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)
        logger.info(msg)
