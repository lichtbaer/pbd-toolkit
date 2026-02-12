# Plan zur Verbesserung der Testabdeckung

**Stand:** 51% Gesamt-Coverage (Ziel: >80%)  
**Datum:** 12. Februar 2025  
**Projekt:** PII Toolkit

---

## 1. Ausgangslage

### 1.1 Aktuelle Teststruktur

- **173 Tests** in 24 Testdateien
- **172 bestanden**, 1 übersprungen (slow/integration)
- **Ziel:** >80% Code-Coverage (laut `tests/README.md`)

### 1.2 Coverage-Übersicht nach Modul

| Kategorie | Module | Aktuelle Coverage | Priorität |
|-----------|--------|-------------------|-----------|
| **0%** | `check_licenses.py`, `globals.py`, `main.py`, `setup.py` | 0% | Niedrig (optional) |
| **Sehr niedrig (<30%)** | `cli_setup.py` (18%), `core/cli.py` (13%), `core/config_loader.py` (26%) | 13–26% | Hoch |
| **Niedrig (30–50%)** | `core/processor.py` (64%), `core/scanner.py` (56%), `core/writers.py` (65%), `core/engines/pydantic_ai_engine.py` (47%), `core/engines/spacy_engine.py` (49%) | 47–65% | Hoch |
| **File Processors** | ical (27%), markdown (24%), mbox (18%), msg (26%), ods (38%), odt (33%), properties (29%), sqlite (21%), vcf (30%), xlsx (22%), xml (33%), zip (24%) | 18–38% | Mittel |
| **Hoch (>80%)** | `core/context.py`, `core/doctor.py`, `core/engines/*`, `core/statistics.py`, `core/statistics_aggregator.py`, `matches.py` | 80–100% | – |

---

## 2. Priorisierte Maßnahmen

### Phase 1: Quick Wins (Geschätzt: +5–8% Gesamt-Coverage)

#### 2.1 ConfigLoader (`core/config_loader.py` – 26%)

**Fehlende Tests:**
- `ConfigLoader.load_config()`: YAML-Laden, JSON-Laden, fehlende Datei, ungültiges Format, Datei nicht lesbar
- `ConfigLoader.merge_with_args()`: Merge-Logik, CLI hat Vorrang, Typer-Defaults werden überschrieben

**Vorschlag:** Neue Datei `tests/test_config_loader.py` mit:
- `test_load_config_yaml()` – gültige YAML-Datei
- `test_load_config_json()` – gültige JSON-Datei
- `test_load_config_file_not_found()` – ValueError
- `test_load_config_unsupported_format()` – .xml, .txt etc.
- `test_load_config_invalid_yaml()` – Parse-Fehler
- `test_merge_with_args_cli_precedence()` – CLI überschreibt Config
- `test_merge_with_args_config_fills_defaults()` – Config füllt Typer-Defaults
- `test_merge_with_args_boolean_strings()` – "true"/"false" als String

#### 2.2 File Processor Registry (`file_processors/registry.py` – 69%)

**Fehlende Tests:**
- `get_processor()` mit `file_path` und `mime_type` (3-Parameter-Signatur)
- `register_class()` 
- `get_all_processors()`
- `get_supported_extensions()`
- `clear()` (für Test-Isolation)
- Cache-Verhalten bei verschiedenen Parametern

**Vorschlag:** Erweiterung von `tests/test_file_type_detector.py` oder neue `tests/test_file_processor_registry.py`

#### 2.3 Scanner – fehlende Pfade (`core/scanner.py` – 56%)

**Nicht abgedeckt (laut Coverage):**
- Zeilen 110–117: Symlink-/Validierungslogik
- Zeilen 124, 148–156: `file_callback`-Fehlerbehandlung
- Zeilen 237–275: `stop_count`-Edge-Cases
- Zeilen 304–328: Magic-Detection-Pfad

**Vorschlag:** Erweiterung `tests/test_scanner.py`:
- `test_scan_with_symlinks()` – Symlinks ignorieren/handhaben
- `test_scan_callback_raises_exception()` – Fehler im Callback werden gefangen
- `test_scan_with_magic_detection_enabled()` – FileTypeDetector-Integration

---

### Phase 2: File Processors (Geschätzt: +3–5% Gesamt-Coverage)

#### 2.4 Processors mit sehr niedriger Coverage

| Processor | Coverage | Maßnahme |
|-----------|----------|----------|
| **sqlite_processor** | 21% | Test mit temporärer SQLite-DB aus `Testdaten/` oder synthetisch erstellt |
| **markdown_processor** | 24% | Einfache `.md`-Datei mit PII erstellen und `extract_text` testen |
| **zip_processor** | 24% | ZIP mit Text-Datei erstellen, Extraktion testen |
| **ical_processor** | 27% | Minimales iCal `.ics` mit VCALENDAR/VEVENT |
| **vcf_processor** | 30% | Einfache VCard 3.0/4.0 mit NAME, EMAIL |
| **xml_processor** | 33% | Einfache XML-Datei mit Text-Inhalt |
| **odt_processor** | 33% | Nutzung von `Testdaten/` falls ODT vorhanden, sonst Skip mit Hinweis |
| **ods_processor** | 38% | Nutzung von `Testdaten/` falls ODS vorhanden |
| **xlsx_processor** | 22% | Minimales XLSX mit openpyxl erstellen |
| **mbox_processor** | 18% | Mbox-Format (einfache Text-Datei mit From_-Zeilen) |
| **properties_processor** | 29% | Java-Properties-Datei `key=value` |

**Vorschlag:** Neue/erweiterte Tests in `tests/test_file_processors.py`:
- Für jeden Processor: mindestens `test_can_process_*` und `test_extract_text_*` (wo möglich)
- Nutzung von `Testdaten/synthetic_data_collection/` für echte Dateien
- Fixtures für ODT/ODS/XLSX/PPTX: minimale Dateien mit `python-pptx`, `openpyxl`, `odfpy` programmatisch erzeugen

---

### Phase 3: Core-Erweiterung (Geschätzt: +5–10% Gesamt-Coverage)

#### 2.5 Processor (`core/processor.py` – 64%)

**Fehlende Pfade:**
- Zeilen 180–184: Timeout-/Größen-Limit
- Zeilen 218–238: Engine-Wahl (Spacy, Ollama, OpenAI, PydanticAI)
- Zeilen 302–342: Chunking und parallele Verarbeitung
- Zeilen 355–385: Fehlerbehandlung

**Vorschlag:** Erweiterung `tests/test_processor.py`:
- `test_process_file_file_too_large()` – max_file_size_mb
- `test_process_text_with_spacy_ner()` – Mock Spacy
- `test_process_text_with_pydantic_ai()` – Mock PydanticAI
- `test_process_text_chunking()` – langer Text, Chunk-Grenzen

#### 2.6 Writers (`core/writers.py` – 65%)

**Fehlende Pfade:**
- Zeilen 82–95: JsonWriter-Fehlerbehandlung
- Zeilen 98–103: JsonWriter-`finalize`
- Zeilen 122–123: CsvWriter-`finalize` Edge-Case
- Zeilen 231–252: MarkdownWriter, HumanWriter

**Vorschlag:** Neue `tests/test_writers.py` oder Erweiterung `test_output_writers_streaming.py`:
- `test_csv_writer_finalize()` – Datei wird geschlossen
- `test_json_writer_io_error()` – Schreibfehler
- `test_markdown_writer()` – Formatierung
- `test_human_writer()` – Konsolenausgabe

#### 2.7 Config (`config.py` – 63%)

**Fehlende Zeilen:** 350–466, 482–483, 503, 506–507 (ausführliche Konfigurationslogik)

**Vorschlag:** Erweiterung `tests/test_config.py`:
- Tests für `from_args()` mit allen Engine-Flags (spacy_ner, ollama, openai_compatible, pydantic_ai)
- Tests für `validate_file_path()` – Datei außerhalb Base-Pfad, Symbolic Links
- Tests für `load_whitelist()` – leere Liste, fehlende Datei

---

### Phase 4: CLI und Setup (Optional, Geschätzt: +2–4%)

#### 2.8 CLI (`core/cli.py` – 13%)

**Strategie:** CLI-Tests sind aufwendig (Typer, Side Effects). Empfehlung:
- `tests/test_cli.py`: `typer.testing.CliRunner` für Hauptbefehle `scan`, `doctor`
- Mindestens: `test_scan_help()`, `test_scan_with_path()`, `test_version_callback()`

#### 2.9 cli_setup.py (18%)

- Tests für `setup_from_args()` – Konfiguration aus Args
- Tests für CSV-/JSON-Output-Setup

---

### Phase 5: Optional / Ausschluss

| Modul | Begründung |
|-------|------------|
| `check_licenses.py` | Lizenzprüfung, oft manuell/CI-spezifisch |
| `globals.py` | Vermutlich nur Konstanten/Imports |
| `main.py` | Entry Point, wird indirekt über CLI getestet |
| `setup.py` | Build-Script, schwer sinnvoll zu testen |

**Empfehlung:** In `.coveragerc` optional excluden oder pragma `no cover` setzen, wenn Coverage-Ziel nicht erreicht wird.

---

## 3. Umsetzungsreihenfolge

| Reihenfolge | Aufgabe | Geschätzter Aufwand | Erwarteter Impact |
|-------------|---------|---------------------|-------------------|
| 1 | ConfigLoader-Tests | 1–2 h | +2% |
| 2 | File Processor Registry | 1 h | +1% |
| 3 | Scanner-Erweiterung | 1 h | +1% |
| 4 | File Processors (Markdown, SQLite, ZIP, XML, VCF, iCal, Properties, Mbox) | 3–4 h | +3–4% |
| 5 | Writers-Tests | 1–2 h | +2% |
| 6 | Processor-Erweiterung | 2 h | +2% |
| 7 | Config-Erweiterung | 1–2 h | +2% |
| 8 | CLI-Tests (optional) | 2–3 h | +2% |

**Gesamtschätzung:** 12–17 Stunden für ~80% Coverage

---

## 4. Technische Hinweise

### 4.1 Fixtures und Testdaten

- `conftest.py`: `mock_config` erweitern um `use_magic_detection=True`, `use_spacy_ner=True` etc.
- `Testdaten/synthetic_data_collection/`: Vorhandene JSON, MD, CSV für Integrationstests nutzen
- Temporäre Dateien: `tempfile.NamedTemporaryFile` oder `temp_dir`-Fixture für SQLite, ZIP, XML, etc.

### 4.2 Abhängigkeiten

- `extract_msg` (MSG): Optional, mit Mock testen
- `python-pptx` (PPTX): Für echte PPTX-Tests
- `openpyxl` (XLSX): Für echte XLSX-Tests
- `odfpy` (ODT/ODS): Für echte ODF-Tests

### 4.3 Markierungen

- `@pytest.mark.slow` für Tests mit echten Modellen oder großen Dateien
- `@pytest.mark.integration` für End-to-End-Szenarien
- `pytest -m "not slow and not integration"` für schnelle Läufe

---

## 5. Erfolgskriterien

- [ ] Gesamt-Coverage ≥ 80%
- [ ] Alle `core/*`-Module (außer optional) ≥ 70%
- [ ] Alle `file_processors/*` mit mindestens `can_process` + `extract_text` (wo sinnvoll) getestet
- [ ] CI läuft weiterhin grün mit `pytest -q`
- [ ] Keine neuen Flaky-Tests

---

## Anhang: Coverage-Details (Stand der Analyse)

```
TOTAL                                      3654   1787    51%
```

Auffällige Lücken:
- `core/cli.py`: 39–44, 49–50, 79–970 (nahezu vollständig ungetestet)
- `core/config_loader.py`: 74–97, 115–190
- `file_processors/sqlite_processor.py`: 29–118
- `file_processors/markdown_processor.py`: 28–82
- `file_processors/xlsx_processor.py`: 30–62, 94–126
