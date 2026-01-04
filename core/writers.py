"""Output writers for PII findings."""

import abc
import csv
import json
from typing import Optional, Any, TextIO

from matches import PiiMatch
from core.exceptions import OutputError


class OutputWriter(abc.ABC):
    """Abstract base class for output writers."""

    def __init__(self, file_path: str, include_header: bool = True):
        self.file_path = file_path
        self.include_header = include_header

    @abc.abstractmethod
    def write_match(self, match: PiiMatch) -> None:
        """Write a single match to the output."""
        pass

    @abc.abstractmethod
    def finalize(self, metadata: Optional[dict] = None) -> None:
        """Finalize the output (e.g. close file, write footer/metadata)."""
        pass

    @property
    @abc.abstractmethod
    def supports_streaming(self) -> bool:
        """Return True if the writer supports streaming (writing matches as they are found)."""
        pass

    # Optional method for backward compatibility
    def get_writer(self) -> Any:
        return None

    @property
    def file_handle(self) -> Optional[Any]:
        return None


class CsvWriter(OutputWriter):
    """Writes findings to a CSV file."""

    def __init__(self, file_path: str, include_header: bool = True):
        super().__init__(file_path, include_header)
        try:
            self._file = open(file_path, "w", newline="", encoding="utf-8")
            self._writer = csv.writer(self._file)
            if self.include_header:
                self._writer.writerow(["Match", "File", "Type", "Score", "Engine"])
        except IOError as e:
            raise OutputError(f"Failed to open output file: {e}")

    def write_match(self, match: PiiMatch) -> None:
        row = [match.text, match.file, match.type, match.ner_score, match.engine]
        self._writer.writerow(row)

    def finalize(self, metadata: Optional[dict] = None) -> None:
        if self._file:
            self._file.close()
            self._file = None

    @property
    def supports_streaming(self) -> bool:
        return True

    def get_writer(self) -> csv.writer:
        return self._writer

    @property
    def file_handle(self) -> TextIO:
        return self._file


class JsonWriter(OutputWriter):
    """Writes findings to a JSON file."""

    def __init__(self, file_path: str, include_header: bool = True):
        super().__init__(file_path, include_header)
        self.matches: list[dict] = []

    def write_match(self, match: PiiMatch) -> None:
        # Convert match to dict
        match_dict = {
            "text": match.text,
            "file": match.file,
            "type": match.type,
            "score": match.ner_score,
            "engine": match.engine,
            "metadata": match.metadata,
        }
        self.matches.append(match_dict)

    def finalize(self, metadata: Optional[dict] = None) -> None:
        output_data = {"metadata": metadata or {}, "findings": self.matches}
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            raise OutputError(f"Failed to write JSON output: {e}")

    @property
    def supports_streaming(self) -> bool:
        return False


class JsonlWriter(OutputWriter):
    """Writes findings to a JSON Lines (JSONL) file.

    Each match is written as one JSON object per line for streaming and easy
    incremental processing. Metadata is appended as a final line with the key
    "_metadata".
    """

    def __init__(self, file_path: str, include_header: bool = True):
        super().__init__(file_path, include_header)
        try:
            self._file = open(file_path, "w", encoding="utf-8")
        except IOError as e:
            raise OutputError(f"Failed to open output file: {e}")

    def write_match(self, match: PiiMatch) -> None:
        payload = {
            "text": match.text,
            "file": match.file,
            "type": match.type,
            "score": match.ner_score,
            "engine": match.engine,
            "metadata": match.metadata,
        }
        self._file.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def finalize(self, metadata: Optional[dict] = None) -> None:
        if metadata:
            self._file.write(
                json.dumps({"_metadata": metadata}, ensure_ascii=False) + "\n"
            )
        if self._file:
            self._file.close()
            self._file = None

    @property
    def supports_streaming(self) -> bool:
        return True

    @property
    def file_handle(self) -> TextIO:
        return self._file


class XlsxWriter(OutputWriter):
    """Writes findings to an Excel file (streaming, write-only workbook)."""

    def __init__(self, file_path: str, include_header: bool = True):
        super().__init__(file_path, include_header)
        try:
            import openpyxl
        except ImportError:
            raise OutputError(
                "openpyxl is required for XLSX output but is not installed."
            )

        # Use write_only mode to avoid holding all rows in memory.
        self._openpyxl = openpyxl
        self._wb = openpyxl.Workbook(write_only=True)
        self._ws = self._wb.create_sheet("Findings")
        if self.include_header:
            self._ws.append(["Match", "File", "Type", "Score", "Engine"])

    def write_match(self, match: PiiMatch) -> None:
        self._ws.append([match.text, match.file, match.type, match.ner_score, match.engine])

    def finalize(self, metadata: Optional[dict] = None) -> None:
        # Add metadata sheet
        if metadata:
            ws_meta = self._wb.create_sheet("Metadata")
            ws_meta.append(["Key", "Value"])
            # Flatten metadata if needed or just dump top level
            for k, v in metadata.items():
                if isinstance(v, (dict, list)):
                    v = json.dumps(v)
                ws_meta.append([k, v])

        try:
            self._wb.save(self.file_path)
        except IOError as e:
            raise OutputError(f"Failed to save Excel file: {e}")

    @property
    def supports_streaming(self) -> bool:
        return True


class PrivacyStatisticsWriter(OutputWriter):
    """Writes privacy-focused statistics to a JSON file.

    This writer generates aggregated statistics by privacy dimensions and
    detection modules without storing individual PII instances or file paths.
    """

    def __init__(self, file_path: str, include_header: bool = True):
        super().__init__(file_path, include_header)
        # This writer doesn't collect matches, but we need to implement write_match
        # for compatibility with the abstract base class
        self._match_count = 0

    def write_match(self, match: PiiMatch) -> None:
        """Write a match (for compatibility).

        Note: This writer doesn't actually store matches, but tracks count
        for validation purposes.

        Args:
            match: PiiMatch object (not stored, only counted)
        """
        self._match_count += 1

    def finalize(self, metadata: Optional[dict] = None) -> None:
        """Write aggregated statistics to JSON file.

        Args:
            metadata: Dictionary containing:
                - statistics: Aggregated statistics from StatisticsAggregator
                - scan_metadata: Scan metadata (start_time, end_time, etc.)
        """
        if metadata is None:
            metadata = {}

        # Extract statistics and scan metadata
        statistics = metadata.get("statistics", {})
        scan_metadata = metadata.get("scan_metadata", {})

        # Build output structure
        output_data = {
            "metadata": scan_metadata,
            "statistics_by_dimension": statistics.get("statistics_by_dimension", {}),
            "statistics_by_module": statistics.get("statistics_by_module", {}),
            "statistics_by_file_type": statistics.get("statistics_by_file_type", {}),
            "summary": statistics.get("summary", {}),
            "performance_metrics": metadata.get("performance_metrics", {}),
        }

        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            raise OutputError(f"Failed to write statistics JSON output: {e}")

    @property
    def supports_streaming(self) -> bool:
        return False


def create_output_writer(
    output_format: str, file_path: str, include_header: bool = True
) -> OutputWriter:
    """Factory function to create the appropriate output writer."""
    if output_format == "json":
        return JsonWriter(file_path, include_header)
    elif output_format == "jsonl":
        return JsonlWriter(file_path, include_header)
    elif output_format == "xlsx":
        return XlsxWriter(file_path, include_header)
    elif output_format == "statistics":
        return PrivacyStatisticsWriter(file_path, include_header)

    # Default to CSV
    return CsvWriter(file_path, include_header)
