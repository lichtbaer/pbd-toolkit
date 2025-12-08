"""iCalendar (ICS) file processor for extracting calendar data."""

from file_processors.base_processor import BaseFileProcessor


class IcalProcessor(BaseFileProcessor):
    """Processor for iCalendar (ICS) files.

    Extracts calendar event information including participants,
    locations, descriptions, and notes which may contain PII.
    """

    def extract_text(self, file_path: str) -> str:
        """Extract text from iCalendar file.

        Args:
            file_path: Path to the ICS file

        Returns:
            Extracted text content from calendar

        Raises:
            UnicodeDecodeError: If file encoding cannot be decoded
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
        """
        with open(file_path, encoding="utf-8", errors="replace") as f:
            content = f.read()

        # iCalendar format is text-based with line continuation
        # Lines ending with semicolon or comma continue on next line
        lines = content.split("\n")
        cleaned_lines = []
        current_line = ""

        for line in lines:
            # Remove line continuation (lines ending with semicolon or comma)
            if line.endswith(";") or line.endswith(","):
                current_line += line.rstrip(";,")
                continue
            else:
                current_line += line
                cleaned_lines.append(current_line)
                current_line = ""

        # Extract relevant properties that may contain PII
        # Properties: SUMMARY, DESCRIPTION, LOCATION, ORGANIZER, ATTENDEE, CONTACT, etc.
        relevant_properties = [
            "SUMMARY",
            "DESCRIPTION",
            "LOCATION",
            "ORGANIZER",
            "ATTENDEE",
            "CONTACT",
            "ATTACH",
            "COMMENT",
            "RESOURCES",
            "URL",
            "UID",
            "CREATED",
            "LAST-MODIFIED",
        ]

        extracted = []
        for line in cleaned_lines:
            line_upper = line.upper()
            for prop in relevant_properties:
                if line_upper.startswith(prop + ":"):
                    # Extract value after colon
                    if ":" in line:
                        value = line.split(":", 1)[1]
                        # Unescape iCalendar escaping
                        value = (
                            value.replace("\\n", "\n")
                            .replace("\\,", ",")
                            .replace("\\\\", "\\")
                        )
                        # Remove property parameters (e.g., ORGANIZER;CN=Name:email@example.com)
                        if ";" in value:
                            # Keep the part after last semicolon if it contains @ (email)
                            parts = value.split(";")
                            for part in reversed(parts):
                                if "@" in part or "=" in part:
                                    value = (
                                        part.split(":", 1)[-1] if ":" in part else part
                                    )
                                    break
                        extracted.append(f"{prop}: {value}")
                    break

        return "\n".join(extracted)

    @staticmethod
    def can_process(extension: str, file_path: str = "", mime_type: str = "") -> bool:
        """Check if this processor can handle the file.

        Args:
            extension: File extension
            file_path: Full path to the file
            mime_type: Detected MIME type

        Returns:
            True if file is an iCalendar file, False otherwise
        """
        if extension.lower() in [".ics", ".ical", ".ifb"]:
            return True

        if mime_type:
            return mime_type in ["text/calendar", "text/x-calendar"]

        # Check file content if file_path is provided
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    first_line = f.readline().strip()
                    if first_line == "BEGIN:VCALENDAR":
                        return True
            except Exception:
                pass

        return False
