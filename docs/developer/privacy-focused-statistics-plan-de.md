# Plan: Datenschutzorientierter Statistik-Ausgabemodus

## Übersicht

Dieses Dokument beschreibt den Plan zur Integration eines datenschutzorientierten Statistik-Ausgabemodus, der JSON-Dateien mit statistischen Auswertungen der Scan-Ergebnisse generiert. Ziel ist es, die Verarbeitung personenbezogener Daten zu minimieren, indem Statistiken auf Datenschutz-Dimensionen und Erkennungsmodulen aggregiert werden, anstatt einzelne PII-Funde zu speichern.

## Ziele

1. **Datenschutz**: Aggregation auf Dimensionen-/Modul-Ebene, um einzelne PII-Instanzen nicht zu speichern
2. **Statistische Erkenntnisse**: Aussagekräftige Statistiken für Analysen ohne Offenlegung sensibler Daten
3. **Modulares Design**: Nahtlose Integration in bestehende Architektur
4. **Compliance**: Unterstützung der DSGVO/Datenschutz-Compliance durch Minimierung der Datenspeicherung

## Datenschutz-Dimensionen

Basierend auf DSGVO Artikel 9 und Datenschutzprinzipien werden folgende Dimensionen definiert:

### 1. Identität
- **Typen**: Namen, IDs, Reisepassnummern, Personalausweis, SSN, RVNR
- **Sensitivität**: Hoch
- **Beispiele**: `NER_PERSON`, `REGEX_PASSPORT`, `REGEX_PERSONALAUSWEIS`, `REGEX_SSN_*`, `REGEX_RVNR`

### 2. Kontaktinformationen
- **Typen**: E-Mail, Telefon, Postleitzahlen, IP-Adressen
- **Sensitivität**: Mittel
- **Beispiele**: `REGEX_EMAIL`, `REGEX_PHONE`, `REGEX_POSTAL_CODE`, `REGEX_IPV4`, `NER_LOCATION`

### 3. Finanziell
- **Typen**: IBAN, BIC, Kreditkarten, Steuer-ID, Finanzinformationen
- **Sensitivität**: Hoch
- **Beispiele**: `REGEX_IBAN`, `REGEX_BIC`, `REGEX_CREDIT_CARD`, `REGEX_TAX_ID`, `NER_FINANCIAL`

### 4. Gesundheit
- **Typen**: Gesundheitsdaten, Krankheiten, Medikamente
- **Sensitivität**: Sehr hoch (DSGVO Artikel 9)
- **Beispiele**: `NER_HEALTH`, `NER_MEDICAL_CONDITION`, `NER_MEDICATION`, `REGEX_MRN`

### 5. Biometrisch
- **Typen**: Biometrische Daten
- **Sensitivität**: Sehr hoch (DSGVO Artikel 9)
- **Beispiele**: `NER_BIOMETRIC`

### 6. Besondere Kategorien personenbezogener Daten (DSGVO Artikel 9)
- **Typen**: Politische Einstellung, Religiöse Überzeugung, Sexuelle Orientierung, Ethnische Herkunft, Strafurteile
- **Sensitivität**: Sehr hoch
- **Beispiele**: `NER_POLITICAL`, `NER_RELIGIOUS`, `NER_SEXUAL_ORIENTATION`, `NER_ETHNIC_ORIGIN`, `NER_CRIMINAL_CONVICTION`

### 7. Standort
- **Typen**: Physische Standorte, Adressen
- **Sensitivität**: Mittel
- **Beispiele**: `NER_LOCATION`, `OLLAMA_LOCATION`

### 8. Zugangsdaten & Sicherheit
- **Typen**: Passwörter, PGP-Schlüssel
- **Sensitivität**: Sehr hoch
- **Beispiele**: `NER_PASSWORD`, `REGEX_PGPPRV`

### 9. Organisatorisch
- **Typen**: Organisationen, Daten, Geldbeträge
- **Sensitivität**: Niedrig
- **Beispiele**: `OLLAMA_ORGANIZATION`, `OLLAMA_DATE`, `OLLAMA_MONEY`

### 10. Signalwörter
- **Typen**: Kontextuelle Indikatoren für sensible Daten
- **Sensitivität**: Mittel (zeigt Vorhandensein sensibler Daten an)
- **Beispiele**: `REGEX_WORDS`, `REGEX_SIGNAL_WORDS_EXTENDED`

### 11. Sonstiges
- **Typen**: Nicht klassifizierte oder unbekannte Typen
- **Sensitivität**: Variabel
- **Beispiele**: Alle nicht zugeordneten Typen

## JSON-Ausgabestruktur

Die Statistik-Ausgabe erfolgt als JSON-Datei mit folgender Struktur:

```json
{
  "metadata": {
    "scan_id": "2024-01-15 10-30-45",
    "start_time": "2024-01-15T10:30:45.123456",
    "end_time": "2024-01-15T11:45:30.654321",
    "duration_seconds": 4485.53,
    "scan_path": "/path/to/scanned/directory",
    "detection_methods": {
      "regex": true,
      "ner": true,
      "spacy_ner": false,
      "pydantic_ai": false
    },
    "total_files_scanned": 1250,
    "total_files_analyzed": 1150,
    "total_matches_found": 3420
  },
  "statistics_by_dimension": {
    "identity": {
      "total_count": 450,
      "by_module": {
        "regex": 320,
        "gliner": 120,
        "spacy-ner": 10
      },
      "by_type": {
        "REGEX_PASSPORT": 45,
        "REGEX_PERSONALAUSWEIS": 78,
        "NER_PERSON": 315
      },
      "files_affected": 234,
      "sensitivity_level": "high"
    }
  },
  "statistics_by_module": {
    "regex": {
      "total_matches": 1434,
      "types_detected": 15,
      "files_processed": 1150,
      "files_with_matches": 890
    }
  },
  "statistics_by_file_type": {
    ".pdf": {
      "files_scanned": 450,
      "files_analyzed": 420,
      "matches_found": 1234,
      "top_dimensions": ["financial", "identity", "contact_information"]
    }
  },
  "summary": {
    "total_matches": 3420,
    "unique_files_with_matches": 890,
    "dimensions_detected": 8,
    "modules_used": 2,
    "highest_risk_dimension": "health",
    "risk_assessment": {
      "very_high_risk_count": 57,
      "high_risk_count": 684,
      "medium_risk_count": 890,
      "low_risk_count": 1789
    }
  }
}
```

## Implementierungsschritte

### Phase 1: Kern-Infrastruktur

1. **Privacy Dimension Mapper erstellen** (`core/privacy_dimensions.py`)
   - Dimension-Mapping-Dictionary definieren
   - Funktion zum Zuordnen von Erkennungstypen zu Dimensionen
   - Behandlung von Edge Cases und unbekannten Typen

2. **Statistics-Klasse erweitern** (`core/statistics.py`)
   - Methoden für datenschutzorientierte Aggregation hinzufügen
   - Statistiken nach Dimension und Modul verfolgen
   - Datei-Level-Zählungen ohne Speicherung von Pfaden

3. **Statistics Aggregator erstellen** (`core/statistics_aggregator.py`)
   - Matches verarbeiten und nach Dimension/Modul aggregieren
   - Verteilungen und Metriken berechnen
   - Zusammenfassungsstatistiken generieren

### Phase 2: Ausgabe-Writer

4. **Privacy Statistics Writer erstellen** (`core/writers.py`)
   - `PrivacyStatisticsWriter`-Klasse implementieren
   - JSON-Ausgabe mit korrekter Struktur generieren
   - Sicherstellen, dass keine PII-Daten in der Ausgabe enthalten sind

5. **Writer Factory aktualisieren** (`core/writers.py`)
   - "statistics" Format zur Factory-Funktion hinzufügen
   - Integration in bestehendes Writer-System

### Phase 3: CLI-Integration

6. **CLI-Optionen hinzufügen** (`core/cli.py`)
   - `--statistics-mode` Flag hinzufügen
   - `--statistics-output` für benutzerdefinierten Ausgabepfad
   - Hilfe-Text und Dokumentation aktualisieren

7. **Integration in Processing Pipeline** (`core/cli.py`)
   - Statistiken während der Verarbeitung sammeln
   - Statistik-Datei nach Scan-Abschluss generieren
   - Kompatibilität mit bestehenden Ausgabeformaten sicherstellen

### Phase 4: Tests & Dokumentation

8. **Unit Tests**
   - Dimension-Mapping testen
   - Aggregationslogik testen
   - JSON-Ausgabeformat testen

9. **Integration Tests**
   - End-to-End Statistik-Generierung testen
   - Test mit verschiedenen Erkennungsmethoden
   - Test mit verschiedenen Dateitypen

10. **Dokumentation**
    - Benutzerhandbuch aktualisieren
    - Beispiele hinzufügen
    - Datenschutz-Überlegungen dokumentieren

## Datenschutz-Überlegungen

1. **Keine PII-Speicherung**: Statistik-Ausgabe enthält nur Zählungen und Aggregationen, keine tatsächlichen PII-Texte
2. **Keine Dateipfade**: Dateipfade werden nicht in Statistiken aufgenommen (nur Zählungen betroffener Dateien)
3. **Anonymisierte Daten**: Alle Daten sind aggregiert und anonymisiert
4. **Optionaler Modus**: Statistik-Modus ist optional und getrennt von detaillierten Findings-Ausgaben
5. **Compliance**: Unterstützt DSGVO-Compliance durch Minimierung der Datenspeicherung

## Verwendung

Der Statistik-Modus kann wie folgt aktiviert werden:

```bash
# Nur Statistik-Modus (keine detaillierten Findings)
pii-toolkit scan /path --regex --ner --statistics-mode

# Statistik + detaillierte Findings
pii-toolkit scan /path --regex --ner --format statistics --format csv

# Benutzerdefinierter Statistik-Ausgabepfad
pii-toolkit scan /path --regex --ner --statistics-mode --statistics-output ./stats.json
```

## Zukünftige Erweiterungen

1. **Risiko-Bewertung**: Risiko-Scoring basierend auf Dimensions-Sensitivität
2. **Trend-Analyse**: Vergleich von Statistiken über mehrere Scans
3. **Visualisierung**: Generierung von Diagrammen/Grafiken aus Statistiken
4. **Export-Formate**: Unterstützung zusätzlicher Export-Formate (CSV, Excel)
5. **Filterung**: Filterung von Statistiken nach Dimension oder Modul
6. **Compliance-Reports**: Generierung von DSGVO-Compliance-Reports aus Statistiken

## Abhängigkeiten

- Keine neuen externen Abhängigkeiten erforderlich
- Verwendet bestehende JSON-Behandlung aus Standardbibliothek
- Nutzt bestehende Statistik-Infrastruktur

## Migrationspfad

- Rückwärtskompatibel: Bestehende Funktionalität unverändert
- Statistik-Modus ist additive Funktion
- Kann parallel zu bestehenden Ausgabeformaten verwendet werden
- Keine Breaking Changes zu bestehenden APIs
