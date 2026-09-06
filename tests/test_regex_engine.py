"""Unit tests for ``core.engines.regex_engine.RegexEngine``.

``tests/test_engines.py`` drives the engine with a mocked pattern object;
``tests/test_new_regex_patterns.py`` exercises individual expressions through
``PiiMatchContainer``. This file constructs the engine from a real ``Config``
whose alternation is compiled by ``Config._load_regex_pattern()`` and checks
end-to-end detection: per-type checksum validation (valid kept, invalid
dropped), confidence tiers, offsets, chunking, timeout/regex-error handling,
custom pattern loading, and how engine output interacts with the container's
context gating and whitelist (both of which live downstream of the engine).
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time

import pytest

import core.engines.regex_engine as engine_mod
from core.config import Config
from core.engines.regex_engine import RegexEngine
from core.matches import PiiMatchContainer, config_regex_sorted
from core.resources import load_config_types

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def regex_config() -> Config:
    cfg = Config()
    cfg._load_regex_pattern()
    cfg.use_regex = True
    return cfg


@pytest.fixture
def engine(regex_config) -> RegexEngine:
    return RegexEngine(regex_config)


def _by_type(results, entity_type):
    return [r for r in results if r.entity_type == entity_type]


# ---------------------------------------------------------------------------
# construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_from_real_config(self, regex_config):
        eng = RegexEngine(regex_config)

        assert eng.name == "regex"
        assert eng.thread_safe is True
        assert eng.enabled is True
        assert isinstance(eng.pattern, re.Pattern)
        assert eng.pattern.flags & re.IGNORECASE
        # One capture group per configured pattern: group index == regex_compiled_pos.
        assert eng.pattern.groups == len(load_config_types()["regex"])
        assert eng.is_available() is True

    def test_disabled_config(self, regex_config):
        regex_config.use_regex = False
        eng = RegexEngine(regex_config)

        assert eng.enabled is False
        assert eng.is_available() is False
        assert eng.detect("max@example.com") == []

    def test_missing_pattern(self):
        cfg = Config()
        cfg.use_regex = True
        assert cfg.regex_pattern is None
        eng = RegexEngine(cfg)

        assert eng.is_available() is False
        assert eng.detect("max@example.com") == []
        assert eng._run_finditer("max@example.com", 0) == []

    def test_group_positions_match_config_order(self):
        entries = load_config_types()["regex"]
        assert [e["regex_compiled_pos"] for e in entries] == list(range(len(entries)))
        assert set(config_regex_sorted) == set(range(len(entries)))


# ---------------------------------------------------------------------------
# validated types
# ---------------------------------------------------------------------------


class TestValidatedTypes:
    @pytest.mark.parametrize(
        ("text", "entity_type"),
        [
            ("DE89370400440532013000", "REGEX_IBAN"),
            ("DE89 3704 0044 0532 0130 00", "REGEX_IBAN"),
            ("de89370400440532013000", "REGEX_IBAN"),  # IGNORECASE + validator upper()
            ("GB82WEST12345698765432", "REGEX_IBAN"),
            ("4111111111111111", "REGEX_CREDIT_CARD"),
            ("4111 1111 1111 1111", "REGEX_CREDIT_CARD"),
            ("5500-0000-0000-0004", "REGEX_CREDIT_CARD"),
            ("DEUTDEFF", "REGEX_BIC"),
            ("DEUTDEFF500", "REGEX_BIC"),
            ("COBADEFFXXX", "REGEX_BIC"),
            ("86095742719", "REGEX_TAX_ID"),
            ("65929970489", "REGEX_TAX_ID"),
        ],
    )
    def test_valid_value_is_detected_with_full_confidence(
        self, engine, text, entity_type
    ):
        results = engine.detect(f"Wert: {text} Ende")

        hits = _by_type(results, entity_type)
        assert len(hits) == 1, results
        hit = hits[0]
        assert hit.text == text
        assert hit.confidence == 1.0
        assert hit.engine_name == "regex"
        assert hit.offset == len("Wert: ")

    @pytest.mark.parametrize(
        ("text", "entity_type"),
        [
            ("DE89370400440532013001", "REGEX_IBAN"),  # wrong mod-97 remainder
            ("DE00370400440532013000", "REGEX_IBAN"),  # bad check digits
            ("XX89370400440532013000", "REGEX_IBAN"),  # unknown country
            ("4111111111111112", "REGEX_CREDIT_CARD"),  # Luhn failure
            ("4111 1111 1111 1112", "REGEX_CREDIT_CARD"),
            ("DEUTZZFF", "REGEX_BIC"),  # ZZ is not a country
            ("12345678901", "REGEX_TAX_ID"),  # structure + check digit fail
            ("65929970488", "REGEX_TAX_ID"),  # check digit off by one
        ],
    )
    def test_invalid_checksum_is_dropped_entirely(self, engine, text, entity_type):
        """The alternation consumes the token, so nothing else may claim it either."""
        results = engine.detect(f"Wert: {text} Ende")

        assert _by_type(results, entity_type) == []
        assert results == []

    def test_leading_zero_eleven_digits_is_claimed_by_phone_pattern(self, engine):
        """Documents alternation order: a 0-prefixed 11-digit token is matched by
        REGEX_PHONE (group 6) before REGEX_TAX_ID (group 7) is ever tried, so the
        tax-ID validator never sees it."""
        results = engine.detect("Wert: 06095742719 Ende")

        assert [(r.entity_type, r.text, r.confidence) for r in results] == [
            ("REGEX_PHONE", "06095742719", 0.8)
        ]

    def test_mixed_valid_and_invalid_in_one_text(self, engine):
        text = (
            "IBAN DE89370400440532013000, falsch DE89370400440532013001, "
            "Karte 4111111111111111, falsch 4111111111111112."
        )
        results = engine.detect(text)

        assert [(r.entity_type, r.text) for r in results] == [
            ("REGEX_IBAN", "DE89370400440532013000"),
            ("REGEX_CREDIT_CARD", "4111111111111111"),
        ]

    def test_validator_unavailable_keeps_match(self, engine, monkeypatch):
        monkeypatch.setattr(engine_mod, "IbanValidator", None)

        results = engine.detect("DE89370400440532013001")

        assert [(r.entity_type, r.confidence) for r in results] == [("REGEX_IBAN", 1.0)]

    @pytest.mark.parametrize(
        "validator", ["CreditCardValidator", "TaxIdValidator", "BicValidator"]
    )
    def test_other_validators_unavailable_keep_match(
        self, engine, monkeypatch, validator
    ):
        monkeypatch.setattr(engine_mod, validator, None)
        sample = {
            "CreditCardValidator": "4111111111111112",
            "TaxIdValidator": "12345678901",
            "BicValidator": "DEUTZZFF",
        }[validator]

        assert len(engine.detect(sample)) == 1

    def test_validate_match_without_validation_key(self, engine):
        m = re.match(r"\w+", "anything")
        assert engine._validate_match(m, {"label": "X"}) is True

    def test_validate_match_unknown_validator_name(self, engine):
        m = re.match(r"\w+", "anything")
        assert engine._validate_match(m, {"label": "X", "validation": "crc32"}) is True


# ---------------------------------------------------------------------------
# unvalidated types, case handling, offsets
# ---------------------------------------------------------------------------


class TestUnvalidatedTypes:
    @pytest.mark.parametrize(
        ("text", "entity_type"),
        [
            ("anna.schmidt@example.com", "REGEX_EMAIL"),
            ("192.168.10.1", "REGEX_IPV4"),
            ("Bewerbung", "REGEX_WORDS"),
            ("BEWERBUNG", "REGEX_WORDS"),  # IGNORECASE applies to plain words
            ("BEGIN PGP PRIVATE KEY", "REGEX_PGPPRV"),
            ("756.1234.5678.97", "REGEX_SSN_CH"),
        ],
    )
    def test_unvalidated_pattern_has_reduced_confidence(
        self, engine, text, entity_type
    ):
        results = engine.detect(f"x {text} y")

        hits = _by_type(results, entity_type)
        assert len(hits) == 1
        assert hits[0].text == text
        assert hits[0].confidence == 0.8

    def test_bic_is_case_sensitive_despite_global_ignorecase(self, engine):
        results = engine.detect("bic deutdeff")
        assert _by_type(results, "REGEX_BIC") == []

    def test_empty_and_clean_text(self, engine):
        assert engine.detect("") == []
        assert engine.detect("Nur harmloser Text ohne Daten.") == []

    def test_labels_argument_is_ignored(self, engine):
        text = "max@example.com"
        assert engine.detect(text, labels=["NER_PERSON"]) == engine.detect(text)

    def test_offsets_index_into_source_text(self, engine):
        text = "A max@example.com B 192.168.0.1 C DE89370400440532013000."
        results = engine.detect(text)

        assert len(results) == 3
        for r in results:
            assert text[r.offset : r.offset + len(r.text)] == r.text
        assert [r.offset for r in results] == sorted(r.offset for r in results)

    def test_unknown_group_position_yields_generic_label(self, engine, monkeypatch):
        monkeypatch.setattr(engine_mod, "config_regex_sorted", {})

        results = engine.detect("max@example.com")

        assert [(r.entity_type, r.confidence) for r in results] == [
            ("REGEX_MATCH", 0.8)
        ]


# ---------------------------------------------------------------------------
# chunking + ReDoS protection
# ---------------------------------------------------------------------------


class TestChunking:
    def test_split_text_overlaps_and_covers_everything(self, monkeypatch):
        monkeypatch.setattr(engine_mod, "_REGEX_CHUNK_SIZE", 300)
        eng = RegexEngine(Config())
        text = "".join(chr(97 + (i % 26)) for i in range(1000))

        chunks = eng._split_text(text)

        assert [base for _, base in chunks] == [0, 100, 200, 300, 400, 500, 600, 700]
        for chunk, base in chunks:
            assert text[base : base + len(chunk)] == chunk
        assert chunks[-1][1] + len(chunks[-1][0]) == len(text)

    def test_split_text_exact_multiple_ends_cleanly(self, monkeypatch):
        monkeypatch.setattr(engine_mod, "_REGEX_CHUNK_SIZE", 300)
        eng = RegexEngine(Config())
        chunks = eng._split_text("x" * 300)
        assert chunks == [("x" * 300, 0)]

    def test_large_text_is_chunked_with_absolute_offsets(self, engine, monkeypatch):
        monkeypatch.setattr(engine_mod, "_REGEX_CHUNK_SIZE", 400)
        filler = "lorem ipsum " * 40  # 480 chars, forces several chunks
        text = f"{filler}a@example.com{filler}b@example.org{filler}"
        expected = {
            ("REGEX_EMAIL", text.index("a@example.com")),
            ("REGEX_EMAIL", text.index("b@example.org")),
        }

        results = engine.detect(text)

        # Chunks overlap by 200 chars, so a match inside an overlap may be reported
        # twice; the container deduplicates downstream. Every match must be present
        # with a correct absolute offset.
        assert {(r.entity_type, r.offset) for r in results} == expected
        for r in results:
            assert text[r.offset : r.offset + len(r.text)] == r.text

    def test_timeout_returns_empty_and_warns(self, monkeypatch, caplog):
        monkeypatch.setattr(engine_mod, "_REGEX_TIMEOUT_SECONDS", 0.05)

        class SlowPattern:
            def finditer(self, text):
                time.sleep(0.3)
                return iter(())

        cfg = Config()
        cfg.use_regex = True
        cfg.regex_pattern = SlowPattern()  # type: ignore[assignment]
        eng = RegexEngine(cfg)

        with caplog.at_level(logging.WARNING, logger="core.engines.regex_engine"):
            assert eng.detect("anything") == []

        assert any("timed out" in r.getMessage() for r in caplog.records)

    def test_regex_error_returns_empty_and_warns(self, monkeypatch, caplog):
        class BrokenPattern:
            def finditer(self, text):
                raise re.error("catastrophic")

        cfg = Config()
        cfg.use_regex = True
        cfg.regex_pattern = BrokenPattern()  # type: ignore[assignment]
        eng = RegexEngine(cfg)

        with caplog.at_level(logging.WARNING, logger="core.engines.regex_engine"):
            assert eng.detect("anything") == []

        assert any(
            "Regex error during detection" in r.getMessage() for r in caplog.records
        )


# ---------------------------------------------------------------------------
# load_custom_patterns
# ---------------------------------------------------------------------------


class TestLoadCustomPatterns:
    def test_yaml_with_patterns_key(self, tmp_path):
        p = tmp_path / "custom.yaml"
        p.write_text(
            "patterns:\n"
            "  - label: REGEX_CUSTOM_ID\n"
            '    expression: "CUST-\\\\d{8}"\n'
            "    description: Customer ID\n"
            "  - label: REGEX_EMP\n"
            '    expression: "EMP[A-Z]\\\\d{6}"\n'
            "    validation: luhn\n",
            encoding="utf-8",
        )

        entries = RegexEngine.load_custom_patterns(str(p))

        assert entries == [
            {
                "label": "REGEX_CUSTOM_ID",
                "expression": "CUST-\\d{8}",
                "description": "Customer ID",
            },
            {
                "label": "REGEX_EMP",
                "expression": "EMP[A-Z]\\d{6}",
                "validation": "luhn",
            },
        ]

    def test_yml_extension_and_top_level_list(self, tmp_path):
        p = tmp_path / "c.yml"
        p.write_text("- label: A\n  expression: a+\n", encoding="utf-8")
        assert RegexEngine.load_custom_patterns(str(p)) == [
            {"label": "A", "expression": "a+"}
        ]

    def test_json_list(self, tmp_path):
        p = tmp_path / "c.json"
        p.write_text(json.dumps([{"label": "A", "expression": "a+"}]), encoding="utf-8")
        assert RegexEngine.load_custom_patterns(str(p)) == [
            {"label": "A", "expression": "a+"}
        ]

    def test_json_dict_with_regex_key(self, tmp_path):
        p = tmp_path / "c.json"
        p.write_text(
            json.dumps({"regex": [{"label": "B", "expression": "b"}]}), encoding="utf-8"
        )
        assert RegexEngine.load_custom_patterns(str(p)) == [
            {"label": "B", "expression": "b"}
        ]

    def test_patterns_key_takes_precedence_over_regex_key(self, tmp_path):
        p = tmp_path / "c.json"
        p.write_text(
            json.dumps(
                {
                    "patterns": [{"label": "P", "expression": "p"}],
                    "regex": [{"label": "R", "expression": "r"}],
                }
            ),
            encoding="utf-8",
        )
        assert [e["label"] for e in RegexEngine.load_custom_patterns(str(p))] == ["P"]

    def test_dict_without_known_key_yields_empty(self, tmp_path):
        p = tmp_path / "c.json"
        p.write_text(
            json.dumps({"foo": [{"label": "X", "expression": "x"}]}), encoding="utf-8"
        )
        assert RegexEngine.load_custom_patterns(str(p)) == []

    def test_invalid_entries_are_skipped(self, tmp_path, caplog):
        p = tmp_path / "c.json"
        p.write_text(
            json.dumps(
                [
                    {"label": "OK", "expression": "ok"},
                    {"label": "no-expression"},
                    {"expression": "no-label"},
                    "a string",
                    42,
                    None,
                ]
            ),
            encoding="utf-8",
        )

        with caplog.at_level(logging.WARNING, logger="core.engines.regex_engine"):
            entries = RegexEngine.load_custom_patterns(str(p))

        assert entries == [{"label": "OK", "expression": "ok"}]
        skipped = [
            r for r in caplog.records if "Skipping custom regex entry" in r.getMessage()
        ]
        assert len(skipped) == 2  # only the two dicts with a missing field are logged

    def test_scalar_top_level_is_rejected(self, tmp_path, caplog):
        p = tmp_path / "c.json"
        p.write_text('"just a string"', encoding="utf-8")

        with caplog.at_level(logging.WARNING, logger="core.engines.regex_engine"):
            assert RegexEngine.load_custom_patterns(str(p)) == []

        assert any(
            "must contain a list; got str" in r.getMessage() for r in caplog.records
        )

    def test_missing_file(self, tmp_path, caplog):
        with caplog.at_level(logging.WARNING, logger="core.engines.regex_engine"):
            assert RegexEngine.load_custom_patterns(str(tmp_path / "nope.json")) == []
        assert any("file not found" in r.getMessage() for r in caplog.records)

    def test_malformed_json(self, tmp_path, caplog):
        p = tmp_path / "c.json"
        p.write_text("{not json", encoding="utf-8")

        with caplog.at_level(logging.WARNING, logger="core.engines.regex_engine"):
            assert RegexEngine.load_custom_patterns(str(p)) == []

        assert any(
            "Failed to load custom regex patterns" in r.getMessage()
            for r in caplog.records
        )

    def test_malformed_yaml(self, tmp_path, caplog):
        p = tmp_path / "c.yaml"
        p.write_text("patterns: [unclosed\n  - label: x\n", encoding="utf-8")

        with caplog.at_level(logging.WARNING, logger="core.engines.regex_engine"):
            assert RegexEngine.load_custom_patterns(str(p)) == []

        assert any(
            "Failed to load custom regex patterns" in r.getMessage()
            for r in caplog.records
        )

    def test_yaml_without_pyyaml(self, tmp_path, monkeypatch, caplog):
        p = tmp_path / "c.yaml"
        p.write_text("- label: A\n  expression: a\n", encoding="utf-8")
        monkeypatch.setitem(sys.modules, "yaml", None)

        with caplog.at_level(logging.WARNING, logger="core.engines.regex_engine"):
            assert RegexEngine.load_custom_patterns(str(p)) == []

        assert any("PyYAML not installed" in r.getMessage() for r in caplog.records)

    def test_invalid_regex_expression_is_not_validated_at_load_time(self, tmp_path):
        """Documents current behaviour: entries are returned verbatim, uncompiled.

        A broken expression only fails later when the caller compiles it.
        """
        p = tmp_path / "c.json"
        p.write_text(
            json.dumps([{"label": "BAD", "expression": "("}]), encoding="utf-8"
        )

        entries = RegexEngine.load_custom_patterns(str(p))

        assert entries == [{"label": "BAD", "expression": "("}]
        with pytest.raises(re.error):
            re.compile(entries[0]["expression"])

    def test_loaded_patterns_can_drive_detection(self, tmp_path, monkeypatch):
        """End-to-end: compile loaded entries the same way Config does and detect."""
        p = tmp_path / "c.json"
        p.write_text(
            json.dumps(
                [
                    {"label": "REGEX_CUSTOMER", "expression": r"CUST-\d{8}"},
                    {
                        "label": "REGEX_CARD",
                        "expression": r"\b\d{16}\b",
                        "validation": "luhn",
                    },
                ]
            ),
            encoding="utf-8",
        )
        entries = RegexEngine.load_custom_patterns(str(p))
        combined = "(" + ")|(".join(e["expression"] for e in entries) + ")"
        monkeypatch.setattr(engine_mod, "config_regex_sorted", dict(enumerate(entries)))

        cfg = Config()
        cfg.use_regex = True
        cfg.regex_pattern = re.compile(combined, flags=re.IGNORECASE)
        eng = RegexEngine(cfg)

        results = eng.detect(
            "id CUST-12345678 card 4111111111111111 bad 4111111111111112"
        )

        assert [(r.entity_type, r.text, r.confidence) for r in results] == [
            ("REGEX_CUSTOMER", "CUST-12345678", 0.8),
            ("REGEX_CARD", "4111111111111111", 1.0),
        ]


# ---------------------------------------------------------------------------
# interaction with PiiMatchContainer (context gating + whitelist)
# ---------------------------------------------------------------------------


class TestContainerInteraction:
    """The engine itself neither gates on context nor applies the whitelist.

    Both happen in ``PiiMatchContainer.add_detection_results``; these tests pin
    down the end-to-end effect on regex findings so the division of labour is
    explicit.
    """

    def test_engine_emits_bic_regardless_of_context(self, engine):
        results = engine.detect("Kennung DEUTDEFF ohne weitere Angaben")
        assert [r.entity_type for r in results] == ["REGEX_BIC"]

    def test_bic_without_context_is_dropped_by_container(self, engine):
        text = "Kennung DEUTDEFF ohne weitere Angaben"
        container = PiiMatchContainer(require_context_for_ambiguous=True)

        container.add_detection_results(engine.detect(text), "/f.txt", source_text=text)

        assert container.pii_matches == []

    def test_bic_with_nearby_keyword_is_kept(self, engine):
        text = "BIC: DEUTDEFF, IBAN DE89370400440532013000"
        container = PiiMatchContainer(require_context_for_ambiguous=True)

        container.add_detection_results(engine.detect(text), "/f.txt", source_text=text)

        assert sorted(m.type for m in container.pii_matches) == [
            "REGEX_BIC",
            "REGEX_IBAN",
        ]

    def test_gating_disabled_keeps_bic(self, engine):
        text = "Kennung DEUTDEFF ohne weitere Angaben"
        container = PiiMatchContainer(require_context_for_ambiguous=False)

        container.add_detection_results(engine.detect(text), "/f.txt", source_text=text)

        assert [m.type for m in container.pii_matches] == ["REGEX_BIC"]

    def test_gating_is_conservative_without_source_text(self, engine):
        text = "Kennung DEUTDEFF ohne weitere Angaben"
        container = PiiMatchContainer(require_context_for_ambiguous=True)

        container.add_detection_results(engine.detect(text), "/f.txt", source_text=None)

        assert [m.type for m in container.pii_matches] == ["REGEX_BIC"]

    def test_whitelist_is_applied_downstream_not_in_engine(self, engine):
        text = "test@example.com and other@example.org"
        results = engine.detect(text)
        assert sorted(r.text for r in results) == [
            "other@example.org",
            "test@example.com",
        ]

        container = PiiMatchContainer(whitelist=["test@example.com"])
        container.add_detection_results(results, "/f.txt", source_text=text)

        assert [m.text for m in container.pii_matches] == ["other@example.org"]

    def test_wildcard_whitelist_entry(self, engine):
        text = "a@example.com b@corp.de"
        container = PiiMatchContainer(whitelist=["*@example.com"])

        container.add_detection_results(engine.detect(text), "/f.txt", source_text=text)

        assert [m.text for m in container.pii_matches] == ["b@corp.de"]

    def test_context_chars_are_captured_from_offsets(self, engine):
        text = "vorher max@example.com nachher"
        container = PiiMatchContainer()

        container.add_detection_results(
            engine.detect(text), "/f.txt", source_text=text, context_chars=4
        )

        (m,) = container.pii_matches
        assert (m.context_before, m.context_after, m.char_offset) == ("her ", " nac", 7)
