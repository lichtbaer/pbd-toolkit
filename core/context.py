"""Application context for dependency injection."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TextIO

from core.config import Config
from core.matches import PiiMatchContainer
from core.statistics import Statistics
from core.writers import OutputWriter

if TYPE_CHECKING:
    import _csv

    from core.protocols import AnalyticsStoreProtocol


@dataclass
class ApplicationContext:
    """Central application context with all dependencies.

    This class centralizes all application dependencies, eliminating
    the need for global variables and enabling better testability.
    """

    # Core dependencies
    config: Config
    logger: logging.Logger
    statistics: Statistics

    # Processing components
    match_container: PiiMatchContainer
    output_writer: OutputWriter | None = None

    # Translation function
    translate_func: Callable[[str], str] = lambda x: x

    # Analytics store (optional, structurally typed via AnalyticsStoreProtocol
    # to avoid a hard import-time dependency on the analytics package).
    analytics_store: AnalyticsStoreProtocol | None = None
    analytics_session_id: str | None = None

    # Backward compatibility: CSV writer and file handle
    csv_writer: _csv.Writer | None = None
    csv_file_handle: TextIO | None = None

    # Output configuration
    output_format: str = "csv"
    output_file_path: str | None = None

    def __post_init__(self) -> None:
        """Derive backward-compatible CSV handles when possible.

        Some parts of the codebase (and tests) still expect `csv_writer` and
        `csv_file_handle` to be available when a CSV output writer is used.
        """
        if self.output_writer and self.output_format == "csv":
            try:
                from core.writers import CsvWriter

                if isinstance(self.output_writer, CsvWriter):
                    if self.csv_writer is None:
                        self.csv_writer = self.output_writer.get_writer()
                    if self.csv_file_handle is None:
                        self.csv_file_handle = self.output_writer.file_handle
            except Exception as exc:
                # Don't fail context creation if optional CSV back-compat wiring fails
                import logging

                logging.getLogger(__name__).debug(
                    "Optional CSV back-compat wiring failed (non-critical): %s", exc
                )

    @classmethod
    def from_cli_args(
        cls,
        args: argparse.Namespace,
        config: Config,
        logger: logging.Logger,
        statistics: Statistics,
        match_container: PiiMatchContainer,
        output_writer: OutputWriter | None = None,
        translate_func: Callable[[str], str] | None = None,
    ) -> ApplicationContext:
        """Create ApplicationContext from CLI arguments and dependencies.

        Args:
            args: Parsed command line arguments
            config: Configuration object
            logger: Logger instance
            statistics: Statistics tracker
            match_container: PII match container
            output_writer: Optional output writer
            translate_func: Optional translation function

        Returns:
            ApplicationContext instance
        """
        # Get output format from args
        output_format = getattr(args, "format", "csv") if args else "csv"

        # Get output file path (will be set by setup)
        output_file_path = None

        # Backward compatibility: CSV writer and file handle
        csv_writer = None
        csv_file_handle = None

        if output_writer and output_format == "csv":
            from core.writers import CsvWriter

            if isinstance(output_writer, CsvWriter):
                csv_writer = output_writer.get_writer()
                csv_file_handle = output_writer.file_handle

        return cls(
            config=config,
            logger=logger,
            statistics=statistics,
            match_container=match_container,
            output_writer=output_writer,
            translate_func=translate_func or (lambda x: x),
            csv_writer=csv_writer,
            csv_file_handle=csv_file_handle,
            output_format=output_format,
            output_file_path=output_file_path,
        )

    def _(self, text: str) -> str:
        """Translate text using translation function.

        Args:
            text: Text to translate

        Returns:
            Translated text
        """
        return self.translate_func(text)
