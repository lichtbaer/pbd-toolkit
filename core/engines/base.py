"""Base classes and protocols for detection engines.

Engine contract
---------------
All detection engines implement the ``DetectionEngine`` Protocol (structural subtyping).
Using a Protocol rather than an ABC has two benefits:

1. Engines can be unit-tested with simple mock objects that satisfy the interface
   without inheriting from a base class.
2. Engines that ship as optional extras (GLiNER, PydanticAI) do not need to import
   this module, avoiding circular import issues.

Engines may optionally expose a ``thread_safe`` class attribute (bool).  When
``True``, ``TextProcessor`` omits the per-engine lock and allows concurrent calls
from multiple worker threads.  When absent or ``False``, calls are serialised.
"""

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class DetectionResult:
    """Result from a detection engine.

    Attributes:
        text: The detected text
        entity_type: The type of entity detected (e.g., "NER_PERSON")
        confidence: Confidence score (0.0-1.0) if available
        engine_name: Name of the engine that found this match
        metadata: Additional engine-specific metadata
    """

    text: str
    entity_type: str
    confidence: float | None = None
    engine_name: str = ""
    metadata: dict = field(default_factory=dict)
    # Character offset within the analyzed text chunk (for context extraction)
    offset: int | None = None


class DetectionEngine(Protocol):
    """Protocol for detection engines.

    All detection engines must implement this protocol to be compatible
    with the engine registry and processor.
    """

    name: str
    """Unique name identifier for this engine."""

    enabled: bool
    """Whether this engine is currently enabled."""

    def __init__(self, config: Any) -> None:
        """Construct an engine from a ``Config`` (or config-like) object."""
        ...

    @abstractmethod
    def detect(
        self, text: str, labels: list[str] | None = None
    ) -> list[DetectionResult]:
        """Detect PII in text.

        Args:
            text: Text content to analyze
            labels: Optional list of entity types to detect.
                   If None, detect all configured entity types.

        Returns:
            List of detection results. Empty list if no matches found.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if engine is available and ready to use.

        Returns:
            True if engine is loaded/configured and ready, False otherwise.
        """
        pass
