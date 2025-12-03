# Analytical Engines Extension Analysis

## Executive Summary

This document analyzes the current architecture of the PII Toolkit and identifies opportunities to add additional analytical engines without replacing existing approaches. The analysis covers:

1. **Additional NER Models**: Integration of spaCy models (ner-german, ner-german-large)
2. **LLM Integration**: Support for Ollama and OpenAI-compatible endpoints
3. **Architectural Design**: Proposal for an extensible engine architecture

**Key Finding**: The current architecture is well-suited for extension. A plugin-based engine system would allow multiple detection engines to run in parallel, complementing existing regex and GLiNER-based detection.

---

## 1. Current Architecture Analysis

### 1.1 Current Detection Engines

The project currently supports two detection methods:

1. **Regex-based Detection** (`--regex`)
   - Pattern matching via compiled regex from `config_types.json`
   - Fast, deterministic, no external dependencies
   - Location: `config.py::_load_regex_pattern()`, `core/processor.py::process_text()`

2. **GLiNER-based NER** (`--ner`)
   - AI-powered Named Entity Recognition
   - Model: `urchade/gliner_medium-v2.1` (HuggingFace)
   - Location: `config.py::_load_ner_model()`, `core/processor.py::process_text()`
   - Thread-safe with separate lock (`_ner_lock`)

### 1.2 Current Integration Points

#### Configuration (`config.py`)
```python
@dataclass
class Config:
    use_regex: bool
    use_ner: bool
    regex_pattern: re.Pattern | None
    ner_model: GLiNER | None
    ner_labels: list[str]
    ner_threshold: float
```

#### Processing (`core/processor.py`)
```python
class TextProcessor:
    def process_text(self, text: str, file_path: str) -> None:
        if self.config.use_regex:
            # Regex processing
        if self.config.use_ner:
            # GLiNER processing
```

#### Match Storage (`matches.py`)
```python
@dataclass
class PiiMatch:
    text: str
    file: str
    type: str
    ner_score: float | None = None  # Currently only for GLiNER
```

### 1.3 Architecture Strengths

✅ **Modular Design**: Clear separation between detection methods
✅ **Dependency Injection**: Config object passed to processors
✅ **Thread Safety**: Separate locks for different operations
✅ **Extensible Match Types**: `config_types.json` allows adding new entity types
✅ **Parallel Execution**: Multiple engines can run simultaneously

### 1.4 Current Limitations

⚠️ **Hard-coded Engine Types**: Only regex and GLiNER supported
⚠️ **Single NER Model**: Only one NER model can be active at a time
⚠️ **No Engine Abstraction**: Each engine type has custom integration code
⚠️ **Limited Metadata**: `ner_score` only for GLiNER, no engine identification
⚠️ **No Engine Registry**: No plugin system for adding new engines

---

## 2. Proposed Extension Architecture

### 2.1 Engine Abstraction Layer

Create a base interface for all analytical engines:

```python
# core/engines/base.py
from abc import ABC, abstractmethod
from typing import Protocol, Optional
from dataclasses import dataclass

@dataclass
class DetectionResult:
    """Result from a detection engine."""
    text: str
    entity_type: str
    confidence: float | None = None
    engine_name: str = ""
    metadata: dict = field(default_factory=dict)

class DetectionEngine(Protocol):
    """Protocol for detection engines."""
    
    name: str
    enabled: bool
    
    @abstractmethod
    def detect(self, text: str, labels: list[str] | None = None) -> list[DetectionResult]:
        """Detect PII in text.
        
        Args:
            text: Text to analyze
            labels: Optional list of entity types to detect
            
        Returns:
            List of detection results
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if engine is available (model loaded, API accessible, etc.)."""
        pass
```

### 2.2 Engine Registry

Similar to the FileProcessorRegistry, create an engine registry:

```python
# core/engines/registry.py
from typing import Dict, Type
from core.engines.base import DetectionEngine

class EngineRegistry:
    """Registry for detection engines."""
    
    _engines: Dict[str, Type[DetectionEngine]] = {}
    
    @classmethod
    def register(cls, name: str, engine_class: Type[DetectionEngine]):
        """Register an engine class."""
        cls._engines[name] = engine_class
    
    @classmethod
    def get_engine(cls, name: str, config) -> Optional[DetectionEngine]:
        """Get an engine instance."""
        if name not in cls._engines:
            return None
        return cls._engines[name](config)
    
    @classmethod
    def list_engines(cls) -> list[str]:
        """List all registered engines."""
        return list(cls._engines.keys())
```

### 2.3 Engine Implementations

#### 2.3.1 Regex Engine (Refactored)

```python
# core/engines/regex_engine.py
from core.engines.base import DetectionEngine, DetectionResult

class RegexEngine:
    """Regex-based detection engine."""
    
    name = "regex"
    
    def __init__(self, config):
        self.config = config
        self.enabled = config.use_regex
        self.pattern = config.regex_pattern
    
    def detect(self, text: str, labels: list[str] | None = None) -> list[DetectionResult]:
        if not self.enabled or not self.pattern:
            return []
        
        results = []
        for match in self.pattern.finditer(text):
            # Determine entity type from match position
            entity_type = self._get_entity_type(match)
            results.append(DetectionResult(
                text=match.group(),
                entity_type=entity_type,
                engine_name="regex"
            ))
        return results
    
    def is_available(self) -> bool:
        return self.enabled and self.pattern is not None
```

#### 2.3.2 GLiNER Engine (Refactored)

```python
# core/engines/gliner_engine.py
from core.engines.base import DetectionEngine, DetectionResult

class GLiNEREngine:
    """GLiNER-based NER engine."""
    
    name = "gliner"
    
    def __init__(self, config):
        self.config = config
        self.enabled = config.use_ner
        self.model = config.ner_model
        self.labels = config.ner_labels
        self.threshold = config.ner_threshold
    
    def detect(self, text: str, labels: list[str] | None = None) -> list[DetectionResult]:
        if not self.enabled or not self.model:
            return []
        
        labels_to_use = labels or self.labels
        entities = self.model.predict_entities(
            text, labels_to_use, threshold=self.threshold
        )
        
        results = []
        for entity in entities:
            results.append(DetectionResult(
                text=entity["text"],
                entity_type=self._map_label(entity["label"]),
                confidence=entity.get("score"),
                engine_name="gliner"
            ))
        return results
    
    def is_available(self) -> bool:
        return self.enabled and self.model is not None
```

#### 2.3.3 spaCy NER Engine (New)

```python
# core/engines/spacy_engine.py
from core.engines.base import DetectionEngine, DetectionResult

class SpacyNEREngine:
    """spaCy-based NER engine for German models."""
    
    name = "spacy-ner"
    
    def __init__(self, config):
        self.config = config
        self.enabled = config.use_spacy_ner
        self.model_name = config.spacy_model_name  # e.g., "de_core_news_lg"
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Lazy load spaCy model."""
        if not self.enabled:
            return
        
        try:
            import spacy
            self.model = spacy.load(self.model_name)
        except OSError:
            self.config.logger.warning(
                f"spaCy model '{self.model_name}' not found. "
                f"Install with: python -m spacy download {self.model_name}"
            )
            self.model = None
        except ImportError:
            self.config.logger.warning("spaCy not installed. Install with: pip install spacy")
            self.model = None
    
    def detect(self, text: str, labels: list[str] | None = None) -> list[DetectionResult]:
        if not self.enabled or not self.model:
            return []
        
        doc = self.model(text)
        results = []
        
        # Map spaCy labels to internal types
        label_mapping = {
            "PER": "NER_PERSON",
            "LOC": "NER_LOCATION",
            "ORG": "NER_ORGANIZATION",
            # Add more mappings as needed
        }
        
        for ent in doc.ents:
            entity_type = label_mapping.get(ent.label_, f"SPACY_{ent.label_}")
            results.append(DetectionResult(
                text=ent.text,
                entity_type=entity_type,
                confidence=ent.score if hasattr(ent, 'score') else None,
                engine_name="spacy-ner",
                metadata={"spacy_label": ent.label_}
            ))
        
        return results
    
    def is_available(self) -> bool:
        return self.enabled and self.model is not None
```

#### 2.3.4 Ollama LLM Engine (New)

```python
# core/engines/ollama_engine.py
from core.engines.base import DetectionEngine, DetectionResult
import requests
import json

class OllamaEngine:
    """Ollama-based LLM detection engine."""
    
    name = "ollama"
    
    def __init__(self, config):
        self.config = config
        self.enabled = config.use_ollama
        self.base_url = config.ollama_base_url  # e.g., "http://localhost:11434"
        self.model_name = config.ollama_model  # e.g., "llama3.2", "mistral"
        self.timeout = config.ollama_timeout
    
    def detect(self, text: str, labels: list[str] | None = None) -> list[DetectionResult]:
        if not self.enabled:
            return []
        
        # Create prompt for PII detection
        prompt = self._create_prompt(text, labels)
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            return self._parse_response(result.get("response", ""))
        except Exception as e:
            self.config.logger.warning(f"Ollama detection failed: {e}")
            return []
    
    def _create_prompt(self, text: str, labels: list[str] | None) -> str:
        """Create prompt for LLM."""
        label_list = ", ".join(labels) if labels else "all PII types"
        return f"""Analyze the following text and extract all personally identifiable information (PII).
        
Entity types to detect: {label_list}

Text:
{text}

Return a JSON array of detected entities in this format:
[
  {{"text": "found text", "type": "entity_type", "confidence": 0.95}}
]
"""
    
    def _parse_response(self, response_text: str) -> list[DetectionResult]:
        """Parse LLM JSON response."""
        try:
            entities = json.loads(response_text)
            results = []
            for entity in entities:
                results.append(DetectionResult(
                    text=entity.get("text", ""),
                    entity_type=entity.get("type", "UNKNOWN"),
                    confidence=entity.get("confidence"),
                    engine_name="ollama"
                ))
            return results
        except json.JSONDecodeError:
            return []
    
    def is_available(self) -> bool:
        if not self.enabled:
            return False
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
```

#### 2.3.5 OpenAI-Compatible Engine (New)

```python
# core/engines/openai_engine.py
from core.engines.base import DetectionEngine, DetectionResult
import requests
import json

class OpenAICompatibleEngine:
    """OpenAI-compatible API detection engine."""
    
    name = "openai-compatible"
    
    def __init__(self, config):
        self.config = config
        self.enabled = config.use_openai_compatible
        self.api_base = config.openai_api_base  # e.g., "https://api.openai.com/v1"
        self.api_key = config.openai_api_key
        self.model = config.openai_model  # e.g., "gpt-4", "gpt-3.5-turbo"
        self.timeout = config.openai_timeout
    
    def detect(self, text: str, labels: list[str] | None = None) -> list[DetectionResult]:
        if not self.enabled:
            return []
        
        prompt = self._create_prompt(text, labels)
        
        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a PII detection expert."},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            return self._parse_response(content)
        except Exception as e:
            self.config.logger.warning(f"OpenAI-compatible detection failed: {e}")
            return []
    
    def _create_prompt(self, text: str, labels: list[str] | None) -> str:
        """Create prompt for OpenAI API."""
        label_list = ", ".join(labels) if labels else "all PII types"
        return f"""Analyze the following text and extract all personally identifiable information (PII).

Entity types to detect: {label_list}

Text:
{text}

Return a JSON object with this structure:
{{
  "entities": [
    {{"text": "found text", "type": "entity_type", "confidence": 0.95}}
  ]
}}
"""
    
    def _parse_response(self, content: str) -> list[DetectionResult]:
        """Parse OpenAI JSON response."""
        try:
            data = json.loads(content)
            results = []
            for entity in data.get("entities", []):
                results.append(DetectionResult(
                    text=entity.get("text", ""),
                    entity_type=entity.get("type", "UNKNOWN"),
                    confidence=entity.get("confidence"),
                    engine_name="openai-compatible"
                ))
            return results
        except json.JSONDecodeError:
            return []
    
    def is_available(self) -> bool:
        if not self.enabled:
            return False
        try:
            response = requests.get(
                f"{self.api_base}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
```

### 2.4 Updated Processor

```python
# core/processor.py (updated)
class TextProcessor:
    """Processes text content for PII detection using multiple engines."""
    
    def __init__(self, config: Config, match_container: PiiMatchContainer, 
                 statistics: Optional[Statistics] = None):
        self.config = config
        self.match_container = match_container
        self.statistics = statistics
        
        # Initialize engines from registry
        self.engines = []
        for engine_name in config.enabled_engines:
            engine = EngineRegistry.get_engine(engine_name, config)
            if engine and engine.is_available():
                self.engines.append(engine)
        
        # Thread locks
        self._process_lock = threading.Lock()
        self._engine_locks = {engine.name: threading.Lock() for engine in self.engines}
    
    def process_text(self, text: str, file_path: str) -> None:
        """Process text with all enabled engines."""
        all_results = []
        
        # Run all engines (can be parallelized)
        for engine in self.engines:
            try:
                with self._engine_locks.get(engine.name, threading.Lock()):
                    results = engine.detect(text, self.config.ner_labels)
                    all_results.extend(results)
            except Exception as e:
                self.config.logger.warning(
                    f"Engine {engine.name} failed: {e}"
                )
        
        # Add all results to match container
        with self._process_lock:
            for result in all_results:
                self.match_container.add_match(
                    text=result.text,
                    file=file_path,
                    type=result.entity_type,
                    confidence=result.confidence,
                    engine=result.engine_name,
                    metadata=result.metadata
                )
```

### 2.5 Updated Configuration

```python
# config.py (extended)
@dataclass
class Config:
    # Existing fields...
    use_regex: bool
    use_ner: bool
    
    # New engine flags
    use_spacy_ner: bool = False
    use_ollama: bool = False
    use_openai_compatible: bool = False
    
    # Engine-specific config
    spacy_model_name: str = "de_core_news_lg"  # or "de_core_news_sm"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout: int = 30
    openai_api_base: str = "https://api.openai.com/v1"
    openai_api_key: str | None = None
    openai_model: str = "gpt-3.5-turbo"
    openai_timeout: int = 30
    
    # Engine registry
    enabled_engines: list[str] = field(default_factory=list)
    
    def __post_init__(self):
        # Build enabled engines list
        self.enabled_engines = []
        if self.use_regex:
            self.enabled_engines.append("regex")
        if self.use_ner:
            self.enabled_engines.append("gliner")
        if self.use_spacy_ner:
            self.enabled_engines.append("spacy-ner")
        if self.use_ollama:
            self.enabled_engines.append("ollama")
        if self.use_openai_compatible:
            self.enabled_engines.append("openai-compatible")
```

### 2.6 Updated Match Container

```python
# matches.py (extended)
@dataclass
class PiiMatch:
    text: str
    file: str
    type: str
    ner_score: float | None = None  # Renamed to confidence
    engine: str | None = None  # New: which engine found this
    metadata: dict = field(default_factory=dict)  # New: engine-specific metadata
```

---

## 3. CLI Integration

### 3.1 New CLI Arguments

```python
# setup.py (extended)
parser.add_argument("--spacy-ner", action="store_true",
                   help="Use spaCy NER models for detection")
parser.add_argument("--spacy-model", default="de_core_news_lg",
                   choices=["de_core_news_sm", "de_core_news_md", "de_core_news_lg"],
                   help="spaCy model to use (default: de_core_news_lg)")

parser.add_argument("--ollama", action="store_true",
                   help="Use Ollama LLM for detection")
parser.add_argument("--ollama-url", default="http://localhost:11434",
                   help="Ollama API base URL")
parser.add_argument("--ollama-model", default="llama3.2",
                   help="Ollama model to use")

parser.add_argument("--openai-compatible", action="store_true",
                   help="Use OpenAI-compatible API for detection")
parser.add_argument("--openai-api-base", default="https://api.openai.com/v1",
                   help="OpenAI-compatible API base URL")
parser.add_argument("--openai-api-key", 
                   help="OpenAI API key (or set OPENAI_API_KEY env var)")
parser.add_argument("--openai-model", default="gpt-3.5-turbo",
                   help="OpenAI model to use")
```

### 3.2 Usage Examples

```bash
# Use multiple engines simultaneously
python main.py --path /data --regex --ner --spacy-ner

# Use Ollama with custom model
python main.py --path /data --ollama --ollama-model mistral

# Use OpenAI-compatible endpoint
python main.py --path /data --openai-compatible \
    --openai-api-base https://api.example.com/v1 \
    --openai-model gpt-4

# Combine all engines
python main.py --path /data \
    --regex \
    --ner \
    --spacy-ner --spacy-model de_core_news_lg \
    --ollama --ollama-model llama3.2 \
    --openai-compatible --openai-model gpt-3.5-turbo
```

---

## 4. Implementation Plan

### Phase 1: Engine Abstraction (Week 1)
1. Create `core/engines/` directory structure
2. Implement `DetectionEngine` protocol/base class
3. Create `EngineRegistry`
4. Refactor existing regex and GLiNER into engines
5. Update `TextProcessor` to use engine registry

### Phase 2: spaCy Integration (Week 2)
1. Implement `SpacyNEREngine`
2. Add CLI arguments
3. Update configuration
4. Add tests
5. Update documentation

### Phase 3: LLM Integration (Week 3-4)
1. Implement `OllamaEngine`
2. Implement `OpenAICompatibleEngine`
3. Add CLI arguments and configuration
4. Add error handling and retry logic
5. Add tests
6. Update documentation

### Phase 4: Enhanced Features (Week 5)
1. Add engine-specific statistics
2. Add engine comparison in output
3. Add confidence threshold per engine
4. Add batch processing for LLM engines
5. Performance optimization

---

## 5. Configuration File Support

### 5.1 Extended config_types.json

```json
{
  "settings": {
    "engines": {
      "regex": {"enabled": true},
      "gliner": {"enabled": true, "threshold": 0.5},
      "spacy-ner": {
        "enabled": false,
        "model": "de_core_news_lg"
      },
      "ollama": {
        "enabled": false,
        "base_url": "http://localhost:11434",
        "model": "llama3.2",
        "timeout": 30
      },
      "openai-compatible": {
        "enabled": false,
        "api_base": "https://api.openai.com/v1",
        "model": "gpt-3.5-turbo",
        "timeout": 30
      }
    }
  }
}
```

---

## 6. Benefits of This Architecture

### 6.1 Extensibility
- ✅ Easy to add new engines (implement `DetectionEngine` protocol)
- ✅ No changes to core processing logic needed
- ✅ Engine-specific configuration isolated

### 6.2 Parallel Execution
- ✅ Multiple engines can run simultaneously
- ✅ Each engine can have its own thread lock
- ✅ Results aggregated automatically

### 6.3 Maintainability
- ✅ Clear separation of concerns
- ✅ Each engine is self-contained
- ✅ Easy to test individual engines

### 6.4 Flexibility
- ✅ Users can choose which engines to use
- ✅ Engines can be combined for better coverage
- ✅ Engine-specific settings per use case

### 6.5 Backward Compatibility
- ✅ Existing `--regex` and `--ner` flags still work
- ✅ Existing output formats unchanged
- ✅ Gradual migration path

---

## 7. Dependencies

### 7.1 New Dependencies

```txt
# For spaCy
spacy>=3.7.0

# For Ollama (optional, uses requests)
requests>=2.31.0

# For OpenAI-compatible (optional, uses requests)
requests>=2.31.0
```

### 7.2 Model Downloads

```bash
# spaCy German models
python -m spacy download de_core_news_sm
python -m spacy download de_core_news_md
python -m spacy download de_core_news_lg

# GLiNER (existing)
hf download urchade/gliner_medium-v2.1

# Ollama models (via Ollama CLI)
ollama pull llama3.2
ollama pull mistral
```

---

## 8. Testing Strategy

### 8.1 Unit Tests
- Test each engine independently
- Test engine registry
- Test result aggregation

### 8.2 Integration Tests
- Test multiple engines running together
- Test error handling (engine failures)
- Test configuration loading

### 8.3 Performance Tests
- Compare engine performance
- Test parallel execution
- Test with large text chunks

---

## 9. Output Format Extensions

### 9.1 Enhanced CSV Output

```csv
match,file,type,confidence,engine,metadata
John Doe,/path/file.txt,AI-NER: Person,0.95,gliner,
John Doe,/path/file.txt,AI-NER: Person,0.92,spacy-ner,"{""spacy_label"": ""PER""}"
```

### 9.2 Enhanced JSON Output

```json
{
  "match": "John Doe",
  "file": "/path/file.txt",
  "type": "AI-NER: Person",
  "confidence": 0.95,
  "engine": "gliner",
  "metadata": {}
}
```

### 9.3 Engine Statistics

Add per-engine statistics to summary:
- Number of matches per engine
- Average confidence per engine
- Processing time per engine

---

## 10. Migration Path

### 10.1 Phase 1: Refactoring (Non-Breaking)
- Refactor existing code into engines
- Keep CLI flags unchanged
- Maintain backward compatibility

### 10.2 Phase 2: New Engines (Additive)
- Add new engines alongside existing ones
- New CLI flags for new engines
- Existing functionality unchanged

### 10.3 Phase 3: Enhanced Features (Optional)
- Add engine comparison features
- Add engine-specific statistics
- Add advanced configuration options

---

## 11. Open Questions

1. **Engine Priority**: Should results from different engines be deduplicated? How?
2. **Confidence Aggregation**: If multiple engines find the same entity, how to combine confidences?
3. **Performance**: Should engines run in parallel or sequentially?
4. **Error Handling**: Should one engine failure stop all engines or continue?
5. **Cost Management**: For LLM engines, should there be rate limiting or cost tracking?

---

## 12. Conclusion

The proposed architecture provides a clean, extensible foundation for adding multiple analytical engines to the PII Toolkit. Key advantages:

- ✅ **Non-breaking**: Existing functionality preserved
- ✅ **Extensible**: Easy to add new engines
- ✅ **Flexible**: Users can choose which engines to use
- ✅ **Maintainable**: Clear separation of concerns
- ✅ **Testable**: Each engine can be tested independently

The implementation can be done incrementally, starting with the abstraction layer and gradually adding new engines.

---

**Document Version**: 1.0  
**Date**: 2024  
**Status**: Proposal
