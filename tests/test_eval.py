"""Tests for the detection-quality evaluation harness (eval/)."""

from pathlib import Path

import pytest

from eval.dataset import load_dataset
from eval.metrics import Annotation, evaluate, evaluate_document
from eval.runner import run_evaluation

DATASET = (
    Path(__file__).resolve().parents[1] / "eval" / "datasets" / "synthetic_de.json"
)
DATASET_EN = (
    Path(__file__).resolve().parents[1] / "eval" / "datasets" / "synthetic_en.json"
)


class TestMetrics:
    """Unit tests for precision/recall/F1 computation."""

    def test_perfect_match(self):
        gold = [Annotation("IBAN", 0, 5, "DE123")]
        pred = [Annotation("IBAN", 0, 5, "DE123")]
        result = evaluate([(gold, pred)])
        m = result.per_type["IBAN"]
        assert (m.tp, m.fp, m.fn) == (1, 0, 0)
        assert m.precision == 1.0 and m.recall == 1.0 and m.f1 == 1.0

    def test_false_positive_and_negative(self):
        gold = [Annotation("EMAIL", 0, 3, "a@b")]
        pred = [Annotation("PHONE", 10, 14, "1234")]
        result = evaluate([(gold, pred)])
        assert result.per_type["EMAIL"].fn == 1
        assert result.per_type["PHONE"].fp == 1
        assert result.per_type["EMAIL"].recall == 0.0

    def test_type_mismatch_is_not_a_match(self):
        """Same span but different canonical type does not count as TP."""
        gold = [Annotation("PERSON", 0, 4, "Anna")]
        pred = [Annotation("LOCATION", 0, 4, "Anna")]
        counts = evaluate_document(gold, pred)
        assert counts["PERSON"].fn == 1
        assert counts["LOCATION"].fp == 1

    def test_canonical_aliases_match(self):
        """A raw engine label that normalises to the gold canonical counts as TP."""
        gold = [Annotation("CREDIT_CARD", 0, 4, "4111")]
        pred = [Annotation("VECTOR_CREDITCARD", 0, 4, "4111")]
        counts = evaluate_document(gold, pred)
        assert counts["CREDIT_CARD"].tp == 1

    def test_text_containment_fallback_without_offsets(self):
        """A chunk-level prediction (no offsets) still credits the gold span it contains."""
        gold = [Annotation("IBAN", 0, 5, "DE123")]
        pred = [Annotation("IBAN", None, None, "Bankverbindung DE123 des Kunden")]
        counts = evaluate_document(gold, pred)
        assert counts["IBAN"].tp == 1

    def test_one_to_one_matching(self):
        """Two gold spans of the same type need two predictions; one leaves an FN."""
        gold = [
            Annotation("EMAIL", 0, 3, "a@b"),
            Annotation("EMAIL", 10, 13, "c@d"),
        ]
        pred = [Annotation("EMAIL", 0, 3, "a@b")]
        counts = evaluate_document(gold, pred)
        assert counts["EMAIL"].tp == 1
        assert counts["EMAIL"].fn == 1

    def test_micro_and_macro(self):
        gold = [Annotation("EMAIL", 0, 3, "a@b"), Annotation("IBAN", 5, 10, "DE123")]
        pred = [Annotation("EMAIL", 0, 3, "a@b")]
        result = evaluate([(gold, pred)])
        micro = result.micro
        assert (micro.tp, micro.fp, micro.fn) == (1, 0, 1)
        # EMAIL F1 = 1.0, IBAN F1 = 0.0 -> macro = 0.5
        assert result.macro_f1 == pytest.approx(0.5)


class TestDataset:
    """Loading and validation of the shipped ground-truth dataset."""

    def test_dataset_loads(self):
        docs = load_dataset(DATASET)
        assert len(docs) >= 20
        # Offsets are validated on load; presence of annotations confirms parsing.
        assert any(doc.annotations for doc in docs)

    def test_annotation_offsets_consistent(self):
        docs = load_dataset(DATASET)
        for doc in docs:
            for ann in doc.annotations:
                if ann.start is not None and ann.end is not None:
                    assert doc.text[ann.start : ann.end] == ann.text

    def test_offset_mismatch_raises(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text(
            '[{"id":"x","text":"hello world",'
            '"annotations":[{"type":"PERSON","start":0,"end":5,"text":"world"}]}]',
            encoding="utf-8",
        )
        with pytest.raises(ValueError):
            load_dataset(bad)


class TestRegexQualityGate:
    """Hermetic regression gate: regex must keep detecting clean structured types.

    Runs offline (regex only, no model downloads), so it is safe for CI.
    """

    def test_regex_baseline_structured_types(self):
        docs = load_dataset(DATASET)
        result = run_evaluation(docs, ["regex"])
        # These structured types are unambiguously regex-detectable; a drop below 1.0
        # signals a regression in the regex patterns or the validation pipeline.
        # CREDIT_CARD/PHONE/BIC/TAX_ID/SIGNAL_WORD were hardened to remove the
        # separated-card miss, the over-broad phone matches, and the BIC/word and
        # phone/card-group false positives — they must stay at F1 1.0.
        for canonical in (
            "IBAN",
            "EMAIL",
            "IP_ADDRESS",
            "CREDIT_CARD",
            "PHONE",
            "BIC",
            "TAX_ID",
            "SIGNAL_WORD",
        ):
            assert result.f1_for(canonical) == 1.0, (
                f"{canonical} F1 regressed: {result.per_type.get(canonical)}"
            )

    def test_regex_precision_is_perfect(self):
        """Regex must not emit any false positive on the curated dataset.

        The dataset includes traps (uppercase dictionary words that satisfy the BIC
        shape, bare digit groups, checksum-invalid numbers).  Any FP means a pattern
        or the validation/context-gating pipeline regressed.
        """
        docs = load_dataset(DATASET)
        result = run_evaluation(docs, ["regex"])
        assert result.micro.fp == 0, f"regex produced false positives: {result.micro}"
        assert result.micro.precision == 1.0

    def test_regex_english_dataset_structured_types(self):
        """The English dataset exercises non-DE formats (e.g. IBANs with letters).

        Guards that the IBAN pattern stays country-agnostic (GB IBANs contain letters)
        and that precision stays perfect on English text.
        """
        docs = load_dataset(DATASET_EN)
        result = run_evaluation(docs, ["regex"])
        assert result.micro.fp == 0, f"regex produced false positives: {result.micro}"
        for canonical in ("IBAN", "EMAIL", "IP_ADDRESS", "CREDIT_CARD", "PHONE"):
            assert result.f1_for(canonical) == 1.0, (
                f"{canonical} F1 regressed: {result.per_type.get(canonical)}"
            )
