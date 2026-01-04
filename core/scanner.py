"""File scanner for discovering and validating files."""

import os
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

from tqdm import tqdm

from config import Config
from core.file_type_detector import FileTypeDetector
from file_processors import FileProcessorRegistry


@dataclass
class ScanResult:
    """Results from file scanning operation."""

    # Number of files found (all extensions)
    total_files_found: int = 0

    # Number of files actually processed (supported extensions)
    files_processed: int = 0

    # Extension counts: {".pdf": 42, ".txt": 10, ...}
    extension_counts: dict[str, int] = field(default_factory=dict)

    # Errors encountered: {"error_type": ["file1", "file2", ...]}
    errors: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class FileInfo:
    """Information about a file to be processed."""

    path: str
    extension: str
    size_mb: Optional[float] = None
    mime_type: Optional[str] = None


class FileScanner:
    """Scans directories for files and validates them.

    This class handles:
    - Recursive directory walking
    - File validation (path traversal, size limits)
    - Extension counting
    - Error collection
    - Progress tracking
    """

    def __init__(self, config: Config):
        """Initialize file scanner.

        Args:
            config: Configuration object with validation settings
        """
        self.config = config
        self._error_lock = threading.Lock()
        self._extension_counts: dict[str, int] = {}
        self._errors: dict[str, list[str]] = {}

        # Initialize file type detector if enabled
        use_magic = getattr(config, "use_magic_detection", False)
        self.file_type_detector = (
            FileTypeDetector(enabled=use_magic) if use_magic else None
        )

    def scan(
        self,
        path: str,
        file_callback: Optional[Callable[[FileInfo], object]] = None,
        stop_count: Optional[int] = None,
    ) -> ScanResult:
        """Scan directory recursively and process files.

        Args:
            path: Root directory to scan
            file_callback: Optional callback function called for each valid file.
                          Receives FileInfo object. If None, files are only counted.
            stop_count: Optional limit on number of files to process

        Returns:
            ScanResult with statistics and errors
        """
        total_files_found = 0
        files_processed = 0
        pending_futures = []
        future_to_path: dict[object, str] = {}

        # Estimate total files for progress bar (if verbose and no stop_count)
        # This can double runtime on huge directory trees, so it's opt-in.
        # Enable via env var: PII_TOOLKIT_PROGRESS_ESTIMATE=1
        total_files_estimate = None
        if (
            not stop_count
            and self.config.verbose
            and os.environ.get("PII_TOOLKIT_PROGRESS_ESTIMATE") == "1"
        ):
            self.config.logger.debug("Counting files for progress estimation...")
            try:
                total_files_estimate = sum(len(files) for _, _, files in os.walk(path))
                self.config.logger.debug(
                    f"Estimated total files: {total_files_estimate}"
                )
            except Exception as e:
                self.config.logger.warning(f"Failed to count files: {e}")

        # Initialize progress bar (verbose-only).
        # Note: tqdm telemetry is disabled by default in recent versions.
        # For additional privacy, set TQDM_DISABLE_TELEMETRY=1 environment variable.
        progress_bar = None
        if self.config.verbose:
            progress_bar = tqdm(
                total=total_files_estimate if total_files_estimate else None,
                desc="Processing files",
                unit="file",
            )

        try:
            # Walk all files and subdirectories
            for root, dirs, files in os.walk(path):
                for filename in files:
                    total_files_found += 1

                    full_path = os.path.join(root, filename)
                    ext = os.path.splitext(full_path)[1].lower()

                    # Count extension (thread-safe)
                    with self._error_lock:
                        self._extension_counts[ext] = (
                            self._extension_counts.get(ext, 0) + 1
                        )

                    # Validate file path
                    is_valid, error_msg = self.config.validate_file_path(full_path)
                    if not is_valid:
                        if error_msg:
                            if "Path traversal" in error_msg:
                                self.config.logger.warning(
                                    f"Security: {error_msg} - {full_path}"
                                )
                            else:
                                self.config.logger.warning(f"{error_msg} - {full_path}")
                            self._add_error(error_msg, full_path)
                        continue

                    # Get file size if possible
                    file_size_mb = None
                    try:
                        file_size_mb = os.path.getsize(full_path) / (1024 * 1024)
                    except OSError:
                        pass

                    # Detect MIME type using magic numbers if enabled
                    mime_type = None
                    if self.file_type_detector:
                        # Use magic detection if:
                        # 1. File has no extension, OR
                        # 2. magic_detection_fallback is enabled AND the extension is unsupported
                        magic_fallback = getattr(
                            self.config, "magic_detection_fallback", True
                        )
                        ext_supported = bool(ext) and (
                            FileProcessorRegistry.get_processor(ext) is not None
                        )
                        should_detect = (not ext) or (
                            bool(magic_fallback) and not ext_supported
                        )
                        if should_detect:
                            mime_type = self.file_type_detector.detect_type(full_path)
                            if mime_type and self.config.verbose:
                                self.config.logger.debug(
                                    f"Detected MIME type for {full_path}: {mime_type}"
                                )
                            # If file has no extension but we detected a type, update extension
                            if not ext and mime_type:
                                detected_ext = (
                                    self.file_type_detector.get_extension_from_mime(
                                        mime_type
                                    )
                                )
                                if detected_ext:
                                    ext = detected_ext
                                    if self.config.verbose:
                                        self.config.logger.debug(
                                            f"Inferred extension from MIME type: {ext}"
                                        )

                    # Log file processing in verbose mode
                    if self.config.verbose:
                        if file_size_mb is not None:
                            self.config.logger.debug(
                                f"Processing file {total_files_found}: {full_path} ({file_size_mb:.2f} MB)"
                            )
                        else:
                            self.config.logger.debug(
                                f"Processing file {total_files_found}: {full_path} (size unknown)"
                            )

                    # Create FileInfo and call callback
                    file_info = FileInfo(
                        path=full_path,
                        extension=ext,
                        size_mb=file_size_mb,
                        mime_type=mime_type,
                    )

                    if file_callback:
                        try:
                            ret = file_callback(file_info)
                            files_processed += 1
                            # If the callback returns a Future-like object, wait for it
                            # before returning from scan, otherwise the CLI may finalize
                            # output before processing completes.
                            if hasattr(ret, "result") and hasattr(ret, "done"):
                                pending_futures.append(ret)
                                future_to_path[ret] = full_path
                        except Exception as e:
                            error_msg = f"Callback error: {type(e).__name__}: {str(e)}"
                            self.config.logger.error(
                                f"{error_msg}: {full_path}",
                                exc_info=self.config.verbose,
                            )
                            self._add_error(error_msg, full_path)
                    else:
                        files_processed += 1

                    # Update progress bar
                    if progress_bar is not None:
                        progress_bar.update(1)
                        progress_bar.set_postfix(
                            {
                                "processed": files_processed,
                                "errors": len(self._errors),
                            }
                        )

                    # Check stop count
                    if stop_count and total_files_found >= stop_count:
                        break

                # Check stop count (break outer loop)
                if stop_count and total_files_found >= stop_count:
                    break

        finally:
            # Close progress bar
            if progress_bar is not None:
                progress_bar.close()

        # Ensure any async processing has completed before we return.
        if pending_futures:
            try:
                # Import lazily to avoid overhead in the common sequential case.
                import concurrent.futures

                concurrent.futures.wait(pending_futures)
                # Surface unexpected exceptions as scan errors (best-effort).
                for fut in pending_futures:
                    try:
                        fut.result()
                    except Exception as e:
                        full_path = future_to_path.get(fut, "<unknown>")
                        error_msg = (
                            f"Callback async error: {type(e).__name__}: {str(e)}"
                        )
                        self.config.logger.error(
                            f"{error_msg}: {full_path}",
                            exc_info=self.config.verbose,
                        )
                        if full_path != "<unknown>":
                            self._add_error(error_msg, full_path)
                        else:
                            self._add_error(error_msg, "")
            except Exception:
                # If waiting itself fails, continue with scan result.
                pass

        # Build and return result
        return ScanResult(
            total_files_found=total_files_found,
            files_processed=files_processed,
            extension_counts=self._extension_counts.copy(),
            errors=self._errors.copy(),
        )

    def _add_error(self, msg: str, path: str) -> None:
        """Add an error message for a specific file path.

        Thread-safe error tracking.

        Args:
            msg: Error message describing the type of error
            path: File path where the error occurred
        """
        with self._error_lock:
            if msg not in self._errors:
                self._errors[msg] = [path]
            else:
                self._errors[msg].append(path)
