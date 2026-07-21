"""Base abstractions for file format processors.

Every file format (PDF, DOCX, CSV, …) has a corresponding processor that knows how
to extract plain text from that format.  All processors share the same interface
(``BaseFileProcessor``) so the scanner can treat them uniformly.

Iterator vs. string return type
--------------------------------
``extract_text`` returns either a ``str`` or an ``Iterator[str]``.  The Iterator
variant is preferred for large files (PDFs, mailboxes, ZIP archives, databases)
because it allows the scanner to process text chunk by chunk without loading the
entire file into memory.  Processors that return a single string are fine for small,
memory-safe formats (HTML, Markdown, plain text).

Exception hierarchy
-------------------
The specialised exception classes (``CorruptedFileError``, ``PasswordProtectedError``,
``UnsupportedFormatError``) exist so the scanner can log meaningful error messages and
update statistics by failure category.  Using a flat ``Exception`` everywhere would
hide whether a file was skipped due to corruption or encryption.
"""

import logging
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

            Subclasses may implement a narrower signature (e.g. just
            ``can_process(extension)``) — ``FileProcessorRegistry`` inspects each
            processor's actual signature via ``inspect.signature`` and calls it
            with only the parameters it declares. This is intentional duck typing
            that a static Liskov check cannot express, hence the
            ``# type: ignore[override]`` on narrower overrides.
        """
        return False


_logger = logging.getLogger(__name__)

# Standard encoding fallback chain used across all text-based file processors.
# Order reflects European document corpus prevalence:
# - utf-8 / utf-8-sig: modern documents and BOM-prefixed Windows files
# - cp1252: Windows-1252 (common in legacy German/Western European Office docs)
# - iso-8859-1 / latin-1: older Unix-generated files and email attachments
_ENCODING_FALLBACK_CHAIN = ("utf-8", "utf-8-sig", "cp1252", "iso-8859-1", "latin-1")


def decode_with_fallback(
    data: bytes,
    encodings: tuple[str, ...] = _ENCODING_FALLBACK_CHAIN,
) -> str:
    """Decode bytes using a chain of encodings, returning the first successful result.

    This provides a unified encoding strategy across all file processors,
    replacing the ad-hoc encoding fallback chains that previously existed
    in individual processors.

    Args:
        data: Raw bytes to decode.
        encodings: Tuple of encoding names to try in order.

    Returns:
        Decoded string.

    Raises:
        UnicodeDecodeError: If none of the encodings succeed.
    """
    last_error: UnicodeDecodeError | None = None
    for enc in encodings:
        try:
            return data.decode(enc)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue

    # All encodings failed — raise the last error
    if last_error is not None:
        raise last_error
    raise UnicodeDecodeError("utf-8", data, 0, len(data), "no encodings provided")


def read_text_with_fallback(
    file_path: str,
    encodings: tuple[str, ...] = _ENCODING_FALLBACK_CHAIN,
) -> str:
    """Read a text file trying multiple encodings.

    Args:
        file_path: Path to the text file.
        encodings: Tuple of encoding names to try in order.

    Returns:
        File content as string.

    Raises:
        UnicodeDecodeError: If none of the encodings succeed.
        FileNotFoundError: If the file does not exist.
        PermissionError: If the file cannot be accessed.
    """
    last_error: UnicodeDecodeError | None = None
    for enc in encodings:
        try:
            with open(file_path, encoding=enc) as fh:
                return fh.read()
        except UnicodeDecodeError as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise UnicodeDecodeError(
            last_error.encoding,
            last_error.object,
            last_error.start,
            last_error.end,
            f"Could not decode file with any of: {', '.join(encodings)}",
        ) from last_error
    raise UnicodeDecodeError("utf-8", b"", 0, 0, "no encodings provided")
