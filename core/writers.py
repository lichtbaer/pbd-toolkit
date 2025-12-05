"""Output writers for PII findings."""

import abc
import csv
import json
import os
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
            self._file = open(file_path, 'w', newline='', encoding='utf-8')
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
            "metadata": match.metadata
        }
        self.matches.append(match_dict)

    def finalize(self, metadata: Optional[dict] = None) -> None:
        output_data = {
            "metadata": metadata or {},
            "findings": self.matches
        }
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            raise OutputError(f"Failed to write JSON output: {e}")

    @property
    def supports_streaming(self) -> bool:
        return False


class XlsxWriter(OutputWriter):
    """Writes findings to an Excel file."""
    
    def __init__(self, file_path: str, include_header: bool = True):
        super().__init__(file_path, include_header)
        self.matches: list[dict] = []

    def write_match(self, match: PiiMatch) -> None:
        match_dict = {
            "text": match.text,
            "file": match.file,
            "type": match.type,
            "score": match.ner_score,
            "engine": match.engine
        }
        self.matches.append(match_dict)

    def finalize(self, metadata: Optional[dict] = None) -> None:
        try:
            import openpyxl
        except ImportError:
            raise OutputError("openpyxl is required for XLSX output but is not installed.")
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Findings"
        
        if self.include_header:
            ws.append(["Match", "File", "Type", "Score", "Engine"])
            
        for m in self.matches:
            ws.append([m["text"], m["file"], m["type"], m["score"], m["engine"]])
            
        # Add metadata sheet
        if metadata:
            ws_meta = wb.create_sheet("Metadata")
            ws_meta.append(["Key", "Value"])
            # Flatten metadata if needed or just dump top level
            for k, v in metadata.items():
                if isinstance(v, (dict, list)):
                    v = json.dumps(v)
                ws_meta.append([k, v])
                
        try:
            wb.save(self.file_path)
        except IOError as e:
            raise OutputError(f"Failed to save Excel file: {e}")

    @property
    def supports_streaming(self) -> bool:
        return False


def create_output_writer(output_format: str, file_path: str, include_header: bool = True) -> OutputWriter:
    """Factory function to create the appropriate output writer."""
    if output_format == "json":
        return JsonWriter(file_path, include_header)
    elif output_format == "xlsx":
        return XlsxWriter(file_path, include_header)
    
    # Default to CSV
    return CsvWriter(file_path, include_header)

