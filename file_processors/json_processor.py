"""JSON file processor using Python's built-in json module."""

import json
from typing import Any
from file_processors.base_processor import BaseFileProcessor


class JsonProcessor(BaseFileProcessor):
    """Processor for JSON files.
    
    Extracts text from JSON files using Python's built-in json module.
    Recursively extracts all string values (both keys and values) for PII detection.
    Handles nested structures, arrays, and objects.
    """
    
    def extract_text(self, file_path: str) -> str:
        """Extract text from a JSON file.
        
        Recursively traverses the JSON structure and extracts all string values.
        Both keys and values are extracted to maximize PII detection coverage.
        
        Args:
            file_path: Path to the JSON file
            
        Returns:
            Extracted text content from all string values as a single string
            
        Raises:
            json.JSONDecodeError: If file is not valid JSON
            UnicodeDecodeError: If file encoding cannot be decoded
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
            Exception: For other JSON processing errors
        """
        text_parts: list[str] = []
        
        with open(file_path, 'r', encoding='utf-8', errors='replace') as jsonfile:
            try:
                data: Any = json.load(jsonfile)
                self._extract_strings(data, text_parts)
            except json.JSONDecodeError as e:
                # If JSON is invalid, try to read as text and extract strings
                # This handles malformed JSON files that might still contain PII
                jsonfile.seek(0)
                content = jsonfile.read()
                # Extract potential string values using simple heuristics
                # Look for patterns like "key": "value" or 'key': 'value'
                import re
                string_pattern = r'["\']([^"\']+)["\']'
                matches = re.findall(string_pattern, content)
                text_parts.extend(matches)
        
        return ' '.join(text_parts)
    
    def _extract_strings(self, obj: Any, text_parts: list[str]) -> None:
        """Recursively extract all string values from a JSON object.
        
        Args:
            obj: The JSON object (dict, list, or primitive)
            text_parts: List to accumulate extracted strings
        """
        if isinstance(obj, dict):
            for key, value in obj.items():
                # Extract key if it's a string
                if isinstance(key, str) and key.strip():
                    text_parts.append(key.strip())
                # Recursively process value
                self._extract_strings(value, text_parts)
        elif isinstance(obj, list):
            for item in obj:
                self._extract_strings(item, text_parts)
        elif isinstance(obj, str):
            # Extract string value
            if obj.strip():
                text_parts.append(obj.strip())
        # Numbers, booleans, None are ignored as they're not useful for PII detection
    
    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle JSON files."""
        return extension.lower() == ".json"
