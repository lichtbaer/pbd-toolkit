"""Custom exception types for PII Toolkit."""


class PiiToolkitError(Exception):
    """Base exception for all PII Toolkit errors."""

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
