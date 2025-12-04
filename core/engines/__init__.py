"""Detection engines for PII analysis."""

from core.engines.base import DetectionEngine, DetectionResult
from core.engines.registry import EngineRegistry

# Import engines to register them
from core.engines.regex_engine import RegexEngine
from core.engines.gliner_engine import GLiNEREngine

# Register built-in engines
EngineRegistry.register("regex", RegexEngine)
EngineRegistry.register("gliner", GLiNEREngine)

# Optional engines (will be registered if dependencies are available)
try:
    from core.engines.spacy_engine import SpacyNEREngine
    EngineRegistry.register("spacy-ner", SpacyNEREngine)
except ImportError:
    pass

try:
    from core.engines.ollama_engine import OllamaEngine
    EngineRegistry.register("ollama", OllamaEngine)
except ImportError:
    pass

try:
    from core.engines.openai_engine import OpenAICompatibleEngine
    EngineRegistry.register("openai-compatible", OpenAICompatibleEngine)
except ImportError:
    pass

try:
    from core.engines.multimodal_engine import MultimodalEngine
    EngineRegistry.register("multimodal", MultimodalEngine)
except ImportError:
    pass

__all__ = [
    "DetectionEngine",
    "DetectionResult",
    "EngineRegistry",
    "RegexEngine",
    "GLiNEREngine",
    "MultimodalEngine",
]
