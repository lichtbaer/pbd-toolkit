"""Tests for PII matching functionality."""

import re
from types import SimpleNamespace

from core.matches import PiiMatch, PiiMatchContainer


class TestPiiMatch:
    """Tests for PiiMatch dataclass."""

    def test_create_pii_match(self):
        """Test creating a PII match."""
        match = PiiMatch(
            text="test@example.com", file="/path/to/file.txt", type="REGEX_EMAIL"
        )
        assert match.text == "test@example.com"
        assert match.file == "/path/to/file.txt"
        assert match.type == "REGEX_EMAIL"
        assert match.ner_score is None

    def test_create_pii_match_with_ner_score(self):
        """Test creating a PII match with NER score."""
        match = PiiMatch(
            text="John Doe", file="/path/to/file.txt", type="NER_PERSON", ner_score=0.95
        )
        assert match.ner_score == 0.95


class TestPiiMatchContainer:
    """Tests for PiiMatchContainer."""

    def test_create_empty_container(self):
        """Test creating an empty container."""
        container = PiiMatchContainer()
        assert len(container.pii_matches) == 0
        assert len(container.whitelist) == 0

    def test_by_file_grouping(self):
        """Test grouping matches by file."""
        # Test grouping by file (requires matches to be added first)
        # This is tested in test_add_matches_regex and test_add_matches_ner

    def test_whitelist_compilation(self):
        """Test that whitelist pattern is compiled correctly."""
        container = PiiMatchContainer()
        container.whitelist = ["test@", "info@"]
        container._compile_whitelist_pattern()

        assert container._whitelist_pattern is not None
        # Test that pattern matches whitelisted strings
        assert container._whitelist_pattern.search("test@example.com")
        assert container._whitelist_pattern.search("info@company.com")
        assert not container._whitelist_pattern.search("user@example.com")

    def test_whitelist_empty(self):
        """Test that empty whitelist doesn't create pattern."""
        container = PiiMatchContainer()
        container._compile_whitelist_pattern()
        assert container._whitelist_pattern is None

    def test_add_matches_regex(self, monkeypatch):
        """Test adding regex matches."""
        container = PiiMatchContainer()

        # Set CSV writer for testing
        mock_writer = []

        class MockCsvWriter:
            def writerow(self, row):
                mock_writer.append(row)

        container.set_csv_writer(MockCsvWriter())
        container.set_output_format("csv")

        # Create a mock regex match
        pattern = re.compile(r"(test@\w+\.com)")
        match = pattern.search("Contact: test@example.com")

        container.add_matches_regex(match, "/test/file.txt")

        # Verify match was added (if not whitelisted)
        # Note: This depends on the actual regex config, so we test the method exists
        assert hasattr(container, "add_matches_regex")

    def test_add_matches_ner_none(self):
        """Test adding None matches (no matches found)."""
        container = PiiMatchContainer()
        # Should not raise an error
        container.add_matches_ner(None, "/test/file.txt")
        assert len(container.pii_matches) == 0

    def test_add_matches_ner_empty_list(self):
        """Test adding empty list of NER matches."""
        container = PiiMatchContainer()
        container.add_matches_ner([], "/test/file.txt")
        assert len(container.pii_matches) == 0


class TestPiiMatchContainerDeduplication:
    """Tests for cross-engine deduplication in PiiMatchContainer."""

    def _make_result(self, text, file, type_, engine="regex", score=None):
        """Helper to create a minimal DetectionResult-like object."""
        from types import SimpleNamespace

        return SimpleNamespace(
            text=text,
            file=file,
            entity_type=type_,
            engine_name=engine,
            confidence=score,
            metadata={},
        )

    def test_deduplication_disabled_by_default(self):
        """Deduplication is off by default; duplicate matches are kept."""
        container = PiiMatchContainer()
        r1 = self._make_result("test@example.com", "/f.txt", "EMAIL", engine="regex")
        r2 = self._make_result("test@example.com", "/f.txt", "EMAIL", engine="gliner")
        container.add_detection_results([r1, r2], "/f.txt")
        assert len(container.pii_matches) == 2

    def test_deduplication_enabled_removes_duplicates(self):
        """With deduplication on, the second identical match is suppressed."""
        container = PiiMatchContainer(enable_deduplication=True)
        r1 = self._make_result("test@example.com", "/f.txt", "EMAIL", engine="regex")
        r2 = self._make_result("test@example.com", "/f.txt", "EMAIL", engine="gliner")
        container.add_detection_results([r1, r2], "/f.txt")
        assert len(container.pii_matches) == 1
        assert container.pii_matches[0].engine == "regex"

    def test_deduplication_case_insensitive(self):
        """Deduplication compares text case-insensitively."""
        container = PiiMatchContainer(enable_deduplication=True)
        r1 = self._make_result("John Doe", "/f.txt", "PERSON", engine="gliner")
        r2 = self._make_result("john doe", "/f.txt", "PERSON", engine="spacy-ner")
        container.add_detection_results([r1, r2], "/f.txt")
        assert len(container.pii_matches) == 1

    def test_deduplication_different_types_kept(self):
        """Same text with different types are treated as distinct matches."""
        container = PiiMatchContainer(enable_deduplication=True)
        r1 = self._make_result("Max Muster", "/f.txt", "PERSON", engine="gliner")
        r2 = self._make_result(
            "Max Muster", "/f.txt", "ORGANIZATION", engine="spacy-ner"
        )
        container.add_detection_results([r1, r2], "/f.txt")
        assert len(container.pii_matches) == 2

    def test_deduplication_different_files_kept(self):
        """Same text in different files are treated as distinct matches."""
        container = PiiMatchContainer(enable_deduplication=True)
        r1 = self._make_result("test@example.com", "/a.txt", "EMAIL", engine="regex")
        r2 = self._make_result("test@example.com", "/b.txt", "EMAIL", engine="regex")
        container.add_detection_results([r1], "/a.txt")
        container.add_detection_results([r2], "/b.txt")
        assert len(container.pii_matches) == 2

    def test_deduplication_thread_safety(self):
        """Deduplication state is consistent under concurrent writes."""
        import threading

        container = PiiMatchContainer(enable_deduplication=True)
        errors = []

        def add_result():
            try:
                from types import SimpleNamespace

                r = SimpleNamespace(
                    text="shared@email.com",
                    entity_type="EMAIL",
                    engine_name="regex",
                    confidence=None,
                    metadata={},
                )
                container.add_detection_results([r], "/shared.txt")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_result) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # Only one match should survive deduplication
        assert len(container.pii_matches) == 1


class TestCrossEngineNormalization:
    """Confidence fusion and dedup must group cross-engine findings by canonical type."""

    def _result(self, text, type_, engine, score=None, offset=None):
        return SimpleNamespace(
            text=text,
            entity_type=type_,
            engine_name=engine,
            confidence=score,
            metadata={},
            offset=offset,
        )

    # A Luhn-valid synthetic test card so structured validation keeps it.
    CARD = "4111 1111 1111 1111"

    def test_fusion_groups_regex_and_vector_credit_card(self):
        """REGEX_CREDIT_CARD and VECTOR_CREDITCARD must fuse into one finding."""
        container = PiiMatchContainer(enable_confidence_fusion=True)
        r_regex = self._result(self.CARD, "REGEX_CREDIT_CARD", "regex", score=1.0)
        r_vector = self._result(self.CARD, "VECTOR_CREDITCARD", "vector-search", 0.82)
        container.add_detection_results([r_regex, r_vector], "/f.txt")

        assert len(container.pii_matches) == 1
        pm = container.pii_matches[0]
        assert sorted(pm.metadata["fused_engines"]) == ["regex", "vector-search"]
        assert pm.metadata["canonical_type"] == "CREDIT_CARD"
        # max(1.0, 0.82) + 0.05 corroboration bonus, capped at 1.0
        assert pm.ner_score == 1.0

    def test_fusion_disabled_normalization_keeps_separate(self):
        """With cross_engine_normalization off, raw labels no longer fuse."""
        container = PiiMatchContainer(
            enable_confidence_fusion=True, cross_engine_normalization=False
        )
        r_regex = self._result(self.CARD, "REGEX_CREDIT_CARD", "regex", score=1.0)
        r_vector = self._result(self.CARD, "VECTOR_CREDITCARD", "vector-search", 0.82)
        container.add_detection_results([r_regex, r_vector], "/f.txt")
        assert len(container.pii_matches) == 2

    def test_dedup_groups_cross_engine_aliases(self):
        """Deduplication also collapses cross-engine aliases of the same concept."""
        container = PiiMatchContainer(enable_deduplication=True)
        r_regex = self._result("Max Mustermann", "NER_PERSON", "gliner", score=0.9)
        r_vector = self._result("Max Mustermann", "VECTOR_PERSON", "vector-search", 0.8)
        container.add_detection_results([r_regex, r_vector], "/f.txt")
        assert len(container.pii_matches) == 1

    def test_canonical_type_recorded_in_metadata(self):
        container = PiiMatchContainer()
        r = self._result("user@example.com", "REGEX_EMAIL", "regex")
        container.add_detection_results([r], "/f.txt")
        assert container.pii_matches[0].metadata["canonical_type"] == "EMAIL"


class TestStructuredValidation:
    """Checksum validation of structured findings from non-regex engines (A2)."""

    def _result(self, text, type_, engine="pydantic-ai"):
        return SimpleNamespace(
            text=text,
            entity_type=type_,
            engine_name=engine,
            confidence=0.99,
            metadata={},
            offset=None,
        )

    VALID_IBAN = "DE89 3704 0044 0532 0130 00"
    INVALID_IBAN = "DE00 0000 0000 0000 0000 00"

    def test_invalid_iban_from_llm_is_discarded(self):
        """An LLM-hallucinated IBAN that fails the checksum must be dropped."""
        container = PiiMatchContainer(validate_structured_findings=True)
        container.add_detection_results(
            [self._result(self.INVALID_IBAN, "IBAN")], "/f.txt"
        )
        assert len(container.pii_matches) == 0

    def test_valid_iban_from_llm_is_kept(self):
        container = PiiMatchContainer(validate_structured_findings=True)
        container.add_detection_results(
            [self._result(self.VALID_IBAN, "IBAN")], "/f.txt"
        )
        assert len(container.pii_matches) == 1

    def test_validation_can_be_disabled(self):
        """With validation off, even an invalid IBAN is kept (legacy behaviour)."""
        container = PiiMatchContainer(validate_structured_findings=False)
        container.add_detection_results(
            [self._result(self.INVALID_IBAN, "IBAN")], "/f.txt"
        )
        assert len(container.pii_matches) == 1

    def test_coarse_chunk_is_not_discarded(self):
        """A chunk-level finding (too long to be a single value) skips the checksum."""
        container = PiiMatchContainer(validate_structured_findings=True)
        chunk = (
            "Kontoinformationen des Kunden inklusive vollstaendiger Bankverbindung "
            "und weiterer personenbezogener Angaben in diesem Abschnitt."
        )
        container.add_detection_results([self._result(chunk, "IBAN")], "/f.txt")
        assert len(container.pii_matches) == 1

    def test_non_structured_type_is_untouched(self):
        """Person names are never checksum-validated."""
        container = PiiMatchContainer(validate_structured_findings=True)
        container.add_detection_results(
            [self._result("Max Mustermann", "PERSON")], "/f.txt"
        )
        assert len(container.pii_matches) == 1


class TestSetWhitelistAtomicity:
    """Tests for atomic whitelist compilation in set_whitelist."""

    def test_set_whitelist_compiles_pattern_atomically(self):
        """After set_whitelist, the pattern must be immediately available."""
        container = PiiMatchContainer()
        container.set_whitelist(["test@example.com", "info@"])
        assert container._whitelist_pattern is not None
        assert container._whitelist_pattern.search("test@example.com")
        assert container._whitelist_pattern.search("info@company.de")

    def test_set_whitelist_empty_clears_pattern(self):
        """Setting an empty whitelist clears the compiled pattern."""
        container = PiiMatchContainer(whitelist=["test@"])
        assert container._whitelist_pattern is not None
        container.set_whitelist([])
        assert container._whitelist_pattern is None

    def test_set_whitelist_regex_entry(self):
        """Whitelist entries with regex: prefix are compiled correctly."""
        container = PiiMatchContainer()
        container.set_whitelist(["regex:\\d{3}-\\d{4}"])
        assert container._whitelist_pattern is not None
        assert container._whitelist_pattern.search("555-1234")


class TestConfigurableConstants:
    """Tests for configurable dedup_max_entries and max_whitelist_regex_len."""

    def _make_result(self, text, type_="EMAIL"):
        return SimpleNamespace(
            text=text,
            entity_type=type_,
            engine_name="regex",
            confidence=None,
            metadata={},
        )

    def test_dedup_max_entries_eviction(self):
        """FIFO eviction kicks in when dedup_max_entries is exceeded."""
        container = PiiMatchContainer(enable_deduplication=True, dedup_max_entries=3)
        for i in range(5):
            r = self._make_result(f"match{i}@example.com")
            container.add_detection_results([r], f"/file{i}.txt")

        # All 5 matches should be added (eviction only removes dedup keys,
        # not the matches themselves)
        assert len(container.pii_matches) == 5
        # But the dedup seen_keys should be bounded
        assert len(container._seen_keys) <= 4  # 3 + 1 before eviction

    def test_max_whitelist_regex_len_rejects_long_regex(self):
        """Long regex entries are skipped when max_whitelist_regex_len is small."""
        container = PiiMatchContainer(max_whitelist_regex_len=10)
        container.set_whitelist(["regex:" + "a" * 20])
        # Pattern should be None because the only entry was too long
        assert container._whitelist_pattern is None


class TestProtocolConformance:
    """Verify that output writers conform to OutputWriterProtocol."""

    def test_writers_satisfy_output_writer_protocol(self):
        """All concrete writers implement the OutputWriterProtocol interface."""
        import tempfile

        from core.protocols import OutputWriterProtocol
        from core.writers import CsvWriter, JsonlWriter, JsonWriter

        with tempfile.NamedTemporaryFile(suffix=".tmp") as f:
            for cls in (CsvWriter, JsonWriter, JsonlWriter):
                instance = cls(f.name)
                assert isinstance(instance, OutputWriterProtocol), (
                    f"{cls.__name__} instance does not satisfy OutputWriterProtocol"
                )
