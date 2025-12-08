"""vCard (VCF) file processor for extracting contact information."""

from file_processors.base_processor import BaseFileProcessor


class VcfProcessor(BaseFileProcessor):
    """Processor for vCard (VCF) contact files.

    Extracts contact information from vCard files.
    vCard files have high PII density (names, phones, emails, addresses).
    """

    def extract_text(self, file_path: str) -> str:
        """Extract text from vCard file.

        Args:
            file_path: Path to the vCard file

        Returns:
            Extracted text content from vCard

        Raises:
            UnicodeDecodeError: If file encoding cannot be decoded
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
        """
        with open(file_path, encoding="utf-8", errors="replace") as f:
            content = f.read()

        # vCard format is text-based, but we can clean it up
        # Remove vCard formatting codes but keep the content
        lines = content.split("\n")
        cleaned_lines = []

        for line in lines:
            # Skip empty lines and BEGIN/END markers (keep content)
            if (
                line.strip()
                and not line.strip().startswith("BEGIN:")
                and not line.strip().startswith("END:")
            ):
                # Remove vCard property prefixes but keep values
                # Format: PROPERTY:value or PROPERTY;PARAM:value
                if ":" in line:
                    # Extract value part after last colon
                    value = line.split(":")[-1]
                    # Unescape vCard escaping (\\ -> \, \n -> newline, \, -> comma)
                    value = (
                        value.replace("\\n", "\n")
                        .replace("\\,", ",")
                        .replace("\\\\", "\\")
                    )
                    if value.strip():
                        cleaned_lines.append(value)

        return "\n".join(cleaned_lines)

    @staticmethod
    def can_process(extension: str, file_path: str = "", mime_type: str = "") -> bool:
        """Check if this processor can handle the file.

        Args:
            extension: File extension
            file_path: Full path to the file
            mime_type: Detected MIME type

        Returns:
            True if file is a vCard file, False otherwise
        """
        if extension.lower() == ".vcf":
            return True

        if mime_type:
            return mime_type in ["text/vcard", "text/x-vcard", "text/directory"]

        # Check file content if file_path is provided
        if file_path and extension == "":
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    first_line = f.readline().strip()
                    if first_line == "BEGIN:VCARD":
                        return True
            except Exception:
                pass

        return False
