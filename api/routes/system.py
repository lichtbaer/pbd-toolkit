"""System and health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from api.models import EngineInfo, HealthResponse
import constants

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="ok", version=constants.VERSION)


@router.get("/system/engines", response_model=list[EngineInfo])
def available_engines() -> list[EngineInfo]:
    """List available detection engines and their install status."""
    engines: list[EngineInfo] = []

    # Regex is always available (built-in)
    engines.append(EngineInfo(name="regex", available=True, description="Regular expression patterns"))

    # GLiNER
    try:
        import gliner  # noqa: F401
        engines.append(EngineInfo(name="gliner", available=True, description="GLiNER NER model"))
    except ImportError:
        engines.append(EngineInfo(name="gliner", available=False, description="GLiNER NER model (pip install gliner)"))

    # spaCy
    try:
        import spacy  # noqa: F401
        engines.append(EngineInfo(name="spacy", available=True, description="spaCy NER models"))
    except ImportError:
        engines.append(EngineInfo(name="spacy", available=False, description="spaCy NER models (pip install spacy)"))

    # PydanticAI
    try:
        import pydantic_ai  # noqa: F401
        engines.append(EngineInfo(name="pydantic-ai", available=True, description="PydanticAI unified LLM engine"))
    except ImportError:
        engines.append(EngineInfo(name="pydantic-ai", available=False, description="PydanticAI LLM engine (pip install pydantic-ai)"))

    # Vector search
    try:
        import sentence_transformers  # noqa: F401
        engines.append(EngineInfo(name="vector", available=True, description="Semantic similarity via sentence-transformers"))
    except ImportError:
        engines.append(EngineInfo(name="vector", available=False, description="Vector search (pip install sentence-transformers)"))

    return engines


@router.get("/system/profiles")
def available_profiles() -> list[dict[str, str]]:
    """List available scan profiles."""
    try:
        from core.profiles import PROFILES
        return [
            {"name": name, "description": p.get("description", "")}
            for name, p in PROFILES.items()
        ]
    except ImportError:
        return []
