"""
aot_harness/examples/chip_idd_demo.py
Vollständige Demo: CHIP-Orchestrator + AoT + Obsidian Vault (Mock)
Use Case: IDD-Dokumentation für Versicherungsmakler
"""
import os
from aot_harness.core.chip_orchestrator import CHIPOrchestrator
from aot_harness.integrations.claude_adapter import ClaudeAdapter
from aot_harness.integrations.obsidian_adapter import ObsidianVault
from aot_harness.core.tool_executor import get_default_registry


if __name__ == "__main__":
    api_key = os.environ.get("ANTHROPIC_API_KEY", "your-api-key-here")

    # Vault im Mock-Modus (kein echtes Obsidian nötig für Demo)
    vault = ObsidianVault(mock=True)

    # Beispiel-Pattern vorab laden (simuliert gelerntes Wissen)
    vault.ingest("/patterns/IDD_Dokumentation.md", """---
task_typ: IDD Dokumentation
qa_score_avg: 0.88
durchlaeufe: 5
---
## Atom-Struktur
- Atom 1: Kundendaten abrufen
- Atom 2: Produktkatalog laden
- Atom 3: Risikoklasse bestimmen
- Atom 4: IDD-Dokument erstellen
## Besonderheiten
Immer § 61 VVG referenzieren. Risikoklasse vor Produktempfehlung.""")

    orch = CHIPOrchestrator(
        llm_client   = ClaudeAdapter(api_key=api_key),
        vault        = vault,
        session_id   = "chip-idd-demo",
        max_retries  = 2,
        max_qa_loops = 2,
        verbose      = True,
    )

    result = orch.run(
        "Erstelle eine vollständige IDD-Dokumentation für Kunde Mustermann, "
        "42 Jahre, mittleres Risikoprofil, Interesse an Haftpflicht-Absicherung."
    )

    print("\n" + "="*60)
    print("ERGEBNIS:")
    print(result["result"])
    print(f"\nQA-Score: {result['qa_score']:.2f} | Cache-Hit: {result['cache_hit']}")
    print(f"Atoms: {result['atoms_used']}")
    if result["notes"]:
        print(f"QA-Hinweise: {result['notes']}")
