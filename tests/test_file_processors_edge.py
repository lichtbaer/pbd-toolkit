"""Edge-case tests for ``file_processors``.

Complements ``tests/test_file_processors.py`` (which covers the happy paths) with
malformed, empty, oddly-encoded and limit-hitting inputs for the processors whose
coverage was lowest. Every fixture is built on the fly under ``tmp_path`` so the
tests stay deterministic and network-free.

Where a processor's current behaviour is questionable (e.g. dropped folded lines),
the test documents *current* behaviour and the docstring says so explicitly rather
than silently asserting the surprising result.
"""

import email
import logging
import os
import sqlite3
import struct
import sys
import types
import zipfile
from email.message import EmailMessage
from unittest.mock import patch

import pytest

from core import skip_counters
from file_processors import (
    EmlProcessor,
    FileProcessorRegistry,
    IcalProcessor,
    MsgProcessor,
    OdtProcessor,
    PdfProcessor,
    PropertiesProcessor,
    RtfProcessor,
    SqliteProcessor,
    VcfProcessor,
    YamlProcessor,
)
from file_processors.base_processor import (
    BaseFileProcessor,
    CorruptedFileError,
    FileProcessingError,
    PasswordProtectedError,
    UnsupportedFormatError,
    decode_with_fallback,
    read_text_with_fallback,
)

IBAN = "DE89 3704 0044 0532 0130 00"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _write(path, content, *, encoding="utf-8"):
    """Write *content* (str or bytes) to *path* and return the path as str."""
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding=encoding)
    return str(path)


def _pdf_string(text: str) -> str:
    """Escape a string for use inside a PDF literal ``( ... )``."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf(pages: list[str]) -> bytes:
    """Build a minimal, valid, uncompressed PDF with one Helvetica text page per entry.

    An empty string produces a page without any content stream text (a "scanned"
    page from pdfminer's point of view).
    """
    objs: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objs.append(
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("latin-1")
    )
    font_obj = 3 + 2 * len(pages)
    for i, text in enumerate(pages):
        page_obj = 3 + 2 * i
        content_obj = page_obj + 1
        objs.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 {font_obj} 0 R >> >> "
                f"/Contents {content_obj} 0 R >>"
            ).encode("latin-1")
        )
        if text:
            ops = " ".join(f"({_pdf_string(line)}) Tj T*" for line in text.split("\n"))
            stream = f"BT /F1 12 Tf 72 720 Td 14 TL {ops} ET"
        else:
            stream = ""
        objs.append(
            f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream".encode(
                "latin-1"
            )
        )
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = b"%PDF-1.4\n"
    offsets = []
    for number, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("latin-1") + obj + b"\nendobj\n"
    xref_offset = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode("latin-1")
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("latin-1")
    out += (
        f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("latin-1")
    return out


def _utf16(text: str) -> bytes:
    return text.encode("utf-16-le")


def _msg_prop(tag: int, ptype: int, value: bytes, flags: int = 6) -> bytes:
    """One 16-byte fixed-length entry of an MSG ``__properties_version1.0`` stream."""
    return struct.pack("<HHI", ptype, tag, flags) + value


def _msg_str_prop(tag: int, text: str) -> bytes:
    return _msg_prop(tag, 0x001F, struct.pack("<II", len(_utf16(text)) + 2, 0))


def _msg_bin_prop(tag: int, data: bytes) -> bytes:
    return _msg_prop(tag, 0x0102, struct.pack("<II", len(data), 0))


def _msg_int_prop(tag: int, value: int) -> bytes:
    return _msg_prop(tag, 0x0003, struct.pack("<II", value, 0))


def _build_msg(
    path,
    *,
    subject: str,
    body: str,
    sender_name: str | None = None,
    sender_email: str | None = None,
    html: bytes | None = None,
    recipients: list[tuple[str, str, int]] | None = None,
    attachments: list[tuple[str, str, str, bytes]] | None = None,
) -> str:
    """Write a genuine OLE2 ``.msg`` file with ``extract_msg.OleWriter``.

    ``recipients`` entries are ``(display_name, smtp_address, recipient_type)`` with
    type 1 = To, 2 = Cc, 3 = Bcc.  ``attachments`` entries are
    ``(long_filename, short_filename, display_name, data)``.
    """
    from extract_msg import OleWriter

    recipients = recipients or []
    attachments = attachments or []
    writer = OleWriter()

    header = (
        b"\x00" * 8
        + struct.pack(
            "<IIII",
            len(recipients),
            len(attachments),
            len(recipients),
            len(attachments),
        )
        + b"\x00" * 8
    )
    props = header + _msg_str_prop(0x0037, subject) + _msg_str_prop(0x1000, body)
    writer.addEntry("__substg1.0_0037001F", _utf16(subject))
    writer.addEntry("__substg1.0_1000001F", _utf16(body))
    if sender_name is not None:
        props += _msg_str_prop(0x0C1A, sender_name)
        writer.addEntry("__substg1.0_0C1A001F", _utf16(sender_name))
    if sender_email is not None:
        props += _msg_str_prop(0x5D01, sender_email)
        writer.addEntry("__substg1.0_5D01001F", _utf16(sender_email))
    if html is not None:
        props += _msg_bin_prop(0x1013, html)
        writer.addEntry("__substg1.0_10130102", html)
    writer.addEntry("__properties_version1.0", props)

    # Named-property streams must exist (even empty) for attachments to load.
    writer.addEntry("__nameid_version1.0", storage=True)
    for stream_id in ("00020102", "00030102", "00040102"):
        writer.addEntry(f"__nameid_version1.0/__substg1.0_{stream_id}", b"")

    for idx, (name, address, rtype) in enumerate(recipients):
        base = f"__recip_version1.0_#{idx:08X}"
        writer.addEntry(base, storage=True)
        rprops = (
            b"\x00" * 8
            + _msg_str_prop(0x3001, name)
            + _msg_str_prop(0x39FE, address)
            + _msg_int_prop(0x0C15, rtype)
            + _msg_int_prop(0x3000, idx)
        )
        writer.addEntry(f"{base}/__properties_version1.0", rprops)
        writer.addEntry(f"{base}/__substg1.0_3001001F", _utf16(name))
        writer.addEntry(f"{base}/__substg1.0_39FE001F", _utf16(address))
        writer.addEntry(f"{base}/__substg1.0_3003001F", _utf16(address))

    for idx, (long_name, short_name, display_name, data) in enumerate(attachments):
        base = f"__attach_version1.0_#{idx:08X}"
        writer.addEntry(base, storage=True)
        aprops = (
            b"\x00" * 8
            + _msg_str_prop(0x3707, long_name)
            + _msg_str_prop(0x3704, short_name)
            + _msg_str_prop(0x3001, display_name)
            + _msg_bin_prop(0x3701, data)
            + _msg_int_prop(0x3705, 1)
        )
        writer.addEntry(f"{base}/__properties_version1.0", aprops)
        writer.addEntry(f"{base}/__substg1.0_3707001F", _utf16(long_name))
        writer.addEntry(f"{base}/__substg1.0_3704001F", _utf16(short_name))
        writer.addEntry(f"{base}/__substg1.0_3001001F", _utf16(display_name))
        writer.addEntry(f"{base}/__substg1.0_37010102", data)

    writer.write(str(path))
    return str(path)


def _write_eml(path, message: EmailMessage) -> str:
    path.write_bytes(message.as_bytes())
    return str(path)


def _sqlite_bytes(tmp_path, statements: list[str]) -> bytes:
    """Return the raw bytes of a small SQLite database built from *statements*."""
    db_path = tmp_path / "_attachment_source.db"
    conn = sqlite3.connect(db_path)
    for statement in statements:
        conn.execute(statement)
    conn.commit()
    conn.close()
    return db_path.read_bytes()


@pytest.fixture
def drained_skips():
    """Clear thread-local skip counters before and after a test."""
    skip_counters.drain()
    yield
    skip_counters.drain()


# --------------------------------------------------------------------------- #
# base_processor
# --------------------------------------------------------------------------- #


class TestDecodeWithFallback:
    def test_utf8_first(self):
        assert decode_with_fallback("Grüße max@example.com".encode()) == (
            "Grüße max@example.com"
        )

    def test_bom_is_kept_because_plain_utf8_succeeds_first(self):
        """Current behaviour: ``utf-8`` precedes ``utf-8-sig`` in the chain, so a BOM
        decodes successfully as U+FEFF and is *not* stripped."""
        result = decode_with_fallback(b"\xef\xbb\xbfname=Max")
        assert result == "﻿name=Max"

    def test_cp1252_fallback_for_windows_bytes(self):
        # 0x80 is invalid UTF-8 but the Euro sign in cp1252.
        assert decode_with_fallback(b"Preis: 5 \x80") == "Preis: 5 €"

    def test_latin1_never_fails_with_default_chain(self):
        # Every byte value is valid latin-1, so the default chain cannot fail.
        result = decode_with_fallback(bytes(range(256)))
        assert len(result) == 256

    def test_all_encodings_fail_raises_last_error(self):
        with pytest.raises(UnicodeDecodeError) as exc_info:
            decode_with_fallback(b"\xff\xfe", encodings=("utf-8", "ascii"))
        # The error from the *last* attempted encoding is surfaced.
        assert exc_info.value.encoding == "ascii"

    def test_empty_encoding_chain(self):
        with pytest.raises(UnicodeDecodeError, match="no encodings provided"):
            decode_with_fallback(b"abc", encodings=())


class TestReadTextWithFallback:
    def test_reads_utf8_file(self, tmp_path):
        path = _write(tmp_path / "a.txt", "Kontakt: anna@example.com")
        assert read_text_with_fallback(path) == "Kontakt: anna@example.com"

    def test_reads_cp1252_file(self, tmp_path):
        path = _write(tmp_path / "w.txt", "Müller €".encode("cp1252"))
        assert read_text_with_fallback(path) == "Müller €"

    def test_all_fail_wraps_with_encoding_list(self, tmp_path):
        path = _write(tmp_path / "bad.txt", b"\xff\xfe\xfd")
        with pytest.raises(UnicodeDecodeError) as exc_info:
            read_text_with_fallback(path, encodings=("utf-8", "ascii"))
        assert "utf-8, ascii" in str(exc_info.value)
        assert exc_info.value.__cause__ is not None

    def test_empty_encoding_chain(self, tmp_path):
        path = _write(tmp_path / "x.txt", "abc")
        with pytest.raises(UnicodeDecodeError, match="no encodings provided"):
            read_text_with_fallback(path, encodings=())

    def test_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_text_with_fallback(str(tmp_path / "missing.txt"))


class TestErrorClassesAndBase:
    def test_error_attributes_and_hierarchy(self):
        cause = ValueError("boom")
        err = CorruptedFileError(
            "broken", file_path="/x.pdf", processor_name="Pdf", original_error=cause
        )
        assert str(err) == "broken"
        assert err.file_path == "/x.pdf"
        assert err.processor_name == "Pdf"
        assert err.original_error is cause
        assert isinstance(err, FileProcessingError)
        for cls in (CorruptedFileError, PasswordProtectedError, UnsupportedFormatError):
            assert issubclass(cls, FileProcessingError)
            assert issubclass(cls, Exception)

    def test_error_defaults(self):
        err = FileProcessingError("plain")
        assert err.file_path == ""
        assert err.processor_name == ""
        assert err.original_error is None

    def test_base_processor_is_abstract(self):
        with pytest.raises(TypeError):
            BaseFileProcessor()  # type: ignore[abstract]

    def test_default_can_process_is_false(self):
        class Dummy(BaseFileProcessor):
            def extract_text(self, file_path):
                return super().extract_text(file_path)

        dummy = Dummy()
        assert Dummy.can_process(".anything") is False
        assert dummy.can_process(".pdf", "/tmp/x.pdf", "application/pdf") is False
        # The abstract body is a bare ``pass`` -> returns None.
        assert dummy.extract_text("/nonexistent") is None


class TestRegistryLookups:
    @pytest.mark.parametrize(
        "extension, expected",
        [
            (".msg", MsgProcessor),
            (".ODT", OdtProcessor),
            (".sqlite3", SqliteProcessor),
            (".yml", YamlProcessor),
            (".env", PropertiesProcessor),
            (".vcf", VcfProcessor),
            (".ifb", IcalProcessor),
            (".rtf", RtfProcessor),
            (".pdf", PdfProcessor),
            (".eml", EmlProcessor),
        ],
    )
    def test_extension_routes_to_expected_processor(self, extension, expected):
        processor = FileProcessorRegistry.get_processor(extension)
        assert isinstance(processor, expected)

    def test_unknown_extension_has_no_processor(self, tmp_path):
        path = _write(tmp_path / "blob.xyz", b"\x00\x01")
        assert FileProcessorRegistry.get_processor(".xyz") is None
        assert (
            FileProcessorRegistry.get_processor(
                ".xyz", path, "application/octet-stream"
            )
            is None
        )

    def test_mime_type_lookup_for_sqlite(self, tmp_path):
        processor = FileProcessorRegistry.get_processor(
            "", str(tmp_path / "x"), "application/x-sqlite3"
        )
        assert isinstance(processor, SqliteProcessor)


# --------------------------------------------------------------------------- #
# msg_processor
# --------------------------------------------------------------------------- #


class _FakeAttachment:
    def __init__(self, longFilename=None, shortFilename=None, displayName=None):
        self.longFilename = longFilename
        self.shortFilename = shortFilename
        self.displayName = displayName


class _FakeMessage:
    """Stand-in for ``extract_msg.Message`` exposing arbitrary attributes."""

    def __init__(self, **attrs):
        self.closed = False
        for name, value in attrs.items():
            setattr(self, name, value)

    def close(self):
        self.closed = True


def _patch_extract_msg(mocker, message_factory):
    fake_module = types.SimpleNamespace(Message=message_factory)
    mocker.patch("file_processors.msg_processor.extract_msg", fake_module)
    return fake_module


class TestMsgProcessorEdge:
    def test_real_msg_file_headers_body_html_and_attachments(self, tmp_path):
        html = b"<html><body>HTML Teil &amp; secret@example.com</body></html>"
        csv = b"name,iban\nAnna,DE02120300000000202051\n"
        path = _build_msg(
            tmp_path / "real.msg",
            subject=f"Rechnung {IBAN}",
            body="Hallo Max Mustermann, Tel +49 30 1234567",
            sender_name="Erika Musterfrau",
            sender_email="erika@example.com",
            html=html,
            recipients=[
                ("Bob Empfaenger", "bob@example.com", 1),
                ("Carol Kopie", "carol@example.com", 2),
                ("Dave Blind", "dave@example.com", 3),
            ],
            attachments=[
                (
                    "kundenliste_2024.csv",
                    "KUNDEN~1.CSV",
                    "Kundenliste Anhang",
                    csv,
                )
            ],
        )

        text = MsgProcessor().extract_text(path)

        assert IBAN in text
        assert "Max Mustermann" in text and "+49 30 1234567" in text
        assert "Erika Musterfrau <erika@example.com>" in text
        assert "bob@example.com" in text
        assert "carol@example.com" in text
        assert "dave@example.com" in text
        # HTML body is tag-stripped and entity-decoded.
        assert "HTML Teil & secret@example.com" in text
        assert "<html>" not in text
        # Attachment metadata: long filename wins over the 8.3 short name.
        assert "kundenliste_2024.csv" in text
        assert "Kundenliste Anhang" in text
        assert "KUNDEN~1.CSV" not in text
        # Attachment *content* is deliberately not extracted (metadata only).
        assert "DE02120300000000202051" not in text

    def test_real_msg_without_html_stream_uses_generated_html(self, tmp_path):
        """extract-msg synthesises an HTML body from the plain body when none is
        stored, so the body text appears twice; the processor tolerates that."""
        path = _build_msg(
            tmp_path / "plain.msg", subject="Nur Text", body="IBAN " + IBAN
        )
        text = MsgProcessor().extract_text(path)
        assert "Nur Text" in text
        assert text.count(IBAN) == 2

    def test_fake_message_covers_list_headers_str_html_and_short_filename(self, mocker):
        fake = _FakeMessage(
            to=["first@example.com", None, "second@example.com"],
            cc="cc@example.com",
            bcc="",
            subject="Betreff",
            body="  Körper mit +49 170 1234567  ",
            htmlBody="<p>Hallo&nbsp;&lt;Welt&gt; &quot;Zitat&quot; &apos;x&apos;</p>",
            attachments=[
                _FakeAttachment(shortFilename="KURZ.PDF"),
                _FakeAttachment(longFilename="", displayName="Nur Anzeige"),
                _FakeAttachment(),
            ],
            senderEmail="sender@example.com",
            sentRepresentingEmailAddress="rep@example.com",
            **{"from": "from@example.com"},
        )
        _patch_extract_msg(mocker, lambda path: fake)

        text = MsgProcessor().extract_text("ignored.msg")

        assert "from@example.com" in text
        assert "first@example.com" in text and "second@example.com" in text
        assert "None" not in text  # falsy list entries are dropped
        assert "cc@example.com" in text
        assert "Körper mit +49 170 1234567" in text
        assert "Hallo <Welt> \"Zitat\" 'x'" in text
        assert "KURZ.PDF" in text
        assert "Nur Anzeige" in text
        assert "sender@example.com" in text and "rep@example.com" in text
        assert fake.closed is True

    def test_fake_message_with_only_whitespace_bodies_yields_no_body(self, mocker):
        fake = _FakeMessage(subject="S", body="   \n", htmlBody=b"<div>  </div>")
        _patch_extract_msg(mocker, lambda path: fake)
        assert MsgProcessor().extract_text("x.msg") == "S"

    def test_html_helper_handles_empty(self):
        assert MsgProcessor()._extract_text_from_html("") == ""

    def test_corrupt_msg_is_wrapped(self, tmp_path):
        path = _write(tmp_path / "bad.msg", b"definitely not an OLE2 container")
        with pytest.raises(Exception, match="Error processing MSG file") as exc_info:
            MsgProcessor().extract_text(path)
        assert exc_info.value.__cause__ is not None

    def test_empty_msg_is_wrapped(self, tmp_path):
        path = _write(tmp_path / "empty.msg", b"")
        with pytest.raises(Exception, match="Error processing MSG file"):
            MsgProcessor().extract_text(path)

    def test_import_error_when_library_missing(self, mocker, tmp_path):
        mocker.patch("file_processors.msg_processor.extract_msg", None)
        with pytest.raises(ImportError, match="extract-msg is required"):
            MsgProcessor().extract_text(str(tmp_path / "x.msg"))

    def test_permission_error_propagates_unwrapped(self, mocker):
        def raise_permission(path):
            raise PermissionError("denied")

        _patch_extract_msg(mocker, raise_permission)
        with pytest.raises(PermissionError):
            MsgProcessor().extract_text("x.msg")

    def test_import_error_from_library_propagates_unwrapped(self, mocker):
        def raise_import(path):
            raise ImportError("missing native dep")

        _patch_extract_msg(mocker, raise_import)
        with pytest.raises(ImportError, match="missing native dep"):
            MsgProcessor().extract_text("x.msg")

    def test_can_process_rejects_other_extensions(self):
        assert not MsgProcessor.can_process(".eml")
        assert not MsgProcessor.can_process("")


# --------------------------------------------------------------------------- #
# odt_processor
# --------------------------------------------------------------------------- #


class TestOdtProcessorEdge:
    @staticmethod
    def _build_doc():
        from odf.opendocument import OpenDocumentText
        from odf.table import Table, TableCell, TableRow
        from odf.text import H, P, Span

        doc = OpenDocumentText()
        heading = H(outlinelevel=1, text="Vertrag mit Max Mustermann")
        doc.text.addElement(heading)
        para = P(text="Kontakt: ")
        para.addElement(Span(text="max@example.com"))
        para.addElement(Span(text=" Tel +49 30 1234567"))
        doc.text.addElement(para)
        doc.text.addElement(P(text="   "))  # whitespace-only paragraph is dropped

        table = Table(name="Konten")
        for name, iban in (("Anna", IBAN), ("Bernd", "")):
            row = TableRow()
            for value in (name, iban):
                cell = TableCell()
                cell.addElement(P(text=value))
                row.addElement(cell)
            table.addElement(row)
        doc.text.addElement(table)
        return doc

    def test_headings_spans_and_tables(self, tmp_path):
        path = tmp_path / "rich.odt"
        self._build_doc().save(str(path))

        text = OdtProcessor().extract_text(str(path))

        assert "Vertrag mit Max Mustermann" in text
        # Each span is joined with a separator, so normalise runs of whitespace.
        normalised = " ".join(text.split())
        assert "Kontakt: max@example.com Tel +49 30 1234567" in normalised
        assert "Anna" in text and IBAN in text and "Bernd" in text
        # Table cell paragraphs are also matched as P -> appear twice; headings once.
        assert text.count("Vertrag mit Max Mustermann") == 1
        assert text.count(IBAN) == 2

    def test_empty_document_yields_empty_string(self, tmp_path):
        from odf.opendocument import OpenDocumentText

        path = tmp_path / "empty.odt"
        OpenDocumentText().save(str(path))
        assert OdtProcessor().extract_text(str(path)) == ""

    def test_corrupt_file_is_wrapped(self, tmp_path):
        path = _write(tmp_path / "bad.odt", b"not a zip archive")
        with pytest.raises(Exception, match="Error processing ODT file") as exc_info:
            OdtProcessor().extract_text(path)
        assert isinstance(exc_info.value.__cause__, zipfile.BadZipFile)

    def test_zip_without_odf_content_is_wrapped(self, tmp_path):
        path = tmp_path / "fake.odt"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("hello.txt", "no content.xml here")
        with pytest.raises(Exception, match="Error processing ODT file"):
            OdtProcessor().extract_text(str(path))

    def test_element_helper_reads_text_nodes_and_ignores_foreign_objects(self):
        from odf.element import Text

        processor = OdtProcessor()
        assert processor._extract_text_from_element(Text("direkt")) == "direkt"
        # Objects with neither ``data`` nor ``childNodes`` contribute nothing.
        assert processor._extract_text_from_element(object()) == ""

        class Node:
            data = None
            childNodes = [Text("a"), object(), Text("")]

        assert processor._extract_text_from_element(Node()) == "a"

    def test_missing_file_propagates_unwrapped(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            OdtProcessor().extract_text(str(tmp_path / "missing.odt"))

    def test_import_error_when_odfpy_missing(self, mocker, tmp_path):
        mocker.patch("file_processors.odt_processor.load", None)
        with pytest.raises(ImportError, match="odfpy is required"):
            OdtProcessor().extract_text(str(tmp_path / "x.odt"))


# --------------------------------------------------------------------------- #
# sqlite_processor
# --------------------------------------------------------------------------- #


class TestSqliteProcessorEdge:
    @staticmethod
    def _db(tmp_path, name, statements):
        path = tmp_path / name
        conn = sqlite3.connect(path)
        for statement in statements:
            conn.execute(statement)
        conn.commit()
        conn.close()
        return str(path)

    def test_multiple_tables_column_types_and_nulls(self, tmp_path):
        path = self._db(
            tmp_path,
            "multi.db",
            [
                'CREATE TABLE "my table" (name TEXT)',
                "INSERT INTO \"my table\" VALUES ('skipped@example.com')",
                "CREATE TABLE users (id INTEGER, name TEXT, email VARCHAR(100), "
                'age REAL, note, "odd-col" TEXT, active BOOLEAN)',
                "INSERT INTO users VALUES (1, 'Max', 'max@example.com', 42.0, "
                "'untyped note', 'oddcol@example.com', 1)",
                "INSERT INTO users VALUES (2, NULL, NULL, NULL, NULL, NULL, NULL)",
                "CREATE TABLE numbers (id INTEGER, amount REAL)",
                "INSERT INTO numbers VALUES (7, 2.5)",
                "CREATE TABLE empty_table (name TEXT)",
                "CREATE TABLE zweite (mail CHAR(50))",
                "INSERT INTO zweite VALUES ('zweite@example.com')",
                "CREATE VIEW v AS SELECT name FROM users",
            ],
        )

        chunks = list(SqliteProcessor().extract_text(path))
        text = "".join(chunks)

        assert "[Table: users]\nMax | max@example.com | untyped note\n" in chunks
        assert "[Table: zweite]\nzweite@example.com\n" in chunks
        # Table with a space in its name and hyphenated column are skipped.
        assert "skipped@example.com" not in text
        assert "oddcol@example.com" not in text
        # Numeric / boolean columns and NULL-only rows are not emitted.
        assert "42" not in text and "2.5" not in text and "numbers" not in text
        assert len([c for c in chunks if "[Table: users]" in c]) == 1
        assert "empty_table" not in text

    def test_blobs_decoded_utf8_then_latin1(self, tmp_path):
        path = self._db(tmp_path, "blob.db", ["CREATE TABLE b (payload BLOB)"])
        conn = sqlite3.connect(path)
        conn.execute("INSERT INTO b VALUES (?)", ("Grüße blob@example.com".encode(),))
        conn.execute("INSERT INTO b VALUES (?)", ("Müller".encode("latin-1"),))
        conn.execute("INSERT INTO b VALUES (?)", (b"",))
        conn.commit()
        conn.close()

        chunks = list(SqliteProcessor().extract_text(path))
        assert "[Table: b]\nGrüße blob@example.com\n" in chunks
        assert "[Table: b]\nMüller\n" in chunks
        # Current behaviour: an empty (but non-NULL) BLOB still yields a chunk
        # with an empty row, because "" is appended to the row parts.
        assert "[Table: b]\n\n" in chunks
        assert len(chunks) == 3

    def test_empty_database_file(self, tmp_path):
        path = _write(tmp_path / "empty.db", b"")
        assert list(SqliteProcessor().extract_text(path)) == []

    def test_schema_only_database(self, tmp_path):
        path = self._db(tmp_path, "schema.db", ["CREATE TABLE t (x TEXT)"])
        assert list(SqliteProcessor().extract_text(path)) == []

    @pytest.mark.parametrize(
        "content",
        [b"SQLite format 3\x00" + b"garbage" * 100, b"plain text, not a database"],
    )
    def test_corrupt_file_raises_sqlite_error(self, tmp_path, content):
        path = _write(tmp_path / "bad.db", content)
        with pytest.raises(sqlite3.DatabaseError):
            list(SqliteProcessor().extract_text(path))

    def test_missing_file_raises(self, tmp_path):
        # sqlite3.connect creates missing files, so a missing *directory* is used.
        with pytest.raises(sqlite3.OperationalError):
            list(SqliteProcessor().extract_text(str(tmp_path / "nope" / "x.db")))

    def test_unreadable_table_is_skipped_and_counted(self, tmp_path, drained_skips):
        """A table whose schema references a missing virtual-table module raises a
        sqlite3 error on PRAGMA; the processor skips it and records the skip."""
        path = self._db(
            tmp_path,
            "ghost.db",
            [
                "PRAGMA writable_schema=ON",
                "INSERT INTO sqlite_master(type,name,tbl_name,rootpage,sql) VALUES("
                "'table','ghost','ghost',0,'CREATE VIRTUAL TABLE ghost USING nomod')",
                "CREATE TABLE real_t (name TEXT)",
                "INSERT INTO real_t VALUES ('real@example.com')",
            ],
        )
        chunks = list(SqliteProcessor().extract_text(path))
        assert chunks == ["[Table: real_t]\nreal@example.com\n"]
        assert skip_counters.drain() == {"sqlite_table_read_error": 1}

    def test_can_process_by_header_mime_and_failures(self, tmp_path):
        real = self._db(tmp_path, "h.db", ["CREATE TABLE t (x TEXT)"])
        text = _write(tmp_path / "t.dat", "not a database")
        assert SqliteProcessor.can_process("", real)
        assert not SqliteProcessor.can_process("", text)
        assert not SqliteProcessor.can_process("", str(tmp_path / "missing"))
        assert not SqliteProcessor.can_process("", str(tmp_path))  # directory
        assert SqliteProcessor.can_process("", "", "application/vnd.sqlite3")
        assert not SqliteProcessor.can_process(".dat", real, "text/plain")
        assert not SqliteProcessor.can_process("")


# --------------------------------------------------------------------------- #
# yaml_processor
# --------------------------------------------------------------------------- #


class TestYamlProcessorEdge:
    def test_anchors_merge_keys_and_mixed_scalars(self, tmp_path):
        path = _write(
            tmp_path / "anchors.yaml",
            "base: &b\n"
            "  email: anchor@example.com\n"
            "derived:\n"
            "  <<: *b\n"
            "  name: Erika\n"
            "list:\n"
            "  - 1\n"
            "  - true\n"
            "  - null\n"
            "  - '   '\n"
            "  - nested: {iban: '" + IBAN + "'}\n"
            "3: numeric key value\n",
        )
        text = YamlProcessor().extract_text(path)
        parts = text.split(" ")
        assert "anchor@example.com" in text
        assert text.count("anchor@example.com") == 2  # merged into ``derived``
        assert "Erika" in text and IBAN in text
        assert "numeric key value" in text
        assert "3" not in parts  # non-string keys are ignored
        assert "True" not in parts and "None" not in parts and "1" not in parts

    def test_top_level_scalar_and_list(self, tmp_path):
        scalar = _write(tmp_path / "scalar.yml", "just text with mail@example.com\n")
        assert YamlProcessor().extract_text(scalar) == "just text with mail@example.com"
        listing = _write(
            tmp_path / "list.yml", "- a@example.com\n- 2\n- b@example.com\n"
        )
        assert YamlProcessor().extract_text(listing) == "a@example.com b@example.com"

    def test_empty_and_comment_only_files(self, tmp_path):
        assert YamlProcessor().extract_text(_write(tmp_path / "e.yaml", "")) == ""
        assert (
            YamlProcessor().extract_text(_write(tmp_path / "c.yaml", "# nur Kommentar"))
            == ""
        )

    def test_invalid_yaml_falls_back_to_quoted_strings_only(self, tmp_path):
        """Current behaviour: the regex fallback only recovers *quoted* values, so an
        unquoted e-mail on a valid line of a broken file is lost."""
        path = _write(
            tmp_path / "bad.yaml",
            "key: [unclosed\n"
            'name: "Max Mustermann"\n'
            "mail: 'max@example.com'\n"
            "lost: unquoted@example.com\n",
        )
        text = YamlProcessor().extract_text(path)
        assert "Max Mustermann" in text
        assert "max@example.com" in text
        assert "unquoted@example.com" not in text

    def test_invalid_utf8_bytes_are_replaced(self, tmp_path):
        path = _write(
            tmp_path / "bin.yaml", b"name: \xff\xfe Max\nmail: m@example.com\n"
        )
        text = YamlProcessor().extract_text(path)
        assert "m@example.com" in text
        assert "�" in text

    def test_directory_is_wrapped(self, tmp_path):
        with pytest.raises(Exception, match="Error processing YAML file"):
            YamlProcessor().extract_text(str(tmp_path))

    def test_missing_file_propagates_unwrapped(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            YamlProcessor().extract_text(str(tmp_path / "missing.yaml"))

    def test_import_error_when_pyyaml_missing(self, mocker, tmp_path):
        mocker.patch("file_processors.yaml_processor.yaml", None)
        with pytest.raises(ImportError, match="PyYAML is required"):
            YamlProcessor().extract_text(str(tmp_path / "x.yaml"))

    def test_can_process(self):
        assert YamlProcessor.can_process(".YML")
        assert not YamlProcessor.can_process(".json")


# --------------------------------------------------------------------------- #
# properties_processor
# --------------------------------------------------------------------------- #


class TestPropertiesProcessorEdge:
    def test_properties_comments_separators_and_current_limitations(self, tmp_path):
        """Documents current behaviour: ``\\uXXXX`` escapes are *not* decoded and a
        backslash line continuation loses the continued part."""
        path = _write(
            tmp_path / "app.properties",
            "# comment with hidden@example.com\n"
            "! bang comment\n"
            "db.user = admin\n"
            "db.pass:s3cret\n"
            "name=Jos\\u00e9\n"
            "long.value=first part \\\n"
            "    second-part@example.com\n"
            "novalue\n"
            "\n"
            "url=http://host:8080/a=b\n",
        )
        text = PropertiesProcessor().extract_text(path)
        lines = text.split("\n")
        assert "db.user = admin" in lines
        assert "db.pass = s3cret" in lines
        assert "url = http://host:8080/a=b" in lines
        assert "hidden@example.com" not in text
        assert "novalue" not in text
        assert "name = Jos\\u00e9" in lines  # not decoded to "José"
        assert "second-part@example.com" not in text  # continuation dropped
        assert "long.value = first part \\" in lines

    def test_ini_with_sections_and_colon_separator(self, tmp_path):
        path = _write(
            tmp_path / "app.ini",
            "[database]\nUser = Admin\npassword: geheim\n\n[mail]\nto = ops@example.com\n",
        )
        text = PropertiesProcessor().extract_text(path)
        # configparser lower-cases option names and preserves section headers.
        assert text == (
            "[database]\nuser = Admin\npassword = geheim\n[mail]\nto = ops@example.com"
        )

    def test_ini_with_duplicate_option_falls_back_to_plain_parsing(self, tmp_path):
        path = _write(tmp_path / "dup.ini", "[db]\nuser=admin\nuser=dup@example.com\n")
        text = PropertiesProcessor().extract_text(path)
        assert text == "user = admin\nuser = dup@example.com"

    def test_ini_with_percent_sign_falls_back_to_plain_parsing(self, tmp_path):
        # ``%`` triggers configparser interpolation errors -> fallback keeps value.
        path = _write(tmp_path / "pct.ini", "[db]\npassword=abc%def\n")
        assert PropertiesProcessor().extract_text(path) == "password = abc%def"

    def test_ini_with_bare_line_falls_back_and_drops_section(self, tmp_path):
        path = _write(tmp_path / "mixed.ini", "[Section]\nFoo=Bar\nbare_line\n")
        assert PropertiesProcessor().extract_text(path) == "Foo = Bar"

    def test_empty_file(self, tmp_path):
        assert PropertiesProcessor().extract_text(_write(tmp_path / "e.ini", "")) == ""

    def test_invalid_utf8_is_replaced_not_raised(self, tmp_path):
        path = _write(tmp_path / "bin.properties", b"key=\xff\xfe value@example.com\n")
        text = PropertiesProcessor().extract_text(path)
        assert "value@example.com" in text
        assert "�" in text

    def test_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            PropertiesProcessor().extract_text(str(tmp_path / "missing.ini"))

    def test_can_process_extensions_and_mime(self):
        for ext in (".properties", ".INI", ".cfg", ".conf", ".env"):
            assert PropertiesProcessor.can_process(ext)
        assert PropertiesProcessor.can_process("", "", "text/x-properties")
        assert PropertiesProcessor.can_process("", "", "text/plain")
        assert not PropertiesProcessor.can_process("", "", "application/json")
        assert not PropertiesProcessor.can_process(".txt")


# --------------------------------------------------------------------------- #
# vcf_processor
# --------------------------------------------------------------------------- #


class TestVcfProcessorEdge:
    def test_multiple_cards_params_escapes_and_current_limitations(self, tmp_path):
        """Documents current behaviour for three known weaknesses: RFC 6350 folded
        continuation lines (leading space, no colon) are dropped, quoted-printable
        values are not decoded, and ``URL:`` loses its scheme because the value is
        taken after the *last* colon."""
        path = _write(
            tmp_path / "contacts.vcf",
            "BEGIN:VCARD\n"
            "VERSION:3.0\n"
            "N:Mustermann;Max;;Dr.;\n"
            "FN:Max Mustermann\n"
            "TEL;TYPE=CELL:+49 170 1234567\n"
            "URL:https://example.com/max\n"
            "NOTE:Zeile 1\\nZeile 2\\, Komma \\\\ Backslash\n"
            "ADR;TYPE=HOME:;;Hauptstr. 1;Berlin;;10115;DE\n"
            "EMAIL:max@example.com\n"
            "X-LONG:erste Haelfte\n"
            " folded@example.com\n"
            "NOTE;ENCODING=QUOTED-PRINTABLE:M=C3=BCller\n"
            "END:VCARD\n"
            "\n"
            "BEGIN:VCARD\n"
            "FN:Erika Musterfrau\n"
            "EMAIL:erika@example.com\n"
            "END:VCARD\n",
        )
        text = VcfProcessor().extract_text(path)
        lines = text.split("\n")

        assert "Max Mustermann" in lines
        assert "Mustermann;Max;;Dr.;" in lines
        assert "+49 170 1234567" in lines
        assert ";;Hauptstr. 1;Berlin;;10115;DE" in lines
        assert "max@example.com" in lines and "erika@example.com" in lines
        assert "Erika Musterfrau" in lines
        # Escapes are unfolded.
        assert "Zeile 1" in lines and "Zeile 2, Komma \\ Backslash" in lines
        # BEGIN/END markers and property names never leak into the output.
        assert "VCARD" not in text and "EMAIL" not in text
        # Known limitations (current behaviour):
        assert "folded@example.com" not in text
        assert "M=C3=BCller" in lines and "Müller" not in text
        assert "//example.com/max" in lines and "https://example.com/max" not in text

    def test_missing_end_marker_still_extracts(self, tmp_path):
        path = _write(
            tmp_path / "trunc.vcf", "BEGIN:VCARD\nFN:Ohne Ende\nTEL:+49 30 1\n"
        )
        assert VcfProcessor().extract_text(path) == "Ohne Ende\n+49 30 1"

    def test_empty_and_marker_only_files(self, tmp_path):
        assert VcfProcessor().extract_text(_write(tmp_path / "e.vcf", "")) == ""
        marker_only = _write(tmp_path / "m.vcf", "BEGIN:VCARD\nEND:VCARD\n")
        assert VcfProcessor().extract_text(marker_only) == ""

    def test_invalid_utf8_is_replaced(self, tmp_path):
        path = _write(tmp_path / "bin.vcf", b"BEGIN:VCARD\nFN:M\xfcller\nEND:VCARD\n")
        assert VcfProcessor().extract_text(path) == "M�ller"

    def test_can_process_sniffs_content_only_without_extension(self, tmp_path):
        vcard = _write(tmp_path / "noext", "BEGIN:VCARD\nFN:X\nEND:VCARD\n")
        other = _write(tmp_path / "other", "hello")
        assert VcfProcessor.can_process("", vcard)
        assert not VcfProcessor.can_process("", other)
        assert not VcfProcessor.can_process(".txt", vcard)  # only sniffed when ext==""
        assert not VcfProcessor.can_process("", str(tmp_path / "missing"))
        assert not VcfProcessor.can_process("", str(tmp_path))  # directory -> OSError
        assert VcfProcessor.can_process("", "", "text/x-vcard")
        assert not VcfProcessor.can_process("", vcard, "text/plain")


# --------------------------------------------------------------------------- #
# ical_processor
# --------------------------------------------------------------------------- #


class TestIcalProcessorEdge:
    def test_multiple_events_escapes_and_current_limitations(self, tmp_path):
        """Documents current behaviour: properties carrying parameters
        (``ORGANIZER;CN=...:``) are not matched by the ``PROP:`` prefix test and are
        dropped entirely, and RFC 5545 folded lines (leading space) are lost."""
        path = _write(
            tmp_path / "cal.ics",
            "BEGIN:VCALENDAR\n"
            "BEGIN:VEVENT\n"
            "UID:evt-1@example.com\n"
            "summary:Jour fixe mit Max Mustermann\n"
            "ORGANIZER;CN=Erika Musterfrau:mailto:erika@example.com\n"
            "ATTENDEE;CN=Bob;RSVP=TRUE:mailto:bob@example.com\n"
            "ATTENDEE:mailto:plain@example.com\n"
            "DESCRIPTION:Erste Zeile\\nZweite Zeile\\, mit Komma \\\\ Ende\n"
            "COMMENT:Lange Beschreibung\n"
            " folded@example.com\n"
            "DTSTART:20240101T100000Z\n"
            "END:VEVENT\n"
            "BEGIN:VEVENT\n"
            "SUMMARY:Zweiter Termin\n"
            "LOCATION:Berlin,\n"
            "Hauptstr. 1\n"
            "CONTACT:Jim Dolittle;ext=123;jim@example.com\n"
            "RESOURCES:Beamer;Room=B12\n"
            "URL:http://example.com/a;b\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n",
        )
        text = IcalProcessor().extract_text(path)
        lines = text.split("\n")

        assert "UID: evt-1@example.com" in lines
        assert "SUMMARY: Jour fixe mit Max Mustermann" in lines  # case-insensitive
        assert "ATTENDEE: mailto:plain@example.com" in lines
        assert "DESCRIPTION: Erste Zeile" in lines
        assert "Zweite Zeile, mit Komma \\ Ende" in lines
        assert "SUMMARY: Zweiter Termin" in lines
        # Trailing comma joins the following line (processor-specific continuation).
        assert "LOCATION: BerlinHauptstr. 1" in lines
        # ';'-separated values: the last part containing '@' or '=' wins.
        assert "CONTACT: jim@example.com" in lines
        assert "RESOURCES: Room=B12" in lines
        assert "URL: http://example.com/a;b" in lines
        assert "DTSTART" not in text
        # Known limitations (current behaviour):
        assert "erika@example.com" not in text
        assert "bob@example.com" not in text
        assert "folded@example.com" not in text

    def test_empty_and_irrelevant_files(self, tmp_path):
        assert IcalProcessor().extract_text(_write(tmp_path / "e.ics", "")) == ""
        only_dates = _write(
            tmp_path / "d.ics", "BEGIN:VCALENDAR\nDTSTART:20240101\nEND:VCALENDAR\n"
        )
        assert IcalProcessor().extract_text(only_dates) == ""

    def test_invalid_utf8_is_replaced(self, tmp_path):
        path = _write(tmp_path / "bin.ics", b"SUMMARY:M\xfcller\n")
        assert IcalProcessor().extract_text(path) == "SUMMARY: M�ller"

    def test_can_process_sniffs_content_and_mime(self, tmp_path):
        ical = _write(tmp_path / "noext", "BEGIN:VCALENDAR\nEND:VCALENDAR\n")
        other = _write(tmp_path / "other.dat", "BEGIN:VCARD\n")
        assert IcalProcessor.can_process("", ical)
        assert IcalProcessor.can_process(".dat", ical)  # sniffed for any extension
        assert not IcalProcessor.can_process(".dat", other)
        assert not IcalProcessor.can_process("", str(tmp_path / "missing"))
        assert not IcalProcessor.can_process("", str(tmp_path))  # directory
        assert IcalProcessor.can_process("", "", "text/calendar")
        assert not IcalProcessor.can_process("", ical, "text/plain")
        assert not IcalProcessor.can_process("")


# --------------------------------------------------------------------------- #
# rtf_processor
# --------------------------------------------------------------------------- #


class TestRtfProcessorEdge:
    def test_hex_and_unicode_escapes_are_decoded(self, tmp_path):
        euro = "\\" + "u8364?"  # RTF unicode escape for the Euro sign
        rtf = (
            "{\\rtf1\\ansi\\ansicpg1252 Name: M\\'fcller, "
            + euro
            + " 50, mail max@example.com\\par IBAN "
            + IBAN
            + "}"
        )
        path = _write(tmp_path / "t.rtf", rtf, encoding="ascii")
        text = RtfProcessor().extract_text(path)
        assert "Name: Müller, € 50, mail max@example.com" in text
        assert IBAN in text
        assert "\\par" not in text and "rtf1" not in text

    def test_plain_text_without_rtf_header_passes_through(self, tmp_path):
        path = _write(tmp_path / "plain.rtf", "just text with mail@example.com")
        assert RtfProcessor().extract_text(path) == "just text with mail@example.com"

    def test_empty_file(self, tmp_path):
        assert RtfProcessor().extract_text(_write(tmp_path / "e.rtf", "")) == ""

    def test_invalid_utf8_bytes_are_replaced_not_retried(self, tmp_path):
        """``errors="replace"`` means the UnicodeDecodeError retry chain is never
        exercised: the first (utf-8) attempt always succeeds with U+FFFD."""
        path = _write(tmp_path / "bin.rtf", b"{\\rtf1 \xff\xfe text@example.com}")
        text = RtfProcessor().extract_text(path)
        assert "text@example.com" in text
        assert "�" in text

    def test_retry_chain_falls_back_when_first_encoding_fails(self, tmp_path):
        """The utf-8 -> latin-1 retry is unreachable with real files (see above), so
        ``open`` is wrapped to fail once with a UnicodeDecodeError."""
        path = _write(tmp_path / "retry.rtf", "{\\rtf1 retry@example.com}")
        real_open = open
        attempts: list[str] = []

        def flaky_open(file, *args, **kwargs):
            attempts.append(kwargs.get("encoding"))
            if len(attempts) == 1:
                raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
            return real_open(file, *args, **kwargs)

        with patch("builtins.open", side_effect=flaky_open):
            text = RtfProcessor().extract_text(path)
        assert text == "retry@example.com"
        assert attempts == ["utf-8", "latin-1"]

    def test_retry_chain_raises_last_error_when_all_encodings_fail(self, tmp_path):
        path = _write(tmp_path / "fail.rtf", "{\\rtf1 x}")

        def always_fail(file, *args, **kwargs):
            enc = kwargs.get("encoding", "?")
            raise UnicodeDecodeError(enc, b"\xff", 0, 1, "nope")

        with patch("builtins.open", side_effect=always_fail):
            with pytest.raises(UnicodeDecodeError) as exc_info:
                RtfProcessor().extract_text(path)
        # The error of the *last* encoding in the chain is surfaced.
        assert exc_info.value.encoding == "iso-8859-1"

    def test_directory_raises_and_logs_warning(self, tmp_path, caplog):
        with caplog.at_level(logging.WARNING, logger="file_processors.rtf_processor"):
            with pytest.raises(IsADirectoryError):
                RtfProcessor().extract_text(str(tmp_path))
        assert "RTF processing error with encoding utf-8" in caplog.text

    def test_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            RtfProcessor().extract_text(str(tmp_path / "missing.rtf"))


# --------------------------------------------------------------------------- #
# pdf_processor
# --------------------------------------------------------------------------- #


class TestPdfProcessorEdge:
    def test_multipage_pdf_yields_one_chunk_per_text_page(self, tmp_path, monkeypatch):
        from file_processors import pdf_processor

        monkeypatch.setattr(pdf_processor, "_ocr_available", lambda: False)
        path = _write(
            tmp_path / "t.pdf",
            _build_pdf(
                [
                    "Kunde: Max Mustermann\nIBAN " + IBAN,
                    "",  # blank page -> skipped without OCR
                    "Seite drei: anna@example.com",
                ]
            ),
        )
        pages = list(PdfProcessor().extract_text(path))
        assert len(pages) == 2
        assert "Max Mustermann" in pages[0] and IBAN in pages[0]
        assert "anna@example.com" in pages[1]

    def test_blank_page_uses_ocr_fallback_only_for_blank_pages(
        self, tmp_path, monkeypatch
    ):
        from file_processors import pdf_processor

        ocr_calls: list[int] = []

        def fake_ocr(file_path, page_number):
            ocr_calls.append(page_number)
            return "Gescannt: scan@example.com"

        monkeypatch.setattr(pdf_processor, "_ocr_available", lambda: True)
        monkeypatch.setattr(pdf_processor, "_ocr_page", fake_ocr)
        path = _write(
            tmp_path / "scan.pdf", _build_pdf(["Text Seite mit +49 30 1234567", ""])
        )
        pages = list(PdfProcessor().extract_text(path))
        assert pages == [
            "Text Seite mit +49 30 1234567\n",
            "Gescannt: scan@example.com",
        ]
        assert ocr_calls == [2]

    def test_blank_page_with_empty_ocr_result_is_skipped(self, tmp_path, monkeypatch):
        from file_processors import pdf_processor

        monkeypatch.setattr(pdf_processor, "_ocr_available", lambda: True)
        monkeypatch.setattr(pdf_processor, "_ocr_page", lambda *_: "   ")
        path = _write(tmp_path / "blank.pdf", _build_pdf([""]))
        assert list(PdfProcessor().extract_text(path)) == []

    @pytest.mark.parametrize(
        "content", [b"", b"%PDF-1.4 garbage", b"hello world this is not a pdf"]
    )
    def test_corrupt_pdf_raises_syntax_error(self, tmp_path, content):
        from pdfminer.pdfparser import PDFSyntaxError

        path = _write(tmp_path / "bad.pdf", content)
        with pytest.raises(PDFSyntaxError):
            list(PdfProcessor().extract_text(path))

    def test_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            list(PdfProcessor().extract_text(str(tmp_path / "missing.pdf")))

    def test_ocr_unavailable_when_pytesseract_missing(self):
        from file_processors.pdf_processor import _ocr_available, _ocr_page

        fake_pdf2image = types.ModuleType("pdf2image")
        with patch.dict(
            sys.modules, {"pdf2image": fake_pdf2image, "pytesseract": None}
        ):
            assert _ocr_available() is False
            # OCR degrades to an empty string instead of raising.
            assert _ocr_page("irrelevant.pdf", 1) == ""

    def test_ocr_dpi_invalid_env_falls_back_to_default(self, monkeypatch):
        from core import constants
        from file_processors.pdf_processor import _ocr_dpi, _ocr_language

        monkeypatch.setenv("PBD_OCR_DPI", "high")
        monkeypatch.delenv("PBD_OCR_LANG", raising=False)
        assert _ocr_dpi() == constants.OCR_DPI
        assert _ocr_language() == constants.OCR_LANGUAGES
        # An *empty* value is not treated as unset: it overrides the default.
        monkeypatch.setenv("PBD_OCR_LANG", "")
        assert _ocr_language() == ""


# --------------------------------------------------------------------------- #
# eml_processor
# --------------------------------------------------------------------------- #


def _eml_with_attachments(path, attachments, body="Hallo") -> str:
    msg = EmailMessage()
    msg["From"] = "outer@example.com"
    msg["To"] = "to@example.com"
    msg["Subject"] = "Anhang"
    msg.set_content(body)
    for data, maintype, subtype, filename in attachments:
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return _write_eml(path, msg)


class TestEmlProcessorEdge:
    def test_all_pii_headers_are_extracted(self, tmp_path):
        raw = (
            "From: a@example.com\n"
            "To: b@example.com\n"
            "Cc: c@example.com\n"
            "Bcc: d@example.com\n"
            "Reply-To: e@example.com\n"
            "Return-Path: <f@example.com>\n"
            "Sender: g@example.com\n"
            "Received: from mail.example.com by relay for <h@example.com>\n"
            "X-Custom: ignored@example.com\n"
            "Subject: Betreff\n"
            "\n"
            "Body\n"
        )
        path = _write(tmp_path / "h.eml", raw)
        text = EmlProcessor().extract_text(path)
        for letter in "abcdefgh":
            assert f"{letter}@example.com" in text
        assert "ignored@example.com" not in text

    def test_single_part_unknown_charset_falls_back_to_utf8(self, tmp_path):
        raw = (
            b"From: a@example.com\n"
            b"Content-Type: text/plain; charset=x-unknown-cs\n\n"
            b"Body with IBAN " + IBAN.encode() + b"\n"
        )
        path = _write(tmp_path / "cs.eml", raw)
        assert IBAN in EmlProcessor().extract_text(path)

    def test_multipart_plain_part_unknown_charset_falls_back(self, tmp_path):
        raw = (
            "From: a@example.com\n"
            'Content-Type: multipart/mixed; boundary="b"\n\n'
            "--b\n"
            'Content-Type: text/plain; charset="no-such-charset"\n\n'
            "Plain mit max@example.com\n"
            "--b--\n"
        )
        path = _write(tmp_path / "mp.eml", raw)
        assert "max@example.com" in EmlProcessor().extract_text(path)

    def test_iterator_returning_processor_attachment_is_joined(self, tmp_path):
        db_bytes = _sqlite_bytes(
            tmp_path,
            [
                "CREATE TABLE kunden (name TEXT, iban TEXT)",
                f"INSERT INTO kunden VALUES ('Anna Adler', '{IBAN}')",
            ],
        )
        path = _eml_with_attachments(
            tmp_path / "db.eml",
            [(db_bytes, "application", "x-sqlite3", "kunden.db")],
        )
        text = EmlProcessor().extract_text(path)
        assert "[Attachment: kunden.db]" in text
        assert "[Table: kunden]" in text
        assert f"Anna Adler | {IBAN}" in text

    def test_nested_eml_attachment_is_recursed(self, tmp_path):
        inner = EmailMessage()
        inner["From"] = "inner@example.com"
        inner.set_content("Innerer Text mit IBAN " + IBAN)
        path = _eml_with_attachments(
            tmp_path / "outer.eml",
            [(inner.as_bytes(), "application", "octet-stream", "weitergeleitet.eml")],
        )
        text = EmlProcessor().extract_text(path)
        assert "[Attachment: weitergeleitet.eml]" in text
        assert "inner@example.com" in text
        assert IBAN in text

    def test_nested_eml_depth_limit(self, tmp_path, monkeypatch):
        from file_processors import eml_processor

        level2 = EmailMessage()
        level2["From"] = "level2@example.com"
        level2.set_content("tiefste Ebene " + IBAN)
        level1 = EmailMessage()
        level1["From"] = "level1@example.com"
        level1.set_content("mittlere Ebene")
        level1.add_attachment(
            level2.as_bytes(),
            maintype="application",
            subtype="octet-stream",
            filename="l2.eml",
        )
        path = _eml_with_attachments(
            tmp_path / "l0.eml",
            [(level1.as_bytes(), "application", "octet-stream", "l1.eml")],
        )

        monkeypatch.setattr(eml_processor, "_MAX_ATTACHMENT_DEPTH", 1)
        text = EmlProcessor().extract_text(path)
        # Depth 0 -> 1 is processed (headers of l1.eml), its own attachments are not.
        assert "level1@example.com" in text
        assert "[Attachment: l1.eml]" in text
        assert "level2@example.com" not in text
        assert IBAN not in text

        monkeypatch.setattr(eml_processor, "_MAX_ATTACHMENT_DEPTH", 3)
        text = EmlProcessor().extract_text(path)
        assert "level2@example.com" in text and IBAN in text

    def test_message_rfc822_part_is_not_extracted(self, tmp_path):
        """Current behaviour: a properly typed ``message/rfc822`` attachment has no
        bytes payload (``get_payload(decode=True)`` is None), so its content is
        skipped rather than routed through the EML processor."""
        inner = EmailMessage()
        inner["From"] = "inner@example.com"
        inner.set_content("verschachtelt " + IBAN)
        outer = EmailMessage()
        outer["From"] = "outer@example.com"
        outer.set_content("Weiterleitung")
        outer.add_attachment(inner)
        path = _write_eml(tmp_path / "fwd.eml", outer)
        text = EmlProcessor().extract_text(path)
        assert "outer@example.com" in text
        # The nested text/plain body is still picked up by the body walk ...
        assert IBAN in text
        # ... but the nested headers are not, and no attachment marker is emitted.
        assert "inner@example.com" not in text
        assert "[Attachment:" not in text

    def test_oversized_attachment_is_skipped(
        self, tmp_path, monkeypatch, drained_skips
    ):
        from file_processors import eml_processor

        monkeypatch.setattr(eml_processor, "_MAX_ATTACHMENT_BYTES", 32)
        big = ("name,iban\nAnna," + IBAN + "\n").encode() * 4
        small = b"name\nKlein Kurz\n"
        path = _eml_with_attachments(
            tmp_path / "big.eml",
            [(big, "text", "csv", "gross.csv"), (small, "text", "csv", "klein.csv")],
        )
        text = EmlProcessor().extract_text(path)
        assert IBAN not in text
        assert "[Attachment: gross.csv]" not in text
        assert "[Attachment: klein.csv]" in text and "Klein Kurz" in text
        assert skip_counters.drain() == {"eml_attachment_oversized": 1}

    def test_attachment_count_limit_stops_processing(
        self, tmp_path, monkeypatch, drained_skips
    ):
        from file_processors import eml_processor

        monkeypatch.setattr(eml_processor, "_MAX_ATTACHMENTS", 1)
        path = _eml_with_attachments(
            tmp_path / "many.eml",
            [
                (b"name\nErster Anhang\n", "text", "csv", "eins.csv"),
                (b"name\nZweiter Anhang\n", "text", "csv", "zwei.csv"),
            ],
        )
        text = EmlProcessor().extract_text(path)
        assert "Erster Anhang" in text
        assert "Zweiter Anhang" not in text
        assert skip_counters.drain() == {"eml_attachment_limit_reached": 1}

    def test_unreadable_attachment_is_skipped(self, tmp_path, drained_skips):
        path = _eml_with_attachments(
            tmp_path / "broken.eml",
            [(b"%PDF-1.4 kaputt", "application", "pdf", "kaputt.pdf")],
            body="Body bleibt: body@example.com",
        )
        text = EmlProcessor().extract_text(path)
        assert "body@example.com" in text
        assert "[Attachment:" not in text
        assert skip_counters.drain() == {"eml_attachment_unreadable": 1}

    def test_attachment_without_processor_is_ignored(self, tmp_path, drained_skips):
        path = _eml_with_attachments(
            tmp_path / "unknown.eml",
            [
                (
                    b"opaque bytes hidden@example.com",
                    "application",
                    "octet-stream",
                    "d.xyz",
                )
            ],
        )
        text = EmlProcessor().extract_text(path)
        assert "hidden@example.com" not in text
        assert "[Attachment:" not in text
        assert skip_counters.drain() == {}

    def test_inline_parts_and_text_attachments_are_not_double_extracted(self, tmp_path):
        msg = EmailMessage()
        msg["From"] = "a@example.com"
        msg.set_content("Haupttext")
        # Inline image without filename: not an attachment, not a body part.
        msg.add_attachment(
            b"\x89PNG\r\n\x1a\n", maintype="image", subtype="png", disposition="inline"
        )
        # text/plain attachment: extracted by the body walk, not as attachment.
        msg.add_attachment(
            "Notiz: notiz@example.com", subtype="plain", filename="n.txt"
        )
        path = _write_eml(tmp_path / "inline.eml", msg)
        text = EmlProcessor().extract_text(path)
        assert "Haupttext" in text
        assert text.count("notiz@example.com") == 1
        assert "[Attachment:" not in text

    def test_temp_file_cleanup_failure_is_logged_not_raised(
        self, tmp_path, mocker, caplog
    ):
        path = _eml_with_attachments(
            tmp_path / "unlink.eml",
            [(b"name\nAnhang Inhalt\n", "text", "csv", "a.csv")],
        )
        real_unlink = os.unlink
        leaked: list[str] = []

        def failing_unlink(target, *args, **kwargs):
            leaked.append(target)
            raise OSError("busy")

        mocker.patch("file_processors.eml_processor.os.unlink", failing_unlink)
        with caplog.at_level(logging.DEBUG, logger="file_processors.eml_processor"):
            text = EmlProcessor().extract_text(path)
        for target in leaked:  # tidy up what the processor could not remove
            real_unlink(target)

        assert "Anhang Inhalt" in text
        assert len(leaked) == 1
        assert "Failed to remove temp file" in caplog.text

    def test_directory_is_wrapped(self, tmp_path):
        with pytest.raises(Exception, match="Error processing EML file"):
            EmlProcessor().extract_text(str(tmp_path))

    def test_empty_file_yields_empty_string(self, tmp_path):
        path = _write(tmp_path / "empty.eml", b"")
        assert EmlProcessor().extract_text(path) == ""

    def test_message_from_bytes_roundtrip_of_8bit_body(self, tmp_path):
        msg = EmailMessage()
        msg["From"] = "ü@example.com"
        msg.set_content("Grüße aus Köln, IBAN " + IBAN)
        path = _write_eml(tmp_path / "utf8.eml", msg)
        parsed = email.message_from_bytes(msg.as_bytes())
        assert parsed.get_content_charset() == "utf-8"
        text = EmlProcessor().extract_text(path)
        assert "Grüße aus Köln" in text and IBAN in text
