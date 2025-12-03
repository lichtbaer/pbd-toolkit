# Verbesserungs-Checkliste

## Sofort umsetzbar (Quick Wins)

### Code-Qualität
- [ ] **Type Hints vervollständigen**: Alle Funktionen sollten vollständige Type Hints haben
  - Dateien: `main.py`, `matches.py`, `setup.py`
  - `Any` durch konkrete Types ersetzen
  
- [ ] **Custom Exception Types**: Statt generischer Exceptions
  ```python
  class PiiToolkitError(Exception): pass
  class ConfigurationError(PiiToolkitError): pass
  class ProcessingError(PiiToolkitError): pass
  ```

- [ ] **Magic Numbers/Strings eliminieren**: Alle in `constants.py` verschieben
  - Beispiel: `500.0` (max_file_size_mb) bereits in Config, aber andere Magic Values prüfen

- [ ] **Dokumentation auf Englisch**: Code-Kommentare sollten Englisch sein (laut User Rules)
  - Aktuell teilweise Deutsch in Kommentaren

### CLI-Verbesserungen
- [ ] **Exit Codes dokumentieren**: In README und Code-Kommentaren
  ```python
  # Exit codes:
  # 0: Success
  # 1: General error
  # 2: Invalid arguments
  # 3: File access error
  # 4: Configuration error
  ```

- [ ] **Quiet-Mode hinzufügen**: `-q, --quiet` Flag
  ```python
  parser.add_argument('-q', '--quiet', action='store_true',
                     help='Suppress all output except errors')
  ```

- [ ] **Config-File-Support**: YAML/JSON Config-File für CLI-Argumente
  ```python
  parser.add_argument('--config', type=Path,
                     help='Path to configuration file')
  ```

- [ ] **Structured Output**: Machine-readable Output-Format
  ```python
  parser.add_argument('--output-format', 
                     choices=['human', 'json', 'yaml'],
                     default='human')
  ```

---

## Kurzfristig (1-2 Wochen)

### Architektur-Refactoring
- [ ] **Output-Writer extrahieren**: Separate Module für CSV/JSON/XLSX Writer
  - Neue Datei: `output/writers.py`
  - Interface: `OutputWriter(ABC)`
  - Implementierungen: `CsvWriter`, `JsonWriter`, `XlsxWriter`
  - Aus `main.py` entfernen (Zeilen 422-527)

- [ ] **Scanner-Logik extrahieren**: File-Walking in separates Modul
  - Neue Datei: `core/scanner.py`
  - Klasse: `FileScanner`
  - Methode: `scan(path: str) -> ScanResult`

- [ ] **Processor-Logik extrahieren**: Text-Processing in separates Modul
  - Neue Datei: `core/processor.py`
  - Klasse: `TextProcessor`
  - Methode: `process_text(text: str, file_path: str) -> list[PiiMatch]`

- [ ] **Statistics-Tracking extrahieren**: In separates Modul
  - Neue Datei: `core/statistics.py`
  - Klasse: `Statistics` (erweitert `NerStats`)

### Dependency Management
- [ ] **Application Context einführen**: Ersetzt `globals.py`
  - Neue Datei: `core/context.py`
  - Klasse: `ApplicationContext` (dataclass)
  - Enthält: config, logger, output_writer, statistics, error_collector
  - Factory-Method: `from_cli_args(args) -> ApplicationContext`

- [ ] **globals.py eliminieren**: Alle Verwendungen durch Context ersetzen
  - Suche nach `import globals` oder `globals.`
  - Ersetze durch Context-Injection

---

## Mittelfristig (1 Monat)

### Erweiterte Features
- [ ] **Plugin-System**: Entry Points für File Processors
  - `setup.py` erweitern mit `entry_points`
  - Auto-Discovery von Processors
  - Dokumentation für Plugin-Entwicklung

- [ ] **Event-System**: Event-basierte Architektur
  - Neue Datei: `core/events.py`
  - Klasse: `EventBus`
  - Events: `FileProcessed`, `MatchFound`, `ErrorOccurred`
  - Ermöglicht Hooks und Plugins

- [ ] **Logging-Strukturierung**: Structured Logging
  - JSON-Format optional
  - Context-Informationen in Logs
  - Konsistente Log-Level

### Testing
- [ ] **Integration Tests erweitern**: End-to-End Tests
  - Typische Use Cases abdecken
  - Verschiedene File-Formate testen
  - Performance-Tests

- [ ] **Test-Coverage messen**: Aktuelle Coverage ermitteln
  ```bash
  pytest --cov=. --cov-report=html
  ```
  - Ziel: > 80% Coverage

- [ ] **Mocking-Strategien**: Dependency Injection für besseres Mocking
  - Factory-Pattern für schwer mockbare Dependencies
  - Test-Doubles für File I/O

---

## Langfristig (Optional)

### Erweiterte Architektur
- [ ] **Subcommands**: Für komplexere CLI-Struktur
  ```python
  python main.py scan --path ...
  python main.py validate --config ...
  python main.py export --format json
  ```

- [ ] **API-Mode**: REST API für Tool (optional)
  - Flask/FastAPI Integration
  - Separate `api/` Module

- [ ] **Docker-Image**: Containerisierung
  - `Dockerfile` erstellen
  - Docker Compose für Development

- [ ] **CI/CD Pipeline**: Automatisierte Tests und Releases
  - GitHub Actions / GitLab CI
  - Automatische Tests bei Commits
  - Automatische Releases bei Tags

---

## Code-Review Checkliste

### Vor jedem Commit
- [ ] Type Hints vorhanden?
- [ ] Docstrings vorhanden (auf Englisch)?
- [ ] Keine Magic Numbers/Strings?
- [ ] Error Handling vorhanden?
- [ ] Tests geschrieben/aktualisiert?
- [ ] Keine globalen Variablen (außer Constants)?
- [ ] Logging statt print()?
- [ ] Code-Formatierung konsistent?

### Vor größeren Refactorings
- [ ] Tests vorhanden für betroffene Bereiche?
- [ ] Backup/Commit vor Refactoring?
- [ ] Schrittweise Refactoring (nicht alles auf einmal)?
- [ ] Tests nach jedem Schritt?

---

## Metriken-Tracking

### Regelmäßig messen
- [ ] **Code-Größe**: Größte Datei sollte < 200 Zeilen sein
- [ ] **Komplexität**: Zyklomatische Komplexität < 10 pro Funktion
- [ ] **Test-Coverage**: > 80%
- [ ] **Globale Variablen**: 0 (außer Constants)
- [ ] **Import-Zyklen**: Keine zirkulären Abhängigkeiten

### Tools
```bash
# Code-Complexity
radon cc . --min B

# Test Coverage
pytest --cov=. --cov-report=term-missing

# Type Checking
mypy .

# Linting
pylint .
flake8 .
```

---

## Priorisierung

### 🔴 Hoch (Sofort)
1. Output-Writer extrahieren
2. Custom Exception Types
3. Exit Codes dokumentieren
4. Quiet-Mode hinzufügen

### 🟡 Mittel (Diese Woche)
1. Scanner/Processor-Logik extrahieren
2. Application Context einführen
3. Config-File-Support
4. Type Hints vervollständigen

### 🟢 Niedrig (Nächster Monat)
1. Plugin-System
2. Event-System
3. Structured Logging
4. Erweiterte Tests

---

**Hinweis**: Diese Checkliste sollte regelmäßig aktualisiert werden, wenn Verbesserungen umgesetzt werden.
