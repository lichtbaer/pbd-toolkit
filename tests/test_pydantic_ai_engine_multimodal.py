"""Tests for real OpenAI-compatible multimodal image detection."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from core.engines.pydantic_ai_engine import PydanticAIEngine


@pytest.fixture()
def minimal_config() -> Mock:
    cfg = Mock()
    cfg.logger = Mock()
    cfg.verbose = True
    cfg.use_ollama = False
    cfg.use_openai_compatible = False
    cfg.use_pydantic_ai = False
    cfg.use_multimodal = True
    cfg.multimodal_model = "gpt-4o-mini"
    cfg.multimodal_api_base = "http://localhost:8000/v1"
    cfg.multimodal_api_key = "test-key"
    cfg.openai_api_base = "http://localhost:8000/v1"
    cfg.openai_api_key = "test-key"
    cfg.openai_model = "gpt-4o-mini"
    cfg.openai_timeout = 10
    cfg.multimodal_timeout = 10
    cfg.ollama_base_url = "http://localhost:11434"
    cfg.ollama_model = "llama3.2"
    cfg.ollama_timeout = 10
    cfg.pydantic_ai_provider = "openai"
    cfg.pydantic_ai_model = None
    cfg.pydantic_ai_api_key = None
    cfg.pydantic_ai_base_url = None
    cfg.ollama_labels = []
    cfg.ner_labels = ["PERSON", "EMAIL"]
    cfg.llm_max_retries = 3
    cfg.llm_retry_base_delay = 1.0
    return cfg


def test_multimodal_image_detection_parses_json(tmp_path, minimal_config, monkeypatch):
    # Create a tiny fake PNG file (content doesn't need to be valid image for base64 encoding)
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\nFAKE")

    # Mock requests.post
    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                "Sure. "
                                '{"entities":[{"text":"John Doe","type":"PERSON","confidence":0.9,"location":"top-left"}]}'
                                " Thanks."
                            )
                        }
                    }
                ]
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        assert url.endswith("/chat/completions")
        assert json["model"] == minimal_config.multimodal_model
        # Hardened mode should try structured output first
        assert "response_format" in json
        assert json["messages"][1]["content"][1]["type"] == "image_url"
        assert json["messages"][1]["content"][1]["image_url"]["url"].startswith(
            "data:image/png;base64,"
        )
        return FakeResp()

    import requests

    monkeypatch.setattr(requests, "post", fake_post)

    engine = PydanticAIEngine(minimal_config)
    results = engine.detect("", labels=["PERSON"], image_path=str(img_path))

    assert len(results) == 1
    assert results[0].text == "John Doe"
    assert results[0].entity_type == "PERSON"
    assert results[0].engine_name == "pydantic-ai"
    assert results[0].metadata["provider"] == "openai"
    assert results[0].metadata["image_path"] == str(img_path)
    assert results[0].metadata["location"] == "top-left"


def test_multimodal_strict_falls_back_without_response_format(
    tmp_path, minimal_config, monkeypatch
):
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\nFAKE")

    import requests

    calls = {"n": 0}

    class FakeRespError:
        def raise_for_status(self):
            # Simulate provider rejecting response_format (HTTP 400)
            raise requests.HTTPError("Bad Request")

        def json(self):  # pragma: no cover
            return {}

    class FakeRespOk:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"entities":[{"text":"Alice","type":"PERSON","confidence":null,"location":null}]}'
                        }
                    }
                ]
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            assert "response_format" in json
            return FakeRespError()
        # Fallback request must not include response_format
        assert "response_format" not in json
        return FakeRespOk()

    monkeypatch.setattr(requests, "post", fake_post)

    engine = PydanticAIEngine(minimal_config)
    results = engine.detect("", labels=["PERSON"], image_path=str(img_path))

    assert calls["n"] == 2
    assert len(results) == 1
    assert results[0].text == "Alice"


def test_multimodal_ollama_provider_is_not_supported(minimal_config, tmp_path):
    img_path = tmp_path / "test.jpg"
    img_path.write_bytes(b"FAKEJPEG")

    minimal_config.use_ollama = True
    minimal_config.use_multimodal = True
    # Even when text detection uses Ollama, multimodal should use the configured
    # OpenAI-compatible endpoint (vLLM/LocalAI) and remain functional.

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"entities":[{"text":"Bob","type":"PERSON","confidence":0.8,"location":null}]}'
                        }
                    }
                ]
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        assert url.startswith(minimal_config.multimodal_api_base)
        assert url.endswith("/chat/completions")
        assert json["model"] == minimal_config.multimodal_model
        return FakeResp()

    import requests

    # Monkeypatch requests.post directly (this test is sync and isolated)
    requests.post = fake_post  # type: ignore

    engine = PydanticAIEngine(minimal_config)
    results = engine.detect("", labels=["PERSON"], image_path=str(img_path))
    assert len(results) == 1
    assert results[0].text == "Bob"


def test_parse_openai_response_malformed_structure_records_skip(minimal_config):
    """A response missing the expected choices/message shape must not raise.

    Previously the ``except Exception: content = ""`` here was completely
    silent. It must now log at debug and record a skip counter so recall loss
    from malformed provider responses is visible in scan statistics.
    """
    from core import skip_counters

    skip_counters.drain()  # start clean
    engine = PydanticAIEngine(minimal_config)

    # "choices" is a string here, not a list: response_data["choices"][0] indexes
    # a character, and .get("message", ...) on that character raises AttributeError.
    result = engine._parse_openai_response_as_pii_detection({"choices": "oops"})

    assert result is None
    assert skip_counters.drain() == {"llm_response_malformed_structure": 1}
    assert minimal_config.logger.debug.called


def test_convert_results_recovers_offsets_from_source_text(minimal_config):
    """_convert_results locates each entity's offset in the source text (forward-only)."""
    from core.engines.pydantic_ai_engine import (
        PIIDetectionEntity,
        PIIDetectionResponse,
    )

    engine = PydanticAIEngine(minimal_config)
    source = "Kontakt: Max und spaeter nochmal Max bei der Firma."
    response = PIIDetectionResponse(
        entities=[
            PIIDetectionEntity(text="Max", type="PERSON", confidence=0.9),
            PIIDetectionEntity(text="Max", type="PERSON", confidence=0.9),
            PIIDetectionEntity(text="Firma", type="ORGANIZATION", confidence=0.7),
        ]
    )

    results = engine._convert_results(response, source_text=source)

    # First "Max" at index 9, second "Max" at index 33 (forward-only cursor), Firma at 45.
    assert results[0].offset == source.index("Max")
    assert results[1].offset == source.index("Max", results[0].offset + 1)
    assert results[2].offset == source.index("Firma")


def test_convert_results_offset_none_when_not_found(minimal_config):
    """An entity text absent from the source (e.g. LLM paraphrase) keeps offset None."""
    from core.engines.pydantic_ai_engine import (
        PIIDetectionEntity,
        PIIDetectionResponse,
    )

    engine = PydanticAIEngine(minimal_config)
    response = PIIDetectionResponse(
        entities=[PIIDetectionEntity(text="Nonexistent", type="PERSON", confidence=0.9)]
    )

    results = engine._convert_results(response, source_text="No match here")

    assert results[0].offset is None


def test_convert_results_no_source_text_keeps_offset_none(minimal_config):
    """Without source_text (e.g. image path) offsets remain None."""
    from core.engines.pydantic_ai_engine import (
        PIIDetectionEntity,
        PIIDetectionResponse,
    )

    engine = PydanticAIEngine(minimal_config)
    response = PIIDetectionResponse(
        entities=[PIIDetectionEntity(text="Max", type="PERSON", confidence=0.9)]
    )

    results = engine._convert_results(response)

    assert results[0].offset is None
