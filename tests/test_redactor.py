"""Tests for PII redaction (core.redactor).

Redaction is one of the two privacy-critical output transforms: a bug here
means the tool ships PII in output that is presented to the user as fully
sanitized.
"""

import logging
import os
from unittest.mock import Mock

from core.config import Config
from core.engines.regex_engine import RegexEngine
from core.matches import PiiMatch
from core.redactor import redact_files, redact_text


def _match(text, type_="REGEX_EMAIL", offset=None, engine="regex"):
    return PiiMatch(
        text=text, file="doc.txt", type=type_, char_offset=offset, engine=engine
    )


class TestRedactText:
    """Unit tests for redact_text()."""

    def test_no_matches_returns_original_text(self):
        assert redact_text("hello world", []) == "hello world"

    def test_empty_text_returns_empty(self):
        assert redact_text("", [_match("x", offset=0)]) == ""

    def test_none_like_falsy_matches_short_circuits_without_reading_text(self):
        # A falsy `matches` list must return `text` unchanged even if malformed.
        assert redact_text("keep me", []) == "keep me"

    def test_no_offset_and_text_not_present_returns_original(self):
        """A match whose text never occurs in `text` (e.g. stale from a prior
        version of the file) and has no char_offset produces no replacements."""
        text = "nothing sensitive here"
        m = _match("test@example.com", offset=None)
        assert redact_text(text, [m]) == text

    def test_replaces_single_match_by_offset(self):
        text = "Contact me at test@example.com today"
        m = _match("test@example.com", offset=text.index("test@"))
        result = redact_text(text, [m])
        assert result == "Contact me at [REDACTED:REGEX_EMAIL] today"

    def test_replaces_multiple_non_overlapping_matches(self):
        text = "Email test@example.com and call 030 1234567"
        m1 = _match("test@example.com", "REGEX_EMAIL", offset=text.index("test@"))
        m2 = _match("030 1234567", "REGEX_PHONE", offset=text.index("030"))
        result = redact_text(text, [m1, m2])
        assert result == "Email [REDACTED:REGEX_EMAIL] and call [REDACTED:REGEX_PHONE]"

    def test_fallback_replaces_all_occurrences_without_offset(self):
        """No char_offset -> every literal occurrence of the match text is redacted."""
        text = "a@b.com wrote to a@b.com"
        m = _match("a@b.com", "REGEX_EMAIL", offset=None)
        result = redact_text(text, [m])
        assert result == "[REDACTED:REGEX_EMAIL] wrote to [REDACTED:REGEX_EMAIL]"

    def test_adjacent_matches_both_replaced(self):
        """Adjacent (non-overlapping, touching) spans are independent and both redacted."""
        text = "JohnDoe"
        m1 = _match("John", "NER_PERSON", offset=0)
        m2 = _match("Doe", "NER_PERSON", offset=4)
        result = redact_text(text, [m1, m2])
        assert result == "[REDACTED:NER_PERSON][REDACTED:NER_PERSON]"

    def test_overlapping_matches_keep_longest_span(self):
        """Regression test: a shorter, contained match must not win over a longer
        overlapping one, or part of the PII (e.g. the first name) leaks unredacted.
        """
        text = "Contact John Doe today"
        full_name = _match("John Doe", "NER_PERSON", offset=text.index("John"))
        surname_only = _match("Doe", "NER_PERSON", offset=text.index("Doe"))
        # Order in the input list must not matter.
        assert redact_text(text, [surname_only, full_name]) == (
            "Contact [REDACTED:NER_PERSON] today"
        )
        assert redact_text(text, [full_name, surname_only]) == (
            "Contact [REDACTED:NER_PERSON] today"
        )

    def test_overlapping_matches_equal_length_ties_break_on_earliest_start(self):
        text = "abcdef"
        m1 = _match("abc", "TYPE_A", offset=0)  # span 0-3
        m2 = _match("bcd", "TYPE_B", offset=1)  # span 1-4, overlaps m1, same length
        result = redact_text(text, [m2, m1])
        assert result == "[REDACTED:TYPE_A]def"

    def test_three_way_overlap_keeps_only_the_longest(self):
        text = "abcdefghij"
        short = _match("cd", "TYPE_A", offset=2)  # 2-4
        medium = _match("bcdef", "TYPE_A", offset=1)  # 1-6
        long_ = _match("abcdefgh", "TYPE_A", offset=0)  # 0-8
        result = redact_text(text, [short, long_, medium])
        assert result == "[REDACTED:TYPE_A]ij"

    def test_matches_at_start_and_end_of_text(self):
        text = "X marks the spot Y"
        m_start = _match("X", "TYPE_A", offset=0)
        m_end = _match("Y", "TYPE_B", offset=len(text) - 1)
        result = redact_text(text, [m_start, m_end])
        assert result == "[REDACTED:TYPE_A] marks the spot [REDACTED:TYPE_B]"

    def test_idempotent_on_already_redacted_text(self):
        """Re-running redaction with no further matches must not alter the text."""
        text = "Contact me at test@example.com today"
        m = _match("test@example.com", offset=text.index("test@"))
        once = redact_text(text, [m])
        twice = redact_text(once, [])
        assert once == twice

    def test_unicode_offsets_are_character_based(self):
        """Offsets must be interpreted as Python character (not byte) offsets."""
        text = "Müller schrieb an test@example.com."
        m = _match("test@example.com", offset=text.index("test@"))
        result = redact_text(text, [m])
        assert result == "Müller schrieb an [REDACTED:REGEX_EMAIL]."

    def test_multibyte_emoji_offsets_stay_aligned(self):
        text = "📧 test@example.com 📧"
        m = _match("test@example.com", offset=text.index("test@"))
        result = redact_text(text, [m])
        assert result == "📧 [REDACTED:REGEX_EMAIL] 📧"

    def test_unchanged_non_match_content_preserved(self):
        text = "Line one.\nLine two with test@example.com.\nLine three."
        m = _match("test@example.com", offset=text.index("test@"))
        result = redact_text(text, [m])
        assert result.startswith("Line one.\nLine two with ")
        assert result.endswith(".\nLine three.")

    def test_placeholder_uses_match_type_label(self):
        text = "SSN 123-45-6789 on file"
        m = _match("123-45-6789", "REGEX_SSN_US", offset=text.index("123"))
        result = redact_text(text, [m])
        assert "[REDACTED:REGEX_SSN_US]" in result
        assert "123-45-6789" not in result

    def test_rescan_after_redaction_finds_no_original_pii(self):
        """Property test: after redaction, re-running real detection on the output
        must not find any of the original PII strings.
        """
        text = (
            "Reach Jane at jane.doe@example.com, "
            "or via IBAN DE89 3704 0044 0532 0130 00."
        )
        config = Config(use_regex=True, logger=logging.getLogger("test-redactor"))
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
        redacted = redact_text(text, matches)

        for d in detections:
            assert d.text not in redacted

        rescanned = engine.detect(redacted)
        assert rescanned == []


class TestRedactFiles:
    """Tests for redact_files() file-level orchestration."""

    def test_redacts_text_file_in_place(self, temp_dir):
        src = os.path.join(temp_dir, "notes.txt")
        content = "Contact me at test@example.com please"
        with open(src, "w", encoding="utf-8") as f:
            f.write(content)

        matches = {src: [_match("test@example.com", offset=content.index("test@"))]}
        out_dir = os.path.join(temp_dir, "out")
        result = redact_files(matches, out_dir)

        assert src in result
        out_path = result[src]
        assert os.path.exists(out_path)
        with open(out_path, encoding="utf-8") as f:
            redacted_content = f.read()
        assert "test@example.com" not in redacted_content
        assert "[REDACTED:REGEX_EMAIL]" in redacted_content

    def test_files_without_matches_are_skipped(self, temp_dir):
        src = os.path.join(temp_dir, "clean.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("nothing sensitive here")

        result = redact_files({src: []}, os.path.join(temp_dir, "out"))
        assert src not in result

    def test_binary_file_gets_redacted_summary_companion(self, temp_dir):
        src = os.path.join(temp_dir, "scan.pdf")
        with open(src, "wb") as f:
            f.write(b"%PDF-1.4 fake binary content")

        matches = {src: [_match("test@example.com", "REGEX_EMAIL", engine="regex")]}
        result = redact_files(matches, os.path.join(temp_dir, "out"))

        assert src in result
        out_path = result[src]
        assert out_path.endswith(".redacted.txt")
        with open(out_path, encoding="utf-8") as f:
            summary = f.read()
        # The original PII text must never appear in the summary companion file.
        assert "test@example.com" not in summary
        assert "REGEX_EMAIL" in summary

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
        out_dir = os.path.join(temp_dir, "out")
        result = redact_files(matches, out_dir)

        assert result[src1] != result[src2]
        assert os.path.exists(result[src1])
        assert os.path.exists(result[src2])

    def test_unreadable_file_fails_safe_and_is_not_reported_as_redacted(self, temp_dir):
        """A file that vanished/became unreadable after the scan must never be
        silently reported as successfully redacted."""
        missing = os.path.join(temp_dir, "gone.txt")
        matches = {missing: [_match("test@example.com", offset=0)]}
        logger = Mock()

        result = redact_files(matches, os.path.join(temp_dir, "out"), logger=logger)

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
        result = redact_files(matches, os.path.join(temp_dir, "out"))

        assert src in result
        with open(result[src], encoding="utf-8") as f:
            redacted_content = f.read()
        assert "test@example.com" not in redacted_content

    def test_creates_output_directory_if_missing(self, temp_dir):
        src = os.path.join(temp_dir, "notes.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("test@example.com")

        out_dir = os.path.join(temp_dir, "does", "not", "exist", "yet")
        matches = {src: [_match("test@example.com", offset=0)]}
        result = redact_files(matches, out_dir)

        assert os.path.isdir(out_dir)
        assert src in result

    def test_logs_info_on_successful_redaction(self, temp_dir):
        src = os.path.join(temp_dir, "notes.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("test@example.com")

        logger = Mock()
        matches = {src: [_match("test@example.com", offset=0)]}
        redact_files(matches, os.path.join(temp_dir, "out"), logger=logger)

        logger.info.assert_called_once()
