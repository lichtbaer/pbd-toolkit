"""Tests for PII pseudo-anonymization (core.pseudonymizer).

Pseudonymization is one of the two privacy-critical output transforms: a bug
here means fake-looking output can still contain the exact PII it claims to
have replaced.
"""

import os
import re
from unittest.mock import Mock

import pytest

from core.config import Config
from core.engines.regex_engine import RegexEngine
from core.matches import PiiMatch
from core.pseudonymizer import (
    Pseudonymizer,
    _fake_address,
    _fake_bic,
    _fake_credit_card,
    _fake_date,
    _fake_email,
    _fake_iban,
    _fake_ip,
    _fake_name,
    _fake_phone,
    _fake_tax_id,
    _seed_rng,
    pseudonymize_files,
)


def _match(text, type_="REGEX_EMAIL", offset=None, engine="regex"):
    return PiiMatch(
        text=text, file="doc.txt", type=type_, char_offset=offset, engine=engine
    )


class TestSeedRng:
    def test_same_text_yields_same_sequence(self):
        rng1 = _seed_rng("Anna Müller")
        rng2 = _seed_rng("Anna Müller")
        assert [rng1.random() for _ in range(5)] == [rng2.random() for _ in range(5)]

    def test_different_text_yields_different_sequence(self):
        rng1 = _seed_rng("Anna Müller")
        rng2 = _seed_rng("Ben Fischer")
        assert rng1.random() != rng2.random()


class TestFakeGenerators:
    """Type-appropriate fake-value generators are deterministic given a seeded RNG."""

    @pytest.mark.parametrize(
        "generator",
        [
            _fake_name,
            _fake_email,
            _fake_phone,
            _fake_iban,
            _fake_credit_card,
            _fake_date,
            _fake_ip,
            _fake_address,
            _fake_tax_id,
            _fake_bic,
        ],
    )
    def test_generator_is_deterministic_for_same_seed(self, generator):
        assert generator(_seed_rng("seed-a")) == generator(_seed_rng("seed-a"))

    def test_fake_email_looks_like_an_email(self):
        value = _fake_email(_seed_rng("x"))
        assert re.match(r"^[\w.]+@[\w.]+\.\w+$", value)

    def test_fake_credit_card_has_visa_shape(self):
        """Fake credit card numbers are 16 digits, grouped in 4s, starting with 4
        (Visa-style), regardless of whether they happen to pass a Luhn check."""
        for i in range(20):
            value = _fake_credit_card(_seed_rng(f"seed-{i}"))
            digits = value.replace(" ", "")
            assert len(digits) == 16
            assert digits.isdigit()
            assert digits.startswith("4")
            assert value == " ".join(digits[j : j + 4] for j in range(0, 16, 4))

    def test_fake_iban_has_correct_length_for_country(self):
        from core.pseudonymizer import _IBAN_LENGTHS

        for _ in range(20):
            value = _fake_iban(_seed_rng(str(_)))
            country = value[:2]
            assert len(value) == _IBAN_LENGTHS[country]

    def test_fake_date_is_within_declared_range(self):
        value = _fake_date(_seed_rng("bday"))
        day, month, year = (int(p) for p in value.split("."))
        assert 1 <= day <= 28
        assert 1 <= month <= 12
        assert 1950 <= year <= 2005

    def test_fake_ip_is_in_private_10_range(self):
        value = _fake_ip(_seed_rng("host"))
        assert value.startswith("10.")
        parts = [int(p) for p in value.split(".")]
        assert len(parts) == 4


class TestPseudonymizerFakeValue:
    def test_same_input_maps_to_same_pseudonym_within_instance(self):
        p = Pseudonymizer()
        first = p.fake_value("Anna Müller", "NER_PERSON")
        second = p.fake_value("Anna Müller", "NER_PERSON")
        assert first == second

    def test_different_type_for_same_text_can_map_differently(self):
        p = Pseudonymizer()
        as_name = p.fake_value("012345", "NER_PERSON")
        as_phone = p.fake_value("012345", "REGEX_PHONE")
        # Different generator families (name vs phone) -> different shape at least.
        assert as_name != as_phone

    def test_type_dispatch_is_case_insensitive_and_matches_by_keyword(self):
        p = Pseudonymizer()
        assert re.match(r"^[\w.]+@[\w.]+\.\w+$", p.fake_value("a@b.com", "regex_email"))
        assert re.match(r"^[\w.]+@[\w.]+\.\w+$", p.fake_value("a@b.com", "E-MAIL"))

    def test_unknown_type_falls_back_to_generic_token(self):
        p = Pseudonymizer()
        value = p.fake_value("something odd", "TOTALLY_UNKNOWN_TYPE")
        assert value.startswith("FAKE-")

    def test_cache_is_scoped_to_the_instance(self):
        p1 = Pseudonymizer()
        p2 = Pseudonymizer()
        assert p1.fake_value("x", "y") == p2.fake_value("x", "y")
        # Same deterministic seed -> same value across independent instances,
        # but each instance's cache is independent state.
        assert ("x", "y") in p1._cache
        assert p1._cache is not p2._cache


class TestPseudonymizeText:
    def test_no_matches_returns_original_text(self):
        p = Pseudonymizer()
        assert p.pseudonymize_text("hello world", []) == "hello world"

    def test_empty_text_returns_empty(self):
        p = Pseudonymizer()
        assert p.pseudonymize_text("", [_match("x", offset=0)]) == ""

    def test_no_offset_and_text_not_present_returns_original(self):
        p = Pseudonymizer()
        text = "nothing sensitive here"
        m = _match("test@example.com", offset=None)
        assert p.pseudonymize_text(text, [m]) == text

    def test_replaces_single_match_by_offset(self):
        p = Pseudonymizer()
        text = "Contact me at test@example.com today"
        m = _match("test@example.com", offset=text.index("test@"))
        result = p.pseudonymize_text(text, [m])
        assert "test@example.com" not in result
        assert result.startswith("Contact me at ")
        assert result.endswith(" today")

    def test_same_text_gets_same_pseudonym_across_multiple_files(self):
        """Consistency guarantee: same (text, type) maps to same fake value even
        when applied to different documents via the same Pseudonymizer instance."""
        p = Pseudonymizer()
        m = _match("Anna Müller", "NER_PERSON", offset=0)
        out1 = p.pseudonymize_text("Anna Müller was here", [m])
        out2 = p.pseudonymize_text("Anna Müller signed twice", [m])
        fake_in_out1 = out1.split(" was here")[0]
        fake_in_out2 = out2.split(" signed twice")[0]
        assert fake_in_out1 == fake_in_out2

    def test_fallback_replaces_all_occurrences_without_offset(self):
        p = Pseudonymizer()
        text = "a@b.com wrote to a@b.com"
        m = _match("a@b.com", offset=None)
        result = p.pseudonymize_text(text, [m])
        assert "a@b.com" not in result
        occurrences = result.count(p.fake_value("a@b.com", "REGEX_EMAIL"))
        assert occurrences == 2

    def test_adjacent_matches_both_replaced(self):
        p = Pseudonymizer()
        text = "JohnDoe"
        m1 = _match("John", "NER_PERSON", offset=0)
        m2 = _match("Doe", "NER_PERSON", offset=4)
        result = p.pseudonymize_text(text, [m1, m2])
        assert "John" not in result
        assert "Doe" not in result

    def test_overlapping_matches_keep_longest_span(self):
        """Regression test mirroring the redactor: a shorter contained match must
        not win over a longer overlapping one and leave part of the name in
        cleartext."""
        p = Pseudonymizer()
        text = "Contact John Doe today"
        full_name = _match("John Doe", "NER_PERSON", offset=text.index("John"))
        surname_only = _match("Doe", "NER_PERSON", offset=text.index("Doe"))
        result = p.pseudonymize_text(text, [surname_only, full_name])
        assert "John" not in result
        assert "Doe" not in result
        assert result.startswith("Contact ")
        assert result.endswith(" today")

    def test_unicode_offsets_are_character_based(self):
        p = Pseudonymizer()
        text = "Müller schrieb an test@example.com."
        m = _match("test@example.com", offset=text.index("test@"))
        result = p.pseudonymize_text(text, [m])
        assert "test@example.com" not in result
        assert result.startswith("Müller schrieb an ")
        assert result.endswith(".")

    def test_idempotent_when_no_further_matches(self):
        p = Pseudonymizer()
        text = "Contact me at test@example.com today"
        m = _match("test@example.com", offset=text.index("test@"))
        once = p.pseudonymize_text(text, [m])
        twice = p.pseudonymize_text(once, [])
        assert once == twice

    def test_rescan_after_pseudonymization_finds_no_original_pii(self):
        """Property test: after pseudonymization, re-running real detection on the
        output must not find any of the original PII strings."""
        text = (
            "Reach Jane at jane.doe@example.com, "
            "or via IBAN DE89 3704 0044 0532 0130 00."
        )
        config = Config(use_regex=True)
        config._load_regex_pattern()
        engine = RegexEngine(config)

        detections = engine.detect(text)
        assert detections, "fixture text must contain detectable PII"

        matches = [
            PiiMatch(
                text=d.text, file="doc.txt", type=d.entity_type, char_offset=d.offset
            )
            for d in detections
        ]
        pseudonymizer = Pseudonymizer()
        pseudonymized = pseudonymizer.pseudonymize_text(text, matches)

        for d in detections:
            assert d.text not in pseudonymized


class TestPseudonymizeFiles:
    def test_pseudonymizes_text_file_in_place(self, temp_dir):
        src = os.path.join(temp_dir, "notes.txt")
        content = "Contact me at test@example.com please"
        with open(src, "w", encoding="utf-8") as f:
            f.write(content)

        matches = {src: [_match("test@example.com", offset=content.index("test@"))]}
        out_dir = os.path.join(temp_dir, "out")
        result = pseudonymize_files(matches, out_dir)

        assert src in result
        out_path = result[src]
        assert os.path.exists(out_path)
        with open(out_path, encoding="utf-8") as f:
            pseudo_content = f.read()
        assert "test@example.com" not in pseudo_content

    def test_files_without_matches_are_skipped(self, temp_dir):
        src = os.path.join(temp_dir, "clean.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("nothing sensitive here")

        result = pseudonymize_files({src: []}, os.path.join(temp_dir, "out"))
        assert src not in result

    def test_binary_file_gets_pseudo_summary_companion(self, temp_dir):
        src = os.path.join(temp_dir, "scan.pdf")
        with open(src, "wb") as f:
            f.write(b"%PDF-1.4 fake binary content")

        matches = {src: [_match("test@example.com", "REGEX_EMAIL", engine="regex")]}
        result = pseudonymize_files(matches, os.path.join(temp_dir, "out"))

        assert src in result
        out_path = result[src]
        assert out_path.endswith(".pseudo.txt")
        with open(out_path, encoding="utf-8") as f:
            summary = f.read()
        assert "test@example.com" not in summary
        assert "PSEUDONYMIZED" in summary

    def test_unique_output_names_on_collision(self, temp_dir):
        src1 = os.path.join(temp_dir, "a", "report.txt")
        src2 = os.path.join(temp_dir, "b", "report.txt")
        os.makedirs(os.path.dirname(src1))
        os.makedirs(os.path.dirname(src2))
        content = "test@example.com"
        for p in (src1, src2):
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)

        matches = {
            src1: [_match("test@example.com", offset=0)],
            src2: [_match("test@example.com", offset=0)],
        }
        result = pseudonymize_files(matches, os.path.join(temp_dir, "out"))

        assert result[src1] != result[src2]
        assert os.path.exists(result[src1])
        assert os.path.exists(result[src2])

    def test_unreadable_file_fails_safe_and_is_not_reported_as_pseudonymized(
        self, temp_dir
    ):
        missing = os.path.join(temp_dir, "gone.txt")
        matches = {missing: [_match("test@example.com", offset=0)]}
        logger = Mock()

        result = pseudonymize_files(
            matches, os.path.join(temp_dir, "out"), logger=logger
        )

        assert missing not in result
        logger.warning.assert_called_once()

    def test_invalid_utf8_bytes_do_not_crash_and_do_not_leak_raw_bytes(self, temp_dir):
        src = os.path.join(temp_dir, "mixed.txt")
        with open(src, "wb") as f:
            f.write(b"Contact test@example.com " + b"\xff\xfe")

        with open(src, encoding="utf-8", errors="replace") as f:
            decoded = f.read()
        offset = decoded.index("test@")

        matches = {src: [_match("test@example.com", offset=offset)]}
        result = pseudonymize_files(matches, os.path.join(temp_dir, "out"))

        assert src in result
        with open(result[src], encoding="utf-8") as f:
            pseudo_content = f.read()
        assert "test@example.com" not in pseudo_content

    def test_creates_output_directory_if_missing(self, temp_dir):
        src = os.path.join(temp_dir, "notes.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("test@example.com")

        out_dir = os.path.join(temp_dir, "does", "not", "exist", "yet")
        matches = {src: [_match("test@example.com", offset=0)]}
        result = pseudonymize_files(matches, out_dir)

        assert os.path.isdir(out_dir)
        assert src in result

    def test_logs_info_on_successful_pseudonymization(self, temp_dir):
        src = os.path.join(temp_dir, "notes.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("test@example.com")

        logger = Mock()
        matches = {src: [_match("test@example.com", offset=0)]}
        pseudonymize_files(matches, os.path.join(temp_dir, "out"), logger=logger)

        logger.info.assert_called_once()
