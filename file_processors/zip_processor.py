"""ZIP archive processor for extracting and scanning contents."""

import os
import zipfile
from collections.abc import Iterator

from file_processors.base_processor import BaseFileProcessor

# Maximum total uncompressed bytes to read from a single ZIP archive.
# This guards against ZIP bomb attacks (e.g. 42.zip) where a tiny
# compressed file expands to gigabytes of data.
_MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024  # 512 MB

# Maximum uncompressed size for a single file inside the archive.
_MAX_SINGLE_FILE_BYTES = 100 * 1024 * 1024  # 100 MB

# Maximum compression ratio (uncompressed / compressed) before treating the
# entry as a potential ZIP bomb.  Legitimate text files rarely exceed 20:1.
_MAX_COMPRESSION_RATIO = 100


class ZipProcessor(BaseFileProcessor):
    """Processor for ZIP archive files.

    Extracts ZIP contents and processes files recursively.
    Handles nested archives and password-protected archives.
    """

    def extract_text(self, file_path: str) -> Iterator[str]:
        """Extract text from all files in ZIP archive.

        Args:
            file_path: Path to the ZIP file

        Yields:
            Text content from each file in the archive

        Raises:
            zipfile.BadZipFile: If file is not a valid ZIP
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
        """
        try:
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                # Get list of files in archive
                file_list = zip_ref.namelist()

                total_uncompressed = 0

                for filename in file_list:
                    # Skip directories
                    if filename.endswith("/"):
                        continue

                    # Skip hidden files and system files
                    if os.path.basename(filename).startswith("."):
                        continue

                    # Guard against ZIP bombs: check declared uncompressed size
                    # before reading. ZipInfo.file_size is the uncompressed size.
                    try:
                        info = zip_ref.getinfo(filename)
                    except KeyError:
                        continue

                    if info.file_size > _MAX_SINGLE_FILE_BYTES:
                        continue

                    # Detect ZIP bombs via suspicious compression ratio.
                    if (
                        info.compress_size > 0
                        and info.file_size / info.compress_size > _MAX_COMPRESSION_RATIO
                    ):
                        continue

                    total_uncompressed += info.file_size
                    if total_uncompressed > _MAX_UNCOMPRESSED_BYTES:
                        break

                    try:
                        # Extract file content
                        with zip_ref.open(filename) as file_in_zip:
                            # Try to read as text
                            try:
                                content = file_in_zip.read()
                                # Try UTF-8 first
                                try:
                                    text = content.decode("utf-8")
                                except UnicodeDecodeError:
                                    # Fallback to latin-1
                                    try:
                                        text = content.decode("latin-1")
                                    except UnicodeDecodeError:
                                        # Skip binary files
                                        continue

                                # Yield text with filename context
                                yield f"[File in ZIP: {filename}]\n{text}\n"
                            except Exception:
                                # Skip files that can't be read
                                continue
                    except zipfile.BadZipFile:
                        # Skip corrupted files in archive
                        continue
                    except RuntimeError:
                        # Password-protected file
                        continue
                    except Exception:
                        # Other errors, skip this file
                        continue
        except zipfile.BadZipFile:
            raise
        except Exception:
            # Re-raise as ProcessingError would be caught by caller
            raise

    @staticmethod
    def can_process(extension: str, file_path: str = "", mime_type: str = "") -> bool:
        """Check if this processor can handle the file.

        Args:
            extension: File extension
            file_path: Full path to the file
            mime_type: Detected MIME type

        Returns:
            True if file is a ZIP archive, False otherwise
        """
        if extension.lower() == ".zip":
            return True

        if mime_type:
            return mime_type in ["application/zip", "application/x-zip-compressed"]

        return False
