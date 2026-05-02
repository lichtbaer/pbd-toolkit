"""PII severity classification and combination-risk escalation.

Severity levels (ascending):
  LOW      – quasi-identifiers / signal words with limited harm potential alone
  MEDIUM   – personally identifiable but low direct-harm risk in isolation
  HIGH     – sensitive personal data, GDPR Art. 9 special categories, financial IDs
  CRITICAL – directly exploitable (credentials, payment data, government IDs, health records)

Combination-risk escalation (applied per file):
  A file whose PII types are individually MEDIUM can be escalated to HIGH or CRITICAL
  when combined with other types – e.g. a name + an IBAN creates a higher risk than
  each alone.  Use ``combined_file_risk`` to compute this aggregate level.
"""

from __future__ import annotations

import logging
from collections.abc import Collection

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-type severity map
# Keys match the ``type`` field stored in PiiMatch (i.e. config_types label).
# ---------------------------------------------------------------------------
SEVERITY_MAP: dict[str, str] = {
    # ── CRITICAL ────────────────────────────────────────────────────────────
    # Directly exploitable: credentials, payment data, government identity numbers,
    # health-record identifiers.
    "REGEX_PGPPRV": "CRITICAL",  # PGP private key
    "REGEX_CREDIT_CARD": "CRITICAL",  # Credit card number (Luhn-validated)
    "REGEX_SSN_US": "CRITICAL",  # US Social Security Number
    "REGEX_SSN_AT": "CRITICAL",  # Austrian SSN
    "REGEX_SSN_CH": "CRITICAL",  # Swiss AHV number
    "REGEX_MRN": "CRITICAL",  # Medical record number
    "NER_PASSWORD": "CRITICAL",  # Passwords / credentials
    "NER_BIOMETRIC": "CRITICAL",  # Biometric data (GDPR Art. 9)
    "NER_CRIMINAL_CONVICTION": "CRITICAL",  # Criminal convictions (GDPR Art. 10)
    # ── HIGH ────────────────────────────────────────────────────────────────
    # Sensitive personal data / GDPR Art. 9 special categories / financial identifiers.
    "REGEX_RVNR": "HIGH",  # German pension-insurance ID
    "REGEX_IBAN": "HIGH",  # International Bank Account Number
    "REGEX_TAX_ID": "HIGH",  # Tax identification number
    "REGEX_PASSPORT": "HIGH",  # Passport number
    "REGEX_PERSONALAUSWEIS": "HIGH",  # German national ID card
    "NER_HEALTH": "HIGH",  # Health data (GDPR Art. 9)
    "NER_MEDICAL_CONDITION": "HIGH",  # Medical conditions
    "NER_MEDICATION": "HIGH",  # Medication / prescriptions
    "NER_SEXUAL_ORIENTATION": "HIGH",  # Sexual orientation (GDPR Art. 9)
    "NER_POLITICAL": "HIGH",  # Political opinions (GDPR Art. 9)
    "NER_RELIGIOUS": "HIGH",  # Religious beliefs (GDPR Art. 9)
    "NER_ETHNIC_ORIGIN": "HIGH",  # Racial / ethnic origin (GDPR Art. 9)
    "NER_FINANCIAL": "HIGH",  # Financial information
    "OLLAMA_SENSITIVE": "HIGH",  # Ollama: generic sensitive data
    "OLLAMA_MONEY": "HIGH",  # Ollama: monetary values / salaries
    # ── MEDIUM ──────────────────────────────────────────────────────────────
    # Personally identifiable; limited harm risk when found in isolation.
    "REGEX_EMAIL": "MEDIUM",
    "REGEX_PHONE": "MEDIUM",
    "NER_PERSON": "MEDIUM",  # Person name
    "NER_LOCATION": "MEDIUM",
    "OLLAMA_PERSON": "MEDIUM",
    "OLLAMA_LOCATION": "MEDIUM",
    "OLLAMA_ORGANIZATION": "MEDIUM",
    "OLLAMA_DATE": "LOW",
    # ── LOW ─────────────────────────────────────────────────────────────────
    # Quasi-identifiers or informational; low harm potential alone.
    "REGEX_IPV4": "LOW",
    "REGEX_WORDS": "LOW",
    "REGEX_SIGNAL_WORDS_EXTENDED": "LOW",
    "REGEX_BIC": "LOW",
    "REGEX_POSTAL_CODE": "LOW",
}

# Numeric weights for comparison / escalation logic
_LEVEL_WEIGHT: dict[str, int] = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}

_WEIGHT_LEVEL: dict[int, str] = {v: k for k, v in _LEVEL_WEIGHT.items()}

# Fail-safe default: unknown PII types are treated as MEDIUM rather than LOW.
# This ensures that new types added to config_types.yaml (but not yet mapped here)
# are never silently under-classified in compliance reports.  Operators who disagree
# can override via --severity-config.
DEFAULT_SEVERITY = "MEDIUM"


def classify(pii_type: str) -> str:
    """Return the severity level for a single PII type label.

    Unknown labels default to ``DEFAULT_SEVERITY`` ("MEDIUM") to avoid silent
    under-classification of new types not yet in the map.

    Args:
        pii_type: PiiMatch.type value (e.g. "REGEX_IBAN", "NER_PERSON").

    Returns:
        One of "LOW", "MEDIUM", "HIGH", "CRITICAL".
    """
    return SEVERITY_MAP.get(pii_type, DEFAULT_SEVERITY)


# ---------------------------------------------------------------------------
# Combination-risk escalation
# ---------------------------------------------------------------------------

# Labels that anchor a document to a named individual.  When any of these appears
# alongside a HIGH-severity type, the combination becomes linkable (re-identifiable),
# which GDPR Art. 4(1) treats as personal data regardless of pseudonymisation.
_PERSON_LABELS: frozenset[str] = frozenset(
    {"NER_PERSON", "OLLAMA_PERSON", "REGEX_PASSPORT", "REGEX_PERSONALAUSWEIS"}
)

# Labels that, when combined with a person identifier, escalate to CRITICAL
_ESCALATE_WITH_PERSON_TO_CRITICAL: frozenset[str] = frozenset(
    {
        "REGEX_IBAN",
        "REGEX_CREDIT_CARD",
        "REGEX_SSN_US",
        "REGEX_SSN_AT",
        "REGEX_SSN_CH",
        "REGEX_RVNR",
        "REGEX_TAX_ID",
        "NER_HEALTH",
        "NER_MEDICAL_CONDITION",
        "NER_BIOMETRIC",
        "NER_PASSWORD",
        "NER_CRIMINAL_CONVICTION",
    }
)


def combined_file_risk(pii_types: Collection[str]) -> str:
    """Compute the aggregate risk level for a file based on its PII types.

    Escalation rules (applied in order, stops at first match):
    1. Any CRITICAL type alone → CRITICAL.
    2. A person identifier combined with any ``_ESCALATE_WITH_PERSON_TO_CRITICAL``
       type → CRITICAL (linkage attack: the name turns financial/health data into a
       directly re-identifiable record).
    3. Three or more distinct HIGH types → CRITICAL.
    4. A person identifier combined with any HIGH type → HIGH (at minimum).
    5. Otherwise: maximum severity of the individual types.

    Args:
        pii_types: Iterable of PiiMatch.type values found in a single file.

    Returns:
        One of "LOW", "MEDIUM", "HIGH", "CRITICAL", or "NONE" for empty input.
    """
    types_set = set(pii_types)
    if not types_set:
        return "NONE"

    individual_levels = {t: classify(t) for t in types_set}

    # Rule 1: any CRITICAL type
    if any(lvl == "CRITICAL" for lvl in individual_levels.values()):
        return "CRITICAL"

    has_person = bool(types_set & _PERSON_LABELS)
    high_types = {t for t, lvl in individual_levels.items() if lvl == "HIGH"}

    # Rule 2: person + escalating HIGH type
    if has_person and (types_set & _ESCALATE_WITH_PERSON_TO_CRITICAL):
        return "CRITICAL"

    # Rule 3: profile aggregation – three or more distinct HIGH types in one file
    # creates a comprehensive personal profile even if no single type is CRITICAL.
    # Example: IBAN + health data + tax ID together uniquely identify and expose a person
    # far more than any one of those alone.
    if len(high_types) >= 3:
        return "CRITICAL"

    # Rule 4: person + any HIGH type
    if has_person and high_types:
        return "HIGH"

    # Rule 5: maximum of individual levels
    max_weight = max(_LEVEL_WEIGHT.get(lvl, 2) for lvl in individual_levels.values())
    return _WEIGHT_LEVEL.get(max_weight, DEFAULT_SEVERITY)


# ---------------------------------------------------------------------------
# Custom severity configuration (YAML/JSON)
# ---------------------------------------------------------------------------


def load_custom_severity_config(path: str) -> None:
    """Load custom severity configuration from a YAML or JSON file.

    The file can contain:

    - ``severity_map``: dict of PII type → severity level overrides
    - ``person_labels``: list of additional person-identifier labels
    - ``escalate_with_person_to_critical``: list of additional labels that
      escalate to CRITICAL when combined with a person identifier
    - ``default_severity``: default severity for unknown types

    Example YAML::

        severity_map:
          REGEX_CUSTOM_ID: CRITICAL
          NER_CUSTOM_FIELD: HIGH
        person_labels:
          - NER_CUSTOM_PERSON
        escalate_with_person_to_critical:
          - REGEX_CUSTOM_ID
        default_severity: MEDIUM

    Args:
        path: Path to a YAML or JSON configuration file.
    """
    global SEVERITY_MAP, _PERSON_LABELS, _ESCALATE_WITH_PERSON_TO_CRITICAL
    global DEFAULT_SEVERITY

    import json as _json

    try:
        if path.lower().endswith((".yaml", ".yml")):
            try:
                import yaml  # type: ignore

                with open(path, encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
            except ImportError:
                _logger.warning(
                    "PyYAML not installed; cannot load YAML severity config. "
                    "Install with: pip install PyYAML"
                )
                return
        else:
            with open(path, encoding="utf-8") as fh:
                data = _json.load(fh)

        if not isinstance(data, dict):
            _logger.warning(
                "Severity config must be a mapping; got %s", type(data).__name__
            )
            return

        # Merge severity map overrides
        custom_map = data.get("severity_map", {})
        if isinstance(custom_map, dict):
            valid_levels = set(_LEVEL_WEIGHT.keys())
            for pii_type, level in custom_map.items():
                if isinstance(level, str) and level.upper() in valid_levels:
                    SEVERITY_MAP[str(pii_type)] = level.upper()
                else:
                    _logger.warning(
                        "Ignoring invalid severity level '%s' for type '%s'",
                        level,
                        pii_type,
                    )

        # Extend person labels
        extra_person = data.get("person_labels", [])
        if isinstance(extra_person, list):
            _PERSON_LABELS = _PERSON_LABELS | frozenset(
                str(lbl) for lbl in extra_person
            )

        # Extend escalation labels
        extra_escalate = data.get("escalate_with_person_to_critical", [])
        if isinstance(extra_escalate, list):
            _ESCALATE_WITH_PERSON_TO_CRITICAL = (
                _ESCALATE_WITH_PERSON_TO_CRITICAL
                | frozenset(str(lbl) for lbl in extra_escalate)
            )

        # Override default severity
        default = data.get("default_severity")
        if isinstance(default, str) and default.upper() in _LEVEL_WEIGHT:
            DEFAULT_SEVERITY = default.upper()

        _logger.debug("Custom severity config loaded from %s", path)

    except FileNotFoundError:
        _logger.warning("Severity config file not found: %s", path)
    except Exception as exc:
        _logger.warning("Failed to load severity config from %s: %s", path, exc)
