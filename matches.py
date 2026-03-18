import csv
import re
import threading
from dataclasses import dataclass, field
from typing import Optional

from core.resources import load_config_types
from core.severity import classify as _classify_severity

# configure support match types
config = load_config_types()
config_ainer = config["ai-ner"]
config_regex = config["regex"]

config_regex_sorted: dict[str, dict] = {}

""" Since we use a concatenated regex that contains multiple types of checks (e. g. bank account, email all in one)
    for efficiency reasons, we now have to figure out exactly which type of match it actually is. This is only possible
    by looking at the position of the group storing the match within the overall regex.
    Sort the regex configuration by position accordingly. """

for conf in config_regex:
    config_regex_sorted[conf["regex_compiled_pos"]] = conf

""" And sort the AI NER configuration by matching terms. """
config_ainer_sorted: dict[str, dict] = {}

for conf in config_ainer:
    config_ainer_sorted[conf["term"]] = conf

""" Class for holding a singular found PII match.

    An __init__ method is implied by the @dataclass decorator. """


@dataclass
class PiiMatch:
    # The text that represents PII
    text: str
    # The file in which the represented PII was found
    file: str
    # The type of PII found. Only types explicitly supported by this application are valid.
    type: str
    # Only for PII found via AI-assisted NER: The likelihood with which a PII string represents a specific PII type, self-assessed by the model used.
    ner_score: float | None = None
    # Name of the engine that found this match (e.g., "regex", "gliner", "spacy-ner")
    engine: str | None = None
    # Additional engine-specific metadata
    metadata: dict = field(default_factory=dict)
    # Severity level: LOW | MEDIUM | HIGH | CRITICAL
    severity: str | None = None
    # Context: surrounding text for easier review (populated when --context-chars > 0)
    context_before: str | None = None
    context_after: str | None = None
    char_offset: int | None = None


""" Class for holding all PII matches found. The aim is to provide helpful functions for processing
    and managing these matches.

    An __init__ method is implied by the @dataclass decorator. """


@dataclass
class PiiMatchContainer:
    pii_matches: list[PiiMatch] = field(default_factory=list)
    # Whitelist used for excluding strings from being identified as PII
    whitelist: list[str] = field(default_factory=list)
    # When True, suppress duplicate (text, file, type) matches across engines.
    # The first match (highest confidence if available) wins.
    enable_deduplication: bool = False
    # Minimum confidence threshold (0.0 = accept all)
    min_confidence: float = 0.0
    # Compiled regex pattern for efficient whitelist matching
    _whitelist_pattern: re.Pattern | None = field(default=None, init=False, repr=False)
    # Set of (text_lower, file, type) keys for O(1) deduplication lookup
    _seen_keys: set = field(default_factory=set, init=False, repr=False)
    # CSV writer for output (injected dependency, only used for CSV format)
    _csv_writer: Optional[csv.writer] = field(default=None, init=False, repr=False)
    # Output format (csv, json, xlsx)
    _output_format: str = field(default="csv", init=False, repr=False)
    # Optional output writer for streaming formats (duck-typed: must implement write_match()).
    _output_writer: Optional[object] = field(default=None, init=False, repr=False)
    # Optional analytics store (duck-typed: must implement record_finding_from_match())
    _analytics_store: Optional[object] = field(default=None, init=False, repr=False)
    _analytics_session_id: Optional[str] = field(default=None, init=False, repr=False)
    # Internal lock for thread-safe match aggregation / streaming writes
    _lock: threading.Lock = field(
        default_factory=threading.Lock, init=False, repr=False
    )

    def set_csv_writer(self, csv_writer: Optional[csv.writer]) -> None:
        """Set the CSV writer for output.

        Args:
            csv_writer: CSV writer instance
        """
        with self._lock:
            self._csv_writer = csv_writer

    def set_output_format(self, output_format: str) -> None:
        """Set the output format.

        Args:
            output_format: Output format (csv, json, xlsx)
        """
        with self._lock:
            self._output_format = output_format

    def set_analytics_store(
        self, store: Optional[object], session_id: Optional[str] = None
    ) -> None:
        """Set an analytics store for persisting findings.

        Duck-typed to avoid circular imports – the store must implement
        ``record_finding_from_match(session_id, match)``.
        """
        with self._lock:
            self._analytics_store = store
            self._analytics_session_id = session_id

    def set_output_writer(self, output_writer: Optional[object]) -> None:
        """Set an output writer for streaming formats.

        This is intentionally duck-typed to avoid import cycles:
        `core.writers` imports `matches.PiiMatch`, so `matches` must not import
        `core.writers.OutputWriter`.
        """
        with self._lock:
            self._output_writer = output_writer

    def by_file(self) -> dict[str, list[PiiMatch]]:
        """Group PII matches by file path.

        Returns:
            Dictionary mapping file paths to lists of PiiMatch objects found in each file.
        """
        with self._lock:
            results: dict[str, list[PiiMatch]] = {}
            for pm in self.pii_matches:
                if pm.file not in results:
                    results[pm.file] = []
                results[pm.file].append(pm)
            return results

    @staticmethod
    def _entry_to_regex(entry: str) -> str:
        """Convert a single whitelist entry to a regex fragment.

        Supported formats:
          - ``regex:PATTERN``  – raw regex (used as-is)
          - ``*foo*``          – wildcard (``*`` maps to ``.*``)
          - ``plain text``     – exact substring match (escaped)
        """
        if entry.startswith("regex:"):
            return entry[6:]
        if "*" in entry:
            # Wildcard mode: split on *, escape non-wildcard parts
            parts = entry.split("*")
            return ".*".join(re.escape(p) for p in parts)
        return re.escape(entry)

    def _compile_whitelist_pattern(self) -> None:
        """Compile whitelist entries into a regex pattern for efficient matching.

        Supports three entry formats: plain text, wildcard (``*``), and raw
        regex (``regex:`` prefix).
        """
        with self._lock:
            if self.whitelist and self._whitelist_pattern is None:
                patterns = [self._entry_to_regex(w) for w in self.whitelist if w]
                if patterns:
                    self._whitelist_pattern = re.compile("|".join(patterns))

    """ Helper function for adding matches to the matches container. This generic, internal method is
        called by the other methods intended for public use, its aim is to reduce redundancy. """

    def __add_match(
        self,
        text: str,
        file: str,
        type: str,
        ner_score: float | None = None,
        engine: str | None = None,
        metadata: dict | None = None,
        context_before: str | None = None,
        context_after: str | None = None,
        char_offset: int | None = None,
    ) -> None:
        with self._lock:
            whitelisted: bool = False

            # Use compiled regex pattern for efficient whitelist checking
            if self.whitelist:
                if self._whitelist_pattern is None:
                    # Inline compile while holding lock (avoid races)
                    patterns = [self._entry_to_regex(w) for w in self.whitelist if w]
                    if patterns:
                        self._whitelist_pattern = re.compile("|".join(patterns))
                if self._whitelist_pattern and self._whitelist_pattern.search(text):
                    whitelisted = True

            if whitelisted:
                return

            # Confidence filtering: skip findings below threshold
            if self.min_confidence > 0.0 and ner_score is not None:
                if ner_score < self.min_confidence:
                    return

            # Deduplication: skip if an identical (text, file, type) match is already stored
            if self.enable_deduplication:
                dedup_key = (text.lower(), file, type)
                if dedup_key in self._seen_keys:
                    return
                self._seen_keys.add(dedup_key)

            pm: PiiMatch = PiiMatch(
                text=text,
                file=file,
                type=type,
                ner_score=ner_score,
                engine=engine,
                metadata=metadata or {},
                severity=_classify_severity(type) if type else None,
                context_before=context_before,
                context_after=context_after,
                char_offset=char_offset,
            )
            self.pii_matches.append(pm)

            # Only write directly for CSV format
            if self._output_format == "csv" and self._csv_writer:
                # Keep CSV row shape stable: Match, File, Type, Score, Engine, Severity
                row = [pm.text, pm.file, pm.type, pm.ner_score, pm.engine, pm.severity]
                try:
                    self._csv_writer.writerow(row)
                except TypeError:
                    # Some tests provide a "writer" where writerow is a function
                    # assigned to an instance, which becomes a bound method and
                    # receives an extra positional argument. Fall back to calling
                    # the underlying function without binding.
                    writerow = getattr(self._csv_writer, "writerow", None)
                    if writerow is not None and hasattr(writerow, "__func__"):
                        writerow.__func__(row)  # type: ignore[attr-defined]
                    else:
                        raise

            # Stream to output writer for non-CSV formats that support streaming.
            # CSV is handled above to keep backward-compatible behavior stable.
            if self._output_format != "csv" and self._output_writer is not None:
                supports_streaming = getattr(
                    self._output_writer, "supports_streaming", False
                )
                if supports_streaming:
                    write_match = getattr(self._output_writer, "write_match", None)
                    if callable(write_match):
                        write_match(pm)

            # Persist finding to analytics database (if configured).
            if self._analytics_store is not None and self._analytics_session_id:
                try:
                    record = getattr(self._analytics_store, "record_finding_from_match", None)
                    if callable(record):
                        record(self._analytics_session_id, pm)
                except Exception:
                    pass  # Never let analytics recording break the scan

    """ Helper function for adding regex-based matches to the matches container. """

    def add_matches_regex(self, matches: re.Match | None, path: str) -> None:
        if matches is not None:
            type: str | None = None
            config_entry: dict | None = None

            for idx, item in enumerate(matches.groups()):
                if item is not None:
                    type = config_regex_sorted[idx]["label"]
                    config_entry = config_regex_sorted[idx]
                    break

            # Validate if validation is required
            if config_entry and "validation" in config_entry:
                validation_type = config_entry["validation"]

                if validation_type == "luhn":
                    try:
                        from validators.credit_card_validator import CreditCardValidator

                        is_valid, card_type = CreditCardValidator.validate(
                            matches.group()
                        )
                        if not is_valid:
                            return
                    except ImportError:
                        pass

                elif validation_type == "iban":
                    try:
                        from validators.iban_validator import IbanValidator

                        if not IbanValidator.validate(matches.group()):
                            return
                    except ImportError:
                        pass

                elif validation_type == "tax_id":
                    try:
                        from validators.tax_id_validator import TaxIdValidator

                        if not TaxIdValidator.validate(matches.group()):
                            return
                    except ImportError:
                        pass

                elif validation_type == "bic":
                    try:
                        from validators.bic_validator import BicValidator

                        if not BicValidator.validate(matches.group()):
                            return
                    except ImportError:
                        pass

            self.__add_match(text=matches.group(), file=path, type=type, engine="regex")

    """ Helper function for adding AI-based NER matches to the matches container. """

    def add_matches_ner(self, matches: list[dict] | None, path: str) -> None:
        if matches is not None:
            for match in matches:
                type: str | None = None

                type = config_ainer_sorted[match["label"]]["label"]

                self.__add_match(
                    text=match["text"],
                    file=path,
                    type=type,
                    ner_score=match["score"],
                    engine="gliner",
                    metadata={"gliner_label": match.get("label", "")},
                )

    """ Helper function for adding detection results from engines. """

    def add_detection_results(
        self, results: list, file_path: str, source_text: str | None = None, context_chars: int = 0
    ) -> None:
        """Add detection results from engine registry.

        Args:
            results: List of DetectionResult objects
            file_path: Path to the file where matches were found
            source_text: Original text chunk (for context extraction)
            context_chars: Number of surrounding chars to capture (0 = disabled)
        """
        for result in results:
            ctx_before = None
            ctx_after = None
            offset = getattr(result, "offset", None)

            if context_chars > 0 and source_text and offset is not None:
                start = max(0, offset - context_chars)
                end_match = offset + len(result.text)
                end = min(len(source_text), end_match + context_chars)
                ctx_before = source_text[start:offset]
                ctx_after = source_text[end_match:end]

            self.__add_match(
                text=result.text,
                file=file_path,
                type=result.entity_type,
                ner_score=result.confidence,
                engine=result.engine_name,
                metadata=result.metadata,
                context_before=ctx_before,
                context_after=ctx_after,
                char_offset=offset,
            )
