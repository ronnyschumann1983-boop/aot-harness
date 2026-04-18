-- Schadenmeldungs-Triage — Demo-Seed für Supabase
-- Legt 5 fiktive Policen in die vault_patterns-Tabelle.
-- Voraussetzung: vault_patterns-Schema aus aot-harness v0.4.0 ist angelegt.

-- Schema-Erinnerung (falls noch nicht vorhanden):
-- create table if not exists vault_patterns (
--     path       text primary key,
--     content    text not null,
--     tags       jsonb default '[]'::jsonb,
--     created_at timestamptz default now(),
--     updated_at timestamptz default now()
-- );

insert into vault_patterns (path, content, tags) values

('/policen/HR-48291-B',
'Policennummer: HR-48291-B
Kunde: Michael Mustermann, 42 Jahre
Adresse: Berliner Str. 42, 10115 Berlin
Sparte: Hausrat
Versicherer: ExampleVersicherung AG
Deckungssumme: 65.000 EUR
Selbstbeteiligung: 150 EUR
Ausschluesse: grobe Fahrlaessigkeit, Schaeden durch Grundwasser
Betreuer: Ronny Schumann
Gueltig bis: 31.03.2027
Besonderheiten: Wertsachen bis 5.000 EUR eingeschlossen; Elementarschaeden inkludiert',
'["hausrat", "demo"]'::jsonb),

('/policen/HP-20044-C',
'Policennummer: HP-20044-C
Kunde: Sabine Weber, 56 Jahre
Sparte: Privathaftpflicht
Versicherer: Musterassekuranz
Deckungssumme: 10.000.000 EUR
Selbstbeteiligung: 0 EUR
Ausschluesse: berufliche Taetigkeit, Kfz-bezogene Schaeden
Betreuer: Ronny Schumann
Gueltig bis: 14.08.2026
Besonderheiten: Schluesselverlust bis 30.000 EUR mitversichert; Forderungsausfall bis 10 Mio.',
'["haftpflicht", "demo"]'::jsonb),

('/policen/KFZ-77812-A',
'Policennummer: KFZ-77812-A
Kunde: Thomas Bauer
Fahrzeug: VW Golf 8, Bj. 2022, Kennzeichen HH-XY 1234
Sparte: KFZ-Versicherung (Vollkasko + Haftpflicht)
Versicherer: AutoPolis GmbH
Deckungssumme: Neuwert 28.500 EUR
Selbstbeteiligung: 300 EUR (Vollkasko), 150 EUR (Teilkasko)
Betreuer: Ronny Schumann
Gueltig bis: 30.11.2026
Besonderheiten: SF-Klasse 12; Werkstattbindung aktiv; Schutzbrief inkludiert',
'["kfz", "demo"]'::jsonb),

('/policen/GW-31188-D',
'Policennummer: GW-31188-D
Kunde: Baeckerei Klein GmbH (Inh. Peter Klein)
Adresse: Hauptstr. 8, 12345 Berlin
Sparte: Gewerbe-Inhaltsversicherung
Versicherer: Mittelstand Assekuranz
Deckungssumme: 380.000 EUR (Inhalt), 150.000 EUR (Betriebsunterbrechung)
Selbstbeteiligung: 500 EUR
Ausschluesse: Krieg, Kernenergie, Kundenbesitz > 5.000 EUR
Betreuer: Ronny Schumann
Gueltig bis: 31.12.2026
Besonderheiten: Kuehlgut bis 25.000 EUR; Rueckwaertsversicherung 30 Tage; Einbruch-Diebstahl inkludiert',
'["gewerbe", "inhalt", "demo"]'::jsonb),

('/policen/RS-99210-F',
'Policennummer: RS-99210-F
Kunde: Anne Richter, 38 Jahre
Sparte: Rechtsschutzversicherung
Versicherer: JurAssekuranz
Bausteine: Privat, Beruf, Verkehr, Miete (Vermieter-RSV NICHT enthalten)
Versicherungssumme: unbegrenzt (Deutschland), 300.000 EUR (Ausland)
Selbstbeteiligung: 300 EUR
Wartezeit: 3 Monate (laeuft ab 01.01.2026)
Betreuer: Ronny Schumann
Gueltig bis: 31.12.2027',
'["rechtsschutz", "demo"]'::jsonb)

on conflict (path) do update set
    content    = excluded.content,
    tags       = excluded.tags,
    updated_at = now();
