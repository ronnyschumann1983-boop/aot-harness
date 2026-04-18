# Test-Mail: Wasserschaden in Küche

Zum Testen des Schadenmeldungs-Triage-Workflows: im Form-Trigger diese Felder
ausfüllen und auf "Submit" klicken.

---

## Formular-Eingaben

| Feld               | Wert                                                    |
|--------------------|---------------------------------------------------------|
| **Kundenname**     | Michael Mustermann                                      |
| **Kunden-E-Mail**  | michael.mustermann@example.com                          |
| **Policennummer**  | HR-48291-B                                              |
| **Dringlichkeit**  | sofort                                                  |

### Police-Daten (aus seed.sql — copy/paste ins Formular)

```
Policennummer: HR-48291-B
Kunde: Michael Mustermann, 42 Jahre
Adresse: Berliner Str. 42, 10115 Berlin
Sparte: Hausrat
Versicherer: ExampleVersicherung AG
Deckungssumme: 65.000 EUR
Selbstbeteiligung: 150 EUR
Ausschluesse: grobe Fahrlaessigkeit, Schaeden durch Grundwasser
Betreuer: Ronny Schumann
Gueltig bis: 31.03.2027
Besonderheiten: Wertsachen bis 5.000 EUR eingeschlossen; Elementarschaeden inkludiert
```

### Schaden-Mail (Kunde)

```
Hallo Herr Schumann,

heute Morgen ist bei uns in der Küche die Spülmaschine undicht geworden.
Ich war gegen 7:30 Uhr in der Küche und das Wasser stand schon ca. 2 cm
hoch, der Boden ist komplett nass, die unteren Küchenschränke ziehen
Wasser, der Parkettboden wölbt sich bereits.

Ich habe den Haupthahn zugedreht und versuche mit Handtüchern zu trocknen,
aber ich weiß nicht was ich als nächstes tun soll. Soll ich schon einen
Handwerker bestellen? Das ist meine Hausratversicherung, oder?

Bitte melden Sie sich schnell.

Viele Grüße
Michael Mustermann
Tel: 030-12345678
```

---

## Erwartetes Ergebnis

Nach dem Submit (ca. 60 Sekunden):

### In Gmail → Entwürfe
1. **Entwurf 1 — an `michael.mustermann@example.com`**
   - Empathischer Ton
   - Sofort-Maßnahmen konkret (Haupthahn zu, Fotos, keine eigenen Reparaturen)
   - Hinweis, dass Hausratversicherung HR-48291-B greift
   - SB 150 EUR erwähnt
   - Nächste Schritte + Rückrufzusage

2. **Entwurf 2 — an `schaden@examplversicherung.example`** (Platzhalter-Adresse)
   - Förmlicher Ton
   - Policennummer HR-48291-B referenziert
   - Schadenart: Leitungswasser (Hausrat)
   - Hergang sachlich zusammengefasst
   - Bitte um Schadennummer + Regulierungszusage

### In der Workflow-Ausgabe (n8n)
- `qa_score: 0.85–0.95`
- `atoms_used: ["a1", "a2", "a3", "a4"]`
- `cost.total_usd: ~0.004`
- `provider_used: google / gemini-2.0-flash`
- `decomposer_provider_used: anthropic / claude-sonnet-4-6`

---

## Weitere Test-Szenarien (für eigene Demos)

Variiere diese Parameter, um das Verhalten zu sehen:

| Szenario                 | Policennummer   | Was sollte passieren?                           |
|--------------------------|-----------------|--------------------------------------------------|
| KFZ-Unfall               | KFZ-77812-A     | Fokus Vollkasko + SB 300 EUR + Werkstattbindung |
| Gewerbe-Einbruch         | GW-31188-D      | Rückwärtsversicherung + Betriebsunterbrechung   |
| Rechtsschutz (Wartezeit) | RS-99210-F      | Hinweis 3-Monats-Wartezeit bis 01.04.2026       |
| **Unbekannte Police**    | `ZZ-99999-X`    | HITL-Branch: Mail an Makler, keine Drafts       |
