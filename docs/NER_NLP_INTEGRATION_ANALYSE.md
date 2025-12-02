# NER/NLP Integration - Architektur-Analyse

## Übersicht

Das Tool verwendet **GLiNER** (Generalist and Lightweight model for Named Entity Recognition) für die KI-basierte Erkennung von personenbezogenen Informationen (PII). Die Integration ist modular aufgebaut und arbeitet parallel zur regex-basierten Erkennung.

## Technologie-Stack

### Verwendete Bibliothek
- **GLiNER** (`gliner~=0.2.22`)
  - Modell: `urchade/gliner_medium-v2.1` (von HuggingFace)
  - Generalistisches NER-Modell für verschiedene Entity-Typen

### Modell-Details
- **Modellname**: `urchade/gliner_medium-v2.1`
- **Threshold**: `0.5` (Standard, konfigurierbar in `config_types.json`)
- **Download**: Via HuggingFace CLI (`hf download urchade/gliner_medium-v2.1`)

## Architektur

### 1. Konfiguration (`config.py`)

Die NER-Integration wird über die `Config`-Klasse verwaltet:

```python
@dataclass
class Config:
    use_ner: bool                    # Aktivierung via CLI-Flag --ner
    ner_model: GLiNER | None         # GLiNER-Modellinstanz
    ner_labels: list[str]            # Liste der zu erkennenden Entity-Typen
```

**Initialisierung:**
- Das Modell wird nur geladen, wenn `use_ner=True` gesetzt ist
- Lazy Loading: `_load_ner_model()` wird nur bei Bedarf aufgerufen
- Fehlerbehandlung: Bei Fehlern wird `ner_model=None` gesetzt

**Modell-Loading:**
```python
def _load_ner_model(self) -> None:
    self.ner_model = GLiNER.from_pretrained(constants.NER_MODEL_NAME)
    # Labels werden aus config_types.json geladen
    self.ner_labels = [c["term"] for c in ner_config]
```

### 2. Entity-Typen (`config_types.json`)

Vier vordefinierte Entity-Typen werden erkannt:

```json
"ai-ner": [
    {
        "label": "NER_PERSON",
        "value": "AI-NER: Person",
        "term": "Person's Name"
    },
    {
        "label": "NER_LOCATION",
        "value": "AI-NER: Location",
        "term": "Location"
    },
    {
        "label": "NER_HEALTH",
        "value": "AI-NER: Health Data (experimental)",
        "term": "Health Data"
    },
    {
        "label": "NER_PASSWORD",
        "value": "AI-NER: Passwords (experimental)",
        "term": "Password"
    }
]
```

**Mapping:**
- `term`: Wird an GLiNER übergeben (z.B. "Person's Name")
- `label`: Interne ID (z.B. "NER_PERSON")
- `value`: Anzeige-Label (z.B. "AI-NER: Person")

### 3. Verarbeitung (`main.py`)

**Text-Verarbeitung:**
```python
def process_text(text: str, file_path: str, pmc: PiiMatchContainer, config: Config):
    if config.use_ner and config.ner_model:
        entities = config.ner_model.predict_entities(
            text, 
            config.ner_labels, 
            threshold=constants.NER_THRESHOLD
        )
        with _process_lock:
            pmc.add_matches_ner(entities, file_path)
```

**Eigenschaften:**
- Thread-safe: Verwendung von `_process_lock` für parallele Verarbeitung
- Pro Text-Chunk wird `predict_entities()` aufgerufen
- PDFs werden in Chunks verarbeitet (für große Dateien)

### 4. Match-Verwaltung (`matches.py`)

**PiiMatch-Dataclass:**
```python
@dataclass
class PiiMatch:
    text: str
    file: str
    type: str
    ner_score: float | None = None  # Confidence-Score vom Modell
```

**Match-Hinzufügung:**
```python
def add_matches_ner(self, matches: list[dict] | None, path: str):
    if matches is not None:
        for match in matches:
            type = config_ainer_sorted[match["label"]]["label"]
            self.__add_match(
                text=match["text"], 
                file=path, 
                type=type, 
                ner_score=match["score"]
            )
```

**GLiNER-Output-Format:**
```python
matches = [
    {
        "text": "John Doe",      # Gefundener Text
        "label": "Person's Name", # GLiNER-Label
        "score": 0.95            # Confidence-Score
    },
    ...
]
```

## Datenfluss

```
1. CLI: --ner Flag gesetzt
   ↓
2. Config.from_args(): use_ner=True
   ↓
3. Config._load_ner_model():
   - GLiNER.from_pretrained("urchade/gliner_medium-v2.1")
   - Labels aus config_types.json laden
   ↓
4. main.py: process_text()
   - config.ner_model.predict_entities(text, labels, threshold=0.5)
   ↓
5. matches.py: add_matches_ner()
   - Mapping: GLiNER-Label → Interne Label-ID
   - PiiMatch mit ner_score erstellen
   ↓
6. Output: CSV/JSON/XLSX mit ner_score-Spalte
```

## Thread-Safety

- **Modell-Instanz**: Eine einzige `GLiNER`-Instanz wird von allen Threads geteilt
- **Synchronisation**: `_process_lock` schützt `pmc.add_matches_ner()`
- **Potenzielle Probleme**: GLiNER-Modell könnte nicht thread-safe sein (siehe `PERFORMANCE_OPTIMIZATIONS.md`)

## Output-Formate

### CSV
```csv
match,file,type,ner_score
John Doe,/path/file.txt,AI-NER: Person,0.95
```

### JSON
```json
{
    "match": "John Doe",
    "file": "/path/file.txt",
    "type": "AI-NER: Person",
    "ner_score": 0.95
}
```

### XLSX
- Spalte 4: NER Score (leer für Regex-Matches)

## Validierung

- Mindestens eines von `--regex` oder `--ner` muss aktiviert sein
- Modell-Loading-Fehler werden geloggt, aber stoppen nicht die Ausführung
- Bei fehlendem Modell: `ner_model=None`, NER wird übersprungen

## Konfiguration

### Constants (`constants.py`)
```python
NER_MODEL_NAME: str = "urchade/gliner_medium-v2.1"
NER_THRESHOLD: float = 0.5
```

### Konfigurationsdatei (`config_types.json`)
```json
{
    "settings": {
        "ner_threshold": 0.5
    },
    "ai-ner": [...]
}
```

**Hinweis**: Der Threshold in `config_types.json` wird aktuell nicht verwendet, stattdessen wird `constants.NER_THRESHOLD` verwendet.

## Performance-Überlegungen

### Aktuelle Implementierung
- **Sequentiell**: Jeder Text-Chunk wird einzeln verarbeitet
- **Kein Batching**: GLiNER wird pro Chunk aufgerufen
- **Keine GPU-Unterstützung**: Läuft auf CPU

### Potenzielle Optimierungen (siehe `PERFORMANCE_OPTIMIZATIONS.md`)
1. **Batch-Processing**: Mehrere Text-Chunks zusammen verarbeiten
2. **GPU-Acceleration**: Falls GLiNER GPU unterstützt
3. **Thread-Safety-Prüfung**: Testen ob Modell thread-safe ist

## Fehlerbehandlung

```python
try:
    self.ner_model = GLiNER.from_pretrained(constants.NER_MODEL_NAME)
    # ...
except Exception as e:
    self.logger.error(f"Failed to load NER model: {e}")
    self.ner_model = None
    self.ner_labels = []
```

- Fehler beim Modell-Loading: Logging, aber keine Exception
- Bei `ner_model=None`: NER wird übersprungen, Regex läuft weiter

## Tests

**Test-Abdeckung** (`tests/test_matches.py`):
- `test_create_pii_match_with_ner_score`: NER-Score wird korrekt gespeichert
- `test_add_matches_ner_none`: None-Handling
- `test_add_matches_ner_empty_list`: Leere Liste-Handling

**Fehlende Tests:**
- Integrationstests mit echtem GLiNER-Modell
- Thread-Safety-Tests
- Threshold-Tests

## Abhängigkeiten

### Direkte Abhängigkeiten
- `gliner~=0.2.22`: NER-Bibliothek
- `huggingface_hub`: Für Modell-Download (optional, via CLI)

### Indirekte Abhängigkeiten
- Transformers (via GLiNER)
- PyTorch (via GLiNER)

## Zusammenfassung

**Stärken:**
- ✅ Modulare Architektur
- ✅ Lazy Loading des Modells
- ✅ Thread-safe Match-Verwaltung
- ✅ Flexible Entity-Typen-Konfiguration
- ✅ Fehlerbehandlung ohne Programm-Abbruch

**Verbesserungspotenzial:**
- ⚠️ Thread-Safety des GLiNER-Modells unklar
- ⚠️ Kein Batch-Processing
- ⚠️ Threshold aus `config_types.json` wird nicht verwendet
- ⚠️ Begrenzte Test-Abdeckung für NER-Funktionalität
- ⚠️ Keine GPU-Unterstützung konfiguriert
