"""GLiNER-based NER detection engine."""

import threading
from typing import Optional
from core.engines.base import DetectionResult
from config import Config


class GLiNEREngine:
    """GLiNER-based NER detection engine.

    Uses GLiNER model for AI-powered Named Entity Recognition.
    This is a refactored version of the existing GLiNER detection logic.
    """

    name = "gliner"

    def __init__(self, config: Config):
        """Initialize GLiNER engine.

        Args:
            config: Configuration object with GLiNER model
        """
        self.config = config
        self.enabled = config.use_ner
        self.model = config.ner_model
        self.labels = config.ner_labels
        self.threshold = config.ner_threshold
        # Separate lock for thread-safe model calls
        self._lock = threading.Lock()

    def detect(
        self, text: str, labels: list[str] | None = None
    ) -> list[DetectionResult]:
        """Detect PII using GLiNER model.

        Args:
            text: Text content to analyze
            labels: Optional list of entity types to detect.
                   If None, uses configured labels from config.

        Returns:
            List of detection results
        """
        if not self.enabled or not self.model:
            return []

        labels_to_use = labels or self.labels
        if not labels_to_use:
            return []

        try:
            # Thread-safe model call
            with self._lock:
                entities = self.model.predict_entities(
                    text, labels_to_use, threshold=self.threshold
                )

            results = []
            if entities:
                for entity in entities:
                    entity_type = self._map_label(entity.get("label", ""))
                    if entity_type:
                        results.append(
                            DetectionResult(
                                text=entity.get("text", ""),
                                entity_type=entity_type,
                                confidence=entity.get("score"),
                                engine_name="gliner",
                                metadata={"gliner_label": entity.get("label", "")},
                            )
                        )

            return results
        except Exception as e:
            self.config.logger.warning(f"GLiNER detection error: {e}")
            return []

    def _map_label(self, gliner_label: str) -> Optional[str]:
        """Map GLiNER label to internal entity type.

        Args:
            gliner_label: Label from GLiNER model

        Returns:
            Internal entity type label or None
        """
        # Import here to avoid circular dependency
        from matches import config_ainer_sorted

        if gliner_label in config_ainer_sorted:
            return config_ainer_sorted[gliner_label]["label"]
        return None

    def is_available(self) -> bool:
        """Check if GLiNER engine is available.

        Returns:
            True if enabled and model is loaded
        """
        return self.enabled and self.model is not None
