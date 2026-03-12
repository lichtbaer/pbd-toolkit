"""Tests for file processors."""

import os
import sqlite3
import zipfile
from pathlib import Path

import pytest

from file_processors import (
    CsvProcessor,
    DocxProcessor,
    EmlProcessor,
    HtmlProcessor,
    IcalProcessor,
    JsonProcessor,
    MarkdownProcessor,
    MboxProcessor,
    MsgProcessor,
    OdsProcessor,
    OdtProcessor,
    PdfProcessor,
    PptProcessor,
    PptxProcessor,
    PropertiesProcessor,
    RtfProcessor,
    SqliteProcessor,
    TextProcessor,
    VcfProcessor,
    XmlProcessor,
    XlsxProcessor,
    YamlProcessor,
    ZipProcessor,
)


class TestPdfProcessor:
    """Tests for PDF processor."""

    def test_can_process_pdf(self):
        """Test that PDF processor recognizes .pdf extension."""
        processor = PdfProcessor()
        assert processor.can_process(".pdf")
        assert processor.can_process(".PDF")
        assert not processor.can_process(".docx")
        assert not processor.can_process(".txt")

    def test_can_process_case_insensitive(self):
        """Test that extension matching is case insensitive."""
        processor = PdfProcessor()
        assert processor.can_process(".PDF")
        assert processor.can_process(".Pdf")


class TestDocxProcessor:
    """Tests for DOCX processor."""

    def test_can_process_docx(self):
        """Test that DOCX processor recognizes .docx extension."""
        processor = DocxProcessor()
        assert processor.can_process(".docx")
        assert processor.can_process(".DOCX")
        assert not processor.can_process(".pdf")
        assert not processor.can_process(".txt")


class TestHtmlProcessor:
    """Tests for HTML processor."""

    def test_can_process_html(self):
        """Test that HTML processor recognizes .html extension."""
        processor = HtmlProcessor()
        assert processor.can_process(".html")
        assert processor.can_process(".HTML")
        assert processor.can_process(".htm")
        assert not processor.can_process(".txt")

    def test_extract_text_from_html(self, sample_html_file):
        """Test text extraction from HTML file."""
        processor = HtmlProcessor()
        text = processor.extract_text(sample_html_file)
        assert "user@example.com" in text
        assert "IBAN" in text
        # HTML tags should be removed
        assert "<html>" not in text
        assert "<p>" not in text
        assert "<" not in text and ">" not in text


class TestTextProcessor:
    """Tests for text processor."""

    def test_can_process_txt(self, temp_dir):
        """Test that text processor recognizes .txt extension."""
        processor = TextProcessor()
        assert processor.can_process(".txt", os.path.join(temp_dir, "test.txt"))
        assert processor.can_process(".TXT", os.path.join(temp_dir, "test.TXT"))
        assert not processor.can_process(".pdf", os.path.join(temp_dir, "test.pdf"))

    def test_extract_text_from_file(self, sample_text_file):
        """Test text extraction from text file."""
        processor = TextProcessor()
        text = processor.extract_text(sample_text_file)
        assert "test@example.com" in text
        assert "IBAN" in text
        assert "This is a test file" in text

    def test_file_not_found(self, temp_dir):
        """Test that FileNotFoundError is raised for non-existent file."""
        processor = TextProcessor()
        non_existent = os.path.join(temp_dir, "nonexistent.txt")
        with pytest.raises(FileNotFoundError):
            processor.extract_text(non_existent)


class TestCsvProcessor:
    """Tests for CSV processor."""

    def test_can_process_csv(self):
        """Test that CSV processor recognizes .csv extension."""
        processor = CsvProcessor()
        assert processor.can_process(".csv")
        assert processor.can_process(".CSV")
        assert not processor.can_process(".txt")
        assert not processor.can_process(".json")

    def test_extract_text_from_csv(self, temp_dir):
        """Test text extraction from CSV file."""
        file_path = os.path.join(temp_dir, "test.csv")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Name,Email,Phone\n")
            f.write("John Doe,john@example.com,123-456-7890\n")
            f.write("Jane Smith,jane@example.com,098-765-4321\n")

        processor = CsvProcessor()
        text = processor.extract_text(file_path)
        assert "John Doe" in text
        assert "john@example.com" in text
        assert "Jane Smith" in text
        assert "jane@example.com" in text
        assert "123-456-7890" in text

    def test_extract_text_from_csv_semicolon(self, temp_dir):
        """Test text extraction from CSV file with semicolon delimiter."""
        file_path = os.path.join(temp_dir, "test.csv")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Name;Email;Phone\n")
            f.write("John Doe;john@example.com;123-456-7890\n")

        processor = CsvProcessor()
        text = processor.extract_text(file_path)
        assert "John Doe" in text
        assert "john@example.com" in text

    def test_extract_text_from_csv_tab(self, temp_dir):
        """Test text extraction from CSV file with tab delimiter."""
        file_path = os.path.join(temp_dir, "test.csv")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Name\tEmail\tPhone\n")
            f.write("John Doe\tjohn@example.com\t123-456-7890\n")

        processor = CsvProcessor()
        text = processor.extract_text(file_path)
        assert "John Doe" in text
        assert "john@example.com" in text

    def test_file_not_found(self, temp_dir):
        """Test that FileNotFoundError is raised for non-existent file."""
        processor = CsvProcessor()
        non_existent = os.path.join(temp_dir, "nonexistent.csv")
        with pytest.raises(FileNotFoundError):
            processor.extract_text(non_existent)


class TestJsonProcessor:
    """Tests for JSON processor."""

    def test_can_process_json(self):
        """Test that JSON processor recognizes .json extension."""
        processor = JsonProcessor()
        assert processor.can_process(".json")
        assert processor.can_process(".JSON")
        assert not processor.can_process(".txt")
        assert not processor.can_process(".csv")

    def test_extract_text_from_json(self, temp_dir):
        """Test text extraction from JSON file."""
        file_path = os.path.join(temp_dir, "test.json")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(
                '{"name": "John Doe", "email": "john@example.com", "phone": "123-456-7890"}'
            )

        processor = JsonProcessor()
        text = processor.extract_text(file_path)
        assert "name" in text
        assert "John Doe" in text
        assert "email" in text
        assert "john@example.com" in text
        assert "phone" in text
        assert "123-456-7890" in text

    def test_extract_text_from_nested_json(self, temp_dir):
        """Test text extraction from nested JSON file."""
        file_path = os.path.join(temp_dir, "test.json")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(
                """{
                "users": [
                    {"name": "John Doe", "email": "john@example.com"},
                    {"name": "Jane Smith", "email": "jane@example.com"}
                ],
                "metadata": {
                    "created": "2024-01-01",
                    "author": "Admin"
                }
            }"""
            )

        processor = JsonProcessor()
        text = processor.extract_text(file_path)
        assert "users" in text
        assert "John Doe" in text
        assert "john@example.com" in text
        assert "Jane Smith" in text
        assert "jane@example.com" in text
        assert "metadata" in text
        assert "created" in text
        assert "author" in text
        assert "Admin" in text

    def test_extract_text_from_json_array(self, temp_dir):
        """Test text extraction from JSON array."""
        file_path = os.path.join(temp_dir, "test.json")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write('["John Doe", "jane@example.com", "123 Main St"]')

        processor = JsonProcessor()
        text = processor.extract_text(file_path)
        assert "John Doe" in text
        assert "jane@example.com" in text
        assert "123 Main St" in text

    def test_extract_text_from_invalid_json(self, temp_dir):
        """Test text extraction from invalid JSON file (should still extract strings)."""
        file_path = os.path.join(temp_dir, "test.json")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write('{"name": "John Doe", "email": "john@example.com" invalid json')

        processor = JsonProcessor()
        text = processor.extract_text(file_path)
        # Should still extract string values using regex fallback
        assert "John Doe" in text or "john@example.com" in text

    def test_file_not_found(self, temp_dir):
        """Test that FileNotFoundError is raised for non-existent file."""
        processor = JsonProcessor()
        non_existent = os.path.join(temp_dir, "nonexistent.json")
        with pytest.raises(FileNotFoundError):
            processor.extract_text(non_existent)


class TestRtfProcessor:
    """Tests for RTF processor."""

    def test_can_process_rtf(self):
        """Test that RTF processor recognizes .rtf extension."""
        processor = RtfProcessor()
        assert processor.can_process(".rtf")
        assert processor.can_process(".RTF")
        assert not processor.can_process(".txt")
        assert not processor.can_process(".docx")

    def test_extract_text_from_rtf(self, temp_dir):
        """Test text extraction from RTF file."""
        file_path = os.path.join(temp_dir, "test.rtf")
        # Create a simple RTF file
        rtf_content = r"{\rtf1\ansi\deff0 {\fonttbl {\f0 Times New Roman;}}\f0\fs24 This is a test RTF document with email test@example.com and IBAN DE89 3704 0044 0532 0130 00.}"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(rtf_content)

        processor = RtfProcessor()
        text = processor.extract_text(file_path)
        assert "test@example.com" in text
        assert "IBAN" in text
        assert "test rtf document" in text.lower()

    def test_file_not_found(self, temp_dir):
        """Test that FileNotFoundError is raised for non-existent file."""
        processor = RtfProcessor()
        non_existent = os.path.join(temp_dir, "nonexistent.rtf")
        with pytest.raises(FileNotFoundError):
            processor.extract_text(non_existent)


class TestOdtProcessor:
    """Tests for ODT processor."""

    def test_can_process_odt(self):
        """Test that ODT processor recognizes .odt extension."""
        processor = OdtProcessor()
        assert processor.can_process(".odt")
        assert processor.can_process(".ODT")
        assert not processor.can_process(".txt")
        assert not processor.can_process(".docx")

    def test_file_not_found(self, temp_dir):
        """Test that FileNotFoundError is raised for non-existent file."""
        processor = OdtProcessor()
        non_existent = os.path.join(temp_dir, "nonexistent.odt")
        with pytest.raises(FileNotFoundError):
            processor.extract_text(non_existent)

    def test_extract_text_from_odt(self, temp_dir):
        """Test text extraction from ODT file (requires odfpy)."""
        pytest.importorskip("odf.opendocument")
        from odf.opendocument import OpenDocumentText
        from odf.text import P

        odt_path = os.path.join(temp_dir, "test.odt")
        doc = OpenDocumentText()
        doc.text.addElement(P(text="Contact: John Doe at john@example.com"))
        doc.save(odt_path)

        processor = OdtProcessor()
        text = processor.extract_text(odt_path)
        assert "John Doe" in text
        assert "john@example.com" in text


class TestEmlProcessor:
    """Tests for EML processor."""

    def test_can_process_eml(self):
        """Test that EML processor recognizes .eml extension."""
        processor = EmlProcessor()
        assert processor.can_process(".eml")
        assert processor.can_process(".EML")
        assert not processor.can_process(".txt")
        assert not processor.can_process(".msg")

    def test_extract_text_from_eml(self, temp_dir):
        """Test text extraction from EML file."""
        file_path = os.path.join(temp_dir, "test.eml")
        # Create a simple EML file
        eml_content = """From: sender@example.com
To: recipient@example.com
Subject: Test Email
Content-Type: text/plain; charset=utf-8

This is a test email with contact info: contact@example.com
IBAN: DE89 3704 0044 0532 0130 00
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(eml_content)

        processor = EmlProcessor()
        text = processor.extract_text(file_path)
        assert "sender@example.com" in text
        assert "recipient@example.com" in text
        assert "Test Email" in text
        assert "contact@example.com" in text
        assert "IBAN" in text

    def test_extract_text_from_multipart_eml(self, temp_dir):
        """Test text extraction from multipart EML file."""
        file_path = os.path.join(temp_dir, "test.eml")
        # Create a multipart EML file
        eml_content = """From: sender@example.com
To: recipient@example.com
Subject: Multipart Test
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="boundary123"

--boundary123
Content-Type: text/plain; charset=utf-8

This is the plain text part with email test@example.com

--boundary123
Content-Type: text/html; charset=utf-8

<html><body>This is the <b>HTML</b> part with email test@example.com</body></html>

--boundary123--
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(eml_content)

        processor = EmlProcessor()
        text = processor.extract_text(file_path)
        assert "sender@example.com" in text
        assert "recipient@example.com" in text
        assert "test@example.com" in text

    def test_file_not_found(self, temp_dir):
        """Test that FileNotFoundError is raised for non-existent file."""
        processor = EmlProcessor()
        non_existent = os.path.join(temp_dir, "nonexistent.eml")
        with pytest.raises(FileNotFoundError):
            processor.extract_text(non_existent)


class TestMsgProcessor:
    """Tests for MSG processor."""

    def test_can_process_msg(self):
        """Test that MSG processor recognizes .msg extension."""
        processor = MsgProcessor()
        assert processor.can_process(".msg")
        assert processor.can_process(".MSG")
        assert not processor.can_process(".txt")
        assert not processor.can_process(".eml")

    def test_import_error_when_extract_msg_not_installed(self, temp_dir, mocker):
        """Test that ImportError is raised when extract-msg is not installed."""
        # Mock the import to raise ImportError
        mocker.patch(
            "file_processors.msg_processor.extract_msg",
            side_effect=ImportError("No module named 'extract_msg'"),
        )

        processor = MsgProcessor()
        file_path = os.path.join(temp_dir, "test.msg")
        # Create a dummy file (won't be read due to import error)
        with open(file_path, "w") as f:
            f.write("dummy")

        with pytest.raises(ImportError) as exc_info:
            processor.extract_text(file_path)
        assert "extract-msg is required" in str(exc_info.value)

    def test_file_not_found(self, temp_dir):
        """Test that FileNotFoundError is raised for non-existent file."""
        processor = MsgProcessor()
        non_existent = os.path.join(temp_dir, "nonexistent.msg")
        # Note: This will raise ImportError if extract-msg is not installed,
        # or FileNotFoundError if it is installed. We test both cases.
        try:
            with pytest.raises((FileNotFoundError, ImportError)):
                processor.extract_text(non_existent)
        except ImportError:
            # If extract-msg is not installed, that's expected
            pass

    # Note: Testing actual MSG extraction would require creating a valid MSG file
    # which is complex and requires Outlook or specialized tools. The can_process test
    # and error handling tests verify the basic functionality. Full integration tests
    # would require sample MSG files from actual Outlook exports.


class TestOdsProcessor:
    """Tests for ODS processor."""

    def test_can_process_ods(self):
        """Test that ODS processor recognizes .ods extension."""
        processor = OdsProcessor()
        assert processor.can_process(".ods")
        assert processor.can_process(".ODS")
        assert not processor.can_process(".txt")
        assert not processor.can_process(".xlsx")

    def test_file_not_found(self, temp_dir):
        """Test that FileNotFoundError is raised for non-existent file."""
        processor = OdsProcessor()
        non_existent = os.path.join(temp_dir, "nonexistent.ods")
        with pytest.raises(FileNotFoundError):
            processor.extract_text(non_existent)

    def test_extract_text_from_ods(self, temp_dir):
        """Test text extraction from ODS file (requires odfpy)."""
        pytest.importorskip("odf.opendocument")
        from odf.opendocument import OpenDocumentSpreadsheet
        from odf.table import Table, TableRow, TableCell
        from odf.text import P

        ods_path = os.path.join(temp_dir, "test.ods")
        doc = OpenDocumentSpreadsheet()
        table = Table(name="Sheet1")
        row = TableRow()
        for cell_text in ["John Doe", "john@example.com"]:
            cell = TableCell()
            cell.addElement(P(text=cell_text))
            row.addElement(cell)
        table.addElement(row)
        doc.spreadsheet.addElement(table)
        doc.save(ods_path)

        processor = OdsProcessor()
        text = processor.extract_text(ods_path)
        assert "John Doe" in text
        assert "john@example.com" in text


class TestXlsxProcessor:
    """Tests for XLSX processor."""

    def test_can_process_xlsx(self):
        """Test that XLSX processor recognizes .xlsx extension."""
        processor = XlsxProcessor()
        assert processor.can_process(".xlsx")
        assert processor.can_process(".XLSX")
        assert not processor.can_process(".xls")
        assert not processor.can_process(".csv")

    def test_extract_text_from_xlsx(self, temp_dir):
        """Test text extraction from XLSX file (requires openpyxl)."""
        pytest.importorskip("openpyxl")
        from openpyxl import Workbook

        xlsx_path = os.path.join(temp_dir, "test.xlsx")
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "John Doe"
        ws["B1"] = "john@example.com"
        wb.save(xlsx_path)

        processor = XlsxProcessor()
        text = processor.extract_text(xlsx_path)
        assert "John Doe" in text
        assert "john@example.com" in text

    def test_file_not_found(self, temp_dir):
        """Test that non-existent file raises an error (XlsxProcessor wraps as Exception)."""
        processor = XlsxProcessor()
        non_existent = os.path.join(temp_dir, "nonexistent.xlsx")
        with pytest.raises(Exception) as exc_info:
            processor.extract_text(non_existent)
        assert "No such file" in str(exc_info.value) or "nonexistent" in str(exc_info.value).lower()


class TestPptxProcessor:
    """Tests for PPTX processor."""

    def test_can_process_pptx(self):
        """Test that PPTX processor recognizes .pptx extension."""
        processor = PptxProcessor()
        assert processor.can_process(".pptx")
        assert processor.can_process(".PPTX")
        assert not processor.can_process(".txt")
        assert not processor.can_process(".docx")

    def test_import_error_when_python_pptx_not_installed(self, temp_dir, mocker):
        """Test that ImportError is raised when python-pptx is not installed."""
        # Mock the import to raise ImportError
        mocker.patch(
            "file_processors.pptx_processor.Presentation",
            side_effect=ImportError("No module named 'pptx'"),
        )

        processor = PptxProcessor()
        file_path = os.path.join(temp_dir, "test.pptx")
        # Create a dummy file (won't be read due to import error)
        with open(file_path, "w") as f:
            f.write("dummy")

        with pytest.raises(ImportError) as exc_info:
            processor.extract_text(file_path)
        assert "python-pptx is required" in str(exc_info.value)

    def test_file_not_found(self, temp_dir):
        """Test that FileNotFoundError is raised for non-existent file."""
        processor = PptxProcessor()
        non_existent = os.path.join(temp_dir, "nonexistent.pptx")
        # Note: This will raise ImportError if python-pptx is not installed,
        # or FileNotFoundError if it is installed. We test both cases.
        try:
            with pytest.raises((FileNotFoundError, ImportError)):
                processor.extract_text(non_existent)
        except ImportError:
            # If python-pptx is not installed, that's expected
            pass

    def test_extract_text_from_pptx(self, temp_dir):
        """Test text extraction from PPTX file (requires python-pptx)."""
        pytest.importorskip("pptx")
        from pptx import Presentation
        from pptx.util import Inches

        pptx_path = os.path.join(temp_dir, "test.pptx")
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank
        slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1)).text_frame.text = (
            "John Doe john@example.com"
        )
        prs.save(pptx_path)

        processor = PptxProcessor()
        text = processor.extract_text(pptx_path)
        assert "John Doe" in text
        assert "john@example.com" in text


class TestPptProcessor:
    """Tests for PPT processor."""

    def test_can_process_ppt(self):
        """Test that PPT processor recognizes .ppt extension."""
        processor = PptProcessor()
        assert processor.can_process(".ppt")
        assert processor.can_process(".PPT")
        assert not processor.can_process(".txt")
        assert not processor.can_process(".pptx")

    def test_not_implemented(self, temp_dir):
        """Test that NotImplementedError is raised for PPT files."""
        processor = PptProcessor()
        file_path = os.path.join(temp_dir, "test.ppt")
        # Create a dummy file
        with open(file_path, "w") as f:
            f.write("dummy")

        with pytest.raises(NotImplementedError) as exc_info:
            processor.extract_text(file_path)
        assert "Older PPT format" in str(
            exc_info.value
        ) or "not fully supported" in str(exc_info.value)


class TestYamlProcessor:
    """Tests for YAML processor."""

    def test_can_process_yaml(self):
        """Test that YAML processor recognizes .yaml and .yml extensions."""
        processor = YamlProcessor()
        assert processor.can_process(".yaml")
        assert processor.can_process(".YAML")
        assert processor.can_process(".yml")
        assert processor.can_process(".YML")
        assert not processor.can_process(".txt")
        assert not processor.can_process(".json")

    def test_extract_text_from_yaml(self, temp_dir):
        """Test text extraction from YAML file."""
        file_path = os.path.join(temp_dir, "test.yaml")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(
                """name: John Doe
email: john@example.com
phone: "123-456-7890"
address:
  street: "123 Main St"
  city: "New York"
"""
            )

        processor = YamlProcessor()
        text = processor.extract_text(file_path)
        assert "name" in text
        assert "John Doe" in text
        assert "email" in text
        assert "john@example.com" in text
        assert "phone" in text
        assert "123-456-7890" in text
        assert "address" in text
        assert "street" in text
        assert "123 Main St" in text
        assert "city" in text
        assert "New York" in text

    def test_extract_text_from_nested_yaml(self, temp_dir):
        """Test text extraction from nested YAML file."""
        file_path = os.path.join(temp_dir, "test.yaml")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(
                """users:
  - name: John Doe
    email: john@example.com
  - name: Jane Smith
    email: jane@example.com
metadata:
  created: "2024-01-01"
  author: Admin
"""
            )

        processor = YamlProcessor()
        text = processor.extract_text(file_path)
        assert "users" in text
        assert "John Doe" in text
        assert "john@example.com" in text
        assert "Jane Smith" in text
        assert "jane@example.com" in text
        assert "metadata" in text
        assert "created" in text
        assert "author" in text
        assert "Admin" in text

    def test_extract_text_from_yaml_array(self, temp_dir):
        """Test text extraction from YAML array."""
        file_path = os.path.join(temp_dir, "test.yaml")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write('- "John Doe"\n- "jane@example.com"\n- "123 Main St"')

        processor = YamlProcessor()
        text = processor.extract_text(file_path)
        assert "John Doe" in text
        assert "jane@example.com" in text
        assert "123 Main St" in text

    def test_import_error_when_pyyaml_not_installed(self, temp_dir, mocker):
        """Test that ImportError is raised when PyYAML is not installed."""
        # Mock the import to raise ImportError
        mocker.patch(
            "file_processors.yaml_processor.yaml",
            side_effect=ImportError("No module named 'yaml'"),
        )

        processor = YamlProcessor()
        file_path = os.path.join(temp_dir, "test.yaml")
        with open(file_path, "w") as f:
            f.write("key: value")

        with pytest.raises(ImportError) as exc_info:
            processor.extract_text(file_path)
        assert "PyYAML is required" in str(exc_info.value)

    def test_file_not_found(self, temp_dir):
        """Test that FileNotFoundError is raised for non-existent file."""
        processor = YamlProcessor()
        non_existent = os.path.join(temp_dir, "nonexistent.yaml")
        # Note: This will raise ImportError if PyYAML is not installed,
        # or FileNotFoundError if it is installed. We test both cases.
        try:
            with pytest.raises((FileNotFoundError, ImportError)):
                processor.extract_text(non_existent)
        except ImportError:
            # If PyYAML is not installed, that's expected
            pass


class TestMarkdownProcessor:
    """Tests for Markdown processor."""

    def test_can_process_md(self):
        """Test that Markdown processor recognizes .md extension."""
        processor = MarkdownProcessor()
        assert processor.can_process(".md")
        assert processor.can_process(".MD")
        assert processor.can_process(".markdown")
        assert not processor.can_process(".txt")

    def test_extract_text_from_markdown(self, temp_dir):
        """Test text extraction from Markdown file."""
        file_path = os.path.join(temp_dir, "test.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(
                "# Header\n\n"
                "Contact: **John Doe** at john@example.com\n"
                "- Item 1\n- Item 2\n"
            )
        processor = MarkdownProcessor()
        text = processor.extract_text(file_path)
        assert "John Doe" in text
        assert "john@example.com" in text
        assert "Header" in text


class TestSqliteProcessor:
    """Tests for SQLite processor."""

    def test_can_process_sqlite(self):
        """Test that SQLite processor recognizes .db extension."""
        processor = SqliteProcessor()
        assert processor.can_process(".db")
        assert processor.can_process(".sqlite")
        assert processor.can_process(".sqlite3")
        assert not processor.can_process(".txt")

    def test_extract_text_from_sqlite(self, temp_dir):
        """Test text extraction from SQLite database."""
        db_path = os.path.join(temp_dir, "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE contacts (name TEXT, email TEXT)"
        )
        conn.execute(
            "INSERT INTO contacts VALUES ('John Doe', 'john@example.com')"
        )
        conn.commit()
        conn.close()

        processor = SqliteProcessor()
        chunks = list(processor.extract_text(db_path))
        text = " ".join(chunks)
        assert "John Doe" in text
        assert "john@example.com" in text
        assert "contacts" in text.lower()


class TestZipProcessor:
    """Tests for ZIP processor."""

    def test_can_process_zip(self):
        """Test that ZIP processor recognizes .zip extension."""
        processor = ZipProcessor()
        assert processor.can_process(".zip")
        assert processor.can_process(".ZIP")
        assert not processor.can_process(".txt")

    def test_extract_text_from_zip(self, temp_dir):
        """Test text extraction from ZIP archive."""
        zip_path = os.path.join(temp_dir, "test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("doc.txt", "Contact: user@example.com")

        processor = ZipProcessor()
        chunks = list(processor.extract_text(zip_path))
        text = " ".join(chunks)
        assert "user@example.com" in text
        assert "doc.txt" in text

    def test_extract_text_from_zip_skips_directories(self, temp_dir):
        """Test that ZIP processor skips directory entries."""
        zip_path = os.path.join(temp_dir, "test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("subdir/", "")
            zf.writestr("subdir/file.txt", "content")

        processor = ZipProcessor()
        chunks = list(processor.extract_text(zip_path))
        text = " ".join(chunks)
        assert "content" in text

    def test_extract_text_from_zip_multiple_files(self, temp_dir):
        """Test ZIP with multiple text files."""
        zip_path = os.path.join(temp_dir, "multi.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("a.txt", "File A: alpha@example.com")
            zf.writestr("b.txt", "File B: beta@example.com")

        processor = ZipProcessor()
        chunks = list(processor.extract_text(zip_path))
        text = " ".join(chunks)
        assert "alpha@example.com" in text
        assert "beta@example.com" in text
        assert len(chunks) == 2


class TestXmlProcessor:
    """Tests for XML processor."""

    def test_extract_text_from_xml(self, temp_dir):
        """Test text extraction from XML file."""
        file_path = os.path.join(temp_dir, "test.xml")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(
                '<?xml version="1.0"?>'
                "<root><name>John Doe</name><email>john@example.com</email></root>"
            )
        processor = XmlProcessor()
        text = processor.extract_text(file_path)
        assert "John Doe" in text
        assert "john@example.com" in text

    def test_extract_text_from_malformed_xml_fallback(self, temp_dir):
        """Test that malformed XML uses regex fallback to extract text."""
        file_path = os.path.join(temp_dir, "malformed.xml")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("<root><name>John Doe</name><email>john@example.com</email></root")  # missing >
        processor = XmlProcessor()
        text = processor.extract_text(file_path)
        assert "John Doe" in text or "john@example.com" in text


class TestVcfProcessor:
    """Tests for VCF processor."""

    def test_can_process_vcf(self):
        """Test that VCF processor recognizes .vcf extension."""
        processor = VcfProcessor()
        assert processor.can_process(".vcf")
        assert processor.can_process(".VCF")
        assert not processor.can_process(".txt")

    def test_extract_text_from_vcf(self, temp_dir):
        """Test text extraction from vCard file."""
        file_path = os.path.join(temp_dir, "test.vcf")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(
                "BEGIN:VCARD\n"
                "FN:John Doe\n"
                "EMAIL:john@example.com\n"
                "END:VCARD\n"
            )
        processor = VcfProcessor()
        text = processor.extract_text(file_path)
        assert "John Doe" in text
        assert "john@example.com" in text


class TestIcalProcessor:
    """Tests for iCal processor."""

    def test_can_process_ics(self):
        """Test that iCal processor recognizes .ics extension."""
        processor = IcalProcessor()
        assert processor.can_process(".ics")
        assert processor.can_process(".ICAL")
        assert not processor.can_process(".txt")

    def test_extract_text_from_ics(self, temp_dir):
        """Test text extraction from iCalendar file."""
        file_path = os.path.join(temp_dir, "test.ics")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(
                "BEGIN:VCALENDAR\n"
                "BEGIN:VEVENT\n"
                "SUMMARY:Meeting with John\n"
                "DESCRIPTION:Contact john@example.com\n"
                "LOCATION:Room 123\n"
                "END:VEVENT\n"
                "END:VCALENDAR\n"
            )
        processor = IcalProcessor()
        text = processor.extract_text(file_path)
        assert "Meeting with John" in text
        assert "john@example.com" in text
        assert "Room 123" in text


class TestPropertiesProcessor:
    """Tests for Properties processor."""

    def test_can_process_properties(self):
        """Test that Properties processor recognizes .properties extension."""
        processor = PropertiesProcessor()
        assert processor.can_process(".properties")
        assert processor.can_process(".ini")
        assert processor.can_process(".cfg")
        assert not processor.can_process(".txt")

    def test_extract_text_from_properties(self, temp_dir):
        """Test text extraction from Java properties file."""
        file_path = os.path.join(temp_dir, "test.properties")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("user.name=John Doe\napi.key=secret123\n")
        processor = PropertiesProcessor()
        text = processor.extract_text(file_path)
        assert "John Doe" in text
        assert "secret123" in text


class TestMboxProcessor:
    """Tests for MBOX processor."""

    def test_can_process_mbox(self):
        """Test that MBOX processor recognizes .mbox extension."""
        processor = MboxProcessor()
        assert processor.can_process(".mbox")
        assert processor.can_process(".MBOX")
        assert not processor.can_process(".eml")

    def test_extract_text_from_mbox(self, temp_dir):
        """Test text extraction from MBOX mailbox file."""
        file_path = os.path.join(temp_dir, "test.mbox")
        with open(file_path, "wb") as f:
            f.write(
                b"From sender@example.com Mon Jan 01 00:00:00 2024\n"
                b"From: sender@example.com\n"
                b"To: recipient@example.com\n"
                b"Subject: Test\n"
                b"\n"
                b"Body with contact@example.com\n"
            )
        processor = MboxProcessor()
        chunks = list(processor.extract_text(file_path))
        text = " ".join(chunks)
        assert "sender@example.com" in text
        assert "recipient@example.com" in text
        assert "contact@example.com" in text
