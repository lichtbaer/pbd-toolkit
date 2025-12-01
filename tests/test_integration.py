"""Integration tests for the PII toolkit."""

import os
import tempfile
import pytest
from matches import PiiMatchContainer


class TestIntegration:
    """Integration tests."""
    
    def test_whitelist_filtering(self, sample_text_file, monkeypatch):
        """Test that whitelist correctly filters matches."""
        container = PiiMatchContainer()
        container.whitelist = ["test@example.com"]
        
        # Mock csvwriter
        written_rows = []
        def mock_writerow(row):
            written_rows.append(row)
        
        monkeypatch.setattr("globals.csvwriter", type('obj', (object,), {'writerow': mock_writerow})())
        
        # Compile whitelist pattern
        container._compile_whitelist_pattern()
        
        # Test that whitelisted text is filtered
        assert container._whitelist_pattern is not None
        assert container._whitelist_pattern.search("test@example.com")
        assert not container._whitelist_pattern.search("other@example.com")
    
    def test_file_processor_integration(self, sample_html_file):
        """Test integration of file processor with text extraction."""
        from file_processors import HtmlProcessor
        
        processor = HtmlProcessor()
        text = processor.extract_text(sample_html_file)
        
        # Verify text was extracted correctly
        assert len(text) > 0
        assert "user@example.com" in text
        # HTML tags should be removed
        assert "<" not in text or ">" not in text
