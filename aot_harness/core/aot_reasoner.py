"""
aot_harness/core/aot_reasoner.py
Atom of Thoughts (AoT) Reasoning Engine
Based on: arXiv:2502.12018 (NeurIPS 2025) — MIT License
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import json


class AtomStatus(str, Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    DONE     = "done"
    FAILED   = "failed"
    SKIPPED  = "skipped"


@dataclass
class Atom:
    """One self-contained unit of reasoning (Markov node in the DAG)."""
    id:           str
    question:     str                          # What must be answered / done
    depends_on:   list[str]  = field(default_factory=list)
    status:       AtomStatus = AtomStatus.PENDING
    result:       Any        = None            # Compressed output after solve
    error:        str | None = None
    retry_count:  int        = 0
    max_retries:  int        = 2

    def context_snapshot(self) -> dict:
        """Return only the compressed result — not the full reasoning chain."""
        return {"id": self.id, "result": self.result, "status": self.status}


@dataclass
class AtomGraph:
    """Directed Acyclic Graph of Atoms — the AoT execution plan."""
    goal:  str
    atoms: dict[str, Atom] = field(default_factory=dict)

    def add(self, atom: Atom) -> None:
        self.atoms[atom.id] = atom

    def ready_atoms(self) -> list[Atom]:
        """Return atoms whose dependencies are all DONE."""
        return [
            a for a in self.atoms.values()
            if a.status == AtomStatus.PENDING
            and all(
                self.atoms[dep].status == AtomStatus.DONE
                for dep in a.depends_on
                if dep in self.atoms
            )
        ]

    def is_complete(self) -> bool:
        return all(
            a.status in (AtomStatus.DONE, AtomStatus.SKIPPED)
            for a in self.atoms.values()
        )

    def has_failed(self) -> bool:
        return any(a.status == AtomStatus.FAILED for a in self.atoms.values())

    def compressed_context(self) -> list[dict]:
        """AoT contraction: only solved atom results, no reasoning chains."""
        return [
            a.context_snapshot()
            for a in self.atoms.values()
            if a.status == AtomStatus.DONE
        ]

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "atoms": {k: {
                "id": v.id, "question": v.question,
                "depends_on": v.depends_on, "status": v.status,
                "result": v.result, "error": v.error
            } for k, v in self.atoms.items()}
        }


class AoTReasoner:
    """
    Decomposes a complex goal into an AtomGraph via an LLM call,
    then provides the interface to solve each Atom independently.
    """

    DECOMPOSE_PROMPT = """You are an expert task decomposer using the Atom of Thoughts (AoT) framework.

Break the following goal into the smallest possible independent sub-questions (atoms).
Each atom must be self-contained and verifiable on its own.
Atoms may depend on results of earlier atoms — model this as a DAG.

Goal: {goal}

Context from solved atoms (if any):
{context}

Respond ONLY with valid JSON in this exact format:
{{
  "atoms": [
    {{
      "id": "a1",
      "question": "...",
      "depends_on": []
    }},
    {{
      "id": "a2",
      "question": "...",
      "depends_on": ["a1"]
    }}
  ]
}}

Rules:
- Maximum 8 atoms
- Each atom solves ONE thing only
- depends_on lists atom ids that must be solved first
- No circular dependencies
- The last atom should synthesize/summarize the final answer"""

    SOLVE_PROMPT = """You are solving one specific atom (sub-task) as part of a larger goal.

Overall Goal: {goal}

Already solved context (compressed results only):
{context}

Your atom to solve:
ID: {atom_id}
Question: {question}

Solve this atom completely and concisely.
Return ONLY the answer/result — no reasoning chain, no explanation of your process.
Your answer will be compressed and passed to dependent atoms."""

    def __init__(self, llm_client):
        """
        llm_client: any object with a .complete(prompt: str) -> str method.
        See integrations/claude_adapter.py for Claude implementation.
        """
        self.llm = llm_client

    def decompose(self, goal: str, existing_context: list[dict] | None = None) -> AtomGraph:
        """Call LLM to build the AtomGraph for a given goal."""
        context_str = json.dumps(existing_context or [], indent=2)
        prompt = self.DECOMPOSE_PROMPT.format(goal=goal, context=context_str)
        raw = self.llm.complete(prompt)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            data = json.loads(match.group()) if match else {"atoms": []}

        graph = AtomGraph(goal=goal)
        for item in data.get("atoms", []):
            graph.add(Atom(
                id=item["id"],
                question=item["question"],
                depends_on=item.get("depends_on", [])
            ))
        return graph

    def solve_atom(self, atom: Atom, graph: AtomGraph) -> str:
        """Solve a single atom using compressed context from its dependencies."""
        dep_context = [
            graph.atoms[dep].context_snapshot()
            for dep in atom.depends_on
            if dep in graph.atoms and graph.atoms[dep].status == AtomStatus.DONE
        ]
        prompt = self.SOLVE_PROMPT.format(
            goal=graph.goal,
            context=json.dumps(dep_context, indent=2),
            atom_id=atom.id,
            question=atom.question
        )
        return self.llm.complete(prompt)
