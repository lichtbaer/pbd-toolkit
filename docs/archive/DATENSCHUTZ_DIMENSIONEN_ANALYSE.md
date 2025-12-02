# Analyse: Weitere Datenschutz-Dimensionen für PII-Erkennung

## Zusammenfassung

Dieses Dokument analysiert das aktuelle PII-Toolkit und schlägt konkrete Erweiterungen vor, um zusätzliche datenschutzrelevante Dimensionen zu identifizieren. Die Vorschläge basieren auf GDPR/DSGVO-Anforderungen, Best Practices der Datenschutz-Auditierung und aktuellen Bedrohungsszenarien.

## Aktueller Stand

### Regex-basierte Erkennung
- **RVNR** (Rentenversicherungsnummer)
- **IBAN** (Internationale Bankkontonummer)
- **E-Mail-Adressen**
- **IPv4-Adressen**
- **Signalwörter** (Abmahnung, Bewerbung, Zeugnis, etc.)
- **Private PGP-Keys**

### AI-NER-basierte Erkennung
- **Personennamen**
- **Orte/Locations**
- **Gesundheitsdaten** (experimentell)
- **Passwörter** (experimentell)

## Vorschläge für Erweiterungen

### 1. Strukturierte Identifikatoren (Regex-basiert)

#### 1.1 Deutsche Identifikatoren

**Steuer-ID (Steueridentifikationsnummer)**
```regex
\b[0-9]{11}\b
```
- **Relevanz**: Sehr hoch - eindeutige Identifikation natürlicher Personen
- **Implementierung**: Einfach
- **Falsch-Positiv-Rate**: Mittel (11-stellige Zahlen können auch andere Daten sein)
- **Verbesserung**: Kontextprüfung (z.B. in Verbindung mit "Steuer-ID", "TIN", "IdNr")

**Personalausweisnummer**
```regex
\b[A-Z0-9]{9}\b
```
- **Relevanz**: Sehr hoch
- **Implementierung**: Einfach
- **Hinweis**: Format kann variieren, Kontextprüfung empfohlen

**Reisepassnummer**
```regex
\b[A-Z0-9]{6,9}\b
```
- **Relevanz**: Hoch
- **Implementierung**: Mittel (Format variiert je nach Land)

**Führerscheinnummer**
```regex
\b[A-Z]{1,2}[0-9]{6,11}\b
```
- **Relevanz**: Hoch
- **Implementierung**: Mittel (Format variiert)

#### 1.2 Internationale Identifikatoren

**Kreditkartennummern**
```regex
\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3[0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b
```
- **Relevanz**: Sehr hoch - besonders sensibel
- **Implementierung**: Mittel (Luhn-Algorithmus zur Validierung)
- **Hinweis**: Sollte mit CVV-Erkennung kombiniert werden

**CVV/CVC (Kreditkarten-Sicherheitscode)**
```regex
\b[0-9]{3,4}\b
```
- **Relevanz**: Sehr hoch (in Kombination mit Kreditkartennummer)
- **Implementierung**: Einfach
- **Hinweis**: Nur relevant in Kontext mit Kreditkartennummer

**US Social Security Number (SSN)**
```regex
\b\d{3}-\d{2}-\d{4}\b
```
- **Relevanz**: Sehr hoch (für US-Daten)
- **Implementierung**: Einfach

**UK National Insurance Number**
```regex
\b[A-Z]{2}[0-9]{6}[A-Z]?\b
```
- **Relevanz**: Hoch (für UK-Daten)
- **Implementierung**: Einfach

#### 1.3 Telekommunikationsdaten

**Telefonnummern (erweitert)**
```regex
\b(?:\+?[1-9]\d{1,14}|0[1-9]\d{1,13})\b
```
- **Relevanz**: Hoch
- **Implementierung**: Mittel (viele Varianten)
- **Hinweis**: Aktuell nicht erkannt, sollte ergänzt werden

**Mobilfunknummern (DE)**
```regex
\b(?:017[0-9]|015[0-9]|016[0-9]|017[0-9])\d{7,8}\b
```
- **Relevanz**: Hoch
- **Implementierung**: Einfach

#### 1.4 Adressdaten (Strukturiert)

**Postleitzahlen (DE)**
```regex
\b[0-9]{5}\b
```
- **Relevanz**: Mittel (in Kombination mit Straße/Name)
- **Implementierung**: Einfach
- **Hinweis**: Kontextabhängig - nur relevant mit weiteren Adressdaten

**Postleitzahlen (International)**
```regex
\b[A-Z0-9]{3,10}\b
```
- **Relevanz**: Mittel
- **Implementierung**: Mittel (Format variiert stark)

#### 1.5 Digitale Identifikatoren

**MAC-Adressen**
```regex
\b(?:[0-9A-Fa-f]{2}[:-]){5}(?:[0-9A-Fa-f]{2})\b
```
- **Relevanz**: Mittel (kann Geräte identifizieren)
- **Implementierung**: Einfach

**IMEI (International Mobile Equipment Identity)**
```regex
\b[0-9]{15}\b
```
- **Relevanz**: Mittel
- **Implementierung**: Einfach (mit Luhn-Check)

**UUID/GUID**
```regex
\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b
```
- **Relevanz**: Niedrig-Mittel (kann pseudonymisierte Daten sein)
- **Implementierung**: Einfach

#### 1.6 Finanzdaten

**BIC (Bank Identifier Code)**
```regex
\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b
```
- **Relevanz**: Mittel (in Kombination mit IBAN)
- **Implementierung**: Einfach

**Kontonummern (DE)**
```regex
\b[0-9]{1,10}\b
```
- **Relevanz**: Hoch (in Kombination mit Bankleitzahl)
- **Implementierung**: Mittel (Format variiert)
- **Hinweis**: Nur relevant mit Bankleitzahl

**Bankleitzahl (DE)**
```regex
\b[0-9]{8}\b
```
- **Relevanz**: Hoch (in Kombination mit Kontonummer)
- **Implementierung**: Einfach

### 2. Unstrukturierte Daten (AI-NER-basiert)

#### 2.1 Erweiterte NER-Labels

**Biometrische Daten**
- Fingerabdrücke
- Gesichtserkennungsdaten
- Iris-Scans
- DNA-Informationen

**Politische/Religiöse Überzeugungen**
- Parteizugehörigkeit
- Religionszugehörigkeit
- Weltanschauung

**Sexuelle Orientierung**
- Explizite oder implizite Hinweise

**Gewerkschaftszugehörigkeit**
- Mitgliedschaft in Gewerkschaften

**Strafregisterdaten**
- Vorstrafen
- Gerichtsverfahren

**Finanzielle Situation**
- Einkommen
- Vermögen
- Schulden
- Kreditwürdigkeit

**Kinderdaten**
- Namen von Minderjährigen
- Geburtsdaten von Kindern
- Schuldaten

**Arbeitsplatzdaten**
- Arbeitgeber
- Position/Titel
- Gehaltsinformationen
- Arbeitszeiten

**Bildungsdaten**
- Schulabschlüsse
- Universitätszugehörigkeit
- Noten/Bewertungen

### 3. Kontext-basierte Erkennung

#### 3.1 Kombinationsmuster

**Vollständige Identität**
- Name + Geburtsdatum + Adresse
- Name + E-Mail + Telefonnummer
- Name + IBAN + Steuer-ID

**Sensible Kombinationen**
- Gesundheitsdaten + Name
- Finanzdaten + Name
- Kinderdaten + Elternnamen

#### 3.2 Signalwörter-Erweiterung

**Medizinische Signalwörter**
```
Diagnose, Therapie, Medikament, Krankheit, Behandlung, Arzt, Klinik, 
Krankenhaus, Patient, Symptom, Operation, Rezept
```

**Finanzielle Signalwörter**
```
Gehalt, Lohn, Einkommen, Vermögen, Schulden, Kredit, Darlehen, 
Kontostand, Überweisung, Rechnung, Mahnung
```

**Rechtliche Signalwörter**
```
Klage, Anwalt, Gericht, Urteil, Vertrag, Vereinbarung, 
Einverständniserklärung, Datenschutzerklärung
```

**Bewerbungs-Signalwörter**
```
Lebenslauf, CV, Bewerbung, Referenz, Zeugnis, Arbeitszeugnis, 
Qualifikation, Erfahrung, Kompetenz
```

### 4. Metadaten-Analyse

#### 4.1 Datei-Metadaten

**EXIF-Daten in Bildern**
- GPS-Koordinaten
- Aufnahmedatum/-zeit
- Kameramodell
- Personen in Bildern (Face Recognition)

**Dokument-Metadaten**
- Autor
- Erstellungsdatum
- Letzte Änderung
- Revisionshistorie
- Kommentare/Anmerkungen

**E-Mail-Metadaten**
- Absender/Empfänger
- CC/BCC
- Betreff
- Anhänge
- Routing-Informationen

#### 4.2 Versteckte Daten

**Kommentare in Dokumenten**
- Word-Kommentare
- PDF-Anmerkungen
- Excel-Kommentare

**Track Changes**
- Änderungsverfolgung in Word
- Revisionshistorie

**Versteckte Spalten/Zeilen**
- Excel versteckte Daten
- Word versteckter Text

### 5. Statistische/Verhaltensmuster

#### 5.1 Anomalie-Erkennung

**Ungewöhnliche Datenmengen**
- Sehr große Dateien mit persönlichen Daten
- Ungewöhnlich viele PII-Funde in einem Dokument
- Konzentration von Daten an ungewöhnlichen Orten

**Zeitmuster**
- Ungewöhnliche Zugriffszeiten
- Häufige Änderungen an sensiblen Dokumenten

#### 5.2 Datenqualitäts-Indikatoren

**Vollständigkeit von Datensätzen**
- Fehlende Felder in strukturierten Daten
- Unvollständige Adressen
- Fehlende Validierung

**Datenkonsistenz**
- Widersprüchliche Informationen
- Alte/veraltete Daten
- Inkonsistente Formate

### 6. Externe Datenquellen

#### 6.1 Datenbank-Integration

**Have I Been Pwned API**
- E-Mail-Adressen gegen bekannte Datenlecks prüfen
- Passwörter gegen bekannte Kompromittierungen prüfen

**Adress-Validierung**
- Adressen gegen Postleitzahlen-Datenbanken validieren
- Plausibilitätsprüfung von Adressen

#### 6.2 Blacklist/Whitelist-Erweiterung

**Öffentliche Datenbanken**
- Öffentliche E-Mail-Domains (z.B. info@example.com)
- Testdaten-Patterns
- Beispiel-Daten

**Sensible Domains**
- Regierungsdomains
- Gesundheitswesen-Domains
- Finanzinstitute

### 7. Maschinelles Lernen

#### 7.1 Klassifizierung von Dokumenten

**Dokumenttyp-Klassifizierung**
- Bewerbungen
- Medizinische Dokumente
- Finanzdokumente
- Rechtliche Dokumente

**Sensibilitäts-Scoring**
- Automatische Bewertung der Sensibilität
- Risiko-Score für Dokumente

#### 7.2 Anomalie-Erkennung mit ML

**Ungewöhnliche Muster**
- Ungewöhnliche Datenkombinationen
- Anomalien in Datenstrukturen
- Verdächtige Dateinamen/Orte

### 8. Spezielle Dateiformate

#### 8.1 Datenbank-Dateien

**SQLite-Datenbanken**
- Tabellen mit personenbezogenen Daten
- SQL-Abfragen analysieren

**Access-Datenbanken (.mdb, .accdb)**
- Tabellenstruktur analysieren
- Datenbankinhalte extrahieren

#### 8.2 Backup-Archive

**ZIP/RAR/7Z-Archive**
- Archivierte Dokumente analysieren
- Passwort-geschützte Archive erkennen

**Backup-Dateien**
- .bak, .tmp, .old Dateien
- Automatische Backups

#### 8.3 Cloud-Exporte

**Google Takeout**
- JSON-Strukturen analysieren
- Metadaten extrahieren

**Facebook-Download**
- HTML-Strukturen analysieren
- Profildaten extrahieren

### 9. Implementierungs-Prioritäten

#### Phase 1: Schnelle Gewinne (Einfach, hohe Relevanz)
1. **Telefonnummern** (Regex)
2. **Steuer-ID** (Regex)
3. **Kreditkartennummern** (Regex mit Luhn-Check)
4. **Erweiterte Signalwörter** (Regex)
5. **BIC** (Regex)

#### Phase 2: Mittlere Komplexität (Mittel, hohe Relevanz)
1. **Erweiterte NER-Labels** (Biometrie, politische Überzeugungen)
2. **Kombinationsmuster** (Kontext-Erkennung)
3. **Metadaten-Analyse** (EXIF, Dokument-Metadaten)
4. **Postleitzahlen** (in Kontext)
5. **MAC-Adressen, IMEI**

#### Phase 3: Erweiterte Features (Komplex, mittlere Relevanz)
1. **ML-basierte Klassifizierung**
2. **Anomalie-Erkennung**
3. **Externe API-Integration**
4. **Datenbank-Dateien**
5. **Backup-Archive**

### 10. Technische Umsetzung

#### 10.1 Konfigurationsdatei-Erweiterung

Die `config_types.json` sollte erweitert werden um:

```json
{
  "regex": [
    // ... bestehende Einträge ...
    {
      "label": "REGEX_TAX_ID",
      "value": "Regex: Tax ID (Steuer-ID)",
      "regex_compiled_pos": 6,
      "expression": "\\b[0-9]{11}\\b",
      "context_keywords": ["Steuer-ID", "TIN", "IdNr", "Steueridentifikationsnummer"],
      "validation": "luhn" // optional
    }
  ],
  "ai-ner": [
    // ... bestehende Einträge ...
    {
      "label": "NER_BIOMETRIC",
      "value": "AI-NER: Biometric Data",
      "term": "Biometric Data"
    }
  ],
  "combinations": [
    {
      "name": "Complete Identity",
      "required_types": ["NER_PERSON", "REGEX_EMAIL", "REGEX_PHONE"],
      "min_matches": 2,
      "severity": "high"
    }
  ],
  "metadata": {
    "extract_exif": true,
    "extract_document_metadata": true,
    "extract_comments": true
  }
}
```

#### 10.2 Code-Struktur

**Neue Module:**
- `detectors/context_detector.py` - Kontext-basierte Erkennung
- `detectors/metadata_extractor.py` - Metadaten-Extraktion
- `detectors/combination_detector.py` - Kombinationsmuster
- `validators/` - Validierungs-Logik (Luhn, etc.)
- `external_apis/` - Externe API-Integrationen

**Erweiterte PiiMatch-Klasse:**
```python
@dataclass
class PiiMatch:
    text: str
    file: str
    type: str
    ner_score: float | None = None
    context: str | None = None  # Kontext, in dem gefunden
    combination_group: str | None = None  # Zugehörigkeit zu Kombination
    metadata: dict | None = None  # Zusätzliche Metadaten
    severity: str = "medium"  # low, medium, high, critical
```

### 11. Falsch-Positiv-Reduzierung

#### 11.1 Validierung

**Luhn-Algorithmus**
- Für Kreditkartennummern
- Für IMEI

**Format-Validierung**
- PLZ gegen gültige Bereiche
- Telefonnummern gegen Ländercodes
- IBAN-Prüfsumme (bereits vorhanden)

#### 11.2 Kontextprüfung

**Signalwörter in der Nähe**
- Steuer-ID nur wenn "Steuer" in der Nähe
- Kontonummer nur wenn "Konto" oder "Bank" in der Nähe

**Plausibilitätsprüfung**
- Geburtsdatum + Alter konsistent
- Adresse + PLZ konsistent
- Name + E-Mail-Domain konsistent

### 12. Performance-Überlegungen

#### 12.1 Optimierungen

**Regex-Kompilierung**
- Bereits implementiert ✓
- Weitere Optimierung: Regex-Gruppierung nach Häufigkeit

**NER-Batching**
- Größere Text-Chunks für bessere Performance
- Batch-Processing für mehrere Labels

**Caching**
- Validierungsergebnisse cachen
- Externe API-Aufrufe cachen

#### 12.2 Ressourcen-Management

**Memory-Management**
- Streaming für große Dateien
- Chunk-basierte Verarbeitung

**Parallelisierung**
- Multi-Threading für unabhängige Operationen
- Multi-Processing für CPU-intensive Tasks

### 13. Testing & Validierung

#### 13.1 Testdaten

**Synthetische Testdaten**
- Verschiedene PII-Typen
- Verschiedene Formate
- Edge Cases

**Realistische Szenarien**
- Typische Dokumente (Bewerbungen, Rechnungen, etc.)
- Verschiedene Dateiformate
- Verschiedene Sprachen

#### 13.2 Metriken

**Erkennungsrate (Recall)**
- Wie viele echte PII werden gefunden?

**Präzision (Precision)**
- Wie viele gefundene PII sind echt?

**F1-Score**
- Balance zwischen Recall und Precision

### 14. Datenschutz-Compliance

#### 14.1 GDPR/DSGVO-Kategorien

**Art. 9 DSGVO - Besondere Kategorien**
- Rassische/ethnische Herkunft
- Politische Meinungen
- Religiöse Überzeugungen
- Gewerkschaftszugehörigkeit
- Genetische Daten
- Biometrische Daten
- Gesundheitsdaten
- Sexuelle Orientierung

**Art. 10 DSGVO - Strafregisterdaten**
- Vorstrafen
- Gerichtsverfahren

#### 14.2 Risiko-Bewertung

**Automatische Risiko-Klassifizierung**
- Niedrig: Öffentliche Daten (Name, E-Mail)
- Mittel: Kontaktdaten (Adresse, Telefon)
- Hoch: Finanzdaten (IBAN, Kreditkarte)
- Kritisch: Besondere Kategorien (Gesundheit, Biometrie)

### 15. Dokumentation & Reporting

#### 15.1 Erweiterte Reports

**Kategorisierte Berichte**
- Nach PII-Typ
- Nach Sensibilität
- Nach Dateityp
- Nach Risiko-Level

**Trend-Analyse**
- Häufigste PII-Typen
- Dateien mit meisten PII
- Zeitliche Entwicklung

#### 15.2 Compliance-Reports

**GDPR-Mapping**
- Welche Artikel werden betroffen?
- Welche Kategorien sind vorhanden?
- Empfohlene Maßnahmen

## Fazit

Die vorgeschlagenen Erweiterungen würden das PII-Toolkit erheblich verbessern und eine umfassendere Erkennung datenschutzrelevanter Dimensionen ermöglichen. Die Priorisierung sollte sich an der Relevanz für Datenschutz-Compliance und der Implementierungskomplexität orientieren.

Die vorgeschlagenen Phasen ermöglichen eine schrittweise Implementierung, beginnend mit schnellen Gewinnen (Phase 1) und schrittweiser Erweiterung zu komplexeren Features (Phase 3).
