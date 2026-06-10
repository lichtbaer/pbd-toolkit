"""GLiNER-based NER detection engine."""

import threading

from core.config import Config
from core.engines.base import DetectionResult

# Exposed for test patching and runtime label mapping
from core.matches import config_ainer_sorted


class GLiNEREngine:
    """GLiNER-based NER detection engine.

    Uses GLiNER model for AI-powered Named Entity Recognition.
    This is a refactored version of the existing GLiNER detection logic.
    """

    name = "gliner"
    # Engine protects the model call with an internal lock.
    thread_safe = True

    def __init__(self, config: Config):
        """Initialize GLiNER engine.

        Args:
            config: Configuration object with GLiNER model
        """
        self.config = config
        self.enabled = getattr(config, "use_ner", False)
        self.model = getattr(config, "ner_model", None)
        self.labels = getattr(config, "ner_labels", []) or []
        self.threshold = getattr(config, "ner_threshold", 0.5)
        # Optional per-label thresholds (keyed by GLiNER label); fall back to threshold.
        _lt = getattr(config, "ner_label_thresholds", {})
        self.label_thresholds = _lt if isinstance(_lt, dict) else {}
        # Separate lock for thread-safe model calls
        self._lock = threading.Lock()

    def _threshold_for(self, gliner_label: str) -> float:
        """Per-label confidence threshold, falling back to the global threshold."""
        return float(self.label_thresholds.get(gliner_label, self.threshold))

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

        # Query the model at the lowest relevant threshold so that per-label
        # thresholds above the global one can still be applied afterwards (GLiNER
        # itself only supports a single cutoff), then filter each entity against
        # its own threshold.
        query_threshold = self.threshold
        if self.label_thresholds:
            query_threshold = min(self.threshold, *self.label_thresholds.values())

        try:
            # Thread-safe model call
            with self._lock:
                entities = self.model.predict_entities(
                    text, labels_to_use, threshold=query_threshold
                )

            results = []
            if entities:
                for entity in entities:
                    raw_label = entity.get("label", "")
                    score = entity.get("score")
                    # Apply the per-label threshold (no-op when none configured).
                    if score is not None and score < self._threshold_for(raw_label):
                        continue
                    entity_type = self._map_label(raw_label)
                    if entity_type:
                        results.append(
                            DetectionResult(
                                text=entity.get("text", ""),
                                entity_type=entity_type,
                                confidence=score,
                                engine_name="gliner",
                                metadata={"gliner_label": raw_label},
                            )
                        )

            return results
        except RuntimeError:
            # Let the caller (processor) handle RuntimeErrors (e.g., GPU/model issues)
            raise
        except Exception as e:
            logger = getattr(self.config, "logger", None)
            if logger:
                logger.warning(f"GLiNER detection error: {e}")
            return []

    def _map_label(self, gliner_label: str) -> str | None:
        """Map GLiNER label to internal entity type.

        Args:
            gliner_label: Label from GLiNER model

        Returns:
            Internal entity type label or None
        """
        if gliner_label in config_ainer_sorted:
            return config_ainer_sorted[gliner_label]["label"]
        # Fallback: preserve label in a normalized internal form
        if gliner_label:
            return f"NER_{gliner_label.upper()}"
        return None

    def is_available(self) -> bool:
        """Check if GLiNER engine is available.

        Returns:
            True if enabled and model is loaded
        """
        return self.enabled and self.model is not None
