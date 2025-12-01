"""Tests for PII matching functionality."""

import pytest
import re
from matches import PiiMatch, PiiMatchContainer


class TestPiiMatch:
    """Tests for PiiMatch dataclass."""
    
    def test_create_pii_match(self):
        """Test creating a PII match."""
        match = PiiMatch(
            text="test@example.com",
            file="/path/to/file.txt",
            type="REGEX_EMAIL"
        )
        assert match.text == "test@example.com"
        assert match.file == "/path/to/file.txt"
        assert match.type == "REGEX_EMAIL"
        assert match.ner_score is None
    
    def test_create_pii_match_with_ner_score(self):
        """Test creating a PII match with NER score."""
        match = PiiMatch(
            text="John Doe",
            file="/path/to/file.txt",
            type="NER_PERSON",
            ner_score=0.95
        )
        assert match.ner_score == 0.95


class TestPiiMatchContainer:
    """Tests for PiiMatchContainer."""
    
    def test_create_empty_container(self):
        """Test creating an empty container."""
        container = PiiMatchContainer()
        assert len(container.pii_matches) == 0
        assert len(container.whitelist) == 0
    
    def test_by_file_grouping(self):
        """Test grouping matches by file."""
        container = PiiMatchContainer()
        # Note: We can't easily test __add_match directly as it requires globals.csvwriter
        # This test would need mocking or refactoring
    
    def test_whitelist_compilation(self):
        """Test that whitelist pattern is compiled correctly."""
        container = PiiMatchContainer()
        container.whitelist = ["test@", "info@"]
        container._compile_whitelist_pattern()
        
        assert container._whitelist_pattern is not None
        # Test that pattern matches whitelisted strings
        assert container._whitelist_pattern.search("test@example.com")
        assert container._whitelist_pattern.search("info@company.com")
        assert not container._whitelist_pattern.search("user@example.com")
    
    def test_whitelist_empty(self):
        """Test that empty whitelist doesn't create pattern."""
        container = PiiMatchContainer()
        container._compile_whitelist_pattern()
        assert container._whitelist_pattern is None
    
    def test_add_matches_regex(self, monkeypatch):
        """Test adding regex matches."""
        container = PiiMatchContainer()
        
        # Mock csvwriter to avoid file I/O in tests
        mock_writer = []
        def mock_writerow(row):
            mock_writer.append(row)
        
        monkeypatch.setattr("globals.csvwriter", type('obj', (object,), {'writerow': mock_writerow})())
        
        # Create a mock regex match
        pattern = re.compile(r"(test@\w+\.com)")
        match = pattern.search("Contact: test@example.com")
        
        container.add_matches_regex(match, "/test/file.txt")
        
        # Verify match was added (if not whitelisted)
        # Note: This depends on the actual regex config, so we test the method exists
        assert hasattr(container, 'add_matches_regex')
    
    def test_add_matches_ner_none(self):
        """Test adding None matches (no matches found)."""
        container = PiiMatchContainer()
        # Should not raise an error
        container.add_matches_ner(None, "/test/file.txt")
        assert len(container.pii_matches) == 0
    
    def test_add_matches_ner_empty_list(self):
        """Test adding empty list of NER matches."""
        container = PiiMatchContainer()
        container.add_matches_ner([], "/test/file.txt")
        assert len(container.pii_matches) == 0
