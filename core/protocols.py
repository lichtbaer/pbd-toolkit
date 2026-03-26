"""Structural typing protocols for duck-typed dependencies.

These protocols formalize the interfaces that were previously duck-typed
(``object | None``) in PiiMatchContainer, enabling IDE support and
compile-time type checking.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from core.matches import PiiMatch


@runtime_checkable
class OutputWriterProtocol(Protocol):
    """Protocol for output writers injected into PiiMatchContainer."""

    @property
    def supports_streaming(self) -> bool: ...

    def write_match(self, match: PiiMatch) -> None: ...

    def finalize(self, metadata: dict | None = None) -> None: ...


@runtime_checkable
class AnalyticsStoreProtocol(Protocol):
    """Protocol for analytics stores injected into PiiMatchContainer."""

    def record_finding_from_match(self, session_id: str, match: PiiMatch) -> None: ...
