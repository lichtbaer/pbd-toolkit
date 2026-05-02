"""Regex-based PII detection engine – the fastest and most deterministic engine.

Regex is the primary engine and should be enabled in virtually all scan scenarios:

- Zero ML overhead: no model loading, no GPU, no network.
- Near-perfect recall for structured PII with fixed formats (IBANs, credit cards,
  email addresses, phone numbers, German tax IDs, social security numbers, etc.).
- Deterministic: the same text always produces the same result.

The engine compiles all configured patterns into a single alternation to run one
``finditer`` pass per text chunk rather than one pass per pattern.  This is critical
for performance when scanning thousands of files.

Post-match validation (Luhn, IBAN checksum, BIC structure, …) is applied to every
structural match before it is recorded.  Raw regex matching without checksum validation
produces an unacceptably high false-positive rate for financial identifiers – e.g. any
16-digit number would look like a credit card without a Luhn check.

Patterns are loaded from ``config_types.json`` by default. Additional patterns can be
loaded at runtime from an external YAML or JSON file via
``RegexEngine.load_custom_patterns(path)``.
"""

import concurrent.futures
import logging
import re

from core.config import Config
from core.engines.base import DetectionResult

# Exposed for test patching and runtime type mapping
from core.matches import config_regex_sorted

_logger = logging.getLogger(__name__)

# ReDoS protection constants
_REGEX_CHUNK_SIZE = 1_048_576  # 1 MB per chunk
_REGEX_TIMEOUT_SECONDS = 10  # seconds per chunk

try:
    from validators.credit_card_validator import CreditCardValidator
except ImportError:
    CreditCardValidator = None  # type: ignore[assignment]
except Exception as _exc:  # pragma: no cover
    _logger.warning("Failed to load CreditCardValidator: %s", _exc)
    CreditCardValidator = None  # type: ignore[assignment]

try:
    from validators.iban_validator import IbanValidator
except ImportError:
    IbanValidator = None  # type: ignore[assignment]
except Exception as _exc:  # pragma: no cover
    _logger.warning("Failed to load IbanValidator: %s", _exc)
    IbanValidator = None  # type: ignore[assignment]

try:
    from validators.tax_id_validator import TaxIdValidator
except ImportError:
    TaxIdValidator = None  # type: ignore[assignment]
except Exception as _exc:  # pragma: no cover
    _logger.warning("Failed to load TaxIdValidator: %s", _exc)
    TaxIdValidator = None  # type: ignore[assignment]

try:
    from validators.bic_validator import BicValidator
except ImportError:
    BicValidator = None  # type: ignore[assignment]
except Exception as _exc:  # pragma: no cover
    _logger.warning("Failed to load BicValidator: %s", _exc)
    BicValidator = None  # type: ignore[assignment]


class RegexEngine:
    """Regex-based detection engine.

    Runs a single compiled alternation of all configured patterns against each text
    chunk with ReDoS protection (chunking + per-chunk timeout).  Post-validation
    via checksum validators (Luhn, IBAN, BIC, tax ID) eliminates false positives
    before results reach the match container.
    """

    name = "regex"
    # Regex detection is thread-safe (pure computation on inputs + shared compiled pattern).
    thread_safe = True

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
        # Process in chunks to limit regex execution time
        chunks = (
            self._split_text(text) if len(text) > _REGEX_CHUNK_SIZE else [(text, 0)]
        )

        for chunk, base_offset in chunks:
            chunk_results = self._detect_chunk(chunk, base_offset)
            results.extend(chunk_results)

        return results

    def _split_text(self, text: str) -> list[tuple[str, int]]:
        """Split text into overlapping chunks for safe regex processing."""
        overlap = 200  # overlap to avoid missing matches at boundaries
        chunks: list[tuple[str, int]] = []
        start = 0
        while start < len(text):
            end = min(start + _REGEX_CHUNK_SIZE, len(text))
            chunks.append((text[start:end], start))
            start = end - overlap if end < len(text) else end
        return chunks

    def _detect_chunk(self, text: str, base_offset: int) -> list[DetectionResult]:
        """Detect PII in a single chunk with timeout protection."""
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._run_finditer, text, base_offset)
                return future.result(timeout=_REGEX_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            _logger.warning(
                "Regex detection timed out after %ds on chunk of %d chars",
                _REGEX_TIMEOUT_SECONDS,
                len(text),
            )
            return []
        except re.error as exc:
            _logger.warning("Regex error during detection: %s", exc)
            return []

    def _run_finditer(self, text: str, base_offset: int) -> list[DetectionResult]:
        """Run finditer and collect results (executed in worker thread)."""
        results = []
        for match in self.pattern.finditer(text):
            entity_type, config_entry = self._get_entity_type(match)
            # If this isn't the "combined" pattern with groups, fall back to a generic label
            if not entity_type:
                entity_type = "REGEX_MATCH"

            # Validate if required
            if config_entry and not self._validate_match(match, config_entry):
                continue

            # Validated patterns (Luhn, IBAN checksum, …) get confidence 1.0 because
            # a checksum-passing match is almost certainly a real PII value.
            # Unvalidated patterns get 0.8 to signal slightly lower certainty and to
            # allow confidence-threshold filtering to distinguish them from validated ones.
            _confidence = (
                1.0 if (config_entry and "validation" in config_entry) else 0.8
            )
            results.append(
                DetectionResult(
                    text=match.group(),
                    entity_type=entity_type,
                    confidence=_confidence,
                    engine_name="regex",
                    offset=match.start() + base_offset,
                )
            )
        return results

    def _get_entity_type(self, match) -> tuple[str | None, dict | None]:
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
            if CreditCardValidator is None:
                return True
            is_valid, _card_type = CreditCardValidator.validate(match.group())
            return is_valid

        if validation_type == "iban":
            if IbanValidator is None:
                return True
            return IbanValidator.validate(match.group())

        if validation_type == "tax_id":
            if TaxIdValidator is None:
                return True
            return TaxIdValidator.validate(match.group())

        if validation_type == "bic":
            if BicValidator is None:
                return True
            return BicValidator.validate(match.group())

        return True

    def is_available(self) -> bool:
        """Check if regex engine is available.

        Returns:
            True if enabled and pattern is loaded
        """
        return self.enabled and self.pattern is not None

    @staticmethod
    def load_custom_patterns(path: str) -> list[dict]:
        """Load additional regex patterns from an external YAML or JSON file.

        The file should contain a list of pattern entries, each with at least:
        - ``expression``: the regex pattern string
        - ``label``: the PII type label (e.g. ``REGEX_CUSTOM_ID``)

        Optional fields:
        - ``validation``: validator name (``luhn``, ``iban``, ``tax_id``, ``bic``)
        - ``description``: human-readable description

        Example YAML::

            patterns:
              - label: REGEX_CUSTOM_ID
                expression: "CUST-\\\\d{8}"
                description: "Custom customer ID"
              - label: REGEX_EMPLOYEE_ID
                expression: "EMP[A-Z]\\\\d{6}"

        Args:
            path: Path to the YAML or JSON file.

        Returns:
            List of pattern dicts suitable for extending config_types regex entries.
        """
        import json as _json

        try:
            if path.lower().endswith((".yaml", ".yml")):
                try:
                    import yaml  # type: ignore

                    with open(path, encoding="utf-8") as fh:
                        data = yaml.safe_load(fh)
                except ImportError:
                    _logger.warning(
                        "PyYAML not installed; cannot load YAML regex patterns."
                    )
                    return []
            else:
                with open(path, encoding="utf-8") as fh:
                    data = _json.load(fh)

            if isinstance(data, dict):
                data = data.get("patterns", data.get("regex", []))

            if not isinstance(data, list):
                _logger.warning(
                    "Custom regex patterns file must contain a list; got %s",
                    type(data).__name__,
                )
                return []

            valid_entries: list[dict] = []
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                if "expression" not in entry or "label" not in entry:
                    _logger.warning(
                        "Skipping custom regex entry without 'expression' and 'label': %s",
                        entry,
                    )
                    continue
                valid_entries.append(entry)

            _logger.debug(
                "Loaded %d custom regex patterns from %s", len(valid_entries), path
            )
            return valid_entries

        except FileNotFoundError:
            _logger.warning("Custom regex patterns file not found: %s", path)
            return []
        except Exception as exc:
            _logger.warning(
                "Failed to load custom regex patterns from %s: %s", path, exc
            )
            return []
