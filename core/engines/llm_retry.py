"""Reusable retry logic for LLM API calls with exponential backoff.

Extracted from ``pydantic_ai_engine.py`` for reuse across LLM-based engines.
"""

from __future__ import annotations

import logging
import time

_logger = logging.getLogger(__name__)

# Transient error indicators that warrant a retry
RETRYABLE_EXCEPTION_SUBSTRINGS = (
    "rate limit",
    "ratelimit",
    "429",
    "503",
    "502",
    "timeout",
    "timed out",
    "connection",
    "temporarily unavailable",
    "overloaded",
    "try again",
)


def is_retryable_error(exc: Exception) -> bool:
    """Return True if the exception looks like a transient/retryable API error."""
    msg = str(exc).lower()
    return any(kw in msg for kw in RETRYABLE_EXCEPTION_SUBSTRINGS)


def retry_with_backoff(
    func,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    verbose: bool = False,
    logger: logging.Logger | None = None,
    context_name: str = "LLM",
    **kwargs,
):
    """Call *func* with exponential backoff retry on transient errors.

    Retries up to ``max_retries`` times for errors that look transient
    (rate limits, timeouts, connection resets, 5xx responses).  Non-transient
    errors are re-raised immediately without any retry.

    Args:
        func: Callable to invoke.
        *args: Positional arguments forwarded to *func*.
        max_retries: Maximum number of retry attempts.
        base_delay: Initial backoff delay in seconds (doubled each attempt).
        verbose: Whether to log retry warnings.
        logger: Logger to use for retry messages.
        context_name: Name for log messages (e.g. engine name).
        **kwargs: Keyword arguments forwarded to *func*.

    Returns:
        Return value of *func* on success.

    Raises:
        The last exception if all attempts are exhausted.
    """
    log = logger or _logger
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries or not is_retryable_error(exc):
                raise
            delay = base_delay * (2**attempt)
            if verbose:
                log.warning(
                    f"[{context_name}] Transient error (attempt {attempt + 1}/{max_retries + 1}), "
                    f"retrying in {delay:.1f}s: {exc}"
                )
            time.sleep(delay)
    # Should never reach here, but satisfy the type checker
    raise last_exc  # type: ignore[misc]
