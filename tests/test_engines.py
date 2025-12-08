"""Tests for detection engines."""

import pytest
from unittest.mock import Mock, patch
from config import Config
from core.engines import EngineRegistry
from core.engines.regex_engine import RegexEngine
from core.engines.gliner_engine import GLiNEREngine


class TestEngineRegistry:
    """Tests for EngineRegistry."""

    def test_register_engine(self):
        """Test engine registration."""

        class TestEngine:
            name = "test"
            enabled = True

            def detect(self, text, labels=None):
                return []

            def is_available(self):
                return True

        EngineRegistry.register("test", TestEngine)
        assert EngineRegistry.is_registered("test")

    def test_get_engine(self):
        """Test getting engine instance."""
        mock_config = Mock(spec=Config)
        mock_config.use_regex = True
        mock_config.regex_pattern = Mock()

        engine = EngineRegistry.get_engine("regex", mock_config)
        assert engine is not None
        assert engine.name == "regex"

    def test_get_nonexistent_engine(self):
        """Test getting non-existent engine."""
        mock_config = Mock()
        engine = EngineRegistry.get_engine("nonexistent", mock_config)
        assert engine is None

    def test_list_engines(self):
        """Test listing registered engines."""
        engines = EngineRegistry.list_engines()
        assert "regex" in engines
        assert "gliner" in engines


class TestRegexEngine:
    """Tests for RegexEngine."""

    def test_regex_engine_initialization(self):
        """Test regex engine initialization."""
        mock_config = Mock(spec=Config)
        mock_config.use_regex = True
        mock_config.regex_pattern = Mock()
        mock_config.regex_pattern.finditer = Mock(return_value=[])

        engine = RegexEngine(mock_config)
        assert engine.name == "regex"
        assert engine.enabled is True

    def test_regex_engine_not_enabled(self):
        """Test regex engine when disabled."""
        mock_config = Mock(spec=Config)
        mock_config.use_regex = False
        mock_config.regex_pattern = None

        engine = RegexEngine(mock_config)
        assert engine.is_available() is False

    def test_regex_engine_detect(self):
        """Test regex engine detection."""
        mock_config = Mock(spec=Config)
        mock_config.use_regex = True
        mock_config.regex_pattern = Mock()

        # Mock regex match
        mock_match = Mock()
        mock_match.group.return_value = "test@example.com"
        mock_match.groups.return_value = (None, "test@example.com", None)

        mock_config.regex_pattern.finditer = Mock(return_value=[mock_match])

        # Mock config_regex_sorted
        with patch(
            "core.engines.regex_engine.config_regex_sorted",
            {1: {"label": "REGEX_EMAIL"}},
        ):
            engine = RegexEngine(mock_config)
            results = engine.detect("test@example.com")

            assert len(results) == 1
            assert results[0].text == "test@example.com"
            assert results[0].engine_name == "regex"
            assert results[0].entity_type == "REGEX_EMAIL"

    def test_regex_engine_validation(self):
        """Test regex engine with validation."""
        mock_config = Mock(spec=Config)
        mock_config.use_regex = True
        mock_config.regex_pattern = Mock()

        # Mock credit card match
        mock_match = Mock()
        mock_match.group.return_value = "4111111111111111"
        mock_match.groups.return_value = (
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            "4111111111111111",
        )

        mock_config.regex_pattern.finditer = Mock(return_value=[mock_match])

        # Mock config with validation
        config_entry = {"label": "REGEX_CREDIT_CARD", "validation": "luhn"}

        with patch("core.engines.regex_engine.config_regex_sorted", {11: config_entry}):
            with patch(
                "core.engines.regex_engine.CreditCardValidator"
            ) as mock_validator:
                mock_validator.validate.return_value = (True, "visa")

                engine = RegexEngine(mock_config)
                engine.detect("4111111111111111")

                # Should validate and include if valid
                mock_validator.validate.assert_called()


class TestGLiNEREngine:
    """Tests for GLiNEREngine."""

    def test_gliner_engine_initialization(self):
        """Test GLiNER engine initialization."""
        mock_config = Mock(spec=Config)
        mock_config.use_ner = True
        mock_config.ner_model = Mock()
        mock_config.ner_labels = ["Person's Name"]
        mock_config.ner_threshold = 0.5
        mock_config.logger = Mock()

        engine = GLiNEREngine(mock_config)
        assert engine.name == "gliner"
        assert engine.enabled is True

    def test_gliner_engine_not_enabled(self):
        """Test GLiNER engine when disabled."""
        mock_config = Mock(spec=Config)
        mock_config.use_ner = False
        mock_config.ner_model = None

        engine = GLiNEREngine(mock_config)
        assert engine.is_available() is False

    def test_gliner_engine_detect(self):
        """Test GLiNER engine detection."""
        mock_config = Mock(spec=Config)
        mock_config.use_ner = True
        mock_config.ner_model = Mock()
        mock_config.ner_labels = ["Person's Name"]
        mock_config.ner_threshold = 0.5
        mock_config.logger = Mock()

        # Mock GLiNER model response
        mock_config.ner_model.predict_entities.return_value = [
            {"text": "John Doe", "label": "Person's Name", "score": 0.95}
        ]

        # Mock config_ainer_sorted
        with patch(
            "core.engines.gliner_engine.config_ainer_sorted",
            {"Person's Name": {"label": "NER_PERSON"}},
        ):
            engine = GLiNEREngine(mock_config)
            results = engine.detect("John Doe is here")

            assert len(results) == 1
            assert results[0].text == "John Doe"
            assert results[0].engine_name == "gliner"
            assert results[0].entity_type == "NER_PERSON"
            assert results[0].confidence == 0.95

    def test_gliner_engine_error_handling(self):
        """Test GLiNER engine error handling."""
        mock_config = Mock(spec=Config)
        mock_config.use_ner = True
        mock_config.ner_model = Mock()
        mock_config.ner_labels = ["Person's Name"]
        mock_config.ner_threshold = 0.5
        mock_config.logger = Mock()

        # Mock error
        mock_config.ner_model.predict_entities.side_effect = Exception("Model error")

        engine = GLiNEREngine(mock_config)
        results = engine.detect("test")

        assert len(results) == 0
        mock_config.logger.warning.assert_called()


class TestSpacyNEREngine:
    """Tests for SpacyNEREngine."""

    @pytest.mark.skipif(True, reason="Requires spaCy to be installed")
    def test_spacy_engine_initialization(self):
        """Test spaCy engine initialization."""
        mock_config = Mock(spec=Config)
        mock_config.use_spacy_ner = True
        mock_config.spacy_model_name = "de_core_news_sm"
        mock_config.logger = Mock()

        from core.engines.spacy_engine import SpacyNEREngine

        engine = SpacyNEREngine(mock_config)
        assert engine.name == "spacy-ner"

    def test_spacy_engine_not_installed(self):
        """Test spaCy engine when spaCy is not installed."""
        mock_config = Mock(spec=Config)
        mock_config.use_spacy_ner = True
        mock_config.spacy_model_name = "de_core_news_sm"
        mock_config.logger = Mock()

        with patch(
            "builtins.__import__", side_effect=ImportError("No module named 'spacy'")
        ):
            from core.engines.spacy_engine import SpacyNEREngine

            engine = SpacyNEREngine(mock_config)
            assert engine.is_available() is False

        # Tests for old engines (OllamaEngine, OpenAICompatibleEngine) removed
        # These engines have been replaced by PydanticAIEngine
        # See tests for PydanticAIEngine instead
        results = engine.detect("test")

        assert len(results) == 0
        mock_config.logger.warning.assert_called()
