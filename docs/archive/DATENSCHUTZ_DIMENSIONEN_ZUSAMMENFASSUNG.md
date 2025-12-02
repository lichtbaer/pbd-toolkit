# Zusammenfassung: Vorschläge für weitere Datenschutz-Dimensionen

## Schnellübersicht

Dieses Dokument fasst die wichtigsten Vorschläge zur Erweiterung der PII-Erkennung zusammen. Eine detaillierte Analyse findet sich in `DATENSCHUTZ_DIMENSIONEN_ANALYSE.md`.

## Top 10 Prioritäten

### 1. Telefonnummern (Regex) ⭐⭐⭐⭐⭐
- **Relevanz**: Sehr hoch
- **Aufwand**: Niedrig
- **Regex**: `\b(?:\+?[1-9]\d{1,14}|0[1-9]\d{1,13})\b`
- **Status**: Noch nicht implementiert

### 2. Steuer-ID (Regex) ⭐⭐⭐⭐⭐
- **Relevanz**: Sehr hoch
- **Aufwand**: Niedrig
- **Regex**: `\b[0-9]{11}\b`
- **Hinweis**: Kontextprüfung empfohlen (Signalwörter: "Steuer-ID", "TIN")

### 3. Kreditkartennummern (Regex) ⭐⭐⭐⭐⭐
- **Relevanz**: Sehr hoch
- **Aufwand**: Mittel
- **Regex**: Siehe Analyse-Dokument
- **Hinweis**: Luhn-Algorithmus zur Validierung

### 4. Erweiterte Signalwörter (Regex) ⭐⭐⭐⭐
- **Relevanz**: Hoch
- **Aufwand**: Niedrig
- **Kategorien**: Medizinisch, Finanziell, Rechtlich, Bewerbung

### 5. Biometrische Daten (NER) ⭐⭐⭐⭐
- **Relevanz**: Sehr hoch (Art. 9 DSGVO)
- **Aufwand**: Mittel
- **NER-Label**: "Biometric Data"

### 6. Kombinationsmuster (Kontext) ⭐⭐⭐⭐
- **Relevanz**: Hoch
- **Aufwand**: Mittel
- **Beispiel**: Name + Geburtsdatum + Adresse = Vollständige Identität

### 7. Metadaten-Extraktion ⭐⭐⭐
- **Relevanz**: Mittel-Hoch
- **Aufwand**: Mittel
- **Typen**: EXIF (GPS), Dokument-Metadaten, Kommentare

### 8. Postleitzahlen (Kontext) ⭐⭐⭐
- **Relevanz**: Mittel
- **Aufwand**: Niedrig
- **Hinweis**: Nur relevant in Kombination mit Adressdaten

### 9. BIC (Bank Identifier Code) ⭐⭐⭐
- **Relevanz**: Mittel
- **Aufwand**: Niedrig
- **Regex**: `\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b`

### 10. Politische/Religiöse Überzeugungen (NER) ⭐⭐⭐
- **Relevanz**: Hoch (Art. 9 DSGVO)
- **Aufwand**: Mittel
- **NER-Labels**: "Political Affiliation", "Religious Belief"

## Implementierungs-Roadmap

### Phase 1: Quick Wins (1-2 Wochen)
1. Telefonnummern
2. Steuer-ID
3. Erweiterte Signalwörter
4. BIC
5. Postleitzahlen (mit Kontextprüfung)

**Erwarteter Impact**: +30-40% Erkennungsrate bei strukturierten Daten

### Phase 2: Erweiterte Features (2-4 Wochen)
1. Kreditkartennummern (mit Luhn-Validierung)
2. Biometrische Daten (NER)
3. Kombinationsmuster-Erkennung
4. Metadaten-Extraktion (EXIF, Dokumente)
5. Erweiterte NER-Labels (politisch, religiös, etc.)

**Erwarteter Impact**: +20-30% Erkennungsrate, bessere Kontext-Erkennung

### Phase 3: Advanced Features (4-8 Wochen)
1. ML-basierte Klassifizierung
2. Anomalie-Erkennung
3. Externe API-Integration (Have I Been Pwned)
4. Datenbank-Dateien (SQLite, Access)
5. Backup-Archive

**Erwarteter Impact**: Umfassende Abdeckung, intelligente Risiko-Bewertung

## Konkrete Code-Beispiele

### Beispiel 1: Telefonnummern-Erkennung

**config_types.json:**
```json
{
  "label": "REGEX_PHONE",
  "value": "Regex: Phone Number",
  "regex_compiled_pos": 6,
  "expression": "\\b(?:\+?[1-9]\\d{1,14}|0[1-9]\\d{1,13})\\b"
}
```

### Beispiel 2: Steuer-ID mit Kontextprüfung

**Neue Funktion in `matches.py`:**
```python
def _check_context(self, text: str, match_text: str, context_window: int = 50) -> bool:
    """Check if match is in relevant context."""
    match_pos = text.find(match_text)
    if match_pos == -1:
        return False
    
    context_start = max(0, match_pos - context_window)
    context_end = min(len(text), match_pos + len(match_text) + context_window)
    context = text[context_start:context_end].lower()
    
    keywords = ["steuer", "tin", "idnr", "steueridentifikationsnummer"]
    return any(keyword in context for keyword in keywords)
```

### Beispiel 3: Kombinationsmuster

**Neue Klasse `combination_detector.py`:**
```python
class CombinationDetector:
    def __init__(self, config: dict):
        self.combinations = config.get("combinations", [])
    
    def detect_combinations(self, matches: list[PiiMatch]) -> list[dict]:
        """Detect combination patterns in matches."""
        results = []
        for combo_config in self.combinations:
            required_types = combo_config["required_types"]
            found_types = {m.type for m in matches}
            
            if len(found_types.intersection(set(required_types))) >= combo_config["min_matches"]:
                results.append({
                    "name": combo_config["name"],
                    "severity": combo_config["severity"],
                    "matches": [m for m in matches if m.type in required_types]
                })
        return results
```

## Metriken & Erfolgsmessung

### Vor Implementierung
- Aktuelle Erkennungsrate messen
- Baseline für verschiedene Dokumenttypen erstellen
- Falsch-Positiv-Rate dokumentieren

### Nach Implementierung
- Vergleich der Erkennungsraten
- Falsch-Positiv-Rate überwachen
- Performance-Impact messen
- Benutzer-Feedback sammeln

## Risiken & Mitigation

### Risiko 1: Hohe Falsch-Positiv-Rate
**Mitigation**: 
- Validierungs-Algorithmen (Luhn, Format-Checks)
- Kontextprüfung
- Whitelist-Erweiterung

### Risiko 2: Performance-Impact
**Mitigation**:
- Regex-Optimierung
- Caching von Validierungen
- Asynchrone Verarbeitung

### Risiko 3: Komplexität
**Mitigation**:
- Schrittweise Implementierung
- Modulare Architektur
- Umfassende Tests

## Nächste Schritte

1. **Review der Vorschläge** mit dem Team
2. **Priorisierung** basierend auf Anwendungsfall
3. **Prototyp** für Top 3 Features
4. **Testing** mit realen Daten
5. **Iterative Verbesserung** basierend auf Feedback

## Referenzen

- Detaillierte Analyse: `DATENSCHUTZ_DIMENSIONEN_ANALYSE.md`
- GDPR/DSGVO: Art. 4, 9, 10
- Best Practices: OWASP Privacy Risks, NIST Privacy Framework
