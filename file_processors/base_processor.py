"""Base class for file processors."""

from abc import ABC, abstractmethod
from collections.abc import Iterator


class FileProcessingError(Exception):
    """Raised when a file processor fails to extract text.

    Attributes:
        file_path: Path of the file that caused the error.
        processor_name: Name of the processor that failed.
        original_error: The underlying exception, if any.
    """

    def __init__(
        self,
        message: str,
        file_path: str = "",
        processor_name: str = "",
        original_error: Exception | None = None,
    ) -> None:
        self.file_path = file_path
        self.processor_name = processor_name
        self.original_error = original_error
        super().__init__(message)


class CorruptedFileError(FileProcessingError):
    """Raised when a file appears to be corrupted or malformed."""


class UnsupportedFormatError(FileProcessingError):
    """Raised when a file format is not supported by the processor."""


class PasswordProtectedError(FileProcessingError):
    """Raised when a file is password-protected and cannot be read."""


class BaseFileProcessor(ABC):
    """Abstract base class for file processors.

    All file processors should inherit from this class and implement
    the extract_text method.

    Processors can optionally implement can_process to indicate which
    file extensions they support. The default implementation returns False.

    Error handling:
        Processors should raise specific error types for known failure modes:
        - ``CorruptedFileError`` for malformed/corrupted files
        - ``PasswordProtectedError`` for encrypted files
        - ``UnsupportedFormatError`` for format mismatches
        - ``FileProcessingError`` for other extraction failures

        Callers can then handle these granularly instead of catching
        generic exceptions.
    """

    @abstractmethod
    def extract_text(self, file_path: str) -> str | Iterator[str]:
        """Extract text content from a file.

        Args:
            file_path: Path to the file to process

        Returns:
            Extracted text content as a string or iterator of strings
            (for chunked processing of large files)

        Raises:
            FileProcessingError: Base class for all processing errors.
            CorruptedFileError: When the file is corrupted or malformed.
            PasswordProtectedError: When the file is password-protected.
            UnsupportedFormatError: When the format is not supported.
        """
        pass

    @staticmethod
    def can_process(extension: str, file_path: str = "", mime_type: str = "") -> bool:
        """Check if this processor can handle the given file extension.

        Args:
            extension: File extension (e.g., '.pdf', '.docx')
            file_path: Optional full path to the file (for processors that need
                      to check file content or MIME type)
            mime_type: Optional detected MIME type (from magic number detection)

        Returns:
            True if this processor can handle the extension, False otherwise

        Note:
            Most processors only need the extension parameter. Some processors
            (like TextProcessor) may need the file_path to check MIME types.
            The mime_type parameter allows processors to match based on detected
            MIME type when magic number detection is enabled.
        """
        return False
