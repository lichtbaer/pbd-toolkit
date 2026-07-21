"""Registry for detection engines.

Registration lifecycle
-----------------------
Built-in and optional engines register themselves exactly once, at import time,
via ``core/engines/__init__.py`` calling ``EngineRegistry.register(...)`` at
module scope. Application code (CLI, API, scanner workers) never registers
engines itself; it only reads the registry through ``get_engine``/``list_engines``.
Because registration happens before any worker thread exists, ``register()``
itself needs no lock.

Thread safety
-------------
``_engines`` is a plain class-level dict. Reads (``get_engine``, ``list_engines``,
``is_registered``) are safe to call concurrently from multiple scanner threads
because CPython's GIL makes individual dict reads atomic, and the table is not
mutated once import-time registration has finished. ``register()`` itself is
*not* thread-safe and must only be called during import or from a single-threaded
setup/test context — never concurrently with a running scan.

Isolation for tests and API/server use
---------------------------------------
Because ``_engines`` is shared, process-wide state, calling ``register()``
directly in a test leaks a fake engine into every test that runs afterwards in
the same process. Use ``EngineRegistry.isolated()`` to scope registrations to a
``with`` block; the previous table is restored on exit even if the block raises.
Use ``EngineRegistry.snapshot()`` to obtain an independent, read-only view of the
engines registered at a point in time (e.g. for a long-lived API/server process
that wants a stable engine set for a request, decoupled from whatever the global
registry looks like by the time the request is actually served).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from core.engines.base import DetectionEngine


def _instantiate_engine(
    engines: dict[str, type[DetectionEngine]], name: str, config: Any
) -> DetectionEngine | None:
    """Look up *name* in *engines* and construct it, handling the failure modes.

    Shared by ``EngineRegistry.get_engine`` and ``EngineRegistrySnapshot.get_engine``
    so both operate on identical lookup/error-handling logic, differing only in
    which engine table they read from.
    """
    logger = getattr(config, "logger", None)
    verbose = bool(getattr(config, "verbose", False))

    if name not in engines:
        if verbose and logger:
            logger.debug(f"Engine '{name}' is not registered")
        return None

    try:
        engine = engines[name](config)
        if engine.is_available():
            return engine
        if verbose and logger:
            logger.debug(f"Engine '{name}' is registered but not available")
        return None
    except Exception as e:
        if verbose and logger:
            logger.debug(
                f"Failed to initialize engine '{name}': {type(e).__name__}: {e}",
                exc_info=True,
            )
        return None


class EngineRegistrySnapshot:
    """Independent, read-only view of the engines registered at snapshot time.

    Unlike ``EngineRegistry``, later calls to ``EngineRegistry.register()`` do not
    affect an already-taken snapshot. Obtain one via ``EngineRegistry.snapshot()``.
    """

    def __init__(self, engines: dict[str, type[DetectionEngine]]):
        self._engines = dict(engines)

    def get_engine(self, name: str, config: Any) -> DetectionEngine | None:
        """Get an engine instance from this snapshot's engine table."""
        return _instantiate_engine(self._engines, name, config)

    def list_engines(self) -> list[str]:
        """List engine names captured in this snapshot."""
        return list(self._engines.keys())

    def is_registered(self, name: str) -> bool:
        """Check whether *name* was registered at snapshot time."""
        return name in self._engines


class EngineRegistry:
    """Registry for detection engines.

    Similar to FileProcessorRegistry, this allows automatic discovery
    and instantiation of detection engines.
    """

    _engines: dict[str, type[DetectionEngine]] = {}

    @classmethod
    def register(cls, name: str, engine_class: type[DetectionEngine]) -> None:
        """Register an engine class.

        Args:
            name: Unique name identifier for the engine
            engine_class: Engine class implementing DetectionEngine protocol
        """
        cls._engines[name] = engine_class

    @classmethod
    def get_engine(cls, name: str, config: Any) -> DetectionEngine | None:
        """Get an engine instance.

        Args:
            name: Engine name
            config: Configuration object to pass to engine constructor

        Returns:
            Engine instance if found and available, None otherwise
        """
        return _instantiate_engine(cls._engines, name, config)

    @classmethod
    def list_engines(cls) -> list[str]:
        """List all registered engine names.

        Returns:
            List of registered engine names
        """
        return list(cls._engines.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if an engine is registered.

        Args:
            name: Engine name to check

        Returns:
            True if engine is registered, False otherwise
        """
        return name in cls._engines

    @classmethod
    def snapshot(cls) -> EngineRegistrySnapshot:
        """Return an independent, read-only snapshot of the current registry.

        Returns:
            An ``EngineRegistrySnapshot`` unaffected by later ``register()`` calls.
        """
        return EngineRegistrySnapshot(cls._engines)

    @classmethod
    @contextmanager
    def isolated(cls) -> Iterator[type["EngineRegistry"]]:
        """Scope registry mutations to this ``with`` block.

        Saves the current registration table, lets the block register/overwrite
        entries via the normal ``EngineRegistry`` API, and restores the original
        table on exit — including when the block raises. Intended for tests that
        need a fake or modified engine without leaking it into tests that run
        afterwards in the same process.

        Yields:
            The ``EngineRegistry`` class itself, so callers can keep using the
            familiar ``EngineRegistry.register(...)`` / ``.get_engine(...)`` API
            inside the block.
        """
        previous = cls._engines
        cls._engines = dict(previous)
        try:
            yield cls
        finally:
            cls._engines = previous
