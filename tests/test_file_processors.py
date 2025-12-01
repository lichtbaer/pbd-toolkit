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
