"""Tests for the text-detection path of PydanticAIEngine.

Covers provider/model/API-key resolution, well-formed and malformed LLM
responses, and retry/backoff behavior. No network access: ``agent.run_sync``
is monkeypatched (via ``_get_agent``) rather than exercising real PydanticAI
provider/model construction.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.engines.pydantic_ai_engine import (
    PIIDetectionEntity,
    PIIDetectionResponse,
    PydanticAIEngine,
)


@pytest.fixture()
def base_config() -> Mock:
    cfg = Mock()
    cfg.logger = Mock()
    cfg.verbose = False
    cfg.use_ollama = False
    cfg.use_openai_compatible = False
    cfg.use_pydantic_ai = True
    cfg.use_multimodal = False
    cfg.pydantic_ai_provider = "openai"
    cfg.pydantic_ai_model = "gpt-4o-mini"
    cfg.pydantic_ai_api_key = "sk-test"
    cfg.pydantic_ai_base_url = None
    cfg.openai_api_base = "https://api.openai.com/v1"
    cfg.openai_api_key = None
    cfg.openai_model = "gpt-4o-mini"
    cfg.openai_timeout = 30
    cfg.ollama_base_url = "http://localhost:11434"
    cfg.ollama_model = "llama3.2"
    cfg.ollama_timeout = 30
    cfg.multimodal_model = "gpt-4-vision-preview"
    cfg.multimodal_api_base = None
    cfg.multimodal_api_key = None
    cfg.multimodal_timeout = 60
    cfg.ollama_labels = []
    cfg.ner_labels = []
    cfg.llm_max_retries = 3
    cfg.llm_retry_base_delay = 0.0
    cfg.engine_concurrency_limits = {}
    return cfg


class TestProviderResolution:
    def test_ollama_provider(self, base_config):
        base_config.use_ollama = True
        base_config.use_pydantic_ai = False
        engine = PydanticAIEngine(base_config)
        assert engine.provider == "ollama"
        assert engine.model == "llama3.2"
        assert engine.api_key is None
        assert engine.base_url == "http://localhost:11434"
        assert engine.timeout == 30

    def test_multimodal_implies_openai_provider(self, base_config):
        base_config.use_multimodal = True
        base_config.use_pydantic_ai = False
        engine = PydanticAIEngine(base_config)
        assert engine.provider == "openai"
        assert engine.model == "gpt-4-vision-preview"

    def test_openai_compatible_provider(self, base_config):
        base_config.use_openai_compatible = True
        base_config.use_pydantic_ai = False
        engine = PydanticAIEngine(base_config)
        assert engine.provider == "openai"
        assert engine.model == "gpt-4o-mini"

    def test_explicit_pydantic_ai_provider_and_model(self, base_config):
        base_config.pydantic_ai_provider = "anthropic"
        base_config.pydantic_ai_model = "claude-sonnet"
        engine = PydanticAIEngine(base_config)
        assert engine.provider == "anthropic"
        assert engine.model == "claude-sonnet"

    def test_default_provider_is_openai(self, base_config):
        base_config.use_pydantic_ai = False
        engine = PydanticAIEngine(base_config)
        assert engine.provider == "openai"
        assert engine.model == "gpt-4o-mini"

    def test_enabled_requires_a_use_flag(self, base_config):
        base_config.use_pydantic_ai = False
        engine = PydanticAIEngine(base_config)
        assert engine.enabled is False


class TestApiKeyResolution:
    def test_ollama_never_needs_api_key(self, base_config):
        base_config.use_ollama = True
        base_config.use_pydantic_ai = False
        engine = PydanticAIEngine(base_config)
        assert engine.api_key is None

    def test_pydantic_ai_explicit_key_used(self, base_config):
        engine = PydanticAIEngine(base_config)
        assert engine.api_key == "sk-test"

    def test_openai_env_var_fallback(self, base_config, monkeypatch):
        base_config.use_pydantic_ai = False
        base_config.openai_api_key = None
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")
        engine = PydanticAIEngine(base_config)
        assert engine.api_key == "env-key"

    def test_explicit_pydantic_ai_anthropic_without_key_is_none(
        self, base_config, monkeypatch
    ):
        """When --pydantic-ai is used, only pydantic_ai_api_key is consulted;
        provider-specific env vars (e.g. ANTHROPIC_API_KEY) are intentionally
        not used as a fallback in this path (see `_get_api_key`)."""
        base_config.pydantic_ai_provider = "anthropic"
        base_config.pydantic_ai_api_key = None
        monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-env-key")
        engine = PydanticAIEngine(base_config)
        assert engine.provider == "anthropic"
        assert engine.api_key is None


class TestIsAvailable:
    def test_disabled_engine_unavailable(self, base_config):
        base_config.use_pydantic_ai = False
        engine = PydanticAIEngine(base_config)
        assert engine.is_available() is False

    def test_pydantic_ai_installed_marks_available(self, base_config, monkeypatch):
        monkeypatch.setattr(
            "core.engines.pydantic_ai_engine._PYDANTIC_AI_AVAILABLE", True
        )
        engine = PydanticAIEngine(base_config)
        assert engine.is_available() is True

    def test_pydantic_ai_missing_marks_unavailable(self, base_config, monkeypatch):
        monkeypatch.setattr(
            "core.engines.pydantic_ai_engine._PYDANTIC_AI_AVAILABLE", False
        )
        engine = PydanticAIEngine(base_config)
        assert engine.is_available() is False

    def test_multimodal_requires_requests(self, base_config, monkeypatch):
        base_config.use_multimodal = True
        engine = PydanticAIEngine(base_config)
        assert engine.is_available() is True  # requests is a hard dependency


class TestDetectTextPath:
    """Exercise engine.detect() with a faked agent (no PydanticAI/network)."""

    def _engine_with_fake_agent(self, base_config, run_sync_impl):
        engine = PydanticAIEngine(base_config)
        fake_agent = Mock()
        fake_agent.run_sync = run_sync_impl
        engine._get_agent = Mock(return_value=fake_agent)
        return engine

    def test_detect_returns_empty_when_disabled(self, base_config):
        base_config.use_pydantic_ai = False
        engine = PydanticAIEngine(base_config)
        assert engine.detect("some text") == []

    def test_detect_well_formed_response_object_output(self, base_config):
        response = PIIDetectionResponse(
            entities=[
                PIIDetectionEntity(
                    text="Max Mustermann", type="PERSON", confidence=0.95
                )
            ]
        )
        engine = self._engine_with_fake_agent(
            base_config, lambda prompt: SimpleNamespace(output=response)
        )

        results = engine.detect("Kontakt: Max Mustermann", labels=["PERSON"])

        assert len(results) == 1
        assert results[0].text == "Max Mustermann"
        assert results[0].entity_type == "PERSON"
        assert results[0].engine_name == "pydantic-ai"

    def test_detect_well_formed_response_via_legacy_data_attr(self, base_config):
        """Older PydanticAI versions exposed `.data` instead of `.output`."""
        response = PIIDetectionResponse(
            entities=[PIIDetectionEntity(text="jane@x.com", type="EMAIL")]
        )
        engine = self._engine_with_fake_agent(
            base_config, lambda prompt: SimpleNamespace(data=response)
        )

        results = engine.detect("Email: jane@x.com")

        assert len(results) == 1
        assert results[0].text == "jane@x.com"

    def test_detect_dict_output_validated_against_schema(self, base_config):
        engine = self._engine_with_fake_agent(
            base_config,
            lambda prompt: SimpleNamespace(
                output={"entities": [{"text": "Berlin", "type": "LOCATION"}]}
            ),
        )

        results = engine.detect("lives in Berlin")

        assert len(results) == 1
        assert results[0].text == "Berlin"

    def test_detect_malformed_dict_output_records_skip_and_returns_empty(
        self, base_config
    ):
        from core import skip_counters

        skip_counters.drain()
        engine = self._engine_with_fake_agent(
            base_config,
            # `entities` must be a list of objects; a plain string fails schema
            # validation and should be treated as a malformed response.
            lambda prompt: SimpleNamespace(output={"entities": "not-a-list"}),
        )

        results = engine.detect("some text")

        assert results == []
        assert skip_counters.drain() == {"llm_response_parse_failed": 1}

    def test_detect_string_output_with_embedded_json(self, base_config):
        engine = self._engine_with_fake_agent(
            base_config,
            lambda prompt: SimpleNamespace(
                output='Sure! {"entities":[{"text":"Alice","type":"PERSON"}]} done.'
            ),
        )

        results = engine.detect("text mentioning Alice")

        assert len(results) == 1
        assert results[0].text == "Alice"

    def test_detect_string_output_unparseable_records_skip(self, base_config):
        from core import skip_counters

        skip_counters.drain()
        engine = self._engine_with_fake_agent(
            base_config, lambda prompt: SimpleNamespace(output="no json here at all")
        )

        results = engine.detect("some text")

        assert results == []
        assert skip_counters.drain() == {}

    def test_detect_unexpected_output_type_logs_warning_and_returns_empty(
        self, base_config
    ):
        engine = self._engine_with_fake_agent(
            base_config, lambda prompt: SimpleNamespace(output=12345)
        )

        results = engine.detect("some text")

        assert results == []
        assert base_config.logger.warning.called

    def test_detect_exception_from_agent_is_caught_and_logged(self, base_config):
        def raise_error(prompt):
            raise RuntimeError("connection refused")

        engine = self._engine_with_fake_agent(base_config, raise_error)

        results = engine.detect("some text")

        assert results == []
        assert base_config.logger.warning.called

    def test_detect_retries_transient_error_then_succeeds(
        self, base_config, monkeypatch
    ):
        monkeypatch.setattr("core.engines.llm_retry.time.sleep", lambda _s: None)
        response = PIIDetectionResponse(
            entities=[PIIDetectionEntity(text="Retry Person", type="PERSON")]
        )
        calls = {"n": 0}

        def run_sync(prompt):
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("503 Service Unavailable")
            return SimpleNamespace(output=response)

        engine = self._engine_with_fake_agent(base_config, run_sync)

        results = engine.detect("some text")

        assert calls["n"] == 2
        assert len(results) == 1
        assert results[0].text == "Retry Person"

    def test_detect_exhausts_retries_returns_empty_not_raises(
        self, base_config, monkeypatch
    ):
        monkeypatch.setattr("core.engines.llm_retry.time.sleep", lambda _s: None)
        base_config.llm_max_retries = 1

        def always_fails(prompt):
            raise RuntimeError("timeout")

        engine = self._engine_with_fake_agent(base_config, always_fails)

        results = engine.detect("some text")

        # detect() catches all exceptions (including retry exhaustion) and
        # degrades to an empty result rather than propagating.
        assert results == []
