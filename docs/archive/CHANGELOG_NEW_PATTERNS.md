# Changelog: Neue Datenschutz-Dimensionen

## Version: Erweiterte PII-Erkennung

### Datum: 2024

### Übersicht

Dieses Update fügt 5 neue Regex-Patterns zur PII-Erkennung hinzu, um weitere datenschutzrelevante Dimensionen zu identifizieren.

## Neue Features

### 1. Telefonnummern-Erkennung (`REGEX_PHONE`)

**Beschreibung**: Erkennt Telefonnummern in verschiedenen Formaten (deutsch, international, national).

**Pattern**: `\b(?:\+?[1-9]\d{1,14}|0[1-9]\d{1,13})\b`

**Erkannte Formate**:
- Deutsche Mobilfunknummern: `01761234567`, `+49 176 1234567`
- Internationale Nummern: `+1 555 123 4567`, `+44 20 7946 0958`
- Nationale Formate: Verschiedene länderspezifische Formate

**Relevanz**: Hoch - Telefonnummern sind personenbezogene Daten gemäß DSGVO

**Hinweise**:
- Pattern ist breit gefasst und kann auch Nicht-Telefonnummern matchen
- Whitelist empfohlen für bekannte False Positives
- Kontextprüfung kann Genauigkeit verbessern (zukünftige Erweiterung)

### 2. Steuer-ID Erkennung (`REGEX_TAX_ID`)

**Beschreibung**: Erkennt deutsche Steueridentifikationsnummern.

**Pattern**: `\b[0-9]{11}\b`

**Format**: 11-stellige Zahl

**Beispiel**: `12345678901`

**Relevanz**: Sehr hoch - Steuer-IDs sind eindeutige Identifikatoren natürlicher Personen

**Hinweise**:
- Pattern matcht jede 11-stellige Zahl
- Steuer-IDs werden oft in Kontext mit "Steuer-ID", "TIN", "IdNr" gefunden
- Kontextprüfung empfohlen für bessere Genauigkeit (zukünftige Erweiterung)
- Kann False Positives bei anderen 11-stelligen Zahlen erzeugen

### 3. BIC Erkennung (`REGEX_BIC`)

**Beschreibung**: Erkennt BIC-Codes (Bank Identifier Code, auch SWIFT-Codes genannt).

**Pattern**: `\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b`

**Format**:
- 4 Buchstaben: Bankcode
- 2 Buchstaben: Ländercode
- 2 alphanumerisch: Standortcode
- Optional 3 alphanumerisch: Filialcode

**Beispiele**: `DEUTDEFF`, `DEUTDEFF500`

**Relevanz**: Mittel-Hoch - In Kombination mit IBAN können BICs zusätzliche Informationen liefern

**Hinweise**:
- BICs werden oft zusammen mit IBANs gefunden
- Pattern ist ISO 9362-konform

### 4. Postleitzahlen Erkennung (`REGEX_POSTAL_CODE`)

**Beschreibung**: Erkennt deutsche Postleitzahlen.

**Pattern**: `\b[0-9]{5}\b`

**Format**: 5-stellige Zahl (00000-99999)

**Beispiel**: `10115` (Berlin)

**Relevanz**: Mittel - Postleitzahlen sind in Kombination mit weiteren Adressdaten relevant

**Hinweise**:
- Pattern matcht jede 5-stellige Zahl
- Postleitzahlen sind am relevantesten in Kombination mit Straßenadressen oder Städtenamen
- Kontextprüfung empfohlen für bessere Genauigkeit (zukünftige Erweiterung)
- Kann False Positives bei anderen 5-stelligen Zahlen erzeugen

### 5. Erweiterte Signalwörter (`REGEX_SIGNAL_WORDS_EXTENDED`)

**Beschreibung**: Erkennt erweiterte deutsche Schlüsselwörter, die häufig mit personenbezogenen Daten assoziiert werden.

**Pattern**: Kombiniertes Pattern mit mehreren Kategorien

**Kategorien**:

**Medizinisch**:
- Diagnose, Therapie, Medikament, Krankheit, Behandlung, Arzt, Klinik, Krankenhaus, Patient, Symptom, Operation, Rezept

**Finanziell**:
- Gehalt, Lohn, Einkommen, Vermögen, Schulden, Kredit, Darlehen, Kontostand, Überweisung, Rechnung, Mahnung

**Rechtlich**:
- Klage, Anwalt, Gericht, Urteil, Vertrag, Vereinbarung, Einverständniserklärung, Datenschutzerklärung

**Bewerbung/Beschäftigung**:
- Lebenslauf, CV, Bewerbung, Referenz, Arbeitszeugnis, Qualifikation, Erfahrung, Kompetenz

**Relevanz**: Hoch - Signalwörter können auf sensible Dokumente hinweisen

**Hinweise**:
- Erweitert das ursprüngliche Signalwörter-Pattern (`REGEX_WORDS`)
- Kann helfen, Dokumente mit hohem Datenschutz-Risiko zu identifizieren
- Kombination mit anderen PII-Typen erhöht die Relevanz

## Technische Details

### Konfiguration

Alle neuen Patterns sind in `config_types.json` definiert:

```json
{
  "regex": [
    // ... bestehende Patterns ...
    {
      "label": "REGEX_PHONE",
      "value": "Regex: Phone Number",
      "regex_compiled_pos": 6,
      "expression": "\\b(?:\\+?[1-9]\\d{1,14}|0[1-9]\\d{1,13})\\b"
    },
    // ... weitere neue Patterns ...
  ]
}
```

### Kompatibilität

- **Rückwärtskompatibel**: Bestehende Konfigurationen funktionieren weiterhin
- **Keine Breaking Changes**: Alle neuen Patterns sind optional und werden automatisch aktiviert, wenn `--regex` verwendet wird
- **Performance**: Minimale Performance-Impact durch zusätzliche Regex-Patterns

### Tests

Neue Tests wurden in `tests/test_new_regex_patterns.py` hinzugefügt:
- `TestPhoneNumberDetection`: Tests für Telefonnummern-Erkennung
- `TestTaxIdDetection`: Tests für Steuer-ID-Erkennung
- `TestBicDetection`: Tests für BIC-Erkennung
- `TestPostalCodeDetection`: Tests für Postleitzahlen-Erkennung
- `TestExtendedSignalWords`: Tests für erweiterte Signalwörter

## Verwendung

### Aktivierung

Die neuen Patterns werden automatisch aktiviert, wenn Regex-basierte Erkennung verwendet wird:

```bash
python main.py --path /data --regex
```

### Ausgabe

Die neuen Patterns erscheinen in der Ausgabe mit ihren Labels:
- `REGEX_PHONE`
- `REGEX_TAX_ID`
- `REGEX_BIC`
- `REGEX_POSTAL_CODE`
- `REGEX_SIGNAL_WORDS_EXTENDED`

### Whitelist

Um False Positives zu reduzieren, können bekannte Werte zur Whitelist hinzugefügt werden:

```bash
python main.py --path /data --regex --whitelist whitelist.txt
```

Beispiel-Whitelist-Einträge:
```
01761111111  # Test-Nummer
12345678901  # Beispiel Steuer-ID
```

## Bekannte Einschränkungen

1. **Steuer-ID**: Pattern matcht jede 11-stellige Zahl, nicht nur gültige Steuer-IDs
2. **Postleitzahlen**: Pattern matcht jede 5-stellige Zahl, nicht nur gültige PLZ
3. **Telefonnummern**: Sehr breites Pattern kann auch andere Zahlen matchen
4. **Keine Validierung**: Aktuell keine Format-Validierung (z.B. Luhn-Algorithmus für Kreditkarten)

## Zukünftige Verbesserungen

Geplante Erweiterungen (siehe `DATENSCHUTZ_DIMENSIONEN_ANALYSE.md`):

1. **Kontextprüfung**: Pattern nur matchen, wenn relevante Schlüsselwörter in der Nähe sind
2. **Validierung**: Format-Validierung für Steuer-IDs, Telefonnummern, etc.
3. **Kreditkartennummern**: Mit Luhn-Algorithmus-Validierung
4. **Erweiterte NER-Labels**: Biometrie, politische Überzeugungen, etc.
5. **Kombinationsmuster**: Erkennung vollständiger Identitäten (Name + Geburtsdatum + Adresse)

## Migration

Keine Migration erforderlich. Die neuen Patterns werden automatisch verwendet.

## Feedback & Issues

Bei Problemen oder False Positives:
1. Whitelist verwenden für bekannte False Positives
2. Issue erstellen mit Beispiel-Daten (anonymisiert)
3. Vorschläge für Verbesserungen willkommen

## Referenzen

- Detaillierte Analyse: `docs/archive/DATENSCHUTZ_DIMENSIONEN_ANALYSE.md`
- Implementierungsbeispiel: `docs/archive/IMPLEMENTIERUNGSBEISPIEL_TELEFONNUMMERN.md`
- Zusammenfassung: `docs/archive/DATENSCHUTZ_DIMENSIONEN_ZUSAMMENFASSUNG.md`
