"""Tests for multimodal detection engine."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from core.engines.multimodal_engine import MultimodalEngine
from config import Config


class TestMultimodalEngine:
    """Tests for MultimodalEngine class."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock config for multimodal engine."""
        config = Mock(spec=Config)
        config.use_multimodal = True
        config.multimodal_api_base = "https://api.openai.com/v1"
        config.multimodal_api_key = "test-key"
        config.multimodal_model = "gpt-4-vision-preview"
        config.multimodal_timeout = 60
        config.openai_api_base = "https://api.openai.com/v1"
        config.openai_api_key = None
        config.logger = Mock()
        config.logger.warning = Mock()
        config.logger.error = Mock()
        config.logger.debug = Mock()
        return config
    
    def test_engine_initialization(self, mock_config):
        """Test MultimodalEngine can be initialized."""
        engine = MultimodalEngine(mock_config)
        assert engine.name == "multimodal"
        assert engine.enabled is True
        assert engine.api_base == "https://api.openai.com/v1"
        assert engine.api_key == "test-key"
        assert engine.model == "gpt-4-vision-preview"
    
    def test_engine_initialization_disabled(self, mock_config):
        """Test MultimodalEngine when disabled."""
        mock_config.use_multimodal = False
        engine = MultimodalEngine(mock_config)
        assert engine.enabled is False
        assert engine.detect("", None, None) == []
    
    def test_detect_no_image_path(self, mock_config):
        """Test detect returns empty list when no image path provided."""
        engine = MultimodalEngine(mock_config)
        result = engine.detect("", None, None)
        assert result == []
    
    def test_detect_nonexistent_file(self, mock_config):
        """Test detect returns empty list for nonexistent file."""
        engine = MultimodalEngine(mock_config)
        result = engine.detect("", None, "/nonexistent/file.jpg")
        assert result == []
        mock_config.logger.warning.assert_called()
    
    @patch('core.engines.multimodal_engine.requests')
    def test_detect_success(self, mock_requests, mock_config, temp_dir):
        """Test successful detection."""
        # Create a dummy image file
        test_file = Path(temp_dir) / "test.jpg"
        test_file.write_bytes(b"fake image data")
        
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"entities": [{"text": "John Doe", "type": "PERSON", "confidence": 0.95, "location": "top left"}]}'
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        mock_requests.post.return_value = mock_response
        
        engine = MultimodalEngine(mock_config)
        results = engine.detect("", None, str(test_file))
        
        assert len(results) == 1
        assert results[0].text == "John Doe"
        assert results[0].entity_type == "PERSON"
        assert results[0].confidence == 0.95
        assert results[0].engine_name == "multimodal"
        assert "image_path" in results[0].metadata
    
    @patch('core.engines.multimodal_engine.requests')
    def test_detect_api_error(self, mock_requests, mock_config, temp_dir):
        """Test detection handles API errors."""
        test_file = Path(temp_dir) / "test.jpg"
        test_file.write_bytes(b"fake image data")
        
        mock_requests.post.side_effect = Exception("API Error")
        
        engine = MultimodalEngine(mock_config)
        results = engine.detect("", None, str(test_file))
        
        assert results == []
        mock_config.logger.warning.assert_called()
    
    @patch('core.engines.multimodal_engine.requests')
    def test_detect_invalid_json(self, mock_requests, mock_config, temp_dir):
        """Test detection handles invalid JSON response."""
        test_file = Path(temp_dir) / "test.jpg"
        test_file.write_bytes(b"fake image data")
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "invalid json"
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        mock_requests.post.return_value = mock_response
        
        engine = MultimodalEngine(mock_config)
        results = engine.detect("", None, str(test_file))
        
        assert results == []
    
    def test_create_prompt(self, mock_config):
        """Test prompt creation."""
        engine = MultimodalEngine(mock_config)
        prompt = engine._create_prompt(["PERSON", "EMAIL"])
        
        assert "PERSON" in prompt
        assert "EMAIL" in prompt
        assert "PII" in prompt
        assert "JSON" in prompt
    
    def test_create_prompt_no_labels(self, mock_config):
        """Test prompt creation without labels."""
        engine = MultimodalEngine(mock_config)
        prompt = engine._create_prompt(None)
        
        assert "all PII types" in prompt
        assert "JSON" in prompt
    
    def test_parse_response_valid(self, mock_config):
        """Test parsing valid JSON response."""
        engine = MultimodalEngine(mock_config)
        content = '{"entities": [{"text": "test@example.com", "type": "EMAIL", "confidence": 0.9}]}'
        
        results = engine._parse_response(content, "/test/image.jpg")
        
        assert len(results) == 1
        assert results[0].text == "test@example.com"
        assert results[0].entity_type == "EMAIL"
        assert results[0].confidence == 0.9
    
    def test_parse_response_invalid(self, mock_config):
        """Test parsing invalid JSON response."""
        engine = MultimodalEngine(mock_config)
        results = engine._parse_response("invalid json", "/test/image.jpg")
        
        assert results == []
    
    @patch('core.engines.multimodal_engine.requests')
    def test_is_available_success(self, mock_requests, mock_config):
        """Test availability check when API is accessible."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        
        engine = MultimodalEngine(mock_config)
        assert engine.is_available() is True
    
    @patch('core.engines.multimodal_engine.requests')
    def test_is_available_failure(self, mock_requests, mock_config):
        """Test availability check when API is not accessible."""
        mock_requests.get.side_effect = Exception("Connection error")
        
        engine = MultimodalEngine(mock_config)
        assert engine.is_available() is False
    
    def test_is_available_no_api_key(self, mock_config):
        """Test availability check when no API key."""
        mock_config.multimodal_api_key = None
        engine = MultimodalEngine(mock_config)
        assert engine.is_available() is False
