"""Custom exception hierarchy for the pbD Toolkit.

All toolkit-specific exceptions inherit from ``PiiToolkitError`` so that callers
can catch the entire hierarchy with a single ``except PiiToolkitError`` clause while
still being able to handle individual categories more specifically.

The hierarchy is intentionally flat (one level deep) because the toolkit's error
space is small and a deep hierarchy would add complexity without benefit.
"""


class PiiToolkitError(Exception):
    """Base exception for all pbD Toolkit errors."""

    pass


class ConfigurationError(PiiToolkitError):
    """Raised when configuration is invalid or missing."""

    pass


class ProcessingError(PiiToolkitError):
    """Raised when file processing fails."""

    pass


class ValidationError(PiiToolkitError):
    """Raised when validation fails."""

    pass


class OutputError(PiiToolkitError):
    """Raised when output generation fails."""

    pass


class ModelError(PiiToolkitError):
    """Raised when NER model operations fail."""

    pass
