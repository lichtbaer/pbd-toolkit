"""RTF file processor using striprtf library."""

from typing import Optional
from file_processors.base_processor import BaseFileProcessor
from striprtf.striprtf import rtf_to_text


class RtfProcessor(BaseFileProcessor):
    """Processor for RTF (Rich Text Format) files.

    Extracts text from RTF files using the striprtf library.
    Removes all RTF formatting codes and extracts plain text content.
    """

    def extract_text(self, file_path: str) -> str:
        """Extract text from an RTF file.

        Args:
            file_path: Path to the RTF file

        Returns:
            Extracted text content without RTF formatting codes

        Raises:
            UnicodeDecodeError: If file encoding cannot be decoded
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
            Exception: For other RTF processing errors
        """
        # RTF files are typically encoded in various formats
        # Try common encodings
        encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]
        last_error: Optional[UnicodeDecodeError] = None

        for encoding in encodings:
            try:
                with open(
                    file_path, "r", encoding=encoding, errors="replace"
                ) as rtf_file:
                    rtf_content = rtf_file.read()
                    # Convert RTF to plain text
                    text = rtf_to_text(rtf_content)
                    return text
            except UnicodeDecodeError as e:
                last_error = e
                continue
            except Exception:
                # Re-raise other exceptions immediately
                raise

        # If all encodings failed, raise the last error
        if last_error:
            raise last_error

        return ""

    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle RTF files."""
        return extension.lower() == ".rtf"
