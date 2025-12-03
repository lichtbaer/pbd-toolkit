"""Application context for dependency injection."""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

from config import Config
from core.statistics import Statistics
from matches import PiiMatchContainer
from output.writers import OutputWriter


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
    output_writer: Optional[OutputWriter] = None
    
    # Translation function
    translate_func: Callable[[str], str] = lambda x: x
    
    # Backward compatibility: CSV writer and file handle
    csv_writer: Any = None
    csv_file_handle: Any = None
    
    # Output configuration
    output_format: str = "csv"
    output_file_path: Optional[str] = None
    
    @classmethod
    def from_cli_args(cls, args: Any, config: Config, logger: logging.Logger,
                     statistics: Statistics, match_container: PiiMatchContainer,
                     output_writer: Optional[OutputWriter] = None,
                     translate_func: Optional[Callable[[str], str]] = None) -> "ApplicationContext":
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
        output_format = getattr(args, 'format', 'csv') if args else 'csv'
        
        # Get output file path (will be set by setup)
        output_file_path = None
        
        # Backward compatibility: CSV writer and file handle
        csv_writer = None
        csv_file_handle = None
        
        if output_writer and output_format == "csv":
            from output.writers import CsvWriter
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
            output_file_path=output_file_path
        )
    
    def _(self, text: str) -> str:
        """Translate text using translation function.
        
        Args:
            text: Text to translate
        
        Returns:
            Translated text
        """
        return self.translate_func(text)
