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

# PydanticAI unified engine (replaces ollama, openai-compatible, multimodal)
try:
    from core.engines.pydantic_ai_engine import PydanticAIEngine

    EngineRegistry.register("pydantic-ai", PydanticAIEngine)
except ImportError:
    pass

__all__ = [
    "DetectionEngine",
    "DetectionResult",
    "EngineRegistry",
    "RegexEngine",
    "GLiNEREngine",
    "PydanticAIEngine",
]
