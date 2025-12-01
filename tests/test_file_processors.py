"""Tests for file processors."""

import os
import pytest
from file_processors import (
    PdfProcessor,
    DocxProcessor,
    HtmlProcessor,
    TextProcessor,
    CsvProcessor,
    JsonProcessor,
    RtfProcessor,
    OdtProcessor,
    EmlProcessor,
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
            f.write('{"name": "John Doe", "email": "john@example.com", "phone": "123-456-7890"}')
        
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
            f.write('''{
                "users": [
                    {"name": "John Doe", "email": "john@example.com"},
                    {"name": "Jane Smith", "email": "jane@example.com"}
                ],
                "metadata": {
                    "created": "2024-01-01",
                    "author": "Admin"
                }
            }''')
        
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
        assert "test RTF document" in text.lower()
    
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
    
    # Note: Testing actual ODT extraction would require creating a valid ODT file
    # which is complex. The can_process test and file_not_found test verify
    # the basic functionality. Full integration tests would require sample ODT files.


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
