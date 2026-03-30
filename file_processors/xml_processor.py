"""XML file processor using defusedxml for secure XML parsing."""

from xml.etree.ElementTree import Element

from file_processors.base_processor import BaseFileProcessor

_defusedxml_import_error: ImportError | None = None
try:
    from defusedxml.ElementTree import ParseError as SafeParseError
    from defusedxml.ElementTree import parse as safe_parse

    DEFUSEDXML_AVAILABLE = True
except ImportError as _exc:
    # defusedxml is a required security dependency – do NOT fall back to the
    # standard-library xml.etree.ElementTree, which is vulnerable to XML bomb
    # (Billion Laughs) and other entity-expansion attacks.
    _defusedxml_import_error = _exc
    DEFUSEDXML_AVAILABLE = False

    # Provide stub names so the module can be imported without defusedxml
    # installed; XmlProcessor.extract_text() will raise ImportError at call time.
    def safe_parse(*_args, **_kwargs):  # type: ignore[misc]
        raise ImportError(
            "defusedxml is required for secure XML parsing. "
            "Install it with: pip install defusedxml"
        ) from _defusedxml_import_error

    class SafeParseError(Exception):  # type: ignore[no-redef]
        pass


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

        except SafeParseError:
            # Do NOT fall back to regex-based extraction — that would bypass
            # the security guarantees of defusedxml (XXE, billion-laughs, etc.).
            # Let the caller handle the parse error via its standard error path.
            import logging

            logging.getLogger(__name__).warning(
                "Skipping malformed XML file (defusedxml rejected it): %s",
                file_path,
            )
            raise

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
