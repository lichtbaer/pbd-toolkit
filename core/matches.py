"""PII match data structures, deduplication, confidence fusion, and output streaming.

This module is the central aggregation point for all findings produced by detection
engines.  Every engine result flows through ``PiiMatchContainer.__add_match``, which
enforces:

- Whitelist filtering (plain, wildcard, and raw-regex entries)
- Confidence thresholding (discard findings below ``min_confidence``)
- Deduplication: the same (text, file, type) triple found by multiple engines is
  stored only once; the highest-confidence occurrence wins.
- Confidence fusion: when deduplication is *off*, multiple-engine confirmation of the
  same triple raises the fused score slightly to reflect corroborating evidence.
- Severity-level output filtering (``min_severity``) without discarding matches from
  the in-memory list, which is needed for post-scan operations such as redaction and
  ``--fail-on-severity``.

Business context:
  PII detection is inherently noisy.  Deduplication and confidence fusion are GDPR
  audit hygiene features: they reduce duplicate report rows without losing any actual
  finding.  The whitelist lets operators exclude known-safe strings (e.g. demo data,
  test fixtures) from compliance reports.
"""

from __future__ import annotations

import logging
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.entity_types import (
    CONTEXT_REQUIREMENT_WINDOW,
    canonical_for,
    context_requirement_for,
    validation_rule_for,
)
from core.resources import load_config_types
from core.severity import classify as _classify_severity

if TYPE_CHECKING:
    import _csv

    from core.protocols import AnalyticsStoreProtocol, OutputWriterProtocol

# FIFO cap prevents unbounded memory growth during large directory scans.
# At ~400 bytes per key tuple, 500 k entries ≈ 200 MB worst-case overhead.
_DEDUP_MAX_ENTRIES = 500_000

# Protect against ReDoS: whitelist patterns with very long alternations can cause
# catastrophic backtracking.  Entries exceeding this limit are silently skipped and
# a warning is logged so operators can fix their whitelist configuration.
_MAX_WHITELIST_REGEX_LEN = 500

# Default per-engine reliability weights for confidence fusion (weighted Noisy-OR).
# They scale how much an additional engine's score contributes when it corroborates a
# finding already reported by another engine.  Regex (checksum-validated structured
# types) is the most reliable; coarse vector-similarity the least.  Values are rough
# priors meant to be tuned against the evaluation harness, not exact probabilities.
_DEFAULT_FUSION_WEIGHTS: dict[str, float] = {
    "regex": 0.95,
    "pydantic-ai": 0.85,
    "gliner": 0.80,
    "spacy-ner": 0.70,
    "vector-search": 0.55,
}
_DEFAULT_FUSION_WEIGHT = 0.70

_logger = logging.getLogger("pbd-toolkit")

# configure support match types
config = load_config_types()
config_ainer = config["ai-ner"]
config_regex = config["regex"]

config_regex_sorted: dict[int, dict] = {}

# The regex engine compiles all patterns into a single alternation (e.g. bank account |
# email | phone | …) for performance: one pass over the text matches every type at once.
# The trade-off is that the matched capture-group *position* is the only way to determine
# which PII type fired.  This dict maps group position → config entry for O(1) lookup.
for conf in config_regex:
    config_regex_sorted[conf["regex_compiled_pos"]] = conf

# NER engines return a label string (e.g. "PERSON", "IBAN") rather than a group index,
# so a term → config entry mapping is sufficient.
config_ainer_sorted: dict[str, dict] = {}

for conf in config_ainer:
    config_ainer_sorted[conf["term"]] = conf


@dataclass
class PiiMatch:
    """A single PII finding produced by any detection engine.

    Instances are immutable after creation (engines must not mutate them).
    The ``severity`` field is auto-populated from the type label at creation
    time so that output writers always have a pre-classified value.
    """

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


@dataclass
class PiiMatchContainer:
    """Thread-safe container for all PII matches collected during a scan.

    Centralises filtering, deduplication, confidence fusion, and output streaming
    so that callers (TextProcessor, scanner workers) only need to call ``add_*``
    methods without knowing the downstream format or storage backend.

    Thread safety: all public mutating methods acquire ``_lock``.  The lock is
    intentionally coarse-grained (one per container) because match writes are fast
    compared to the I/O and ML inference happening on worker threads.
    """

    pii_matches: list[PiiMatch] = field(default_factory=list)
    # Whitelist used for excluding strings from being identified as PII
    whitelist: list[str] = field(default_factory=list)
    # When True, suppress duplicate (text, file, type) matches across engines.
    # The first match (highest confidence if available) wins.
    enable_deduplication: bool = False
    # When True, fuse confidence scores from multiple engines for the same
    # (text, file, type) triple via weighted Noisy-OR: the first engine contributes at
    # full weight and each corroborating engine raises the score by
    # 1 - Π(1 - wᵢ·sᵢ), capped at 1.0.  This rewards agreement monotonically (more than
    # a flat bonus) while the per-engine weights (engine_fusion_weights) dampen
    # unreliable engines — engine scores are not statistically independent (all see the
    # same text), so weights below 1.0 avoid over-counting corroboration.  A single
    # engine's score is left unchanged.
    enable_confidence_fusion: bool = False
    # Per-engine reliability weights for the Noisy-OR fusion above.  Empty -> defaults
    # (_DEFAULT_FUSION_WEIGHTS); unknown engines fall back to _DEFAULT_FUSION_WEIGHT.
    engine_fusion_weights: dict = field(default_factory=dict)
    # Minimum confidence threshold (0.0 = accept all)
    min_confidence: float = 0.0
    # Minimum severity level for output (None = no filter). Does not affect pii_matches storage.
    min_severity: str | None = None
    # When True, deduplication and confidence fusion group findings by their *canonical*
    # entity type (see core.entity_types) instead of the raw engine label.  This is what
    # lets a credit card found by both the regex engine (REGEX_CREDIT_CARD) and the vector
    # engine (VECTOR_CREDITCARD) fuse into a single corroborated finding.
    cross_engine_normalization: bool = True
    # When True, structured findings whose canonical type carries a checksum validator
    # (IBAN, credit card, tax ID, BIC) are checksum-validated regardless of which engine
    # produced them; invalid candidates are discarded.  This extends the regex engine's
    # existing validation to LLM/vector findings, cutting their false-positive rate.
    validate_structured_findings: bool = True
    # When True, findings of context-required canonical types (see
    # core.entity_types._CONTEXT_REQUIREMENTS, currently BIC) are only kept when a
    # related keyword appears near the match.  This rejects uppercase dictionary words
    # that satisfy the weak BIC shape but are not bank codes.  Requires the surrounding
    # text to be available; when it is not, the finding is kept (conservative).
    require_context_for_ambiguous: bool = True
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
    _csv_writer: _csv.Writer | None = field(default=None, init=False, repr=False)
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

    def set_csv_writer(self, csv_writer: _csv.Writer | None) -> None:
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

        if self._whitelist_pattern is None:
            return False

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

    def _grouping_key(self, text: str, file: str, type: str) -> tuple[str, str, str]:
        """Key used for deduplication and confidence fusion.

        When ``cross_engine_normalization`` is on, the type component is the canonical
        entity type so that the same real-world PII reported by different engines (with
        different raw labels) groups together.  Otherwise the raw label is used, which
        preserves the previous per-engine behaviour.
        """
        type_key = canonical_for(type) if self.cross_engine_normalization else type
        return (text.lower(), file, type_key)

    def _fusion_weight(self, engine: str | None) -> float:
        """Reliability weight for *engine* in Noisy-OR confidence fusion."""
        if engine and engine in self.engine_fusion_weights:
            return float(self.engine_fusion_weights[engine])
        return _DEFAULT_FUSION_WEIGHTS.get(engine or "", _DEFAULT_FUSION_WEIGHT)

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
        """Internal entry point for all match additions; enforces all filtering rules.

        Caller does NOT need to hold ``_lock`` – this method acquires it internally.
        The analytics store write is intentionally done *outside* the lock to avoid
        blocking other threads while waiting on I/O.
        """
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

            # Confidence fusion: when the same (text, file, type) is found by multiple
            # engines, update the stored match's score (weighted Noisy-OR) instead of
            # creating a new entry.  ``comp`` tracks Π(1 - wᵢ·sᵢ); the fused score is
            # 1 - comp.  The first engine is folded in at full weight (so a single
            # engine keeps its raw score); corroborating engines are weighted.
            if self.enable_confidence_fusion:
                fusion_key = self._grouping_key(text, file, type)
                if fusion_key in self._fusion_index:
                    idx, engines_seen, comp = self._fusion_index[fusion_key]
                    if engine not in engines_seen:
                        engines_seen.add(engine)
                        if ner_score is not None:
                            comp *= 1.0 - self._fusion_weight(engine) * ner_score
                            existing = self.pii_matches[idx]
                            existing.ner_score = round(min(1.0, 1.0 - comp), 4)
                        self.pii_matches[idx].metadata["fused_engines"] = sorted(
                            engines_seen
                        )
                        self._fusion_index[fusion_key] = (idx, engines_seen, comp)
                    return

            # Deduplication: skip if an identical (text, file, type) match is already stored
            if self.enable_deduplication:
                dedup_key = self._grouping_key(text, file, type)
                if dedup_key in self._seen_keys:
                    return
                self._seen_keys[dedup_key] = None
                if len(self._seen_keys) > self.dedup_max_entries:
                    self._seen_keys.popitem(last=False)  # evict oldest

            # Record the canonical type alongside the raw label so reports and the
            # evaluation harness can group cross-engine findings without re-deriving it.
            match_metadata = dict(metadata or {})
            if type and "canonical_type" not in match_metadata:
                match_metadata["canonical_type"] = canonical_for(type)

            pm = PiiMatch(
                text=text,
                file=file,
                type=type,
                ner_score=ner_score,
                engine=engine,
                metadata=match_metadata,
                severity=_classify_severity(type) if type else None,
                context_before=context_before,
                context_after=context_after,
                char_offset=char_offset,
            )
            self.pii_matches.append(pm)

            # Register in fusion index for future multi-engine matches.  The first
            # engine enters at full weight (comp = 1 - s) so a lone finding keeps its
            # raw score; corroborating engines are folded in weighted (see above).
            if self.enable_confidence_fusion:
                fusion_key = self._grouping_key(text, file, type)
                comp = (1.0 - ner_score) if ner_score is not None else 1.0
                self._fusion_index[fusion_key] = (
                    len(self.pii_matches) - 1,
                    {engine},
                    comp,
                )

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

    def add_matches_regex(self, matches: re.Match | None, path: str) -> None:
        """Add a match from the combined regex engine.

        The combined regex matches multiple PII types in a single pass (email, phone,
        IBAN, …).  The capture-group index identifies which type fired; ``config_regex_sorted``
        maps that index to the config entry.  Post-match validation (Luhn, IBAN checksum,
        etc.) is applied before recording to eliminate false positives common in raw regex
        matching.
        """
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

            # `type` may legitimately be None here (e.g. a standalone compiled
            # pattern with no capture groups, outside the "combined" alternation
            # this method is primarily designed for) — __add_match tolerates it
            # (guards internally with `if type`), so this is intentional, not a
            # bug: see `_run_finditer`'s "REGEX_MATCH" fallback in regex_engine.py
            # for the equivalent case in the primary detection path.
            self.__add_match(text=matches.group(), file=path, type=type, engine="regex")  # type: ignore[arg-type]

    def add_matches_ner(self, matches: list[dict] | None, path: str) -> None:
        """Add matches from the GLiNER NER engine.

        GLiNER returns a label string (e.g. "PERSON") rather than a group index, so
        ``config_ainer_sorted`` maps label → config entry.  Unknown labels (not in the
        config) are silently skipped to avoid polluting output with unsupported types.
        """
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

    def _passes_structured_validation(self, text: str, entity_type: str) -> bool:
        """Checksum-validate a structured finding from *any* engine.

        Extends the regex engine's checksum validation (Luhn, IBAN mod-97, German tax
        ID, BIC) to findings produced by NER / vector / LLM engines, which otherwise
        emit unvalidated structured identifiers and inflate the false-positive rate.

        A length guard ensures this only fires on tight single-value candidates: coarse
        engines (vector search) report whole text chunks, and running a checksum over a
        chunk would spuriously fail and discard a legitimate finding.  Out-of-range
        candidates and types without a validator are accepted unchanged.

        Returns:
            True if the finding should be kept, False if it failed checksum validation.
        """
        if not self.validate_structured_findings:
            return True
        rule = validation_rule_for(canonical_for(entity_type))
        if rule is None:
            return True  # not a checksum-validatable type
        validator_name, clean_mode, min_len, max_len = rule
        if clean_mode == "digits":
            cleaned = re.sub(r"\D", "", text)
        else:  # alnum
            cleaned = re.sub(r"[^0-9A-Za-z]", "", text)
        if not (min_len <= len(cleaned) <= max_len):
            return True  # not a tight single-value candidate -> do not checksum

        from validators import get_validator

        validator = get_validator(validator_name)
        if validator is None:
            return True  # validator unavailable -> do not discard
        try:
            result = validator.validate(text)
        except Exception:  # pragma: no cover - defensive
            return True
        is_valid = result[0] if isinstance(result, tuple) else result
        return bool(is_valid)

    def _passes_context_requirement(
        self,
        entity_type: str,
        source_text: str | None,
        offset: int | None,
        text: str,
    ) -> bool:
        """Return True unless a context-required finding lacks a nearby keyword.

        For canonical types listed in ``core.entity_types._CONTEXT_REQUIREMENTS``
        (currently BIC), at least one related keyword must appear within
        ``CONTEXT_REQUIREMENT_WINDOW`` characters of the match.  The check is skipped
        (returns True) when gating is disabled or the surrounding text/offset is
        unavailable, so it never drops a finding it cannot evaluate.
        """
        if not self.require_context_for_ambiguous:
            return True
        keywords = context_requirement_for(canonical_for(entity_type))
        if not keywords:
            return True
        if source_text is None or offset is None:
            return True  # cannot evaluate context -> keep (conservative)
        start = max(0, offset - CONTEXT_REQUIREMENT_WINDOW)
        end = min(len(source_text), offset + len(text) + CONTEXT_REQUIREMENT_WINDOW)
        window = source_text[start:end].lower()
        return any(kw in window for kw in keywords)

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
            # Drop structured findings (IBAN, credit card, …) that fail checksum
            # validation regardless of which engine produced them.
            if not self._passes_structured_validation(result.text, result.entity_type):
                continue

            offset = getattr(result, "offset", None)

            # Drop context-required findings (e.g. BIC) that lack a related keyword
            # nearby.  Cheaply rejects uppercase dictionary words that pass the weak
            # BIC structural check.  Skipped when surrounding text is unavailable.
            if not self._passes_context_requirement(
                result.entity_type, source_text, offset, result.text
            ):
                continue

            ctx_before = None
            ctx_after = None

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
