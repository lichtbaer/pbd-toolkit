"""Registry for detection engines.

Registry lifecycle: default vs. isolated
-----------------------------------------
``EngineRegistry``'s classmethods operate on process-global state, populated once at
import time by ``core/engines/__init__.py`` (built-in engines unconditionally,
optional engines guarded by ``try/except ImportError`` so a missing dependency never
prevents the rest of the module from importing). CLI scans use this default registry
unchanged.

For tests or long-running processes (the REST API) that must not mutate — or be
affected by mutations of — that global state, use an isolated registry instead:

- ``EngineRegistry.create_isolated()`` returns an empty :class:`IsolatedEngineRegistry`.
- ``EngineRegistry.snapshot()`` returns an :class:`IsolatedEngineRegistry`
  pre-populated with a copy of whatever engine classes are currently registered
  globally — the shape the REST API uses for a stable engine set independent of
  concurrent global registrations elsewhere in the process.

Both registry classes expose the same method names (``register``, ``get_engine``,
``list_engines``, ``is_registered``), so callers that accept "a registry" (e.g.
``TextProcessor``) can be handed either the ``EngineRegistry`` class or an isolated
instance interchangeably.

Thread safety: registration, like ``FileProcessorRegistry``, is expected to happen
once at import time (or, for an isolated instance, once during test/request setup)
before concurrent reads begin; ``get_engine`` reads are safe under CPython's GIL.

Optional-engine availability has two independent layers, both preserved by isolated
registries: (1) a missing dependency can prevent an engine class from being
registered at all (``core/engines/__init__.py``'s import guard), and (2) even a
registered engine class's ``is_available()`` may return ``False`` at construction
time (checked below in ``get_engine``) — e.g. spaCy's class always imports
successfully, and only reports unavailability via ``is_available()`` once its model
load is attempted.
"""

from typing import Any

from core.engines.base import DetectionEngine


def _resolve_engine(
    engines: dict[str, type[DetectionEngine]], name: str, config: Any
) -> DetectionEngine | None:
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


class EngineRegistry:
    """Registry for detection engines.

    Similar to FileProcessorRegistry, this allows automatic discovery
    and instantiation of detection engines. See the module docstring for the
    default-vs-isolated registry lifecycle.
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
        return _resolve_engine(cls._engines, name, config)

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
    def create_isolated(cls) -> "IsolatedEngineRegistry":
        """Create a new, empty engine registry that never touches global state.

        Use this in tests that need a clean engine set without racing other tests
        or mutating the process-wide default registry.
        """
        return IsolatedEngineRegistry()

    @classmethod
    def snapshot(cls) -> "IsolatedEngineRegistry":
        """Create an isolated registry pre-populated from the current global state.

        Intended for long-running processes (the REST API) that want a stable
        engine set for the lifetime of a service instance, decoupled from whatever
        else might register engines on the global registry at runtime.
        """
        isolated = IsolatedEngineRegistry()
        for name, engine_class in cls._engines.items():
            isolated.register(name, engine_class)
        return isolated


class IsolatedEngineRegistry:
    """An isolated, instance-scoped counterpart to :class:`EngineRegistry`.

    Construct via ``EngineRegistry.create_isolated()`` (empty) or
    ``EngineRegistry.snapshot()`` (pre-populated copy of the global registry).
    Exposes the same method names as the classmethods above so a caller that accepts
    "a registry" can be handed either the ``EngineRegistry`` class or an instance of
    this class interchangeably.
    """

    def __init__(self) -> None:
        self._engines: dict[str, type[DetectionEngine]] = {}

    def register(self, name: str, engine_class: type[DetectionEngine]) -> None:
        """Register an engine class on this isolated instance only."""
        self._engines[name] = engine_class

    def get_engine(self, name: str, config: Any) -> DetectionEngine | None:
        """Get an engine instance from this isolated instance's registrations."""
        return _resolve_engine(self._engines, name, config)

    def list_engines(self) -> list[str]:
        """List engine names registered on this isolated instance."""
        return list(self._engines.keys())

    def is_registered(self, name: str) -> bool:
        """Check if an engine is registered on this isolated instance."""
        return name in self._engines
