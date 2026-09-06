"""Tests for core.severity: per-type classification, combination-risk
escalation and custom severity configuration loading."""

from __future__ import annotations

import json
import logging

import pytest

from core import severity


@pytest.fixture(autouse=True)
def _restore_severity_globals():
    """``load_custom_severity_config`` mutates module globals; restore them
    after every test so the order of tests never matters."""
    saved_map = dict(severity.SEVERITY_MAP)
    saved_person = severity._PERSON_LABELS
    saved_escalate = severity._ESCALATE_WITH_PERSON_TO_CRITICAL
    saved_default = severity.DEFAULT_SEVERITY
    yield
    severity.SEVERITY_MAP.clear()
    severity.SEVERITY_MAP.update(saved_map)
    severity._PERSON_LABELS = saved_person
    severity._ESCALATE_WITH_PERSON_TO_CRITICAL = saved_escalate
    severity.DEFAULT_SEVERITY = saved_default


# ---------------------------------------------------------------------------
# classify()
# ---------------------------------------------------------------------------


class TestClassify:
    @pytest.mark.parametrize(
        ("pii_type", "expected"),
        [
            ("REGEX_CREDIT_CARD", "CRITICAL"),
            ("NER_PASSWORD", "CRITICAL"),
            ("REGEX_IBAN", "HIGH"),
            ("NER_HEALTH", "HIGH"),
            ("REGEX_EMAIL", "MEDIUM"),
            ("NER_PERSON", "MEDIUM"),
            ("OLLAMA_DATE", "LOW"),
            ("REGEX_IPV4", "LOW"),
            ("REGEX_BIC", "LOW"),
        ],
    )
    def test_known_types(self, pii_type, expected):
        assert severity.classify(pii_type) == expected

    def test_unknown_type_defaults_to_medium(self):
        assert severity.classify("REGEX_DOES_NOT_EXIST") == "MEDIUM"
        assert severity.classify("") == severity.DEFAULT_SEVERITY

    def test_lookup_is_case_sensitive(self):
        # The map keys are upper-case labels; lower-case is *not* a known type.
        assert severity.classify("regex_iban") == severity.DEFAULT_SEVERITY

    def test_every_map_value_is_a_valid_level(self):
        assert set(severity.SEVERITY_MAP.values()) <= set(severity._LEVEL_WEIGHT)

    def test_weight_tables_are_inverse(self):
        for level, weight in severity._LEVEL_WEIGHT.items():
            assert severity._WEIGHT_LEVEL[weight] == level
        assert severity._LEVEL_WEIGHT["LOW"] < severity._LEVEL_WEIGHT["MEDIUM"]
        assert severity._LEVEL_WEIGHT["MEDIUM"] < severity._LEVEL_WEIGHT["HIGH"]
        assert severity._LEVEL_WEIGHT["HIGH"] < severity._LEVEL_WEIGHT["CRITICAL"]


# ---------------------------------------------------------------------------
# combined_file_risk()
# ---------------------------------------------------------------------------


class TestCombinedFileRisk:
    def test_empty_input_is_none(self):
        assert severity.combined_file_risk([]) == "NONE"
        assert severity.combined_file_risk(set()) == "NONE"
        assert severity.combined_file_risk(()) == "NONE"

    def test_single_types_return_their_own_level(self):
        assert severity.combined_file_risk(["REGEX_IPV4"]) == "LOW"
        assert severity.combined_file_risk(["REGEX_EMAIL"]) == "MEDIUM"
        assert severity.combined_file_risk(["REGEX_IBAN"]) == "HIGH"
        assert severity.combined_file_risk(["REGEX_SSN_US"]) == "CRITICAL"

    def test_rule1_any_critical_wins(self):
        assert (
            severity.combined_file_risk(["REGEX_IPV4", "NER_PASSWORD", "REGEX_EMAIL"])
            == "CRITICAL"
        )

    def test_rule2_person_plus_escalating_high_is_critical(self):
        assert severity.combined_file_risk(["NER_PERSON", "REGEX_IBAN"]) == "CRITICAL"
        # Passport is itself a person label (and HIGH), tax id escalates.
        assert (
            severity.combined_file_risk(["REGEX_PASSPORT", "REGEX_TAX_ID"])
            == "CRITICAL"
        )
        assert (
            severity.combined_file_risk(["OLLAMA_PERSON", "NER_MEDICAL_CONDITION"])
            == "CRITICAL"
        )

    def test_rule3_three_distinct_high_types_is_critical(self):
        # No person label, none of them CRITICAL individually.
        assert (
            severity.combined_file_risk(
                ["NER_POLITICAL", "NER_RELIGIOUS", "OLLAMA_MONEY"]
            )
            == "CRITICAL"
        )

    def test_two_high_types_without_person_stay_high(self):
        assert severity.combined_file_risk(["NER_POLITICAL", "NER_RELIGIOUS"]) == "HIGH"

    def test_duplicates_do_not_count_as_distinct(self):
        # Three entries but only two distinct HIGH types -> not escalated.
        assert (
            severity.combined_file_risk(
                ["NER_POLITICAL", "NER_POLITICAL", "NER_RELIGIOUS"]
            )
            == "HIGH"
        )

    def test_rule4_person_plus_non_escalating_high_is_high(self):
        # NER_POLITICAL is HIGH but not in the escalate-to-critical set.
        assert severity.combined_file_risk(["NER_PERSON", "NER_POLITICAL"]) == "HIGH"

    def test_rule5_max_of_individual_levels(self):
        assert (
            severity.combined_file_risk(["REGEX_IPV4", "REGEX_EMAIL", "REGEX_BIC"])
            == "MEDIUM"
        )
        assert severity.combined_file_risk(["REGEX_IPV4", "REGEX_BIC"]) == "LOW"

    def test_person_plus_medium_only_is_medium(self):
        assert severity.combined_file_risk(["NER_PERSON", "REGEX_EMAIL"]) == "MEDIUM"

    def test_unknown_types_count_as_default_medium(self):
        assert severity.combined_file_risk(["SOMETHING_NEW"]) == "MEDIUM"
        assert severity.combined_file_risk(["SOMETHING_NEW", "REGEX_IPV4"]) == "MEDIUM"

    def test_accepts_any_collection(self):
        assert (
            severity.combined_file_risk({"NER_PERSON", "REGEX_CREDIT_CARD"})
            == "CRITICAL"
        )
        assert severity.combined_file_risk(("REGEX_IBAN",)) == "HIGH"


# ---------------------------------------------------------------------------
# load_custom_severity_config()
# ---------------------------------------------------------------------------


class TestLoadCustomSeverityConfig:
    def test_json_overrides_and_extensions(self, tmp_path):
        cfg = tmp_path / "sev.json"
        cfg.write_text(
            json.dumps(
                {
                    "severity_map": {
                        "REGEX_CUSTOM_ID": "critical",  # lower-case is normalised
                        "REGEX_EMAIL": "HIGH",  # override existing
                    },
                    "person_labels": ["NER_CUSTOM_PERSON"],
                    "escalate_with_person_to_critical": ["NER_CUSTOM_SECRET"],
                    "default_severity": "low",
                }
            ),
            encoding="utf-8",
        )

        severity.load_custom_severity_config(str(cfg))

        assert severity.classify("REGEX_CUSTOM_ID") == "CRITICAL"
        assert severity.classify("REGEX_EMAIL") == "HIGH"
        assert "NER_CUSTOM_PERSON" in severity._PERSON_LABELS
        assert "NER_CUSTOM_SECRET" in severity._ESCALATE_WITH_PERSON_TO_CRITICAL
        assert severity.DEFAULT_SEVERITY == "LOW"
        # Unknown type now uses the new default.
        assert severity.classify("TOTALLY_UNKNOWN") == "LOW"
        # Custom person label + custom escalation label combine to CRITICAL
        # (NER_CUSTOM_SECRET is unknown -> default LOW alone, but rule 2 fires).
        assert (
            severity.combined_file_risk(["NER_CUSTOM_PERSON", "NER_CUSTOM_SECRET"])
            == "CRITICAL"
        )

    @pytest.mark.parametrize("suffix", [".yaml", ".yml", ".YAML"])
    def test_yaml_variants(self, tmp_path, suffix):
        pytest.importorskip("yaml")
        cfg = tmp_path / f"sev{suffix}"
        cfg.write_text(
            "severity_map:\n  NER_YAML_TYPE: HIGH\nperson_labels:\n  - NER_YAML_PERSON\n",
            encoding="utf-8",
        )

        severity.load_custom_severity_config(str(cfg))

        assert severity.classify("NER_YAML_TYPE") == "HIGH"
        assert "NER_YAML_PERSON" in severity._PERSON_LABELS

    def test_invalid_levels_are_ignored_with_warning(self, tmp_path, caplog):
        cfg = tmp_path / "sev.json"
        cfg.write_text(
            json.dumps(
                {
                    "severity_map": {
                        "REGEX_A": "EXTREME",  # unknown level
                        "REGEX_B": 3,  # wrong type
                        "REGEX_C": "HIGH",  # valid
                    },
                    "default_severity": "SEVERE",  # unknown -> ignored
                }
            ),
            encoding="utf-8",
        )

        with caplog.at_level(logging.WARNING, logger="core.severity"):
            severity.load_custom_severity_config(str(cfg))

        assert "REGEX_A" not in severity.SEVERITY_MAP
        assert "REGEX_B" not in severity.SEVERITY_MAP
        assert severity.classify("REGEX_C") == "HIGH"
        assert severity.DEFAULT_SEVERITY == "MEDIUM"
        warnings = [r.getMessage() for r in caplog.records]
        assert any("EXTREME" in m and "REGEX_A" in m for m in warnings)
        assert any("REGEX_B" in m for m in warnings)

    def test_non_mapping_document_is_rejected(self, tmp_path, caplog):
        cfg = tmp_path / "sev.json"
        cfg.write_text(json.dumps(["REGEX_A", "CRITICAL"]), encoding="utf-8")
        before = dict(severity.SEVERITY_MAP)

        with caplog.at_level(logging.WARNING, logger="core.severity"):
            severity.load_custom_severity_config(str(cfg))

        assert severity.SEVERITY_MAP == before
        assert any("must be a mapping" in r.getMessage() for r in caplog.records)
        assert any("list" in r.getMessage() for r in caplog.records)

    def test_wrong_container_types_are_skipped(self, tmp_path):
        """Non-dict/list sections are ignored rather than crashing."""
        cfg = tmp_path / "sev.json"
        cfg.write_text(
            json.dumps(
                {
                    "severity_map": ["REGEX_A"],
                    "person_labels": "NER_PERSON_X",
                    "escalate_with_person_to_critical": {"a": 1},
                    "default_severity": 42,
                }
            ),
            encoding="utf-8",
        )
        before_map = dict(severity.SEVERITY_MAP)
        before_person = severity._PERSON_LABELS
        before_escalate = severity._ESCALATE_WITH_PERSON_TO_CRITICAL

        severity.load_custom_severity_config(str(cfg))

        assert severity.SEVERITY_MAP == before_map
        assert severity._PERSON_LABELS == before_person
        assert severity._ESCALATE_WITH_PERSON_TO_CRITICAL == before_escalate
        assert severity.DEFAULT_SEVERITY == "MEDIUM"

    def test_missing_file_logs_warning(self, tmp_path, caplog):
        missing = tmp_path / "nope.json"
        before = dict(severity.SEVERITY_MAP)

        with caplog.at_level(logging.WARNING, logger="core.severity"):
            severity.load_custom_severity_config(str(missing))

        assert severity.SEVERITY_MAP == before
        assert any("not found" in r.getMessage() for r in caplog.records)

    def test_malformed_json_logs_warning(self, tmp_path, caplog):
        cfg = tmp_path / "broken.json"
        cfg.write_text("{not json", encoding="utf-8")

        with caplog.at_level(logging.WARNING, logger="core.severity"):
            severity.load_custom_severity_config(str(cfg))

        assert any(
            "Failed to load severity config" in r.getMessage() for r in caplog.records
        )

    def test_malformed_yaml_logs_warning(self, tmp_path, caplog):
        pytest.importorskip("yaml")
        cfg = tmp_path / "broken.yaml"
        cfg.write_text("severity_map: [unclosed\n", encoding="utf-8")

        with caplog.at_level(logging.WARNING, logger="core.severity"):
            severity.load_custom_severity_config(str(cfg))

        assert any(
            "Failed to load severity config" in r.getMessage() for r in caplog.records
        )

    def test_yaml_without_pyyaml_is_skipped(self, tmp_path, caplog, monkeypatch):
        import builtins

        cfg = tmp_path / "sev.yaml"
        cfg.write_text("severity_map:\n  NER_X: HIGH\n", encoding="utf-8")
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("no yaml")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        with caplog.at_level(logging.WARNING, logger="core.severity"):
            severity.load_custom_severity_config(str(cfg))

        assert "NER_X" not in severity.SEVERITY_MAP
        assert any("PyYAML not installed" in r.getMessage() for r in caplog.records)

    def test_empty_mapping_is_a_no_op(self, tmp_path, caplog):
        cfg = tmp_path / "empty.json"
        cfg.write_text("{}", encoding="utf-8")
        before = dict(severity.SEVERITY_MAP)

        with caplog.at_level(logging.DEBUG, logger="core.severity"):
            severity.load_custom_severity_config(str(cfg))

        assert severity.SEVERITY_MAP == before
        assert any(
            "Custom severity config loaded" in r.getMessage() for r in caplog.records
        )

    def test_non_string_type_keys_are_stringified(self, tmp_path):
        pytest.importorskip("yaml")
        cfg = tmp_path / "sev.yaml"
        # YAML integer key -> str(123)
        cfg.write_text("severity_map:\n  123: LOW\n", encoding="utf-8")

        severity.load_custom_severity_config(str(cfg))

        assert severity.SEVERITY_MAP["123"] == "LOW"
