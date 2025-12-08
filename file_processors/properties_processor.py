"""Properties and INI file processor for extracting configuration data."""

import configparser
from file_processors.base_processor import BaseFileProcessor


class PropertiesProcessor(BaseFileProcessor):
    """Processor for Java properties files and INI configuration files.

    Extracts key-value pairs from configuration files.
    These files often contain credentials, API keys, and sensitive configuration.
    """

    def extract_text(self, file_path: str) -> str:
        """Extract text from properties or INI file.

        Args:
            file_path: Path to the properties/INI file

        Returns:
            Extracted text content (key-value pairs)

        Raises:
            UnicodeDecodeError: If file encoding cannot be decoded
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
        """
        with open(file_path, encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Try to parse as INI first (more structured)
        try:
            config = configparser.ConfigParser()
            config.read_string(content)

            # Extract all key-value pairs
            lines = []
            for section in config.sections():
                lines.append(f"[{section}]")
                for key, value in config.items(section):
                    lines.append(f"{key} = {value}")

            return "\n".join(lines)
        except (configparser.Error, AttributeError):
            # Fall back to simple properties format (key=value)
            # Properties files are simpler - just key=value pairs
            lines = []
            for line in content.split("\n"):
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith("#") and not line.startswith("!"):
                    # Handle key=value or key:value
                    if "=" in line:
                        key, value = line.split("=", 1)
                        lines.append(f"{key.strip()} = {value.strip()}")
                    elif ":" in line:
                        key, value = line.split(":", 1)
                        lines.append(f"{key.strip()} = {value.strip()}")

            return "\n".join(lines)

    @staticmethod
    def can_process(extension: str, file_path: str = "", mime_type: str = "") -> bool:
        """Check if this processor can handle the file.

        Args:
            extension: File extension
            file_path: Full path to the file
            mime_type: Detected MIME type

        Returns:
            True if file is a properties or INI file, False otherwise
        """
        ext_lower = extension.lower()
        if ext_lower in [".properties", ".ini", ".cfg", ".conf", ".env"]:
            return True

        if mime_type:
            return mime_type in [
                "text/x-properties",
                "text/plain",  # Properties files are often plain text
            ]

        return False
