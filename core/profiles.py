"""Built-in scan profiles (presets) for common use cases.

Each profile is a dictionary of configuration values that can be loaded
via the ``--profile`` CLI flag.  CLI arguments provided explicitly by the
user always take precedence over profile values.
"""

from __future__ import annotations

PROFILES: dict[str, dict] = {
    "quick": {
        "_description": "Fast regex-only scan for large directories",
        "regex": True,
        "ner": False,
        "spacy_ner": False,
        "pydantic_ai": False,
        "mode": "fast",
    },
    "standard": {
        "_description": "Balanced scan with regex and NER, deduplication enabled",
        "regex": True,
        "ner": True,
        "spacy_ner": False,
        "pydantic_ai": False,
        "deduplicate": True,
        "mode": "balanced",
    },
    "deep": {
        "_description": "Thorough analysis with all available engines",
        "regex": True,
        "ner": True,
        "spacy_ner": False,
        "pydantic_ai": True,
        "deduplicate": True,
        "text_chunk_size": 2000,
        "text_chunk_overlap": 200,
        "mode": "balanced",
    },
    "gdpr-audit": {
        "_description": "GDPR Article 9 focused audit with privacy statistics",
        "regex": True,
        "ner": True,
        "deduplicate": True,
        "statistics_mode": True,
        "mode": "balanced",
    },
    "ci": {
        "_description": "CI/CD pipeline scan: fast regex with machine-readable output",
        "regex": True,
        "ner": False,
        "format": "json",
        "summary_format": "json",
        "quiet": False,
        "mode": "fast",
    },
}


def get_profile(name: str) -> dict:
    """Return a profile configuration by name.

    Args:
        name: Profile name (case-insensitive).

    Returns:
        Configuration dictionary (without internal ``_description`` key).

    Raises:
        ValueError: If the profile name is unknown.
    """
    key = name.lower()
    if key not in PROFILES:
        available = ", ".join(sorted(PROFILES))
        raise ValueError(
            f"Unknown profile '{name}'. Available profiles: {available}"
        )
    # Return a copy without the internal _description key
    return {k: v for k, v in PROFILES[key].items() if not k.startswith("_")}


def list_profiles() -> list[dict[str, str]]:
    """Return a list of all available profiles with their descriptions.

    Returns:
        List of dicts with ``name`` and ``description`` keys.
    """
    return [
        {"name": name, "description": profile.get("_description", "")}
        for name, profile in PROFILES.items()
    ]
