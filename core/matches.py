from __future__ import annotations

import csv
import logging
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.resources import load_config_types
from core.severity import classify as _classify_severity

if TYPE_CHECKING:
    from core.protocols import AnalyticsStoreProtocol, OutputWriterProtocol

_DEDUP_MAX_ENTRIES = 500_000
_MAX_WHITELIST_REGEX_LEN = 500

_logger = logging.getLogger("pbd-toolkit")

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
    # When True, fuse confidence scores from multiple engines for the same
    # (text, file, type) triple. The fused score is max(scores) + bonus based
    # on the number of confirming engines, capped at 1.0.
    enable_confidence_fusion: bool = False
    # Minimum confidence threshold (0.0 = accept all)
    min_confidence: float = 0.0
    # Minimum severity level for output (None = no filter). Does not affect pii_matches storage.
    min_severity: str | None = None
    # Configurable limits (defaults match previous hardcoded values)
    dedup_max_entries: int = _DEDUP_MAX_ENTRIES
    max_whitelist_regex_len: int = _MAX_WHITELIST_REGEX_LEN
    # Compiled regex pattern for efficient whitelist matching (pre-compiled at init)
    _whitelist_pattern: re.Pattern | None = field(default=None, init=False, repr=False)
    # Ordered dict of (text_lower, file, type) keys for O(1) deduplication lookup
    # with bounded capacity (FIFO eviction when exceeding dedup_max_entries)
    _seen_keys: OrderedDict = field(default_factory=OrderedDict, init=False, repr=False)
    # Maps dedup_key → (list_index, set_of_engines) for confidence fusion
    _fusion_index: dict = field(default_factory=dict, init=False, repr=False)
    # CSV writer for output (injected dependency, only used for CSV format)
    _csv_writer: csv.writer | None = field(default=None, init=False, repr=False)
    # Output format (csv, json, xlsx)
    _output_format: str = field(default="csv", init=False, repr=False)
    # Optional output writer for streaming formats (implements OutputWriterProtocol).
    _output_writer: OutputWriterProtocol | None = field(
        default=None, init=False, repr=False
    )
    # Optional analytics store (implements AnalyticsStoreProtocol).
    _analytics_store: AnalyticsStoreProtocol | None = field(
        default=None, init=False, repr=False
    )
    _analytics_session_id: str | None = field(default=None, init=False, repr=False)
    # Internal lock for thread-safe match aggregation / streaming writes
    _lock: threading.Lock = field(
        default_factory=threading.Lock, init=False, repr=False
    )

    def __post_init__(self) -> None:
        """Pre-compile whitelist patterns at initialization time."""
        if self.whitelist:
            self._compile_whitelist_pattern()

    def set_whitelist(self, whitelist: list[str]) -> None:
        """Set the whitelist and pre-compile the regex pattern atomically.

        Args:
            whitelist: List of whitelist entries.
        """
        with self._lock:
            self.whitelist = whitelist
            self._whitelist_pattern = None
            if whitelist:
                max_len = self.max_whitelist_regex_len
                patterns = [self._entry_to_regex(w, max_len) for w in whitelist if w]
                valid = [p for p in patterns if p]
                if valid:
                    self._whitelist_pattern = re.compile("|".join(valid))

    def set_csv_writer(self, csv_writer: csv.writer | None) -> None:
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
        self, store: AnalyticsStoreProtocol | None, session_id: str | None = None
    ) -> None:
        """Set an analytics store for persisting findings.

        The store must implement :class:`~core.protocols.AnalyticsStoreProtocol`.
        """
        with self._lock:
            self._analytics_store = store
            self._analytics_session_id = session_id

    def set_output_writer(self, output_writer: OutputWriterProtocol | None) -> None:
        """Set an output writer for streaming formats.

        The writer must implement :class:`~core.protocols.OutputWriterProtocol`.
        Uses TYPE_CHECKING import to avoid circular imports with ``core.writers``.
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
    def _entry_to_regex(
        entry: str, max_regex_len: int = _MAX_WHITELIST_REGEX_LEN
    ) -> str:
        """Convert a single whitelist entry to a regex fragment.

        Supported formats:
          - ``regex:PATTERN``  – raw regex (used as-is, validated)
          - ``*foo*``          – wildcard (``*`` maps to ``.*``)
          - ``plain text``     – exact substring match (escaped)
        """
        if entry.startswith("regex:"):
            raw = entry[6:]
            if len(raw) > max_regex_len:
                _logger.warning(
                    "Whitelist regex too long (%d chars), skipping: %.40s...",
                    len(raw),
                    raw,
                )
                return ""  # empty fragment is harmless in alternation
            try:
                re.compile(raw)
            except re.error as exc:
                _logger.warning("Invalid whitelist regex '%s': %s", raw, exc)
                return ""
            return raw
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
                max_len = self.max_whitelist_regex_len
                patterns = [
                    self._entry_to_regex(w, max_len) for w in self.whitelist if w
                ]
                valid = [p for p in patterns if p]
                if valid:
                    self._whitelist_pattern = re.compile("|".join(valid))

    def _is_whitelisted(self, text: str) -> bool:
        """Check if text matches whitelist pattern with timeout protection."""
        import concurrent.futures

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._whitelist_pattern.search, text)
                result = future.result(timeout=2)
                return result is not None
        except concurrent.futures.TimeoutError:
            _logger.warning(
                "Whitelist regex timed out on text of %d chars",
                len(text),
            )
            return False
        except re.error as exc:
            _logger.warning("Whitelist regex error: %s", exc)
            return False

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
        pm: PiiMatch | None = None
        analytics_store = None
        analytics_session_id = None

        with self._lock:
            whitelisted: bool = False

            # Use pre-compiled regex pattern for efficient whitelist checking.
            # The pattern is compiled at init or when set_whitelist() is called.
            # Lazy fallback retained for safety if whitelist was set directly.
            if self.whitelist:
                if self._whitelist_pattern is None:
                    patterns = [self._entry_to_regex(w) for w in self.whitelist if w]
                    if patterns:
                        self._whitelist_pattern = re.compile("|".join(patterns))
                if self._whitelist_pattern and self._is_whitelisted(text):
                    whitelisted = True

            if whitelisted:
                return

            # Confidence filtering: skip findings below threshold
            if self.min_confidence > 0.0 and ner_score is not None:
                if ner_score < self.min_confidence:
                    return

            # Confidence fusion: when the same (text, file, type) is found by
            # multiple engines, update the stored match's score instead of
            # creating a new entry.  The fused score is:
            #   max(all_scores) + 0.05 * (n_engines - 1), capped at 1.0
            if self.enable_confidence_fusion:
                fusion_key = (text.lower(), file, type)
                if fusion_key in self._fusion_index:
                    idx, engines_seen = self._fusion_index[fusion_key]
                    if engine not in engines_seen:
                        engines_seen.add(engine)
                        existing = self.pii_matches[idx]
                        scores = [
                            s
                            for s in [existing.ner_score, ner_score]
                            if s is not None
                        ]
                        if scores:
                            bonus = 0.05 * (len(engines_seen) - 1)
                            existing.ner_score = min(1.0, max(scores) + bonus)
                        existing.metadata["fused_engines"] = sorted(engines_seen)
                    return

            # Deduplication: skip if an identical (text, file, type) match is already stored
            if self.enable_deduplication:
                dedup_key = (text.lower(), file, type)
                if dedup_key in self._seen_keys:
                    return
                self._seen_keys[dedup_key] = None
                if len(self._seen_keys) > self.dedup_max_entries:
                    self._seen_keys.popitem(last=False)  # evict oldest

            pm = PiiMatch(
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

            # Register in fusion index for future multi-engine matches
            if self.enable_confidence_fusion:
                fusion_key = (text.lower(), file, type)
                self._fusion_index[fusion_key] = (len(self.pii_matches) - 1, {engine})

            # Check min_severity output filter before writing to output streams.
            # pii_matches always keeps all matches for post-scan processing (fail_on_severity, redaction).
            _meets_min_sev = True
            if self.min_severity:
                from core.severity import _LEVEL_WEIGHT as _SW

                _threshold = _SW.get(self.min_severity, 0)
                _pm_weight = _SW.get(pm.severity or "", 0)
                _meets_min_sev = _pm_weight >= _threshold

            if not _meets_min_sev:
                return

            # Only write directly for CSV format
            if self._output_format == "csv" and self._csv_writer:
                # Keep CSV row shape stable: Match, File, Type, Score, Engine, Severity
                row = [pm.text, pm.file, pm.type, pm.ner_score, pm.engine, pm.severity]
                self._csv_writer.writerow(row)

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

            # Capture analytics references while holding lock
            analytics_store = self._analytics_store
            analytics_session_id = self._analytics_session_id

        # Persist finding to analytics database outside the lock (if configured).
        if pm is not None and analytics_store is not None and analytics_session_id:
            try:
                record = getattr(analytics_store, "record_finding_from_match", None)
                if callable(record):
                    record(analytics_session_id, pm)
            except Exception:
                import logging

                logging.getLogger("pbd-toolkit").debug(
                    "Analytics recording failed", exc_info=True
                )

    """ Helper function for adding regex-based matches to the matches container. """

    def add_matches_regex(self, matches: re.Match | None, path: str) -> None:
        if matches is not None:
            type: str | None = None
            config_entry: dict | None = None

            for idx, item in enumerate(matches.groups()):
                if item is not None:
                    config_entry = config_regex_sorted.get(idx)
                    if config_entry is None:
                        return  # unknown regex group index, skip
                    type = config_entry["label"]
                    break

            # Validate if validation is required
            if config_entry and "validation" in config_entry:
                from validators import get_validator

                validator = get_validator(config_entry["validation"])
                if validator is not None:
                    result = validator.validate(matches.group())
                    # CreditCardValidator returns Tuple[bool, str|None]; others return bool
                    is_valid = result[0] if isinstance(result, tuple) else result
                    if not is_valid:
                        return

            self.__add_match(text=matches.group(), file=path, type=type, engine="regex")

    """ Helper function for adding AI-based NER matches to the matches container. """

    def add_matches_ner(self, matches: list[dict] | None, path: str) -> None:
        if matches is not None:
            for match in matches:
                type: str | None = None

                config_entry = config_ainer_sorted.get(match["label"])
                if config_entry is None:
                    continue  # unknown NER label, skip
                type = config_entry["label"]

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
        self,
        results: list,
        file_path: str,
        source_text: str | None = None,
        context_chars: int = 0,
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
