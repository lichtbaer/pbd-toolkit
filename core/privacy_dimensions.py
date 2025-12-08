"""Privacy dimension mapping for PII detection types.

This module maps detection types (labels) to privacy dimensions based on
GDPR Article 9 and data protection principles. This enables aggregation
of statistics without storing individual PII instances.
"""

from typing import Dict


# Mapping of detection types to privacy dimensions
DIMENSION_MAPPING: Dict[str, str] = {
    # Identity dimension
    "REGEX_RVNR": "identity",
    "REGEX_PASSPORT": "identity",
    "REGEX_PERSONALAUSWEIS": "identity",
    "REGEX_SSN_US": "identity",
    "REGEX_SSN_AT": "identity",
    "REGEX_SSN_CH": "identity",
    "NER_PERSON": "identity",
    "OLLAMA_PERSON": "identity",
    # Contact information dimension
    "REGEX_EMAIL": "contact_information",
    "REGEX_PHONE": "contact_information",
    "REGEX_POSTAL_CODE": "contact_information",
    "REGEX_IPV4": "contact_information",
    "NER_LOCATION": "contact_information",
    "OLLAMA_LOCATION": "contact_information",
    # Financial dimension
    "REGEX_IBAN": "financial",
    "REGEX_BIC": "financial",
    "REGEX_CREDIT_CARD": "financial",
    "REGEX_TAX_ID": "financial",
    "NER_FINANCIAL": "financial",
    "OLLAMA_MONEY": "financial",
    # Health dimension
    "NER_HEALTH": "health",
    "NER_MEDICAL_CONDITION": "health",
    "NER_MEDICATION": "health",
    "REGEX_MRN": "health",
    # Biometric dimension
    "NER_BIOMETRIC": "biometric",
    # Sensitive personal data dimension (GDPR Article 9)
    "NER_POLITICAL": "sensitive_personal_data",
    "NER_RELIGIOUS": "sensitive_personal_data",
    "NER_SEXUAL_ORIENTATION": "sensitive_personal_data",
    "NER_ETHNIC_ORIGIN": "sensitive_personal_data",
    "NER_CRIMINAL_CONVICTION": "sensitive_personal_data",
    "OLLAMA_SENSITIVE": "sensitive_personal_data",
    # Location dimension (separate from contact information for detailed analysis)
    # Note: NER_LOCATION and OLLAMA_LOCATION are mapped to contact_information
    # but can be analyzed separately if needed
    # Credentials & Security dimension
    "NER_PASSWORD": "credentials_security",
    "REGEX_PGPPRV": "credentials_security",
    # Organizational dimension
    "OLLAMA_ORGANIZATION": "organizational",
    "OLLAMA_DATE": "organizational",
    # Signal words dimension
    "REGEX_WORDS": "signal_words",
    "REGEX_SIGNAL_WORDS_EXTENDED": "signal_words",
}

# Sensitivity levels for each dimension
SENSITIVITY_LEVELS: Dict[str, str] = {
    "identity": "high",
    "contact_information": "medium",
    "financial": "high",
    "health": "very_high",
    "biometric": "very_high",
    "sensitive_personal_data": "very_high",
    "location": "medium",
    "credentials_security": "very_high",
    "organizational": "low",
    "signal_words": "medium",
    "other": "variable",
}


def get_dimension(detection_type: str) -> str:
    """Map detection type to privacy dimension.

    Args:
        detection_type: Detection type label (e.g., "REGEX_EMAIL", "NER_PERSON")

    Returns:
        Privacy dimension name (e.g., "contact_information", "identity")
        Returns "other" if type is not mapped
    """
    return DIMENSION_MAPPING.get(detection_type, "other")


def get_sensitivity_level(dimension: str) -> str:
    """Get sensitivity level for a privacy dimension.

    Args:
        dimension: Privacy dimension name

    Returns:
        Sensitivity level: "very_high", "high", "medium", "low", or "variable"
    """
    return SENSITIVITY_LEVELS.get(dimension, "variable")


def get_all_dimensions() -> list[str]:
    """Get list of all defined privacy dimensions.

    Returns:
        List of dimension names
    """
    return list(SENSITIVITY_LEVELS.keys())


def get_types_for_dimension(dimension: str) -> list[str]:
    """Get all detection types that map to a specific dimension.

    Args:
        dimension: Privacy dimension name

    Returns:
        List of detection type labels
    """
    return [det_type for det_type, dim in DIMENSION_MAPPING.items() if dim == dimension]
