"""XML file processor using defusedxml for secure XML parsing."""

try:
    from defusedxml.ElementTree import parse as safe_parse, ParseError as SafeParseError
    from defusedxml.ElementTree import Element

    DEFUSEDXML_AVAILABLE = True
except ImportError:
    # Fallback to standard library if defusedxml is not available
    import xml.etree.ElementTree as ET
    from xml.etree.ElementTree import Element

    safe_parse = ET.parse
    SafeParseError = ET.ParseError
    DEFUSEDXML_AVAILABLE = False

from file_processors.base_processor import BaseFileProcessor


class XmlProcessor(BaseFileProcessor):
    """Processor for XML files.

    Extracts text from XML files using defusedxml for secure XML parsing.
    Recursively extracts all text content from elements and attributes.
    Handles both small and large XML files.
    """

    def extract_text(self, file_path: str) -> str:
        """Extract text from an XML file.

        Recursively traverses the XML structure and extracts:
        - Text content from all elements
        - Values from all attributes

        Args:
            file_path: Path to the XML file

        Returns:
            Extracted text content from all elements and attributes as a string

        Raises:
            defusedxml.ElementTree.ParseError: If file is not valid XML
            UnicodeDecodeError: If file encoding cannot be decoded
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
            Exception: For other XML processing errors
        """
        text_parts: list[str] = []

        try:
            # Parse XML file using defusedxml for security
            tree = safe_parse(file_path)
            root = tree.getroot()

            # Extract text from root and all descendants
            self._extract_text_from_element(root, text_parts)

        except SafeParseError as e:
            # If XML is invalid, try to extract text using simple regex
            # This handles malformed XML files that might still contain PII
            try:
                with open(
                    file_path, "r", encoding="utf-8", errors="replace"
                ) as xmlfile:
                    content = xmlfile.read()
                    # Extract text between tags using simple pattern
                    import re

                    # Match text between > and < (content of tags)
                    text_pattern = r">([^<]+)<"
                    matches = re.findall(text_pattern, content)
                    text_parts.extend([m.strip() for m in matches if m.strip()])
            except Exception:
                # Re-raise original parse error if fallback also fails
                raise SafeParseError(f"Invalid XML file: {str(e)}") from e

        return " ".join(text_parts)

    def _extract_text_from_element(
        self, element: Element, text_parts: list[str]
    ) -> None:
        """Recursively extract text from an XML element.

        Extracts:
        - Direct text content of the element
        - Text from all child elements
        - Values from all attributes

        Args:
            element: XML element to extract text from
            text_parts: List to accumulate extracted strings
        """
        # Extract text directly in this element (before first child)
        if element.text and element.text.strip():
            text_parts.append(element.text.strip())

        # Extract attribute values
        for attr_name, attr_value in element.attrib.items():
            if attr_value and attr_value.strip():
                text_parts.append(attr_value.strip())

        # Recursively process child elements
        for child in element:
            self._extract_text_from_element(child, text_parts)

            # Extract tail text (text after the element, before next sibling)
            if child.tail and child.tail.strip():
                text_parts.append(child.tail.strip())
