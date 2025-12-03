# Detection Engines Architecture

## Overview

The PII Toolkit uses a plugin-based engine architecture that allows multiple detection engines to run in parallel. This design enables easy extension with new detection methods without modifying core processing logic.

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
EngineRegistry.register("ollama", OllamaEngine)
EngineRegistry.register("openai-compatible", OpenAICompatibleEngine)
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

### OllamaEngine

**Location**: `core/engines/ollama_engine.py`

Local LLM-based detection using Ollama.

**Features**:
- Completely offline
- Configurable models
- JSON response parsing

### OpenAICompatibleEngine

**Location**: `core/engines/openai_engine.py`

Cloud-based detection using OpenAI API or compatible endpoints.

**Features**:
- Multiple provider support
- Configurable API endpoints
- Environment variable support

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
- **Slow engines** (LLMs): Consider batching or rate limiting
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
