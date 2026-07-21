"""Tests for detection engines."""

from unittest.mock import Mock, patch

import pytest

from core.config import Config
from core.engines import EngineRegistry
from core.engines.gliner_engine import GLiNEREngine
from core.engines.regex_engine import RegexEngine


class TestEngineRegistry:
    """Tests for EngineRegistry."""

    def test_register_engine(self):
        """Test engine registration on an isolated registry.

        Uses ``create_isolated()`` rather than the global ``EngineRegistry`` so
        this test cannot leak a "test" engine into the process-wide registry
        for the rest of the suite (issue #78).
        """

        class TestEngine:
            name = "test"
            enabled = True

            def detect(self, text, labels=None):
                return []

            def is_available(self):
                return True

        registry = EngineRegistry.create_isolated()
        registry.register("test", TestEngine)
        assert registry.is_registered("test")
        assert not EngineRegistry.is_registered("test")

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


class TestEngineRegistryIsolation:
    """Tests for EngineRegistry.create_isolated() / snapshot() (issue #78)."""

    def test_create_isolated_starts_empty_and_does_not_affect_global(self):
        isolated = EngineRegistry.create_isolated()
        assert isolated.list_engines() == []

        class TestEngine:
            name = "isolated-only"
            enabled = True

            def detect(self, text, labels=None):
                return []

            def is_available(self):
                return True

        isolated.register("isolated-only", TestEngine)
        assert isolated.is_registered("isolated-only")
        assert not EngineRegistry.is_registered("isolated-only")

    def test_snapshot_is_a_copy_not_a_live_view(self):
        snapshot = EngineRegistry.snapshot()
        assert set(snapshot.list_engines()) == set(EngineRegistry.list_engines())

        class LateEngine:
            name = "late"
            enabled = True

            def detect(self, text, labels=None):
                return []

            def is_available(self):
                return True

        # Registering on the snapshot must not leak into the global registry.
        snapshot.register("late", LateEngine)
        assert not EngineRegistry.is_registered("late")

    def test_two_isolated_registries_do_not_leak_into_each_other(self):
        """One test's custom registry must not affect another (issue #78 test notes)."""

        class EngineA:
            name = "a-only"
            enabled = True

            def detect(self, text, labels=None):
                return []

            def is_available(self):
                return True

        registry_1 = EngineRegistry.create_isolated()
        registry_1.register("a-only", EngineA)

        registry_2 = EngineRegistry.create_isolated()

        assert registry_1.is_registered("a-only")
        assert not registry_2.is_registered("a-only")


class TestEngineRegistryOptionalDependencies:
    """Optional engines degrade gracefully when their dependency is unavailable.

    ``core/engines/__init__.py`` guards optional-engine class imports with
    ``try/except ImportError`` so a missing dependency never prevents the rest
    of the module (and thus ``core.processor``) from importing. The second,
    independent layer is exercised here: even when an engine class *is*
    registered, ``EngineRegistry.get_engine`` must return ``None`` (not raise)
    when the engine reports itself unavailable at construction time.
    """

    def test_get_engine_pydantic_ai_unavailable_dependency_returns_none(self):
        import core.engines.pydantic_ai_engine as pydantic_ai_engine

        mock_config = Mock()
        mock_config.logger = Mock()
        mock_config.verbose = False
        mock_config.use_ollama = False
        mock_config.use_openai_compatible = False
        mock_config.use_multimodal = False
        mock_config.use_pydantic_ai = True

        with patch.object(pydantic_ai_engine, "_PYDANTIC_AI_AVAILABLE", False):
            engine = EngineRegistry.get_engine("pydantic-ai", mock_config)

        assert engine is None

    def test_get_engine_vector_search_unavailable_dependency_returns_none(self):
        from core.indexer.document_indexer import DocumentIndexer

        mock_config = Mock(spec=Config)
        mock_config.use_vector_search = True
        mock_config.use_vector_triage = False
        mock_config.vector_threshold = 0.75
        mock_config.vector_model = "sentence-transformers/all-MiniLM-L6-v2"
        mock_config.vector_save_index = None
        mock_config.vector_load_index = None
        mock_config.vector_custom_exemplars = None
        mock_config.verbose = False
        mock_config.logger = Mock()

        with patch.object(DocumentIndexer, "is_available", return_value=False):
            engine = EngineRegistry.get_engine("vector-search", mock_config)

        assert engine is None


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
        mock_match.start.return_value = 0

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
        mock_match.start.return_value = 0
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

    def test_gliner_engine_propagates_offset(self):
        """GLiNER's entity 'start' is propagated to DetectionResult.offset."""
        mock_config = Mock(spec=Config)
        mock_config.use_ner = True
        mock_config.ner_model = Mock()
        mock_config.ner_labels = ["Person's Name"]
        mock_config.ner_threshold = 0.5
        mock_config.logger = Mock()

        mock_config.ner_model.predict_entities.return_value = [
            {
                "text": "John Doe",
                "label": "Person's Name",
                "score": 0.95,
                "start": 5,
                "end": 13,
            }
        ]

        with patch(
            "core.engines.gliner_engine.config_ainer_sorted",
            {"Person's Name": {"label": "NER_PERSON"}},
        ):
            engine = GLiNEREngine(mock_config)
            results = engine.detect("Hi   John Doe is here")

        assert len(results) == 1
        assert results[0].offset == 5

    def test_gliner_engine_offset_none_when_absent(self):
        """When the model omits 'start', offset stays None (robust fallback)."""
        mock_config = Mock(spec=Config)
        mock_config.use_ner = True
        mock_config.ner_model = Mock()
        mock_config.ner_labels = ["Person's Name"]
        mock_config.ner_threshold = 0.5
        mock_config.logger = Mock()

        mock_config.ner_model.predict_entities.return_value = [
            {"text": "John Doe", "label": "Person's Name", "score": 0.95}
        ]

        with patch(
            "core.engines.gliner_engine.config_ainer_sorted",
            {"Person's Name": {"label": "NER_PERSON"}},
        ):
            engine = GLiNEREngine(mock_config)
            results = engine.detect("John Doe is here")

        assert len(results) == 1
        assert results[0].offset is None

    def test_gliner_per_label_threshold_filters(self):
        """A per-label threshold drops entities below it while keeping others."""
        mock_config = Mock(spec=Config)
        mock_config.use_ner = True
        mock_config.ner_model = Mock()
        mock_config.ner_labels = ["Person's Name", "Health Data"]
        mock_config.ner_threshold = 0.3
        # Person must clear 0.9; health keeps the global 0.3.
        mock_config.ner_label_thresholds = {"Person's Name": 0.9}
        mock_config.logger = Mock()

        mock_config.ner_model.predict_entities.return_value = [
            {"text": "Maybe Name", "label": "Person's Name", "score": 0.55},
            {"text": "Diabetes", "label": "Health Data", "score": 0.40},
        ]

        with patch(
            "core.engines.gliner_engine.config_ainer_sorted",
            {
                "Person's Name": {"label": "NER_PERSON"},
                "Health Data": {"label": "NER_HEALTH"},
            },
        ):
            engine = GLiNEREngine(mock_config)
            results = engine.detect("text")

        # The model is queried at the lowest relevant threshold (0.3).
        _, kwargs = mock_config.ner_model.predict_entities.call_args
        assert kwargs["threshold"] == 0.3
        # Person 0.55 < 0.9 -> dropped; Health 0.40 >= 0.3 -> kept.
        types = {r.entity_type for r in results}
        assert types == {"NER_HEALTH"}

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

        real_import = __import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "spacy" or name.startswith("spacy."):
                raise ImportError("No module named 'spacy'")
            return real_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=fake_import):
            from core.engines.spacy_engine import SpacyNEREngine

            engine = SpacyNEREngine(mock_config)
            assert engine.is_available() is False

        # Tests for old engines (OllamaEngine, OpenAICompatibleEngine) removed
        # These engines have been replaced by PydanticAIEngine
        # See tests for PydanticAIEngine instead
        results = engine.detect("test")

        assert len(results) == 0
        mock_config.logger.warning.assert_called()

    def test_spacy_engine_propagates_offset(self):
        """spaCy's ent.start_char is propagated to DetectionResult.offset."""
        from core.engines.spacy_engine import SpacyNEREngine

        mock_config = Mock(spec=Config)
        # Keep _load_model a no-op by disabling, then inject a fake model.
        mock_config.use_spacy_ner = False
        mock_config.spacy_model_name = "de_core_news_sm"
        mock_config.logger = Mock()

        class _Ent:
            def __init__(self, text, label_, start_char, end_char):
                self.text = text
                self.label_ = label_
                self.label = 0
                self.start_char = start_char
                self.end_char = end_char

        class _Doc:
            ents = [_Ent("Anna Schmidt", "PER", 7, 19)]

        engine = SpacyNEREngine(mock_config)
        engine.enabled = True
        engine.model = Mock(return_value=_Doc())

        results = engine.detect("Hallo, Anna Schmidt!")

        assert len(results) == 1
        assert results[0].entity_type == "NER_PERSON"
        assert results[0].offset == 7
        assert results[0].metadata["start_char"] == 7
