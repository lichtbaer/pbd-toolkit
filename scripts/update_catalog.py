#!/usr/bin/env python3
"""Regenerate locales/base.pot and update the de/en catalogs from source.

Usage:
    python scripts/update_catalog.py extract   # re-extract base.pot from source
    python scripts/update_catalog.py update     # merge base.pot into de/en .po
    python scripts/update_catalog.py fill-de    # apply scripts/_i18n_de_translations.py
    python scripts/update_catalog.py fill-en    # set msgstr = msgid for the English catalog
    python scripts/update_catalog.py compile    # compile de/en .po -> .mo
    python scripts/update_catalog.py check      # fail if the catalog is stale or incomplete
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALES = ROOT / "locales"
POT = LOCALES / "base.pot"
SOURCES = ["core/cli.py", "core/scan_reporting.py"]
KEYWORDS = ["-k", "_", "-k", "translate_func"]


def extract() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "babel.messages.frontend",
            "extract",
            "-F",
            "babel.cfg",
            *KEYWORDS,
            "-o",
            str(POT),
            "--no-location",
            "--sort-output",
            "--project=pbd-toolkit",
            *SOURCES,
        ],
        cwd=ROOT,
        check=True,
    )


def update() -> None:
    for lang in ("de", "en"):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "babel.messages.frontend",
                "update",
                "-i",
                str(POT),
                "-d",
                str(LOCALES),
                "-l",
                lang,
                "-D",
                "base",
            ],
            cwd=ROOT,
            check=True,
        )


def fill_de() -> None:
    from babel.messages.pofile import read_po, write_po

    sys.path.insert(0, str(ROOT / "scripts"))
    from _i18n_de_translations import DE_TRANSLATIONS

    po_path = LOCALES / "de" / "LC_MESSAGES" / "base.po"
    with open(po_path, "rb") as f:
        catalog = read_po(f, locale="de")

    missing = []
    for message in catalog:
        if not message.id or not isinstance(message.id, str):
            continue
        translation = DE_TRANSLATIONS.get(message.id)
        if translation is None:
            missing.append(message.id)
            continue
        message.string = translation
        message.flags.discard("fuzzy")

    if missing:
        print("Missing German translations for:", file=sys.stderr)
        for m in missing:
            print(f"  {m!r}", file=sys.stderr)
        sys.exit(1)

    with open(po_path, "wb") as f:
        write_po(f, catalog, sort_output=True)


def fill_en() -> None:
    from babel.messages.pofile import read_po, write_po

    po_path = LOCALES / "en" / "LC_MESSAGES" / "base.po"
    with open(po_path, "rb") as f:
        catalog = read_po(f, locale="en")

    for message in catalog:
        if not message.id:
            continue
        message.string = message.id
        message.flags.discard("fuzzy")

    with open(po_path, "wb") as f:
        write_po(f, catalog, sort_output=True)


def compile_catalogs() -> None:
    for lang in ("de", "en"):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "babel.messages.frontend",
                "compile",
                "-d",
                str(LOCALES),
                "-l",
                lang,
                "-D",
                "base",
            ],
            cwd=ROOT,
            check=True,
        )


def check() -> None:
    """CI drift gate: re-extract to a temp file and diff msgids against the
    committed catalog; fail if any de/en entry is fuzzy or untranslated."""
    import tempfile

    from babel.messages.pofile import read_po

    with tempfile.TemporaryDirectory() as tmp:
        tmp_pot = Path(tmp) / "base.pot"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "babel.messages.frontend",
                "extract",
                "-F",
                "babel.cfg",
                *KEYWORDS,
                "-o",
                str(tmp_pot),
                "--no-location",
                "--sort-output",
                "--omit-header",
                "--project=pbd-toolkit",
                *SOURCES,
            ],
            cwd=ROOT,
            check=True,
        )

        with open(POT, "rb") as f:
            committed_catalog = read_po(f)
        with open(tmp_pot, "rb") as f:
            fresh_catalog = read_po(f)

        committed_ids = {m.id for m in committed_catalog if m.id}
        fresh_ids = {m.id for m in fresh_catalog if m.id}
        if committed_ids != fresh_ids:
            missing = fresh_ids - committed_ids
            extra = committed_ids - fresh_ids
            if missing:
                print(
                    "New strings not yet extracted into locales/base.pot:",
                    file=sys.stderr,
                )
                for m in sorted(missing):
                    print(f"  + {m!r}", file=sys.stderr)
            if extra:
                print(
                    "Stale strings in locales/base.pot (no longer in source):",
                    file=sys.stderr,
                )
                for m in sorted(extra):
                    print(f"  - {m!r}", file=sys.stderr)
            sys.exit(1)

    for lang in ("de", "en"):
        po_path = LOCALES / lang / "LC_MESSAGES" / "base.po"
        with open(po_path, "rb") as f:
            catalog = read_po(f, locale=lang)
        bad = [m.id for m in catalog if m.id and (not m.string or "fuzzy" in m.flags)]
        if bad:
            print(f"Untranslated/fuzzy entries in {po_path}:", file=sys.stderr)
            for m in bad:
                print(f"  {m!r}", file=sys.stderr)
            sys.exit(1)

    print("i18n catalog check passed.")


COMMANDS = {
    "extract": extract,
    "update": update,
    "fill-de": fill_de,
    "fill-en": fill_en,
    "compile": compile_catalogs,
    "check": check,
}


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(2)
    COMMANDS[sys.argv[1]]()
