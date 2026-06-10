"""Canonical PII entity-type taxonomy and cross-engine label normalisation.

Why this module exists
----------------------
Each detection engine emits PII-type labels in its **own** namespace for what are
often the *same* real-world concepts:

    regex   :  REGEX_CREDIT_CARD, REGEX_IBAN, REGEX_PERSONALAUSWEIS, ...
    gliner  :  NER_PERSON, NER_FINANCIAL, NER_HEALTH, ...
    vector  :  VECTOR_CREDITCARD, VECTOR_PERSON, VECTOR_FINANCIAL, ...
    llm     :  CREDIT_CARD, PERSON, ... (provider-dependent)

Because :class:`core.matches.PiiMatchContainer` keys deduplication and confidence
fusion on the raw ``type`` string, a credit card found by *both* the regex engine
(``REGEX_CREDIT_CARD``) and the vector engine (``VECTOR_CREDITCARD``) is stored as
two unrelated findings — the multi-engine "defense in depth" corroboration never
actually fuses.

This module provides a small canonical taxonomy plus a raw-label → canonical map so
that the container can group cross-engine findings by the underlying concept while the
human-readable engine label is preserved on the match for reporting.

Design notes
------------
- ``canonical_for`` falls back to returning the input label unchanged for unknown
  (e.g. user-defined custom regex) labels, so normalisation never loses a finding.
- The map is deliberately data-only and import-light: it must be safe to import from
  ``core.matches`` without pulling in optional ML dependencies.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Canonical entity types
# ---------------------------------------------------------------------------
# String constants (not an Enum) so values interoperate directly with the existing
# ``str`` typed ``type`` field on PiiMatch and with JSON serialisation.
PERSON = "PERSON"
LOCATION = "LOCATION"
ADDRESS = "ADDRESS"
EMAIL = "EMAIL"
PHONE = "PHONE"
IBAN = "IBAN"
BIC = "BIC"
CREDIT_CARD = "CREDIT_CARD"
TAX_ID = "TAX_ID"
SSN = "SSN"
PASSPORT = "PASSPORT"
NATIONAL_ID = "NATIONAL_ID"
PENSION_ID = "PENSION_ID"
IP_ADDRESS = "IP_ADDRESS"
POSTAL_CODE = "POSTAL_CODE"
HEALTH = "HEALTH"
MEDICATION = "MEDICATION"
MEDICAL_CONDITION = "MEDICAL_CONDITION"
MRN = "MRN"
BIOMETRIC = "BIOMETRIC"
POLITICAL = "POLITICAL"
RELIGIOUS = "RELIGIOUS"
SEXUAL_ORIENTATION = "SEXUAL_ORIENTATION"
ETHNIC_ORIGIN = "ETHNIC_ORIGIN"
CRIMINAL = "CRIMINAL"
FINANCIAL = "FINANCIAL"
CREDENTIALS = "CREDENTIALS"
VEHICLE = "VEHICLE"
ID_DOCUMENT = "ID_DOCUMENT"
SIGNAL_WORD = "SIGNAL_WORD"
PGP_KEY = "PGP_KEY"
ORGANIZATION = "ORGANIZATION"
DATE = "DATE"
SENSITIVE = "SENSITIVE"

CANONICAL_TYPES: frozenset[str] = frozenset(
    {
        PERSON,
        LOCATION,
        ADDRESS,
        EMAIL,
        PHONE,
        IBAN,
        BIC,
        CREDIT_CARD,
        TAX_ID,
        SSN,
        PASSPORT,
        NATIONAL_ID,
        PENSION_ID,
        IP_ADDRESS,
        POSTAL_CODE,
        HEALTH,
        MEDICATION,
        MEDICAL_CONDITION,
        MRN,
        BIOMETRIC,
        POLITICAL,
        RELIGIOUS,
        SEXUAL_ORIENTATION,
        ETHNIC_ORIGIN,
        CRIMINAL,
        FINANCIAL,
        CREDENTIALS,
        VEHICLE,
        ID_DOCUMENT,
        SIGNAL_WORD,
        PGP_KEY,
        ORGANIZATION,
        DATE,
        SENSITIVE,
    }
)

# ---------------------------------------------------------------------------
# Raw engine label -> canonical type
# ---------------------------------------------------------------------------
# Sources kept in sync with:
#   - core/config_types.json   (regex "label" + ai-ner "label")
#   - core/indexer/pii_queries.py  (VECTOR_* exemplar categories)
#   - core/severity.py         (legacy OLLAMA_* labels)
LABEL_TO_CANONICAL: dict[str, str] = {
    # ── regex (REGEX_*) ──────────────────────────────────────────────────
    "REGEX_RVNR": PENSION_ID,
    "REGEX_IBAN": IBAN,
    "REGEX_EMAIL": EMAIL,
    "REGEX_IPV4": IP_ADDRESS,
    "REGEX_WORDS": SIGNAL_WORD,
    "REGEX_PGPPRV": PGP_KEY,
    "REGEX_PHONE": PHONE,
    "REGEX_TAX_ID": TAX_ID,
    "REGEX_BIC": BIC,
    "REGEX_POSTAL_CODE": POSTAL_CODE,
    "REGEX_SIGNAL_WORDS_EXTENDED": SIGNAL_WORD,
    "REGEX_CREDIT_CARD": CREDIT_CARD,
    "REGEX_PASSPORT": PASSPORT,
    "REGEX_PERSONALAUSWEIS": NATIONAL_ID,
    "REGEX_SSN_US": SSN,
    "REGEX_SSN_AT": SSN,
    "REGEX_SSN_CH": SSN,
    "REGEX_MRN": MRN,
    # ── gliner / spaCy NER (NER_*) ───────────────────────────────────────
    "NER_PERSON": PERSON,
    "NER_LOCATION": LOCATION,
    "NER_HEALTH": HEALTH,
    "NER_PASSWORD": CREDENTIALS,
    "NER_BIOMETRIC": BIOMETRIC,
    "NER_POLITICAL": POLITICAL,
    "NER_RELIGIOUS": RELIGIOUS,
    "NER_SEXUAL_ORIENTATION": SEXUAL_ORIENTATION,
    "NER_ETHNIC_ORIGIN": ETHNIC_ORIGIN,
    "NER_CRIMINAL_CONVICTION": CRIMINAL,
    "NER_FINANCIAL": FINANCIAL,
    "NER_MEDICAL_CONDITION": MEDICAL_CONDITION,
    "NER_MEDICATION": MEDICATION,
    # ── vector search (VECTOR_*) ─────────────────────────────────────────
    "VECTOR_PERSON": PERSON,
    "VECTOR_ADDRESS": ADDRESS,
    "VECTOR_LOCATION": LOCATION,
    "VECTOR_EMAIL": EMAIL,
    "VECTOR_PHONE": PHONE,
    "VECTOR_CREDITCARD": CREDIT_CARD,
    "VECTOR_FINANCIAL": FINANCIAL,
    "VECTOR_SSN": SSN,
    "VECTOR_HEALTH": HEALTH,
    "VECTOR_BIOMETRIC": BIOMETRIC,
    "VECTOR_ID_DOCUMENT": ID_DOCUMENT,
    "VECTOR_VEHICLE": VEHICLE,
    "VECTOR_CREDENTIALS": CREDENTIALS,
    # ── legacy LLM/Ollama (OLLAMA_*) ─────────────────────────────────────
    "OLLAMA_PERSON": PERSON,
    "OLLAMA_LOCATION": LOCATION,
    "OLLAMA_ORGANIZATION": ORGANIZATION,
    "OLLAMA_DATE": DATE,
    "OLLAMA_MONEY": FINANCIAL,
    "OLLAMA_SENSITIVE": SENSITIVE,
}


def canonical_for(label: str | None) -> str:
    """Return the canonical entity type for a raw engine label.

    Unknown labels (e.g. user-defined custom regex patterns or provider-specific
    LLM labels) are returned unchanged so that normalisation never merges or drops
    a finding it does not understand.

    Args:
        label: Raw engine label such as ``"REGEX_IBAN"`` or ``"VECTOR_CREDITCARD"``.

    Returns:
        The canonical type string, or the original label if not mapped. Empty input
        returns an empty string.
    """
    if not label:
        return ""
    return LABEL_TO_CANONICAL.get(label, label)


# ---------------------------------------------------------------------------
# Checksum-validatable canonical types
# ---------------------------------------------------------------------------
# Maps a canonical type to the validator name understood by
# ``validators.get_validator`` plus the plausible length range (after cleaning) of a
# *single* value of that type.  The range is used as a guard: coarse-grained engines
# (e.g. vector search) report whole text chunks rather than a tight token, and running
# a checksum over a chunk would spuriously fail and discard a legitimate finding.  We
# therefore only apply checksum validation when the candidate's cleaned length is
# within range; out-of-range candidates are left untouched.
#
# Each entry: canonical -> (validator_name, clean_mode, min_len, max_len)
#   clean_mode "digits" -> keep [0-9] only (credit card, tax id)
#   clean_mode "alnum"  -> keep [0-9A-Za-z] only (IBAN, BIC)
_VALIDATION_RULES: dict[str, tuple[str, str, int, int]] = {
    IBAN: ("iban", "alnum", 15, 34),
    CREDIT_CARD: ("luhn", "digits", 13, 19),
    TAX_ID: ("tax_id", "digits", 11, 11),
    BIC: ("bic", "alnum", 8, 11),
}


def validation_rule_for(canonical_type: str) -> tuple[str, str, int, int] | None:
    """Return the checksum-validation rule for a canonical type, or None.

    Args:
        canonical_type: A canonical type string (e.g. ``"IBAN"``).

    Returns:
        Tuple ``(validator_name, clean_mode, min_len, max_len)`` or ``None`` if the
        type has no checksum validator.
    """
    return _VALIDATION_RULES.get(canonical_type)


def is_validatable(canonical_type: str) -> bool:
    """Return True if the canonical type has an associated checksum validator."""
    return canonical_type in _VALIDATION_RULES
