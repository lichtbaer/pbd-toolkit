"""Tests for scripts/update_catalog.py, the i18n drift gate that CI runs.

The script's globals (ROOT, LOCALES, POT, SOURCES) are redirected to a tiny
throw-away project under ``tmp_path`` so the tests do not depend on the
repository's real catalog (whose extraction output differs between Python
versions) and cannot modify it.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

pytest.importorskip("babel")

uc = importlib.import_module("scripts.update_catalog")

_POT_HEADER = """\
msgid ""
msgstr ""
"Project-Id-Version: pbd-toolkit VERSION\\n"
"Content-Type: text/plain; charset=utf-8\\n"
"Content-Transfer-Encoding: 8bit\\n"

"""


def _write_po(path: Path, entries: dict[str, str], fuzzy: set[str] = frozenset()):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = _POT_HEADER
    for msgid, msgstr in entries.items():
        if msgid in fuzzy:
            body += "#, fuzzy\n"
        body += f'msgid "{msgid}"\nmsgstr "{msgstr}"\n\n'
    path.write_text(body, encoding="utf-8")


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A minimal project with one source file and matching de/en catalogs."""
    root = tmp_path / "proj"
    (root / "app").mkdir(parents=True)
    (root / "babel.cfg").write_text("[python: app/main.py]\n")
    source = root / "app" / "main.py"
    source.write_text('_("Hello")\ntranslate_func("Bye")\n')

    locales = root / "locales"
    _write_po(locales / "base.pot", {"Bye": "", "Hello": ""})
    _write_po(
        locales / "de" / "LC_MESSAGES" / "base.po", {"Bye": "Tschüss", "Hello": "Hallo"}
    )
    _write_po(
        locales / "en" / "LC_MESSAGES" / "base.po", {"Bye": "Bye", "Hello": "Hello"}
    )

    monkeypatch.setattr(uc, "ROOT", root)
    monkeypatch.setattr(uc, "LOCALES", locales)
    monkeypatch.setattr(uc, "POT", locales / "base.pot")
    monkeypatch.setattr(uc, "SOURCES", ["app/main.py"])
    return root


class TestCheck:
    def test_passes_when_catalog_matches_source(self, project, capsys):
        uc.check()
        assert "i18n catalog check passed" in capsys.readouterr().out

    def test_fails_on_new_string_in_source(self, project, capsys):
        (project / "app" / "main.py").write_text('_("Hello")\n_("Bye")\n_("New one")\n')
        with pytest.raises(SystemExit) as excinfo:
            uc.check()
        assert excinfo.value.code == 1
        err = capsys.readouterr().err
        assert "New strings not yet extracted" in err
        assert "'New one'" in err

    def test_fails_on_stale_string_in_catalog(self, project, capsys):
        (project / "app" / "main.py").write_text('_("Hello")\n')  # 'Bye' removed
        with pytest.raises(SystemExit):
            uc.check()
        err = capsys.readouterr().err
        assert "Stale strings" in err
        assert "'Bye'" in err

    def test_fails_on_untranslated_entry(self, project, capsys):
        _write_po(
            project / "locales" / "de" / "LC_MESSAGES" / "base.po",
            {"Bye": "", "Hello": "Hallo"},
        )
        with pytest.raises(SystemExit):
            uc.check()
        err = capsys.readouterr().err
        assert "Untranslated/fuzzy entries" in err
        assert "de" in err

    def test_fails_on_fuzzy_entry(self, project, capsys):
        _write_po(
            project / "locales" / "en" / "LC_MESSAGES" / "base.po",
            {"Bye": "Bye", "Hello": "Hello"},
            fuzzy={"Hello"},
        )
        with pytest.raises(SystemExit):
            uc.check()
        assert "Untranslated/fuzzy" in capsys.readouterr().err


class TestFillAndCompile:
    def test_fill_en_copies_msgid_and_clears_fuzzy(self, project):
        po = project / "locales" / "en" / "LC_MESSAGES" / "base.po"
        _write_po(po, {"Bye": "", "Hello": "old"}, fuzzy={"Hello"})
        uc.fill_en()
        from babel.messages.pofile import read_po

        with open(po, "rb") as f:
            catalog = read_po(f, locale="en")
        entries = {m.id: (m.string, "fuzzy" in m.flags) for m in catalog if m.id}
        assert entries == {"Bye": ("Bye", False), "Hello": ("Hello", False)}

    def test_fill_de_applies_table_and_reports_missing(
        self, project, monkeypatch, capsys
    ):
        scripts_dir = project / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "_i18n_de_translations.py").write_text(
            'DE_TRANSLATIONS = {"Hello": "Hallo!"}\n'
        )
        # fill_de imports the table from ROOT/scripts by inserting it on sys.path;
        # make sure the repository's own table is not picked up instead, and
        # restore sys.path afterwards so the temp dir does not leak into later tests.
        monkeypatch.setattr(sys, "path", list(sys.path))
        monkeypatch.delitem(sys.modules, "_i18n_de_translations", raising=False)
        with pytest.raises(SystemExit):
            uc.fill_de()  # 'Bye' has no translation in the table
        assert "'Bye'" in capsys.readouterr().err

        (scripts_dir / "_i18n_de_translations.py").write_text(
            'DE_TRANSLATIONS = {"Hello": "Hallo!", "Bye": "Ciao"}\n'
        )
        monkeypatch.delitem(sys.modules, "_i18n_de_translations", raising=False)
        uc.fill_de()
        text = (project / "locales" / "de" / "LC_MESSAGES" / "base.po").read_text()
        assert 'msgstr "Hallo!"' in text
        assert 'msgstr "Ciao"' in text

    def test_extract_update_compile_roundtrip(self, project):
        uc.extract()
        pot = (project / "locales" / "base.pot").read_text()
        assert 'msgid "Hello"' in pot and 'msgid "Bye"' in pot
        uc.update()
        uc.compile_catalogs()
        for lang in ("de", "en"):
            assert (project / "locales" / lang / "LC_MESSAGES" / "base.mo").exists()
        uc.check()
