"""Edge-case tests for ``core.file_type_detector``.

``tests/test_file_type_detector.py`` covers construction, the disabled path and
the MIME→extension table for a handful of entries. This file exercises the
library-selection logic deterministically by faking ``magic`` / ``filetype`` in
``sys.modules``: python-magic present, absent, or broken; the filetype fallback;
detection errors; unknown bytes; mismatched extensions; and missing files.
"""

from __future__ import annotations

import logging
import os
import sys
import types

import pytest

from core.file_type_detector import FileTypeDetector

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\n"


# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------


def _fake_magic(
    mime_by_name: dict[str, str] | None = None,
    init_exc: Exception | None = None,
    from_file_exc: Exception | None = None,
):
    """Build a stand-in for the ``magic`` package with a recording ``Magic`` class."""
    mod = types.ModuleType("magic")
    calls: dict[str, list] = {"init": [], "from_file": []}

    class Magic:
        def __init__(self, mime=False):
            calls["init"].append(mime)
            if init_exc is not None:
                raise init_exc

        def from_file(self, path):
            calls["from_file"].append(path)
            if from_file_exc is not None:
                raise from_file_exc
            return (mime_by_name or {}).get(
                os.path.basename(path), "application/octet-stream"
            )

    mod.Magic = Magic
    mod.calls = calls
    return mod


def _fake_filetype(
    mime_by_name: dict[str, str] | None = None, guess_exc: Exception | None = None
):
    mod = types.ModuleType("filetype")
    calls: list[str] = []

    def guess(path):
        calls.append(path)
        if guess_exc is not None:
            raise guess_exc
        mime = (mime_by_name or {}).get(os.path.basename(path))
        return types.SimpleNamespace(mime=mime) if mime else None

    mod.guess = guess
    mod.calls = calls
    return mod


@pytest.fixture
def sample(tmp_path):
    p = tmp_path / "doc.pdf"
    p.write_bytes(PDF_BYTES)
    return str(p)


# ---------------------------------------------------------------------------
# library selection
# ---------------------------------------------------------------------------


class TestLibrarySelection:
    def test_magic_preferred_when_available(self, monkeypatch, sample):
        magic = _fake_magic({"doc.pdf": "application/pdf"})
        filetype = _fake_filetype({"doc.pdf": "application/x-should-not-be-used"})
        monkeypatch.setitem(sys.modules, "magic", magic)
        monkeypatch.setitem(sys.modules, "filetype", filetype)

        det = FileTypeDetector(enabled=True)

        assert det.is_available() is True
        assert magic.calls["init"] == [True]  # constructed with mime=True
        assert det._filetype is None  # fallback not even imported
        assert det.detect_type(sample) == "application/pdf"
        assert filetype.calls == []

    def test_magic_absent_falls_back_to_filetype(self, monkeypatch, sample):
        monkeypatch.setitem(sys.modules, "magic", None)  # -> ImportError
        filetype = _fake_filetype({"doc.pdf": "application/pdf"})
        monkeypatch.setitem(sys.modules, "filetype", filetype)

        det = FileTypeDetector(enabled=True)

        assert det._magic is None
        assert det.is_available() is True
        assert det.detect_type(sample) == "application/pdf"
        assert filetype.calls == [sample]

    def test_magic_init_failure_logs_warning_and_falls_back(
        self, monkeypatch, sample, caplog
    ):
        magic = _fake_magic(init_exc=OSError("libmagic.so not found"))
        monkeypatch.setitem(sys.modules, "magic", magic)
        monkeypatch.setitem(
            sys.modules, "filetype", _fake_filetype({"doc.pdf": "application/pdf"})
        )

        with caplog.at_level(logging.WARNING, logger="core.file_type_detector"):
            det = FileTypeDetector(enabled=True)

        assert det._magic is None
        assert det._filetype is not None
        assert any(
            "python-magic available but failed to initialize" in r.getMessage()
            and "libmagic.so not found" in r.getMessage()
            for r in caplog.records
        )
        assert det.detect_type(sample) == "application/pdf"

    def test_both_libraries_absent(self, monkeypatch, sample):
        monkeypatch.setitem(sys.modules, "magic", None)
        monkeypatch.setitem(sys.modules, "filetype", None)

        det = FileTypeDetector(enabled=True)

        assert det.enabled is True
        assert det.is_available() is False
        assert det.detect_type(sample) is None  # file exists, nothing to detect with

    def test_disabled_never_imports_libraries(self, monkeypatch, sample):
        magic = _fake_magic({"doc.pdf": "application/pdf"})
        monkeypatch.setitem(sys.modules, "magic", magic)

        det = FileTypeDetector(enabled=False)

        assert magic.calls["init"] == []
        assert det.is_available() is False
        assert det.detect_type(sample) is None


# ---------------------------------------------------------------------------
# detect_type behaviour
# ---------------------------------------------------------------------------


class TestDetectType:
    def test_magic_failure_falls_back_to_filetype(self, monkeypatch, sample, caplog):
        magic = _fake_magic(from_file_exc=RuntimeError("corrupt db"))
        monkeypatch.setitem(sys.modules, "magic", magic)
        # filetype is only imported when magic could not be initialised, so the
        # per-call fallback needs it injected after construction.
        det = FileTypeDetector(enabled=True)
        det._filetype = _fake_filetype({"doc.pdf": "application/pdf"})

        with caplog.at_level(logging.DEBUG, logger="core.file_type_detector"):
            assert det.detect_type(sample) == "application/pdf"

        assert magic.calls["from_file"] == [sample]
        assert any(
            "python-magic detection failed" in r.getMessage() for r in caplog.records
        )

    def test_magic_failure_without_fallback_returns_none(self, monkeypatch, sample):
        monkeypatch.setitem(
            sys.modules, "magic", _fake_magic(from_file_exc=ValueError("x"))
        )
        det = FileTypeDetector(enabled=True)
        assert det._filetype is None
        assert det.detect_type(sample) is None

    def test_filetype_guess_failure_returns_none(self, monkeypatch, sample, caplog):
        monkeypatch.setitem(sys.modules, "magic", None)
        monkeypatch.setitem(
            sys.modules, "filetype", _fake_filetype(guess_exc=OSError("read error"))
        )
        det = FileTypeDetector(enabled=True)

        with caplog.at_level(logging.DEBUG, logger="core.file_type_detector"):
            assert det.detect_type(sample) is None

        assert any(
            "filetype detection failed" in r.getMessage() for r in caplog.records
        )

    def test_unknown_bytes_return_none(self, monkeypatch, tmp_path):
        monkeypatch.setitem(sys.modules, "magic", None)
        monkeypatch.setitem(sys.modules, "filetype", _fake_filetype({}))
        unknown = tmp_path / "blob.bin"
        unknown.write_bytes(bytes(range(200, 256)))
        det = FileTypeDetector(enabled=True)

        assert det.detect_type(str(unknown)) is None

    def test_missing_file_short_circuits_before_detection(self, monkeypatch, tmp_path):
        magic = _fake_magic({"ghost.pdf": "application/pdf"})
        monkeypatch.setitem(sys.modules, "magic", magic)
        det = FileTypeDetector(enabled=True)

        assert det.detect_type(str(tmp_path / "ghost.pdf")) is None
        assert magic.calls["from_file"] == []

    def test_directory_is_reported_by_library_not_short_circuited(
        self, monkeypatch, tmp_path
    ):
        """os.path.exists() is true for directories, so the library gets asked."""
        magic = _fake_magic({tmp_path.name: "inode/directory"})
        monkeypatch.setitem(sys.modules, "magic", magic)
        det = FileTypeDetector(enabled=True)

        assert det.detect_type(str(tmp_path)) == "inode/directory"

    def test_mismatched_extension_is_exposed_via_mime(self, monkeypatch, tmp_path):
        monkeypatch.setitem(sys.modules, "magic", None)
        monkeypatch.setitem(
            sys.modules, "filetype", _fake_filetype({"notes.txt": "image/png"})
        )
        disguised = tmp_path / "notes.txt"
        disguised.write_bytes(PNG_BYTES)
        det = FileTypeDetector(enabled=True)

        mime = det.detect_type(str(disguised))
        assert mime == "image/png"
        assert det.get_extension_from_mime(mime) == ".png"
        assert det.get_extension_from_mime(mime) != os.path.splitext(disguised.name)[1]

    def test_empty_file_with_no_signature(self, monkeypatch, tmp_path):
        monkeypatch.setitem(sys.modules, "magic", None)
        monkeypatch.setitem(sys.modules, "filetype", _fake_filetype({}))
        empty = tmp_path / "empty"
        empty.write_bytes(b"")
        det = FileTypeDetector(enabled=True)

        assert det.detect_type(str(empty)) is None


# ---------------------------------------------------------------------------
# real libraries (skipped when not installed)
# ---------------------------------------------------------------------------


class TestWithRealLibraries:
    def test_real_python_magic_detects_pdf_header(self, tmp_path):
        pytest.importorskip("magic")
        det = FileTypeDetector(enabled=True)
        if det._magic is None:
            pytest.skip("python-magic importable but libmagic unavailable")
        pdf = tmp_path / "x.pdf"
        pdf.write_bytes(PDF_BYTES)

        assert det.detect_type(str(pdf)) == "application/pdf"

    def test_real_filetype_fallback_detects_pdf_and_png(self, tmp_path, monkeypatch):
        pytest.importorskip("filetype")
        monkeypatch.setitem(sys.modules, "magic", None)
        det = FileTypeDetector(enabled=True)
        assert det._magic is None and det._filetype is not None

        pdf = tmp_path / "x.pdf"
        pdf.write_bytes(PDF_BYTES)
        png_as_txt = tmp_path / "x.txt"
        png_as_txt.write_bytes(PNG_BYTES)
        text = tmp_path / "plain.txt"
        text.write_text("hello world\n", encoding="utf-8")

        assert det.detect_type(str(pdf)) == "application/pdf"
        assert det.detect_type(str(png_as_txt)) == "image/png"
        # Pure-Python filetype has no signature for plain text.
        assert det.detect_type(str(text)) is None


# ---------------------------------------------------------------------------
# MIME -> extension table
# ---------------------------------------------------------------------------


class TestExtensionMapping:
    @pytest.mark.parametrize(
        ("mime", "ext"),
        [
            ("application/vnd.oasis.opendocument.text", ".odt"),
            ("application/vnd.ms-excel", ".xls"),
            (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".xlsx",
            ),
            ("application/x-sqlite3", ".sqlite"),
            ("application/vnd.sqlite3", ".sqlite"),
            ("application/x-sqlite", ".sqlite"),
            ("text/vcard", ".vcf"),
            ("text/x-vcard", ".vcf"),
            ("text/directory", ".vcf"),
            ("text/calendar", ".ics"),
            ("text/x-markdown", ".md"),
            ("application/yaml", ".yaml"),
            ("text/yaml", ".yaml"),
            ("message/rfc822", ".eml"),
            ("application/vnd.ms-outlook", ".msg"),
            ("application/x-zip-compressed", ".zip"),
            ("image/webp", ".webp"),
        ],
    )
    def test_known_mime_types(self, mime, ext):
        assert FileTypeDetector(enabled=False).get_extension_from_mime(mime) == ext

    @pytest.mark.parametrize(
        "mime", ["", "application/octet-stream", "IMAGE/PNG", "png"]
    )
    def test_unknown_or_miscased_mime_returns_none(self, mime):
        assert FileTypeDetector(enabled=False).get_extension_from_mime(mime) is None
