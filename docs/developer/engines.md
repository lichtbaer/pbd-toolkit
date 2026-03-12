# Detection Engines Architecture

## Overview

The PII Toolkit uses a plugin-based engine architecture that allows multiple detection engines to run in parallel. This design enables easy extension with new detection methods without modifying core processing logic.

In the current implementation, enabled engines are executed **sequentially per text chunk/file** (with per-engine locks to ensure thread safety). The architecture is designed so future parallel execution can be added safely, but it is not enabled today.

## Engine Architecture

### Engine Protocol

All detection engines implement the `DetectionEngine` protocol:

```python
class DetectionEngine(Protocol):
    name: str
    enabled: bool
    
    def detect(text: str, labels: list[str] | None = None) -> list[DetectionResult]:
        """Detect PII in text."""
        pass
    
    def is_available(self) -> bool:
        """Check if engine is available."""
        pass
```

### DetectionResult

All engines return `DetectionResult` objects:

```python
@dataclass
class DetectionResult:
    text: str
    entity_type: str
    confidence: float | None = None
    engine_name: str = ""
    metadata: dict = field(default_factory=dict)
```

## Engine Registry

Engines are registered in `core/engines/__init__.py`:

```python
EngineRegistry.register("regex", RegexEngine)
EngineRegistry.register("gliner", GLiNEREngine)
EngineRegistry.register("spacy-ner", SpacyNEREngine)
EngineRegistry.register("pydantic-ai", PydanticAIEngine)
EngineRegistry.register("vector-search", VectorEngine)
```

## Available Engines

### RegexEngine

**Location**: `core/engines/regex_engine.py`

Fast pattern-based detection using compiled regex patterns.

**Features**:
- Credit card validation (Luhn algorithm)
- Thread-safe
- No external dependencies

### GLiNEREngine

**Location**: `core/engines/gliner_engine.py`

AI-powered NER using GLiNER model.

**Features**:
- Thread-safe model calls
- Confidence scores
- GPU support

### SpacyNEREngine

**Location**: `core/engines/spacy_engine.py`

German-optimized NER using spaCy models.

**Features**:
- Multiple model sizes (sm, md, lg)
- German-specific optimization
- Local execution

### PydanticAIEngine

**Location**: `core/engines/pydantic_ai_engine.py`

Unified LLM-based detection using PydanticAI. Replaces the old OllamaEngine, OpenAICompatibleEngine, and MultimodalEngine.

**Features**:
- Type-safe structured outputs with Pydantic models
- Supports multiple providers: Ollama, OpenAI, Anthropic
- Completely offline (with Ollama)
- Cloud-based (with OpenAI/Anthropic)
- Multimodal image detection support
- Adaptive rate limiting (preserved from OllamaEngine)
- Automatic retry mechanism
- Unified interface for all LLM providers

### VectorEngine

**Location**: `core/engines/vector_engine.py`
**Supporting module**: `core/indexer/` (`DocumentIndexer`, `pii_queries`)

Semantic similarity-based detection using sentence-transformers embeddings. Operates in two modes:

**Inline mode** (default with `--vector-search`):
- Embeds each text chunk and computes cosine similarity against pre-computed exemplar vectors
- Returns `VECTOR_*` category results for chunks that exceed the threshold
- Thread-safe; model is lazily loaded and cached at the class level

**Triage mode** (`--vector-triage`):
- Exposes a `triage_pass(text) -> bool` method called by `TextProcessor` before the main engine loop
- Chunks without a PII signal are skipped entirely – other engines never see them
- Useful for reducing LLM API costs on large collections

**Optional index persistence** (`--vector-save-index`):
- After the scan, `finalize()` is called by `TextProcessor` and the FAISS index is written to disk
- A saved index can be reloaded with `--vector-load-index` for cross-document queries

**`core/indexer/pii_queries.py`** defines 13 PII categories with 7 exemplar texts each (DE + EN):
`VECTOR_PERSON`, `VECTOR_ADDRESS`, `VECTOR_EMAIL`, `VECTOR_PHONE`, `VECTOR_ID_DOCUMENT`,
`VECTOR_SSN`, `VECTOR_FINANCIAL`, `VECTOR_CREDITCARD`, `VECTOR_HEALTH`, `VECTOR_BIOMETRIC`,
`VECTOR_LOCATION`, `VECTOR_VEHICLE`, `VECTOR_CREDENTIALS`

**`core/indexer/document_indexer.py`** – `DocumentIndexer`:
- Lazily loads the sentence-transformers model (class-level cache, shared across instances)
- Pre-computes and normalises all exemplar embeddings on first use
- `detect(text)` → embed + cosine similarity → sorted `CategoryMatch` list
- `add_chunk()` + `save_index()` / `_load_faiss_index()` for FAISS persistence

**Key design decisions**:
- `text` in `DetectionResult` is the full chunk (not an exact span) – use alongside NER/regex for precise spans
- Confidence is the cosine similarity score (0.0–1.0)
- Privacy-first defaults: local model, no network calls, FAISS index stores only embeddings + file paths

## Adding a New Engine

### Step 1: Create Engine Class

Create a new file in `core/engines/`:

```python
# core/engines/my_engine.py
from core.engines.base import DetectionEngine, DetectionResult
from config import Config

class MyEngine:
    name = "my-engine"
    
    def __init__(self, config: Config):
        self.config = config
        self.enabled = getattr(config, 'use_my_engine', False)
        # Initialize your engine here
    
    def detect(self, text: str, labels: list[str] | None = None) -> list[DetectionResult]:
        # Your detection logic
        results = []
        # ... detection code ...
        return results
    
    def is_available(self) -> bool:
        return self.enabled and self._model_loaded
```

### Step 2: Register Engine

Add to `core/engines/__init__.py`:

```python
try:
    from core.engines.my_engine import MyEngine
    EngineRegistry.register("my-engine", MyEngine)
except ImportError:
    pass
```

### Step 3: Add Configuration

Update `config.py`:

```python
@dataclass
class Config:
    # ... existing fields ...
    use_my_engine: bool = False
    my_engine_setting: str = "default"
```

### Step 4: Add CLI Arguments

Update `setup.py`:

```python
parser.add_argument("--my-engine", action="store_true",
                   help="Use my engine for detection")
parser.add_argument("--my-engine-setting", default="default",
                   help="My engine setting")
```

### Step 5: Update TextProcessor

The `TextProcessor` automatically discovers engines from the registry, so no changes needed if you follow the protocol.

## Thread Safety

Each engine should handle thread safety:

1. **Stateless engines** (like regex): No special handling needed
2. **Model-based engines** (like GLiNER): Use locks for model calls
3. **API-based engines** (like Ollama): Use locks or connection pooling

Example:

```python
import threading

class MyEngine:
    def __init__(self, config):
        self._lock = threading.Lock()
    
    def detect(self, text, labels=None):
        with self._lock:
            # Thread-safe model call
            results = self.model.predict(text)
        return results
```

## Error Handling

Engines should handle errors gracefully:

```python
def detect(self, text: str, labels: list[str] | None = None) -> list[DetectionResult]:
    try:
        # Detection logic
        return results
    except Exception as e:
        self.config.logger.warning(f"MyEngine detection error: {e}")
        return []  # Return empty list on error
```

## Testing

Create tests in `tests/test_engines.py`:

```python
def test_my_engine_detect():
    mock_config = Mock(spec=Config)
    mock_config.use_my_engine = True
    # ... setup ...
    
    engine = MyEngine(mock_config)
    results = engine.detect("test text")
    
    assert len(results) > 0
```

## Best Practices

1. **Graceful degradation**: Return empty list if engine unavailable
2. **Logging**: Log warnings for errors, debug for verbose info
3. **Configuration**: Use `getattr()` with defaults for optional config
4. **Documentation**: Document engine-specific requirements
5. **Testing**: Test both success and error cases

## Performance Considerations

- **Fast engines** (regex): Can run in parallel without locks
- **Slow engines** (LLMs): Consider batching or rate limiting (e.g., PydanticAIEngine implements adaptive rate limiting)
- **Resource-intensive**: Check availability before processing
- **Caching**: Consider caching for repeated patterns

## Output Format

All engines should return results in the same format:

```python
DetectionResult(
    text="detected text",
    entity_type="ENTITY_TYPE",
    confidence=0.95,  # Optional
    engine_name="my-engine",
    metadata={"custom": "data"}  # Optional
)
```

The `TextProcessor` aggregates results from all engines and adds them to the match container.
