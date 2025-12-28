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


def test_multimodal_ollama_provider_is_not_supported(minimal_config, tmp_path):
    img_path = tmp_path / "test.jpg"
    img_path.write_bytes(b"FAKEJPEG")

    minimal_config.use_ollama = True
    minimal_config.use_multimodal = True
    # Provider selection prefers ollama if use_ollama is enabled
    engine = PydanticAIEngine(minimal_config)
    results = engine.detect("", labels=["PERSON"], image_path=str(img_path))
    assert results == []
    minimal_config.logger.warning.assert_called()

