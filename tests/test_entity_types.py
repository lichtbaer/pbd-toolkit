"""Tests for the canonical entity-type taxonomy and label normalisation."""

from core import entity_types
from core.entity_types import (
    CANONICAL_TYPES,
    LABEL_TO_CANONICAL,
    canonical_for,
    is_validatable,
    validation_rule_for,
)
from core.resources import load_config_types
from core.severity import SEVERITY_MAP


class TestCanonicalMapping:
    """Completeness and consistency of LABEL_TO_CANONICAL."""

    def test_all_mapped_canonicals_are_known(self):
        """Every value in the map must be a declared canonical type."""
        for raw, canonical in LABEL_TO_CANONICAL.items():
            assert canonical in CANONICAL_TYPES, (
                f"{raw} maps to unknown canonical {canonical!r}"
            )

    def test_all_config_labels_are_mapped(self):
        """Every regex and ai-ner label in config_types.json must be mapped."""
        config = load_config_types()
        labels = [c["label"] for c in config["regex"]]
        labels += [c["label"] for c in config["ai-ner"]]
        unmapped = [label for label in labels if label not in LABEL_TO_CANONICAL]
        assert not unmapped, f"Unmapped config labels: {unmapped}"

    def test_all_vector_labels_are_mapped(self):
        """Every VECTOR_* exemplar category must be mapped."""
        from core.indexer.pii_queries import PII_EXEMPLARS

        unmapped = [label for label in PII_EXEMPLARS if label not in LABEL_TO_CANONICAL]
        assert not unmapped, f"Unmapped vector labels: {unmapped}"

    def test_all_severity_labels_are_mapped(self):
        """Every label that carries a severity must have a canonical type."""
        unmapped = [label for label in SEVERITY_MAP if label not in LABEL_TO_CANONICAL]
        assert not unmapped, f"Unmapped severity labels: {unmapped}"


class TestCanonicalFor:
    """Behaviour of canonical_for()."""

    def test_known_labels(self):
        assert canonical_for("REGEX_CREDIT_CARD") == entity_types.CREDIT_CARD
        assert canonical_for("VECTOR_CREDITCARD") == entity_types.CREDIT_CARD
        assert canonical_for("REGEX_IBAN") == entity_types.IBAN
        assert canonical_for("NER_FINANCIAL") == entity_types.FINANCIAL
        assert canonical_for("NER_PERSON") == entity_types.PERSON
        assert canonical_for("VECTOR_PERSON") == entity_types.PERSON

    def test_cross_engine_credit_card_aliases_converge(self):
        """The whole point: every credit-card alias collapses to one canonical type."""
        aliases = ["REGEX_CREDIT_CARD", "VECTOR_CREDITCARD"]
        canonicals = {canonical_for(a) for a in aliases}
        assert canonicals == {entity_types.CREDIT_CARD}

    def test_unknown_label_falls_back_to_itself(self):
        assert canonical_for("REGEX_CUSTOM_ID") == "REGEX_CUSTOM_ID"

    def test_empty_input(self):
        assert canonical_for("") == ""
        assert canonical_for(None) == ""


class TestValidationRules:
    """Checksum-validation rule lookup."""

    def test_validatable_types(self):
        for t in (
            entity_types.IBAN,
            entity_types.CREDIT_CARD,
            entity_types.TAX_ID,
            entity_types.BIC,
        ):
            assert is_validatable(t)
            assert validation_rule_for(t) is not None

    def test_non_validatable_types(self):
        assert not is_validatable(entity_types.PERSON)
        assert validation_rule_for(entity_types.EMAIL) is None

    def test_rule_shape(self):
        name, mode, lo, hi = validation_rule_for(entity_types.CREDIT_CARD)
        assert name == "luhn"
        assert mode == "digits"
        assert lo <= hi
