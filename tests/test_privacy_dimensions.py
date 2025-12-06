"""Tests for privacy dimension mapping."""

import pytest

from core.privacy_dimensions import (
    get_dimension,
    get_sensitivity_level,
    get_all_dimensions,
    get_types_for_dimension
)


def test_get_dimension_identity():
    """Test mapping of identity-related detection types."""
    assert get_dimension("REGEX_PASSPORT") == "identity"
    assert get_dimension("REGEX_PERSONALAUSWEIS") == "identity"
    assert get_dimension("REGEX_SSN_US") == "identity"
    assert get_dimension("NER_PERSON") == "identity"
    assert get_dimension("OLLAMA_PERSON") == "identity"


def test_get_dimension_contact():
    """Test mapping of contact information types."""
    assert get_dimension("REGEX_EMAIL") == "contact_information"
    assert get_dimension("REGEX_PHONE") == "contact_information"
    assert get_dimension("REGEX_POSTAL_CODE") == "contact_information"
    assert get_dimension("NER_LOCATION") == "contact_information"


def test_get_dimension_financial():
    """Test mapping of financial types."""
    assert get_dimension("REGEX_IBAN") == "financial"
    assert get_dimension("REGEX_BIC") == "financial"
    assert get_dimension("REGEX_CREDIT_CARD") == "financial"
    assert get_dimension("NER_FINANCIAL") == "financial"


def test_get_dimension_health():
    """Test mapping of health-related types."""
    assert get_dimension("NER_HEALTH") == "health"
    assert get_dimension("NER_MEDICAL_CONDITION") == "health"
    assert get_dimension("NER_MEDICATION") == "health"
    assert get_dimension("REGEX_MRN") == "health"


def test_get_dimension_sensitive():
    """Test mapping of sensitive personal data types."""
    assert get_dimension("NER_POLITICAL") == "sensitive_personal_data"
    assert get_dimension("NER_RELIGIOUS") == "sensitive_personal_data"
    assert get_dimension("NER_SEXUAL_ORIENTATION") == "sensitive_personal_data"
    assert get_dimension("NER_ETHNIC_ORIGIN") == "sensitive_personal_data"
    assert get_dimension("NER_CRIMINAL_CONVICTION") == "sensitive_personal_data"


def test_get_dimension_unknown():
    """Test that unknown types map to 'other'."""
    assert get_dimension("UNKNOWN_TYPE") == "other"
    assert get_dimension("") == "other"


def test_get_sensitivity_level():
    """Test sensitivity level retrieval."""
    assert get_sensitivity_level("health") == "very_high"
    assert get_sensitivity_level("biometric") == "very_high"
    assert get_sensitivity_level("sensitive_personal_data") == "very_high"
    assert get_sensitivity_level("identity") == "high"
    assert get_sensitivity_level("financial") == "high"
    assert get_sensitivity_level("contact_information") == "medium"
    assert get_sensitivity_level("organizational") == "low"
    assert get_sensitivity_level("unknown_dimension") == "variable"


def test_get_all_dimensions():
    """Test that all dimensions are returned."""
    dimensions = get_all_dimensions()
    assert isinstance(dimensions, list)
    assert "identity" in dimensions
    assert "health" in dimensions
    assert "financial" in dimensions
    assert len(dimensions) > 0


def test_get_types_for_dimension():
    """Test retrieval of types for a dimension."""
    identity_types = get_types_for_dimension("identity")
    assert isinstance(identity_types, list)
    assert "REGEX_PASSPORT" in identity_types
    assert "NER_PERSON" in identity_types
    
    health_types = get_types_for_dimension("health")
    assert "NER_HEALTH" in health_types
    assert "NER_MEDICAL_CONDITION" in health_types
