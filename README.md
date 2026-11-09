# Projekt 1: Bundeswehr Dienstplan — Vollautomatisierte Dienstplanung

## Vision
Eine vollautomatisierte Software zur Erstellung, Verwaltung und Optimierung von Dienstplänen für die Bundeswehr. Verkaufbar an das Verteidigungsministerium und Bundeswehr-Einheiten.

## Kernfunktionen
- Automatische Dienstplan-Generierung basierend auf Personalverfügbarkeit, Qualifikationen, Urlaub, Krankheit
- Berücksichtigung von Vorschriften (Arbeitszeitgesetz, Bundeswehr-interne Regelungen)
- Rollen-basierte Zugriffe (Kompaniechef, Zugführer, Soldat)
- Schichtplanung, Wachdienst, Übungsbetrieb
- Export als PDF, Excel, Druck
- Mobile App für Soldaten (Dienstplan einsehen, Tausch anfragen)

## Zielgruppe
Bundeswehr (Kompanien, Bataillone, Einheiten), Verteidigungsministerium

## Technische Anforderungen
- Multi-Tenant (pro Einheit/Kompanie)
- Rollen: Admin, Planer, Soldat (Viewer)
- DSGVO-konform, BSI-Grundschutz
- Offline-fähig (Feldlager)
- Export: PDF, Excel, Kalender (iCal)

## Monetarisierung
- Lizenzmodell pro Einheit
- Enterprise-Lizenz für Bataillone
- Wartungsvertrag
