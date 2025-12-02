# NER/NLP Integration - Verbesserungsvorschläge

## Übersicht

Dieses Dokument enthält konkrete, umsetzbare Verbesserungsvorschläge für die NER/NLP-Integration basierend auf der aktuellen Architektur-Analyse.

## Priorisierung

- 🔴 **Hoch**: Kritische Verbesserungen für Stabilität und Korrektheit
- 🟡 **Mittel**: Wichtige Performance- und Funktionalitätsverbesserungen
- 🟢 **Niedrig**: Nice-to-have Features und Optimierungen

---

## 🔴 Hoch-Priorität

### 1. Thread-Safety des GLiNER-Modells prüfen und absichern

**Problem**: 
- GLiNER-Modell wird von mehreren Threads geteilt (wenn parallel processing implementiert wird)
- Unklar ob `predict_entities()` thread-safe ist
- Potenzielle Race Conditions bei gleichzeitiger Nutzung

**Lösung**:
```python
# Option 1: Thread-Lock für NER-Verarbeitung
_ner_lock = threading.Lock()

def process_text(text: str, file_path: str, pmc: PiiMatchContainer, config: Config) -> None:
    if config.use_ner and config.ner_model:
        with _ner_lock:  # Serialisiere NER-Aufrufe
            entities = config.ner_model.predict_entities(
                text, config.ner_labels, threshold=constants.NER_THRESHOLD
            )
        with _process_lock:
            pmc.add_matches_ner(entities, file_path)

# Option 2: Modell pro Thread (wenn Modell nicht thread-safe)
# Modell-Cloning oder separate Instanzen pro Worker-Thread
```

**Implementierung**:
- Test-Suite erstellen für Thread-Safety
- Benchmark mit paralleler Verarbeitung
- Dokumentation der Thread-Safety-Annahme

**Dateien**: `main.py`, `config.py`

---

### 2. Threshold-Konfiguration aus config_types.json nutzen

**Problem**: 
- Threshold wird aus `constants.NER_THRESHOLD` (0.5) verwendet
- Threshold in `config_types.json` wird ignoriert
- Keine Möglichkeit, Threshold pro Entity-Typ zu setzen

**Lösung**:
```python
# config.py
def _load_ner_model(self) -> None:
    """Load NER model and labels."""
    try:
        self.ner_model = GLiNER.from_pretrained(constants.NER_MODEL_NAME)
        
        with open(constants.CONFIG_FILE) as f:
            config_data = json.load(f)
        
        ner_config = config_data.get("ai-ner", [])
        self.ner_labels = [c["term"] for c in ner_config]
        
        # Load threshold from config, fallback to constant
        settings = config_data.get("settings", {})
        self.ner_threshold = settings.get("ner_threshold", constants.NER_THRESHOLD)
        
        # Optional: Per-entity thresholds
        self.ner_thresholds = {}
        for c in ner_config:
            if "threshold" in c:
                self.ner_thresholds[c["term"]] = c["threshold"]
    except Exception as e:
        self.logger.error(f"Failed to load NER model: {e}")
        self.ner_model = None
        self.ner_labels = []
        self.ner_threshold = constants.NER_THRESHOLD
```

**Erweiterte Konfiguration** (optional):
```json
{
    "ai-ner": [
        {
            "label": "NER_PERSON",
            "value": "AI-NER: Person",
            "term": "Person's Name",
            "threshold": 0.7  // Höherer Threshold für Personen
        },
        {
            "label": "NER_LOCATION",
            "value": "AI-NER: Location",
            "term": "Location",
            "threshold": 0.5  // Standard-Threshold
        }
    ]
}
```

**Dateien**: `config.py`, `main.py`, `config_types.json`

---

### 3. Fehlerbehandlung bei NER-Verarbeitung verbessern

**Problem**:
- Generisches `Exception`-Handling
- Fehler beim `predict_entities()` stoppen nicht die Verarbeitung, werden aber nicht geloggt
- Keine Unterscheidung zwischen temporären und permanenten Fehlern

**Lösung**:
```python
def process_text(text: str, file_path: str, pmc: PiiMatchContainer, config: Config) -> None:
    """Process text content with regex and/or NER-based PII detection."""
    if config.use_regex and config.regex_pattern:
        for match in config.regex_pattern.finditer(text):
            with _process_lock:
                pmc.add_matches_regex(match, file_path)
    
    if config.use_ner and config.ner_model:
        try:
            entities = config.ner_model.predict_entities(
                text, config.ner_labels, threshold=config.ner_threshold
            )
            with _process_lock:
                pmc.add_matches_ner(entities, file_path)
        except RuntimeError as e:
            # GPU/Model-spezifische Fehler
            config.logger.warning(f"NER processing error for {file_path}: {e}")
            add_error("NER processing error", file_path)
        except MemoryError as e:
            # Speicherprobleme
            config.logger.error(f"Out of memory during NER processing: {file_path}")
            add_error("NER memory error", file_path)
        except Exception as e:
            # Unerwartete Fehler
            config.logger.error(
                f"Unexpected NER error for {file_path}: {type(e).__name__}: {e}",
                exc_info=config.verbose
            )
            add_error(f"NER error: {type(e).__name__}", file_path)
```

**Dateien**: `main.py`

---

### 4. Modell-Loading-Fehler besser behandeln

**Problem**:
- Bei Modell-Loading-Fehler wird `ner_model=None` gesetzt
- Keine klare Meldung an den Benutzer
- Programm läuft weiter, obwohl NER nicht funktioniert

**Lösung**:
```python
def _load_ner_model(self) -> None:
    """Load NER model and labels."""
    try:
        self.logger.info("Loading NER model...")
        self.ner_model = GLiNER.from_pretrained(constants.NER_MODEL_NAME)
        self.logger.info(f"NER model loaded: {constants.NER_MODEL_NAME}")
        
        with open(constants.CONFIG_FILE) as f:
            config_data = json.load(f)
        
        ner_config = config_data.get("ai-ner", [])
        self.ner_labels = [c["term"] for c in ner_config]
        
        settings = config_data.get("settings", {})
        self.ner_threshold = settings.get("ner_threshold", constants.NER_THRESHOLD)
        
        if not self.ner_labels:
            self.logger.warning("No NER labels configured")
            
    except FileNotFoundError as e:
        error_msg = (
            f"NER model not found. Please download it first:\n"
            f"  hf download {constants.NER_MODEL_NAME}\n"
            f"Original error: {e}"
        )
        self.logger.error(error_msg)
        raise RuntimeError(error_msg) from e
    except ImportError as e:
        error_msg = (
            f"GLiNER library not installed. Install with:\n"
            f"  pip install gliner\n"
            f"Original error: {e}"
        )
        self.logger.error(error_msg)
        raise RuntimeError(error_msg) from e
    except Exception as e:
        error_msg = f"Failed to load NER model: {e}"
        self.logger.error(error_msg, exc_info=True)
        raise RuntimeError(error_msg) from e
```

**Dateien**: `config.py`, `main.py`

---

## 🟡 Mittel-Priorität

### 5. Batch-Processing für NER implementieren

**Problem**:
- Jeder Text-Chunk wird einzeln verarbeitet
- Ineffizient bei vielen kleinen Chunks
- GLiNER unterstützt möglicherweise Batch-Processing

**Lösung**:
```python
# Batch-Collector für NER-Verarbeitung
class NerBatchProcessor:
    def __init__(self, config: Config, batch_size: int = 10):
        self.config = config
        self.batch_size = batch_size
        self.batch: list[tuple[str, str]] = []  # [(text, file_path), ...]
        self._lock = threading.Lock()
    
    def add(self, text: str, file_path: str) -> None:
        """Add text to batch."""
        with self._lock:
            self.batch.append((text, file_path))
            if len(self.batch) >= self.batch_size:
                self._process_batch()
    
    def flush(self) -> None:
        """Process remaining items in batch."""
        with self._lock:
            if self.batch:
                self._process_batch()
    
    def _process_batch(self) -> None:
        """Process current batch."""
        if not self.batch or not self.config.ner_model:
            return
        
        texts = [item[0] for item in self.batch]
        file_paths = [item[1] for item in self.batch]
        
        try:
            # Batch prediction (wenn unterstützt)
            all_entities = self.config.ner_model.predict_entities(
                texts,  # Liste von Texten
                self.config.ner_labels,
                threshold=self.config.ner_threshold
            )
            
            # Entpacke Ergebnisse und füge Matches hinzu
            for entities, file_path in zip(all_entities, file_paths):
                with _process_lock:
                    pmc.add_matches_ner(entities, file_path)
        except Exception as e:
            # Fallback: Einzelne Verarbeitung
            for text, file_path in self.batch:
                try:
                    entities = self.config.ner_model.predict_entities(
                        text, self.config.ner_labels, threshold=self.config.ner_threshold
                    )
                    with _process_lock:
                        pmc.add_matches_ner(entities, file_path)
                except Exception as inner_e:
                    config.logger.warning(f"NER error for {file_path}: {inner_e}")
        
        self.batch.clear()

# Verwendung in main.py
ner_batch_processor = NerBatchProcessor(config, batch_size=10)

# In process_text():
if config.use_ner and config.ner_model:
    ner_batch_processor.add(text, file_path)

# Am Ende der Verarbeitung:
ner_batch_processor.flush()
```

**Hinweis**: Zuerst prüfen, ob GLiNER Batch-Processing unterstützt!

**Dateien**: `main.py` (neue Klasse), `config.py`

---

### 6. GPU-Unterstützung hinzufügen

**Problem**:
- NER-Verarbeitung läuft nur auf CPU
- GPU könnte Performance deutlich verbessern

**Lösung**:
```python
# config.py
def _load_ner_model(self) -> None:
    """Load NER model and labels."""
    try:
        import torch
        
        # Prüfe GPU-Verfügbarkeit
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        if device == "cuda":
            self.logger.info(f"Using GPU: {torch.cuda.get_device_name(0)}")
        else:
            self.logger.info("Using CPU for NER processing")
        
        self.ner_model = GLiNER.from_pretrained(
            constants.NER_MODEL_NAME,
            device=device  # Falls GLiNER device-Parameter unterstützt
        )
        
        # Oder nach dem Laden:
        if hasattr(self.ner_model, 'to'):
            self.ner_model = self.ner_model.to(device)
        
        # ...
    except Exception as e:
        # ...
```

**Konfiguration**:
```python
# constants.py oder config_types.json
FORCE_CPU: bool = False  # Option zum Erzwingen von CPU
```

**Dateien**: `config.py`, `constants.py`

---

### 7. NER-Performance-Metriken hinzufügen

**Problem**:
- Keine Metriken über NER-Performance
- Unklar, wie lange NER-Verarbeitung dauert
- Keine Statistiken über gefundene Entities

**Lösung**:
```python
# config.py
@dataclass
class NerStats:
    """Statistics for NER processing."""
    total_chunks_processed: int = 0
    total_entities_found: int = 0
    total_processing_time: float = 0.0
    entities_by_type: dict[str, int] = field(default_factory=dict)
    errors: int = 0

# In Config-Klasse:
ner_stats: NerStats = field(default_factory=NerStats)

# In process_text():
import time

if config.use_ner and config.ner_model:
    start_time = time.time()
    try:
        entities = config.ner_model.predict_entities(...)
        processing_time = time.time() - start_time
        
        config.ner_stats.total_chunks_processed += 1
        config.ner_stats.total_processing_time += processing_time
        config.ner_stats.total_entities_found += len(entities) if entities else 0
        
        for entity in (entities or []):
            entity_type = entity.get("label", "unknown")
            config.ner_stats.entities_by_type[entity_type] = \
                config.ner_stats.entities_by_type.get(entity_type, 0) + 1
    except Exception:
        config.ner_stats.errors += 1

# In Output:
if config.use_ner:
    avg_time = (config.ner_stats.total_processing_time / 
                max(config.ner_stats.total_chunks_processed, 1))
    config.logger.info(f"NER Statistics:")
    config.logger.info(f"  Chunks processed: {config.ner_stats.total_chunks_processed}")
    config.logger.info(f"  Entities found: {config.ner_stats.total_entities_found}")
    config.logger.info(f"  Avg time per chunk: {avg_time:.3f}s")
    config.logger.info(f"  Entities by type: {config.ner_stats.entities_by_type}")
```

**Dateien**: `config.py`, `main.py`

---

### 8. Text-Chunking-Strategie für große Texte

**Problem**:
- Sehr große Texte werden komplett an GLiNER übergeben
- Kann zu Memory-Problemen führen
- GLiNER hat möglicherweise maximale Textlänge

**Lösung**:
```python
# constants.py
MAX_NER_TEXT_LENGTH: int = 10000  # Maximale Zeichen pro NER-Aufruf
NER_CHUNK_OVERLAP: int = 200  # Overlap zwischen Chunks

# In process_text():
def process_text_with_ner(text: str, file_path: str, pmc: PiiMatchContainer, 
                          config: Config) -> None:
    """Process text with NER, handling large texts by chunking."""
    if not config.use_ner or not config.ner_model:
        return
    
    if len(text) <= constants.MAX_NER_TEXT_LENGTH:
        # Normale Verarbeitung
        entities = config.ner_model.predict_entities(
            text, config.ner_labels, threshold=config.ner_threshold
        )
        with _process_lock:
            pmc.add_matches_ner(entities, file_path)
    else:
        # Chunking für große Texte
        chunk_size = constants.MAX_NER_TEXT_LENGTH
        overlap = constants.NER_CHUNK_OVERLAP
        
        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i:i + chunk_size]
            if not chunk.strip():
                continue
            
            try:
                entities = config.ner_model.predict_entities(
                    chunk, config.ner_labels, threshold=config.ner_threshold
                )
                with _process_lock:
                    pmc.add_matches_ner(entities, file_path)
            except Exception as e:
                config.logger.warning(
                    f"NER error in chunk {i//chunk_size} of {file_path}: {e}"
                )
```

**Dateien**: `main.py`, `constants.py`

---

### 9. Erweiterte Test-Abdeckung für NER

**Problem**:
- Nur grundlegende Tests vorhanden
- Keine Integrationstests mit echtem Modell
- Keine Tests für Edge Cases

**Lösung**:
```python
# tests/test_ner_integration.py
import pytest
from unittest.mock import Mock, patch
from config import Config
from matches import PiiMatchContainer

class TestNerIntegration:
    """Integration tests for NER functionality."""
    
    @pytest.fixture
    def mock_ner_model(self):
        """Mock GLiNER model for testing."""
        model = Mock()
        model.predict_entities.return_value = [
            {"text": "John Doe", "label": "Person's Name", "score": 0.95},
            {"text": "Berlin", "label": "Location", "score": 0.87}
        ]
        return model
    
    def test_ner_model_loading(self, tmp_path):
        """Test NER model loading."""
        # Test mit Mock-Modell
        pass
    
    def test_ner_threshold_filtering(self, mock_ner_model):
        """Test that entities below threshold are filtered."""
        # Mock sollte nur Entities über Threshold zurückgeben
        pass
    
    def test_ner_empty_text(self, mock_ner_model):
        """Test NER with empty text."""
        # Sollte keine Fehler werfen
        pass
    
    def test_ner_very_long_text(self, mock_ner_model):
        """Test NER with very long text (chunking)."""
        long_text = "A" * 50000
        # Sollte in Chunks verarbeitet werden
        pass
    
    def test_ner_error_handling(self):
        """Test error handling when NER fails."""
        # Modell wirft Exception
        pass
    
    def test_ner_label_mapping(self, mock_ner_model):
        """Test correct mapping from GLiNER labels to internal labels."""
        # Prüfe Mapping-Korrektheit
        pass

# tests/test_ner_performance.py
class TestNerPerformance:
    """Performance tests for NER."""
    
    def test_ner_batch_processing(self):
        """Test batch processing performance."""
        pass
    
    def test_ner_memory_usage(self):
        """Test memory usage with large texts."""
        pass
```

**Dateien**: `tests/test_ner_integration.py`, `tests/test_ner_performance.py`

---

## 🟢 Niedrig-Priorität

### 10. Modell-Caching und Warm-Up

**Problem**:
- Modell wird bei jedem Start neu geladen
- Erster Aufruf kann langsam sein (Warm-Up)

**Lösung**:
```python
# Modell-Cache für wiederholte Nutzung
# Optional: Modell-Warm-Up beim Start
def _load_ner_model(self) -> None:
    """Load NER model and labels."""
    # ... existing code ...
    
    # Warm-up: Erster Aufruf mit Dummy-Text
    if self.ner_model:
        try:
            dummy_text = "This is a test sentence."
            self.ner_model.predict_entities(
                dummy_text, 
                self.ner_labels[:1],  # Nur ein Label für Warm-Up
                threshold=self.ner_threshold
            )
            self.logger.debug("NER model warmed up")
        except Exception as e:
            self.logger.warning(f"NER warm-up failed: {e}")
```

**Dateien**: `config.py`

---

### 11. Konfigurierbare Entity-Typen zur Laufzeit

**Problem**:
- Entity-Typen sind fest in `config_types.json` definiert
- Keine Möglichkeit, Entity-Typen zur Laufzeit zu ändern

**Lösung**:
```python
# CLI-Option für benutzerdefinierte Labels
# --ner-labels "Person's Name,Location,Email Address"

# In setup.py:
parser.add_argument(
    "--ner-labels",
    type=str,
    help="Comma-separated list of NER labels to detect"
)

# In config.py:
def _load_ner_labels(self, custom_labels: list[str] | None = None) -> None:
    """Load NER labels from config or custom labels."""
    if custom_labels:
        self.ner_labels = custom_labels
    else:
        with open(constants.CONFIG_FILE) as f:
            config_data = json.load(f)
        ner_config = config_data.get("ai-ner", [])
        self.ner_labels = [c["term"] for c in ner_config]
```

**Dateien**: `config.py`, `setup.py`

---

### 12. NER-Ergebnisse validieren und deduplizieren

**Problem**:
- Keine Validierung der NER-Ergebnisse
- Mögliche Duplikate bei Overlap-Chunking
- Keine Plausibilitätsprüfung

**Lösung**:
```python
# In matches.py
def add_matches_ner(self, matches: list[dict] | None, path: str) -> None:
    """Add AI-based NER matches with validation and deduplication."""
    if matches is not None:
        seen_matches = set()  # Für Deduplizierung
        
        for match in matches:
            # Validierung
            if not match.get("text") or not match.get("label"):
                continue
            
            # Score-Validierung
            score = match.get("score", 0.0)
            if score < self._min_ner_score:  # Konfigurierbar
                continue
            
            # Deduplizierung (Text + Position)
            match_key = (match["text"].lower(), path)
            if match_key in seen_matches:
                continue
            seen_matches.add(match_key)
            
            # Label-Mapping
            type = config_ainer_sorted.get(match["label"], {}).get("label")
            if not type:
                # Unbekanntes Label - loggen
                continue
            
            self.__add_match(
                text=match["text"], 
                file=path, 
                type=type, 
                ner_score=score
            )
```

**Dateien**: `matches.py`

---

### 13. NER-Ergebnisse mit Kontext anreichern

**Problem**:
- NER-Ergebnisse enthalten nur Text und Score
- Kein Kontext um die Entity herum

**Lösung**:
```python
# Erweiterte PiiMatch-Klasse
@dataclass
class PiiMatch:
    text: str
    file: str
    type: str
    ner_score: float | None = None
    context_before: str | None = None  # Text vor der Entity
    context_after: str | None = None   # Text nach der Entity
    start_pos: int | None = None       # Position im Text
    end_pos: int | None = None         # Endposition im Text

# In add_matches_ner():
# Extrahiere Kontext aus Originaltext
context_window = 50  # Zeichen vor/nach Entity
start = max(0, match["start"] - context_window)
end = min(len(original_text), match["end"] + context_window)
context_before = original_text[start:match["start"]]
context_after = original_text[match["end"]:end]
```

**Dateien**: `matches.py`, `main.py`

---

## Implementierungsreihenfolge

### Phase 1 (Sofort)
1. ✅ Thread-Safety prüfen und absichern (#1)
2. ✅ Threshold aus config_types.json nutzen (#2)
3. ✅ Fehlerbehandlung verbessern (#3)
4. ✅ Modell-Loading-Fehler besser behandeln (#4)

### Phase 2 (Nächste Iteration)
5. ✅ Batch-Processing implementieren (#5)
6. ✅ GPU-Unterstützung hinzufügen (#6)
7. ✅ Performance-Metriken (#7)
8. ✅ Erweiterte Tests (#9)

### Phase 3 (Langfristig)
9. ✅ Text-Chunking-Strategie (#8)
10. ✅ Modell-Caching (#10)
11. ✅ Konfigurierbare Entity-Typen (#11)
12. ✅ Validierung und Deduplizierung (#12)
13. ✅ Kontext-Anreicherung (#13)

---

## Metriken für Erfolgsmessung

- **Performance**: 
  - NER-Verarbeitungszeit pro Chunk
  - Durchsatz (Chunks/Sekunde)
  - Memory-Verbrauch
  
- **Qualität**:
  - False-Positive-Rate
  - False-Negative-Rate
  - Durchschnittlicher Confidence-Score
  
- **Stabilität**:
  - Fehlerrate bei NER-Verarbeitung
  - Thread-Safety-Verifikation
  - Memory-Leak-Tests

---

## Weitere Überlegungen

### Alternative NER-Modelle evaluieren
- Vergleich verschiedener GLiNER-Versionen
- Alternative Modelle (spaCy, transformers-basierte Modelle)
- Performance-Vergleich

### Modell-Fine-Tuning
- Fine-Tuning auf PII-spezifische Daten
- Domain-Adaptation für deutsche Daten
- Custom Entity-Typen trainieren

### Integration mit Regex-Ergebnissen
- Kombination von Regex- und NER-Ergebnissen
- Cross-Validation zwischen Methoden
- Confidence-Weighting
