"""Tests for the shared LLM retry-with-backoff helper."""

from __future__ import annotations

import logging

import pytest

from core.engines.llm_retry import is_retryable_error, retry_with_backoff


class TestIsRetryableError:
    @pytest.mark.parametrize(
        "message",
        [
            "Rate limit exceeded",
            "RATELIMIT hit",
            "HTTP 429 Too Many Requests",
            "503 Service Unavailable",
            "502 Bad Gateway",
            "Request timeout",
            "Connection timed out",
            "Connection reset by peer",
            "Service temporarily unavailable",
            "Server overloaded",
            "please try again later",
        ],
    )
    def test_retryable_messages(self, message):
        assert is_retryable_error(Exception(message)) is True

    @pytest.mark.parametrize(
        "message",
        [
            "401 Unauthorized",
            "403 Forbidden",
            "404 model not found",
            "Invalid API key",
            "Malformed request body",
        ],
    )
    def test_non_retryable_messages(self, message):
        assert is_retryable_error(Exception(message)) is False


class TestRetryWithBackoff:
    def test_succeeds_on_first_attempt_without_sleeping(self, monkeypatch):
        sleeps = []
        monkeypatch.setattr("core.engines.llm_retry.time.sleep", sleeps.append)

        calls = {"n": 0}

        def func():
            calls["n"] += 1
            return "ok"

        result = retry_with_backoff(func, max_retries=3, base_delay=1.0)

        assert result == "ok"
        assert calls["n"] == 1
        assert sleeps == []

    def test_retries_transient_error_then_succeeds(self, monkeypatch):
        sleeps = []
        monkeypatch.setattr("core.engines.llm_retry.time.sleep", sleeps.append)

        calls = {"n": 0}

        def func():
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("503 Service Unavailable")
            return "recovered"

        result = retry_with_backoff(func, max_retries=5, base_delay=1.0)

        assert result == "recovered"
        assert calls["n"] == 3
        # Exponential backoff: 1s, then 2s between the two failed attempts.
        assert sleeps == [1.0, 2.0]

    def test_exhausts_retries_and_raises_last_exception(self, monkeypatch):
        sleeps = []
        monkeypatch.setattr("core.engines.llm_retry.time.sleep", sleeps.append)

        def func():
            raise RuntimeError("timeout while connecting")

        with pytest.raises(RuntimeError, match="timeout while connecting"):
            retry_with_backoff(func, max_retries=2, base_delay=0.5)

        # 2 retries => 2 sleeps (after attempt 1 and attempt 2), then attempt 3 raises.
        assert sleeps == [0.5, 1.0]

    def test_non_retryable_error_raises_immediately_without_sleep(self, monkeypatch):
        sleeps = []
        monkeypatch.setattr("core.engines.llm_retry.time.sleep", sleeps.append)

        calls = {"n": 0}

        def func():
            calls["n"] += 1
            raise ValueError("401 Unauthorized")

        with pytest.raises(ValueError, match="401 Unauthorized"):
            retry_with_backoff(func, max_retries=3, base_delay=1.0)

        assert calls["n"] == 1
        assert sleeps == []

    def test_passes_args_and_kwargs_through(self, monkeypatch):
        monkeypatch.setattr("core.engines.llm_retry.time.sleep", lambda _s: None)

        def func(a, b, c=None):
            return (a, b, c)

        result = retry_with_backoff(func, "x", "y", c="z", max_retries=1)
        assert result == ("x", "y", "z")

    def test_verbose_logs_retry_warning(self, monkeypatch):
        monkeypatch.setattr("core.engines.llm_retry.time.sleep", lambda _s: None)
        logger = logging.getLogger("test-llm-retry")
        messages = []
        monkeypatch.setattr(logger, "warning", lambda msg: messages.append(msg))

        calls = {"n": 0}

        def func():
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("429 rate limit")
            return "ok"

        result = retry_with_backoff(
            func,
            max_retries=2,
            base_delay=0.1,
            verbose=True,
            logger=logger,
            context_name="unit-test",
        )

        assert result == "ok"
        assert len(messages) == 1
        assert "unit-test" in messages[0]
