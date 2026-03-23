"""Detection engines for PII analysis."""

from core.engines.base import DetectionEngine, DetectionResult
from core.engines.gliner_engine import GLiNEREngine

# Import engines to register them
from core.engines.regex_engine import RegexEngine
from core.engines.registry import EngineRegistry

# Register built-in engines
EngineRegistry.register("regex", RegexEngine)
EngineRegistry.register("gliner", GLiNEREngine)

# Optional engines (will be registered if dependencies are available)
try:
    from core.engines.spacy_engine import SpacyNEREngine

    EngineRegistry.register("spacy-ner", SpacyNEREngine)
except ImportError:
    pass

# PydanticAI unified engine (replaces ollama, openai-compatible, multimodal)
try:
    from core.engines.pydantic_ai_engine import PydanticAIEngine

    EngineRegistry.register("pydantic-ai", PydanticAIEngine)
except ImportError:
    pass

# Vector-search engine (requires sentence-transformers)
try:
    from core.engines.vector_engine import VectorEngine

    EngineRegistry.register("vector-search", VectorEngine)
except ImportError:
    pass

__all__ = [
    "DetectionEngine",
    "DetectionResult",
    "EngineRegistry",
    "RegexEngine",
    "GLiNEREngine",
    "PydanticAIEngine",
    "VectorEngine",
]
