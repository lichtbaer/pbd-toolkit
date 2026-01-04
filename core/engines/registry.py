"""Registry for detection engines."""

from typing import Dict, Type, Optional, Any
from core.engines.base import DetectionEngine


class EngineRegistry:
    """Registry for detection engines.

    Similar to FileProcessorRegistry, this allows automatic discovery
    and instantiation of detection engines.
    """

    _engines: Dict[str, Type[DetectionEngine]] = {}

    @classmethod
    def register(cls, name: str, engine_class: Type[DetectionEngine]) -> None:
        """Register an engine class.

        Args:
            name: Unique name identifier for the engine
            engine_class: Engine class implementing DetectionEngine protocol
        """
        cls._engines[name] = engine_class

    @classmethod
    def get_engine(cls, name: str, config: Any) -> Optional[DetectionEngine]:
        """Get an engine instance.

        Args:
            name: Engine name
            config: Configuration object to pass to engine constructor

        Returns:
            Engine instance if found and available, None otherwise
        """
        logger = getattr(config, "logger", None)
        verbose = bool(getattr(config, "verbose", False))

        if name not in cls._engines:
            if verbose and logger:
                logger.debug(f"Engine '{name}' is not registered")
            return None

        try:
            engine = cls._engines[name](config)
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
