"""
aot_harness/examples/insurance_idd.py
Demo: IDD-Dokumentation für Versicherungsmakler via aot-harness
"""
import os
from aot_harness.core import Orchestrator
from aot_harness.integrations.claude_adapter import ClaudeAdapter
from aot_harness.core.tool_executor import get_default_registry, ToolRegistry


def build_insurance_tools() -> ToolRegistry:
    reg = get_default_registry()

    def fetch_customer_data(customer_id: str = "") -> str:
        # In production: query your CRM/DB
        return f"Kunde {customer_id}: Max Mustermann, Alter 42, Risikoprofil mittel"

    def fetch_product_catalog(category: str = "") -> str:
        return f"Produkte ({category}): BasisSchutz (€180/Jahr), PremiumSchutz (€340/Jahr)"

    def generate_idd_document(customer: str = "", product: str = "", risk: str = "") -> str:
        return f"""IDD-Dokument:
Kunde: {customer}
Empfohlenes Produkt: {product}
Risikoklassifizierung: {risk}
Beratungsgrundlage: § 61 VVG, IDD-Richtlinie 2016/97/EU"""

    reg.register("fetch_customer_data",  fetch_customer_data,
        {"name": "fetch_customer_data", "description": "Kundendaten aus CRM abrufen"})
    reg.register("fetch_product_catalog", fetch_product_catalog,
        {"name": "fetch_product_catalog", "description": "Produktkatalog abrufen"})
    reg.register("generate_idd_document", generate_idd_document,
        {"name": "generate_idd_document", "description": "IDD-Dokument generieren"})
    return reg


if __name__ == "__main__":
    api_key = os.environ.get("ANTHROPIC_API_KEY", "your-api-key-here")

    orch = Orchestrator(
        llm_client   = ClaudeAdapter(api_key=api_key),
        tools        = build_insurance_tools(),
        session_id   = "idd-demo-001",
        max_retries  = 2,
        verbose      = True,
    )

    result = orch.run(
        "Erstelle eine vollständige IDD-Dokumentation für Kunde #KD-0042 "
        "inklusive Risikoanalyse, Produktempfehlung und rechtlicher Grundlage."
    )

    print("\n" + "="*60)
    print("FINAL RESULT:")
    print(result["result"])
    print(f"\nAtoms: {result['atoms_done']}/{result['atoms_total']} | Success: {result['success']}")
