# Verbesserungsvorschläge für das PII-Toolkit

## 1. Code-Organisation und Architektur

### 1.1 Modularisierung
**Problem**: `main.py` enthält zu viel Logik (240 Zeilen) und ist schwer wartbar.

**Vorschlag**:
- Datei-Extraktion in separate Module auslagern:
  - `file_processors/pdf_processor.py`
  - `file_processors/docx_processor.py`
  - `file_processors/html_processor.py`
  - `file_processors/text_processor.py`
- Gemeinsame Basisklasse `BaseFileProcessor` für alle Prozessoren
- Factory-Pattern für die Auswahl des richtigen Prozessors

### 1.2 Globale Variablen reduzieren
**Problem**: `globals.py` enthält viele globale Variablen, die schwer zu testen sind.

**Vorschlag**:
- Dependency Injection verwenden
- Konfigurationsobjekt erstellen (`Config`-Klasse)
- Logger und CSV-Writer als Parameter übergeben statt global zu nutzen

### 1.3 Code-Duplikation eliminieren
**Problem**: Regex- und NER-Matching wird für jeden Dateityp wiederholt.

**Vorschlag**:
```python
def process_text(text: str, file_path: str, config: Config) -> None:
    """Process text content with regex and/or NER."""
    if config.use_regex:
        matches = config.regex_all.search(text)
        pmc.add_matches_regex(matches, file_path)
    
    if config.use_ner:
        entities = config.ner_model.predict_entities(
            text, config.ner_labels, threshold=0.5
        )
        pmc.add_matches_ner(entities, file_path)
```

## 2. Performance-Optimierungen

### 2.1 Whitelist-Performance
**Problem**: TODO-Kommentar in `matches.py:70` - Whitelist-Check ist ineffizient.

**Vorschlag**:
```python
# Whitelist als Set für O(1) Lookups
self.whitelist_set = set(self.whitelist)

# Oder als kompilierte Regex für Pattern-Matching
if self.whitelist:
    whitelist_pattern = re.compile(
        "|".join(re.escape(word) for word in self.whitelist)
    )
    if whitelist_pattern.search(text):
        return  # Skip whitelisted matches
```

### 2.2 Model-Lazy-Loading
**Problem**: NER-Model wird geladen, auch wenn `--ner` nicht aktiviert ist.

**Vorschlag**: Model erst beim ersten Gebrauch laden (Lazy Loading).

### 2.3 Batch-Processing für große Dateien
**Problem**: Große Dateien werden komplett in den Speicher geladen.

**Vorschlag**: Streaming-Processing für große Dateien implementieren.

## 3. Fehlerbehandlung

### 3.1 Spezifische Exception-Handling
**Problem**: Zu generische `except Exception` Blöcke.

**Vorschlag**:
```python
except docx.opc.exceptions.PackageNotFoundError:
    add_error("DOCX Empty Or Protected", full_path)
except PermissionError:
    add_error("Permission denied", full_path)
except FileNotFoundError:
    add_error("File not found", full_path)
except Exception as excpt:
    add_error(f"Unexpected error: {type(excpt).__name__}: {str(excpt)}", full_path)
```

### 3.2 Validierung der Eingabeparameter
**Problem**: Keine Validierung, ob `--path` existiert oder lesbar ist.

**Vorschlag**:
```python
if not os.path.exists(globals.args.path):
    exit(globals._("Path does not exist: {}").format(globals.args.path))
if not os.path.isdir(globals.args.path):
    exit(globals._("Path is not a directory: {}").format(globals.args.path))
```

## 4. Code-Qualität

### 4.1 Type Hints vervollständigen
**Problem**: Nicht alle Funktionen haben vollständige Type Hints.

**Vorschlag**: Alle Funktionen mit vollständigen Type Hints versehen.

### 4.2 Docstrings
**Problem**: Viele Funktionen haben keine oder unvollständige Docstrings.

**Vorschlag**: Google-Style oder NumPy-Style Docstrings für alle öffentlichen Funktionen.

### 4.3 Magic Numbers/Strings eliminieren
**Problem**: Hardcoded Werte wie `threshold=0.5`, `len(text) < 10`.

**Vorschlag**: In Konfigurationsdatei oder als Konstanten definieren.

## 5. Ressourcen-Management

### 5.1 File Handles schließen
**Problem**: CSV-Datei wird geöffnet, aber nie explizit geschlossen.

**Vorschlag**:
```python
with open("./output/" + outslug + "_findings.csv", "w") as outf:
    globals.csvwriter = csv.writer(outf)
    # ... processing ...
# File wird automatisch geschlossen
```

Oder Context Manager für die gesamte Ausführung verwenden.

### 5.2 Memory Management
**Problem**: Potenzielle Memory-Leaks bei großen Dateien.

**Vorschlag**: Explizites Cleanup und Memory-Monitoring für große Operationen.

## 6. Testing

### 6.1 Unit Tests
**Problem**: Keine Tests vorhanden.

**Vorschlag**:
- `tests/test_file_processors.py` - Tests für Datei-Prozessoren
- `tests/test_matches.py` - Tests für PII-Matching
- `tests/test_whitelist.py` - Tests für Whitelist-Funktionalität
- `tests/fixtures/` - Test-Dateien (PDF, DOCX, HTML, TXT)

### 6.2 Integration Tests
**Vorschlag**: End-to-End Tests mit Beispiel-Daten.

## 7. Logging und Monitoring

### 7.1 Progress Indication
**Problem**: Keine Fortschrittsanzeige bei langen Analysen.

**Vorschlag**:
- Progress Bar (z.B. mit `tqdm`)
- ETA (Estimated Time of Arrival)
- Verarbeitungsgeschwindigkeit in Echtzeit

### 7.2 Strukturiertes Logging
**Problem**: Logging verwendet nur `logging.INFO`.

**Vorschlag**:
- Verschiedene Log-Level (DEBUG, INFO, WARNING, ERROR)
- Strukturiertes Logging (JSON-Format für bessere Analyse)
- Separate Log-Dateien für verschiedene Kategorien

## 8. Konfiguration

### 8.1 Konfigurationsdatei erweitern
**Problem**: Viele Einstellungen sind hardcoded.

**Vorschlag**: Erweiterte `config.json` mit:
- NER-Threshold
- Minimale Textlänge für PDFs
- Unterstützte Dateitypen
- Logging-Einstellungen

### 8.2 Environment Variables
**Vorschlag**: Unterstützung für Konfiguration via Environment Variables.

## 9. Dokumentation

### 9.1 API-Dokumentation
**Vorschlag**: Sphinx oder ähnliches für automatische API-Dokumentation.

### 9.2 Code-Kommentare
**Problem**: Einige komplexe Stellen haben keine Kommentare.

**Vorschlag**: Kommentare für komplexe Algorithmen (z.B. Regex-Kompilierung).

## 10. Sicherheit

### 10.1 Path Traversal Protection
**Problem**: Keine Validierung gegen Path Traversal-Angriffe.

**Vorschlag**: Validierung von Dateipfaden.

### 10.2 Resource Limits
**Problem**: Keine Limits für Dateigröße oder Verarbeitungszeit.

**Vorschlag**: Konfigurierbare Limits für:
- Maximale Dateigröße
- Maximale Verarbeitungszeit pro Datei
- Maximale Gesamtspeichernutzung

## 11. Benutzerfreundlichkeit

### 11.1 CLI-Verbesserungen
**Vorschlag**:
- Farbige Ausgabe für bessere Lesbarkeit
- Verbose-Modus für detaillierte Informationen
- Dry-Run-Modus zum Testen

### 11.2 Output-Formate
**Vorschlag**: Unterstützung für weitere Output-Formate:
- JSON
- XML
- HTML-Report

## 12. Wartbarkeit

### 12.1 Code-Formatierung
**Vorschlag**: 
- `black` für Code-Formatierung
- `isort` für Import-Sortierung
- Pre-commit Hooks

### 12.2 Linting
**Vorschlag**: 
- `pylint` oder `ruff` für Code-Qualität
- `mypy` für Type-Checking
- CI/CD Integration

## 13. Spezifische Code-Verbesserungen

### 13.1 matches.py Zeile 98
**Problem**: `type: PiiMatch.PiiMatchType | None = None` - `PiiMatchType` existiert nicht.

**Vorschlag**: Korrektur zu `type: str | None = None`

### 13.2 main.py Zeile 222
**Problem**: List Comprehension für Side-Effects (Logging).

**Vorschlag**: Normale Schleife verwenden:
```python
for k, v in sorted(exts_found.items(), key=lambda item: item[1], reverse=True):
    globals.logger.info("{:>10}: {:>10} Dateien".format(k, v))
```

### 13.3 main.py Zeile 234
**Problem**: `.encode("utf-8", "replace")` auf String - sollte nicht nötig sein.

**Vorschlag**: Entfernen oder durch bessere Fehlerbehandlung ersetzen.

## Priorisierung

### Hoch (Sofort umsetzbar):
1. File Handles schließen (5.1)
2. Code-Duplikation eliminieren (1.3)
3. Whitelist-Performance (2.1)
4. Spezifische Exception-Handling (3.1)
5. Bug-Fix matches.py Zeile 98 (13.1)

### Mittel (Nächste Iteration):
1. Modularisierung (1.1)
2. Unit Tests (6.1)
3. Progress Indication (7.1)
4. Validierung der Eingabeparameter (3.2)

### Niedrig (Langfristig):
1. API-Dokumentation (9.1)
2. Erweiterte Output-Formate (11.2)
3. CI/CD Integration (12.2)
