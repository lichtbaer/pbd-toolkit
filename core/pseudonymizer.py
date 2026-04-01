"""Pseudo-anonymization: replace PII with realistic-looking fake data.

Unlike simple redaction (``[REDACTED:TYPE]``), pseudo-anonymization produces
plausible substitute values so that documents remain readable and usable as
test data while no longer containing real PII.

Consistency guarantee: the same input text always maps to the same fake
replacement within a single ``Pseudonymizer`` instance (deterministic mapping
seeded from the input hash).
"""

from __future__ import annotations

import hashlib
import random
import re
from pathlib import Path

from core.matches import PiiMatch

# ---------------------------------------------------------------------------
# Fake-value pools
# ---------------------------------------------------------------------------

_FIRST_NAMES = [
    "Anna", "Ben", "Clara", "David", "Eva", "Felix", "Greta", "Hans",
    "Ida", "Jan", "Klara", "Lukas", "Mia", "Noah", "Olivia", "Paul",
    "Quinn", "Rosa", "Stefan", "Tina", "Uwe", "Vera", "Walter", "Xara",
    "Yara", "Zoe",
]

_LAST_NAMES = [
    "Bauer", "Fischer", "Hoffmann", "Koch", "Lange", "Maier", "Müller",
    "Neumann", "Otto", "Peters", "Richter", "Schmitt", "Schneider",
    "Schulz", "Schwarz", "Wagner", "Weber", "Werner", "Wolf", "Zimmermann",
]

_STREET_NAMES = [
    "Hauptstraße", "Bahnhofstraße", "Gartenweg", "Bergstraße", "Kirchgasse",
    "Lindenallee", "Rosenweg", "Schillerstraße", "Mozartstraße", "Beethovenplatz",
]

_CITIES = [
    "Musterstadt", "Neustadt", "Kleinburg", "Großfeld", "Waldheim",
    "Seebach", "Bergdorf", "Talheim", "Wiesenau", "Steinbach",
]

_DOMAINS = [
    "example.com", "testmail.de", "sample.org", "fakeemail.net", "demo.io",
]

_COUNTRIES = ["DE", "AT", "CH", "NL", "FR"]

# IBAN country-specific digit lengths (modulo-97 check digit not enforced intentionally)
_IBAN_LENGTHS = {"DE": 22, "AT": 20, "CH": 21, "NL": 18, "FR": 27}


def _seed_rng(text: str) -> random.Random:
    """Return a seeded Random instance deterministic for *text*."""
    digest = int(hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest(), 16)  # noqa: S324
    return random.Random(digest)


def _fake_name(rng: random.Random) -> str:
    return f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"


def _fake_email(rng: random.Random) -> str:
    first = rng.choice(_FIRST_NAMES).lower()
    last = rng.choice(_LAST_NAMES).lower()
    domain = rng.choice(_DOMAINS)
    suffix = rng.randint(1, 99)
    return f"{first}.{last}{suffix}@{domain}"


def _fake_phone(rng: random.Random) -> str:
    prefix = rng.choice(["030", "040", "089", "069", "0221"])
    number = rng.randint(1000000, 9999999)
    return f"{prefix} {number}"


def _fake_iban(rng: random.Random) -> str:
    country = rng.choice(_COUNTRIES)
    length = _IBAN_LENGTHS.get(country, 22)
    digits = "".join(str(rng.randint(0, 9)) for _ in range(length - 4))
    check = rng.randint(10, 99)
    return f"{country}{check}{digits}"


def _fake_credit_card(rng: random.Random) -> str:
    # Fake Visa-style number (starts with 4, 16 digits) – fails Luhn on purpose
    digits = "4" + "".join(str(rng.randint(0, 9)) for _ in range(14)) + str(rng.randint(0, 9))
    return " ".join(digits[i:i+4] for i in range(0, 16, 4))


def _fake_date(rng: random.Random) -> str:
    day = rng.randint(1, 28)
    month = rng.randint(1, 12)
    year = rng.randint(1950, 2005)
    return f"{day:02d}.{month:02d}.{year}"


def _fake_ip(rng: random.Random) -> str:
    return f"10.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,254)}"


def _fake_address(rng: random.Random) -> str:
    street = rng.choice(_STREET_NAMES)
    number = rng.randint(1, 200)
    zip_code = rng.randint(10000, 99999)
    city = rng.choice(_CITIES)
    return f"{street} {number}, {zip_code} {city}"


def _fake_tax_id(rng: random.Random) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(11))


def _fake_bic(rng: random.Random) -> str:
    bank = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(4))
    country = rng.choice(_COUNTRIES)
    loc = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(2))
    return f"{bank}{country}{loc}XXX"


# ---------------------------------------------------------------------------
# Dispatch table: PII type → fake generator
# ---------------------------------------------------------------------------

_PII_TYPE_PATTERNS = [
    (re.compile(r"name|person", re.I), _fake_name),
    (re.compile(r"email|e-mail", re.I), _fake_email),
    (re.compile(r"phone|tel|mobile|handy", re.I), _fake_phone),
    (re.compile(r"iban", re.I), _fake_iban),
    (re.compile(r"credit.?card|kreditkarte", re.I), _fake_credit_card),
    (re.compile(r"date|datum|geburt", re.I), _fake_date),
    (re.compile(r"ip.?addr", re.I), _fake_ip),
    (re.compile(r"address|adresse|street|straße", re.I), _fake_address),
    (re.compile(r"tax|steuernummer|steuer.?id", re.I), _fake_tax_id),
    (re.compile(r"bic|swift", re.I), _fake_bic),
]


def _fake_for_type(pii_type: str, rng: random.Random) -> str:
    """Return a type-appropriate fake value."""
    for pattern, generator in _PII_TYPE_PATTERNS:
        if pattern.search(pii_type):
            return generator(rng)
    # Fallback: short random alphanumeric token
    return "FAKE-" + "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(8))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class Pseudonymizer:
    """Replaces PII text with deterministic, type-appropriate fake values.

    Each unique (text, type) pair always maps to the same fake value within
    this instance, enabling consistent replacement across multiple files.
    """

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], str] = {}

    def fake_value(self, text: str, pii_type: str) -> str:
        """Return a deterministic fake value for *text* of *pii_type*."""
        key = (text, pii_type)
        if key not in self._cache:
            rng = _seed_rng(text + pii_type)
            self._cache[key] = _fake_for_type(pii_type, rng)
        return self._cache[key]

    def pseudonymize_text(self, text: str, matches: list[PiiMatch]) -> str:
        """Replace all PII matches in *text* with fake values.

        Matches are processed from end to start so character offsets remain
        valid during in-place substitution.
        """
        if not matches or not text:
            return text

        replacements: list[tuple[int, int, str]] = []
        for m in matches:
            fake = self.fake_value(m.text, m.type or "unknown")
            if m.char_offset is not None:
                start = m.char_offset
                end = start + len(m.text)
                replacements.append((start, end, fake))
            else:
                idx = 0
                while True:
                    pos = text.find(m.text, idx)
                    if pos == -1:
                        break
                    replacements.append((pos, pos + len(m.text), fake))
                    idx = pos + len(m.text)

        if not replacements:
            return text

        # Sort descending by start to preserve offsets
        replacements.sort(key=lambda x: x[0], reverse=True)

        # Remove overlaps (keep first / longest)
        cleaned: list[tuple[int, int, str]] = []
        min_start: float = float("inf")
        for start, end, fake in replacements:
            if end <= min_start:
                cleaned.append((start, end, fake))
                min_start = start

        result = text
        for start, end, fake in cleaned:
            result = result[:start] + fake + result[end:]
        return result


def pseudonymize_files(
    matches_by_file: dict[str, list[PiiMatch]],
    output_dir: str,
    logger=None,
) -> dict[str, str]:
    """Create pseudo-anonymized copies of files containing PII.

    Text-based files are rewritten with fake-but-plausible substitutions.
    Binary formats receive a ``.pseudo.txt`` companion with the pseudonymized
    extracted text summary (same approach as the redactor for binary files).

    Returns:
        Dict mapping original file paths to pseudo-anonymized output paths.
    """
    import os

    os.makedirs(output_dir, exist_ok=True)
    output_paths: dict[str, str] = {}
    pseudonymizer = Pseudonymizer()

    TEXT_EXTENSIONS = {
        ".txt", ".csv", ".json", ".xml", ".html", ".htm", ".md",
        ".markdown", ".yaml", ".yml", ".eml", ".properties", ".ini",
        ".cfg", ".conf", ".env", ".rtf",
    }

    for file_path, file_matches in matches_by_file.items():
        if not file_matches:
            continue

        try:
            ext = Path(file_path).suffix.lower()
            basename = Path(file_path).name
            out_path = os.path.join(output_dir, basename + ".pseudo.txt")

            counter = 1
            while os.path.exists(out_path):
                out_path = os.path.join(output_dir, f"{basename}.pseudo.{counter}.txt")
                counter += 1

            if ext in TEXT_EXTENSIONS:
                with open(file_path, encoding="utf-8", errors="replace") as f:
                    content = f.read()

                pseudonymized = pseudonymizer.pseudonymize_text(content, file_matches)

                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(pseudonymized)
            else:
                lines = [
                    f"# Pseudo-anonymized content from: {file_path}",
                    f"# Original format: {ext}",
                    f"# PII findings replaced: {len(file_matches)}\n",
                ]
                for m in file_matches:
                    fake = pseudonymizer.fake_value(m.text, m.type or "unknown")
                    lines.append(
                        f"[PSEUDONYMIZED:{m.type}] → {fake}  (engine: {m.engine})"
                    )

                with open(out_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")

            output_paths[file_path] = out_path
            if logger:
                logger.info("Pseudonymized: %s -> %s", file_path, out_path)

        except Exception as e:
            if logger:
                logger.warning("Failed to pseudonymize %s: %s", file_path, e)

    return output_paths
