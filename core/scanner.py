"""File scanner for discovering and validating files."""

import fnmatch
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from tqdm import tqdm

from core.config import Config
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

    # Skipped files grouped by reason (e.g., "password_protected", "too_large", "corrupt")
    skipped_files: dict[str, list[str]] = field(default_factory=dict)

    def record_skipped(self, reason: str, file_path: str) -> None:
        """Record a skipped file with the reason it was skipped.

        Args:
            reason: Category of skip (e.g., "password_protected", "too_large", "corrupt")
            file_path: Path of the skipped file
        """
        if reason not in self.skipped_files:
            self.skipped_files[reason] = []
        self.skipped_files[reason].append(file_path)


@dataclass
class FileInfo:
    """Information about a file to be processed."""

    path: str
    extension: str
    size_mb: float | None = None
    mime_type: str | None = None


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

        Only ``config.scan`` (file discovery/safety settings) and
        ``config.runtime`` (logger, verbosity) are actually used internally —
        the full ``Config`` is accepted (and kept as ``self.config``) purely
        for backward compatibility with existing callers, not because the
        scanner needs the rest of it.

        Args:
            config: Configuration object with validation settings
        """
        self.config = config
        self.scan_config = config.scan
        self.runtime_config = config.runtime
        self._error_lock = threading.Lock()
        self._extension_counts: dict[str, int] = {}
        self._errors: dict[str, list[str]] = {}

        # Initialize file type detector if enabled
        use_magic = self.scan_config.use_magic_detection
        self.file_type_detector = (
            FileTypeDetector(enabled=use_magic) if use_magic else None
        )

    def _is_excluded(self, file_path: str) -> bool:
        """Return True if *file_path* matches any configured exclude pattern.

        Patterns support fnmatch glob syntax and are matched against:
        - the full path
        - the path relative to the scan root (when available)
        - individual path components (for simple directory names like 'tests/')

        Args:
            file_path: Absolute or relative file/directory path to test.

        Returns:
            True if the path should be excluded from scanning.
        """
        patterns = self.scan_config.exclude_patterns
        if not patterns:
            return False
        for pattern in patterns:
            # Normalize: strip trailing slash so 'tests/' matches the dir name
            pat = pattern.rstrip("/")
            # 1. Full path match (supports **/*.bak style patterns)
            if fnmatch.fnmatch(file_path, pat):
                return True
            if fnmatch.fnmatch(file_path, f"*/{pat}"):
                return True
            # 2. Any path component matches a simple name pattern
            parts = file_path.replace("\\", "/").split("/")
            if any(fnmatch.fnmatch(part, pat) for part in parts):
                return True
        return False

    def scan(
        self,
        path: str,
        file_callback: Callable[[FileInfo], object] | None = None,
        stop_count: int | None = None,
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
        # Lazy import avoids overhead in the common sequential (no-callback) case.
        import concurrent.futures

        total_files_found = 0
        # "Processed" counts only files that are eligible for processing, i.e.
        # supported by a registered file processor (extension/mime-type based).
        files_processed = 0
        pending_futures: list[concurrent.futures.Future] = []
        future_to_path: dict[concurrent.futures.Future, str] = {}
        # Prevent unbounded growth of pending futures when scanning large trees.
        # This is especially important for multi-worker runs where file_callback
        # submits to a ThreadPoolExecutor and returns futures.
        max_pending_futures = self.scan_config.max_pending_futures

        # Estimate total files for progress bar (if verbose and no stop_count)
        # This can double runtime on huge directory trees, so it's opt-in.
        # Enable via env var: PII_TOOLKIT_PROGRESS_ESTIMATE=1
        total_files_estimate = None
        if (
            not stop_count
            and self.runtime_config.verbose
            and os.environ.get("PII_TOOLKIT_PROGRESS_ESTIMATE") == "1"
        ):
            self.runtime_config.logger.debug(
                "Counting files for progress estimation..."
            )
            try:
                total_files_estimate = sum(len(files) for _, _, files in os.walk(path))
                self.runtime_config.logger.debug(
                    f"Estimated total files: {total_files_estimate}"
                )
            except Exception as e:
                self.runtime_config.logger.warning(f"Failed to count files: {e}")

        # Initialize progress bar (verbose-only).
        # Note: tqdm telemetry is disabled by default in recent versions.
        # For additional privacy, set TQDM_DISABLE_TELEMETRY=1 environment variable.
        progress_bar = None
        if self.runtime_config.verbose:
            progress_bar = tqdm(
                total=total_files_estimate if total_files_estimate else None,
                desc="Processing files",
                unit="file",
            )

        try:
            # Walk all files and subdirectories
            for root, dirs, files in os.walk(path):
                # Prune excluded subdirectories in-place (prevents descent)
                dirs[:] = [
                    d for d in dirs if not self._is_excluded(os.path.join(root, d))
                ]

                for filename in files:
                    total_files_found += 1

                    full_path = os.path.join(root, filename)

                    # Skip files matching exclude patterns
                    if self._is_excluded(full_path):
                        continue

                    ext = os.path.splitext(full_path)[1].lower()

                    # Count extension (thread-safe)
                    with self._error_lock:
                        self._extension_counts[ext] = (
                            self._extension_counts.get(ext, 0) + 1
                        )

                    # Validate file path
                    is_valid, error_msg = self.scan_config.validate_file_path(full_path)
                    if not is_valid:
                        if error_msg:
                            if "Path traversal" in error_msg:
                                self.runtime_config.logger.warning(
                                    f"Security: {error_msg} - {full_path}"
                                )
                            else:
                                self.runtime_config.logger.warning(
                                    f"{error_msg} - {full_path}"
                                )
                            self._add_error(error_msg, full_path)
                        continue

                    # Get file size if possible
                    file_size_mb = None
                    try:
                        file_size_mb = os.path.getsize(full_path) / (1024 * 1024)
                    except OSError as e:
                        self.runtime_config.logger.debug(
                            "Could not determine file size for %s: %s", full_path, e
                        )

                    # Detect MIME type using magic numbers if enabled
                    mime_type = None
                    if self.file_type_detector:
                        # Use magic detection if:
                        # 1. File has no extension, OR
                        # 2. magic_detection_fallback is enabled AND the extension is unsupported
                        magic_fallback = self.scan_config.magic_detection_fallback
                        ext_supported = bool(ext) and (
                            FileProcessorRegistry.get_processor(ext) is not None
                        )
                        should_detect = (not ext) or (
                            bool(magic_fallback) and not ext_supported
                        )
                        if should_detect:
                            mime_type = self.file_type_detector.detect_type(full_path)
                            if mime_type and self.runtime_config.verbose:
                                self.runtime_config.logger.debug(
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
                                    if self.runtime_config.verbose:
                                        self.runtime_config.logger.debug(
                                            f"Inferred extension from MIME type: {ext}"
                                        )

                    # Determine whether the file is eligible (supported) before invoking callback.
                    # This keeps "files_processed" aligned with "qualified/analyzed" semantics.
                    mime_type_str = mime_type or ""
                    processor = FileProcessorRegistry.get_processor(
                        ext, full_path, mime_type_str
                    )
                    if processor is None:
                        # Unsupported file type: skip processing (but keep extension counts).
                        continue

                    # Log file processing in verbose mode
                    if self.runtime_config.verbose:
                        if file_size_mb is not None:
                            self.runtime_config.logger.debug(
                                f"Processing file {total_files_found}: {full_path} ({file_size_mb:.2f} MB)"
                            )
                        else:
                            self.runtime_config.logger.debug(
                                f"Processing file {total_files_found}: {full_path} (size unknown)"
                            )

                    # Create FileInfo and call callback
                    file_info = FileInfo(
                        path=full_path,
                        extension=ext,
                        size_mb=file_size_mb,
                        mime_type=mime_type_str or None,
                    )

                    if file_callback:
                        try:
                            ret = file_callback(file_info)
                            files_processed += 1
                            # If the callback returns a Future, wait for it before
                            # returning from scan, otherwise the CLI may finalize
                            # output before processing completes.
                            if isinstance(ret, concurrent.futures.Future):
                                pending_futures.append(ret)
                                future_to_path[ret] = full_path
                                # Bound memory usage: periodically drain completed futures.
                                if len(pending_futures) >= max_pending_futures:
                                    try:
                                        done, not_done = concurrent.futures.wait(
                                            pending_futures,
                                            return_when=concurrent.futures.FIRST_COMPLETED,
                                        )
                                        pending_futures = list(not_done)
                                        # Surface unexpected exceptions as scan errors (best-effort).
                                        for fut in done:
                                            try:
                                                fut.result()
                                            except Exception as e:
                                                fpath = future_to_path.get(
                                                    fut, "<unknown>"
                                                )
                                                error_msg = f"Callback async error: {type(e).__name__}: {str(e)}"
                                                self.runtime_config.logger.error(
                                                    f"{error_msg}: {fpath}",
                                                    exc_info=self.runtime_config.verbose,
                                                )
                                                if fpath != "<unknown>":
                                                    self._add_error(error_msg, fpath)
                                                else:
                                                    self._add_error(error_msg, "")
                                    except Exception as drain_exc:
                                        # Keep scanning even if draining fails, but log for debuggability.
                                        self.runtime_config.logger.warning(
                                            "Failed to drain pending futures: %s: %s",
                                            type(drain_exc).__name__,
                                            drain_exc,
                                            exc_info=self.runtime_config.verbose,
                                        )
                        except Exception as e:
                            error_msg = f"Callback error: {type(e).__name__}: {str(e)}"
                            self.runtime_config.logger.error(
                                f"{error_msg}: {full_path}",
                                exc_info=self.runtime_config.verbose,
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
                    if stop_count and files_processed >= stop_count:
                        break

                # Check stop count (break outer loop)
                if stop_count and files_processed >= stop_count:
                    break

        finally:
            # Close progress bar
            if progress_bar is not None:
                progress_bar.close()

        # Ensure any async processing has completed before we return.
        if pending_futures:
            try:
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
                        self.runtime_config.logger.error(
                            f"{error_msg}: {full_path}",
                            exc_info=self.runtime_config.verbose,
                        )
                        if full_path != "<unknown>":
                            self._add_error(error_msg, full_path)
                        else:
                            self._add_error(error_msg, "")
            except Exception as wait_exc:
                # If waiting itself fails, log and continue with scan result.
                self.runtime_config.logger.warning(
                    "Failed to wait for pending futures at scan end: %s: %s",
                    type(wait_exc).__name__,
                    wait_exc,
                    exc_info=self.runtime_config.verbose,
                )

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
