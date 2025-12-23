"""Regex-based detection engine."""

from typing import Optional
from core.engines.base import DetectionResult
from config import Config

# Exposed for test patching and runtime type mapping
from matches import config_regex_sorted

try:
    from validators.credit_card_validator import CreditCardValidator
except Exception:  # pragma: no cover - optional dependency / import-time issues
    CreditCardValidator = None  # type: ignore[assignment]


class RegexEngine:
    """Regex-based detection engine.

    Uses compiled regex patterns from config_types.json to detect PII.
    This is a refactored version of the existing regex detection logic.
    """

    name = "regex"

    def __init__(self, config: Config):
        """Initialize regex engine.

        Args:
            config: Configuration object with regex pattern
        """
        self.config = config
        self.enabled = config.use_regex
        self.pattern = config.regex_pattern

    def detect(
        self, text: str, labels: list[str] | None = None
    ) -> list[DetectionResult]:
        """Detect PII using regex patterns.

        Args:
            text: Text content to analyze
            labels: Ignored for regex (uses all configured patterns)

        Returns:
            List of detection results
        """
        if not self.enabled or not self.pattern:
            return []

        results = []
        for match in self.pattern.finditer(text):
            entity_type, config_entry = self._get_entity_type(match)
            # If this isn't the "combined" pattern with groups, fall back to a generic label
            if not entity_type:
                entity_type = "REGEX_MATCH"

            # Validate if required
            if config_entry and not self._validate_match(match, config_entry):
                continue

            results.append(
                DetectionResult(
                    text=match.group(),
                    entity_type=entity_type,
                    confidence=None,  # Regex has no confidence score
                    engine_name="regex",
                )
            )

        return results

    def _get_entity_type(self, match) -> tuple[Optional[str], Optional[dict]]:
        """Determine entity type from regex match position.

        Args:
            match: Regex match object

        Returns:
            Tuple of (entity_type, config_entry) or (None, None)
        """
        for idx, item in enumerate(match.groups()):
            if item is not None:
                if idx in config_regex_sorted:
                    config_entry = config_regex_sorted[idx]
                    return config_entry["label"], config_entry
        return None, None

    def _validate_match(self, match, config_entry: dict) -> bool:
        """Validate a regex match if validation is required.

        Args:
            match: Regex match object
            config_entry: Configuration entry for this match type

        Returns:
            True if match is valid, False otherwise
        """
        if "validation" not in config_entry:
            return True

        validation_type = config_entry["validation"]

        if validation_type == "luhn":
            # Credit card validation using Luhn algorithm
            if CreditCardValidator is None:
                # If validator module not available, skip validation
                return True
            is_valid, _card_type = CreditCardValidator.validate(match.group())
            return is_valid

        return True

    def is_available(self) -> bool:
        """Check if regex engine is available.

        Returns:
            True if enabled and pattern is loaded
        """
        return self.enabled and self.pattern is not None
