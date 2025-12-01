"""Tests for file processors."""

import os
import pytest
from file_processors import (
    PdfProcessor,
    DocxProcessor,
    HtmlProcessor,
    TextProcessor,
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
