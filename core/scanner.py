"""File scanner for discovering and validating files."""

import os
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

from tqdm import tqdm

from config import Config
from core.exceptions import ProcessingError


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
    
    def scan(
        self,
        path: str,
        file_callback: Optional[Callable[[FileInfo], None]] = None,
        stop_count: Optional[int] = None
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
        
        # Estimate total files for progress bar (if verbose and no stop_count)
        total_files_estimate = None
        if not stop_count and self.config.verbose:
            self.config.logger.debug("Counting files for progress estimation...")
            try:
                total_files_estimate = sum(
                    len(files) for _, _, files in os.walk(path)
                )
                self.config.logger.debug(f"Estimated total files: {total_files_estimate}")
            except Exception as e:
                self.config.logger.warning(f"Failed to count files: {e}")
        
        # Initialize progress bar
        progress_bar = None
        if self.config.verbose or not stop_count:
            progress_bar = tqdm(
                total=total_files_estimate if total_files_estimate else None,
                desc="Processing files",
                unit="file",
                disable=not self.config.verbose and stop_count is not None
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
                        self._extension_counts[ext] = self._extension_counts.get(ext, 0) + 1
                    
                    # Validate file path
                    is_valid, error_msg = self.config.validate_file_path(full_path)
                    if not is_valid:
                        if error_msg:
                            if "Path traversal" in error_msg:
                                self.config.logger.warning(f"Security: {error_msg} - {full_path}")
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
                        size_mb=file_size_mb
                    )
                    
                    if file_callback:
                        try:
                            file_callback(file_info)
                            files_processed += 1
                        except Exception as e:
                            error_msg = f"Callback error: {type(e).__name__}: {str(e)}"
                            self.config.logger.error(f"{error_msg}: {full_path}", exc_info=self.config.verbose)
                            self._add_error(error_msg, full_path)
                    else:
                        files_processed += 1
                    
                    # Update progress bar
                    if progress_bar is not None:
                        progress_bar.update(1)
                        progress_bar.set_postfix({
                            'processed': files_processed,
                            'errors': len(self._errors),
                        })
                    
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
        
        # Build and return result
        return ScanResult(
            total_files_found=total_files_found,
            files_processed=files_processed,
            extension_counts=self._extension_counts.copy(),
            errors=self._errors.copy()
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
