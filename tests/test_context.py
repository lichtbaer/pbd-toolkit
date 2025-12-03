"""Tests for application context."""

from unittest.mock import Mock

import pytest

from core.context import ApplicationContext
from config import Config
from core.statistics import Statistics
from matches import PiiMatchContainer


class TestApplicationContext:
    """Tests for ApplicationContext class."""
    
    def test_context_initialization(self, mock_config):
        """Test ApplicationContext can be initialized."""
        logger = Mock()
        statistics = Statistics()
        match_container = PiiMatchContainer()
        
        context = ApplicationContext(
            config=mock_config,
            logger=logger,
            statistics=statistics,
            match_container=match_container
        )
        
        assert context.config == mock_config
        assert context.logger == logger
        assert context.statistics == statistics
        assert context.match_container == match_container
        assert context.output_format == "csv"
        assert context.output_file_path is None
    
    def test_from_cli_args(self, mock_config):
        """Test creating context from CLI arguments."""
        from argparse import Namespace
        
        args = Namespace(format="json")
        logger = Mock()
        statistics = Statistics()
        match_container = PiiMatchContainer()
        translate_func = lambda x: x
        
        context = ApplicationContext.from_cli_args(
            args=args,
            config=mock_config,
            logger=logger,
            statistics=statistics,
            match_container=match_container,
            translate_func=translate_func
        )
        
        assert context.config == mock_config
        assert context.logger == logger
        assert context.statistics == statistics
        assert context.match_container == match_container
        assert context.output_format == "json"
        assert context.translate_func == translate_func
    
    def test_translate_method(self, mock_config):
        """Test translation method."""
        logger = Mock()
        statistics = Statistics()
        match_container = PiiMatchContainer()
        
        def translate(text):
            return f"translated_{text}"
        
        context = ApplicationContext(
            config=mock_config,
            logger=logger,
            statistics=statistics,
            match_container=match_container,
            translate_func=translate
        )
        
        assert context._("test") == "translated_test"
    
    def test_context_with_output_writer(self, mock_config):
        """Test context with output writer."""
        from output.writers import CsvWriter
        import tempfile
        import os
        
        logger = Mock()
        statistics = Statistics()
        match_container = PiiMatchContainer()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            temp_path = f.name
        
        try:
            writer = CsvWriter(temp_path, include_header=True)
            
            context = ApplicationContext(
                config=mock_config,
                logger=logger,
                statistics=statistics,
                match_container=match_container,
                output_writer=writer
            )
            
            assert context.output_writer == writer
            assert context.csv_writer is not None
            assert context.csv_file_handle is not None
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
