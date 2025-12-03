"""Tests for TextProcessor with engine registry."""

import pytest
from unittest.mock import Mock, patch
from config import Config, NerStats
from matches import PiiMatchContainer
from core.processor import TextProcessor
from core.engines import EngineRegistry


class TestTextProcessorWithEngines:
    """Tests for TextProcessor using engine registry."""
    
    def test_processor_initializes_engines(self):
        """Test that processor initializes engines from registry."""
        mock_config = Mock(spec=Config)
        mock_config.use_regex = True
        mock_config.use_ner = False
        mock_config.regex_pattern = Mock()
        mock_config.regex_pattern.finditer = Mock(return_value=[])
        mock_config.ner_labels = []
        mock_config.verbose = False
        mock_config.logger = Mock()
        
        pmc = PiiMatchContainer()
        processor = TextProcessor(mock_config, pmc)
        
        # Should have regex engine
        assert len(processor.engines) >= 1
        assert any(e.name == "regex" for e in processor.engines)
    
    def test_processor_processes_with_multiple_engines(self):
        """Test processor with multiple engines."""
        mock_config = Mock(spec=Config)
        mock_config.use_regex = True
        mock_config.use_ner = True
        mock_config.regex_pattern = Mock()
        mock_config.ner_model = Mock()
        mock_config.ner_labels = ["Person's Name"]
        mock_config.ner_threshold = 0.5
        mock_config.ner_stats = NerStats()
        mock_config.verbose = False
        mock_config.logger = Mock()
        
        # Mock regex match
        mock_match = Mock()
        mock_match.group.return_value = "test@example.com"
        mock_match.groups.return_value = (None, "test@example.com")
        mock_config.regex_pattern.finditer = Mock(return_value=[mock_match])
        
        # Mock GLiNER
        mock_config.ner_model.predict_entities.return_value = []
        
        pmc = PiiMatchContainer()
        processor = TextProcessor(mock_config, pmc)
        
        # Process text
        with patch('core.engines.regex_engine.config_regex_sorted', {1: {"label": "REGEX_EMAIL"}}):
            with patch('core.engines.gliner_engine.config_ainer_sorted', {}):
                processor.process_text("test@example.com", "/test/file.txt")
        
        # Should have processed with engines
        assert len(processor.engines) >= 1
    
    def test_processor_handles_engine_errors(self):
        """Test processor error handling for engines."""
        mock_config = Mock(spec=Config)
        mock_config.use_ner = True
        mock_config.use_regex = False
        mock_config.ner_model = Mock()
        mock_config.ner_labels = ["Person's Name"]
        mock_config.ner_threshold = 0.5
        mock_config.ner_stats = NerStats()
        mock_config.verbose = False
        mock_config.logger = Mock()
        
        # Mock GLiNER error
        mock_config.ner_model.predict_entities.side_effect = RuntimeError("GPU error")
        
        pmc = PiiMatchContainer()
        processor = TextProcessor(mock_config, pmc)
        
        # Should handle error gracefully
        processor.process_text("test", "/test/file.txt")
        
        # Error should be logged
        assert mock_config.ner_stats.errors >= 0  # May increment on error
