"""MSG file processor using extract-msg library."""

import re
from file_processors.base_processor import BaseFileProcessor


class MsgProcessor(BaseFileProcessor):
    """Processor for MSG (Microsoft Outlook Message) files.

    Extracts text from MSG files using the extract-msg library.
    Extracts headers (From, To, Subject, etc.), body content (both plain text and HTML),
    and attachment metadata for PII detection.
    """

    def extract_text(self, file_path: str) -> str:
        """Extract text from an MSG file.

        Extracts:
        - Email headers (From, To, Cc, Bcc, Subject, etc.)
        - Body content (plain text and HTML)
        - Attachment filenames and metadata

        Args:
            file_path: Path to the MSG file

        Returns:
            Extracted text content from headers, body, and attachments

        Raises:
            ImportError: If extract-msg is not installed
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
            Exception: For other MSG processing errors
        """
        try:
            import extract_msg
        except ImportError:
            raise ImportError(
                "extract-msg is required for MSG processing. "
                "Install it with: pip install extract-msg"
            )

        text_parts: list[str] = []

        try:
            # Open MSG file
            msg = extract_msg.Message(file_path)

            # Extract headers (these often contain PII)
            headers_to_extract = [
                "from",
                "to",
                "cc",
                "bcc",
                "replyTo",
                "subject",
                "returnPath",
                "sender",
                "receivedRepresentingName",
                "displayTo",
                "displayCc",
                "displayBcc",
            ]

            for header_name in headers_to_extract:
                header_value = getattr(msg, header_name, None)
                if header_value:
                    # Handle both string and list values
                    if isinstance(header_value, list):
                        text_parts.extend([str(v) for v in header_value if v])
                    else:
                        text_parts.append(str(header_value))

            # Extract body content
            # Try plain text first
            if hasattr(msg, "body") and msg.body:
                body_text = msg.body
                if body_text.strip():
                    text_parts.append(body_text.strip())

            # Try HTML body if available
            if hasattr(msg, "htmlBody") and msg.htmlBody:
                html_body = msg.htmlBody
                # Extract text from HTML (remove tags)
                text = self._extract_text_from_html(html_body)
                if text.strip():
                    text_parts.append(text.strip())

            # Extract attachment metadata (filenames may contain PII)
            if hasattr(msg, "attachments") and msg.attachments:
                for attachment in msg.attachments:
                    # Extract attachment filename
                    if hasattr(attachment, "longFilename") and attachment.longFilename:
                        text_parts.append(attachment.longFilename)
                    elif (
                        hasattr(attachment, "shortFilename")
                        and attachment.shortFilename
                    ):
                        text_parts.append(attachment.shortFilename)

                    # Extract attachment display name if available
                    if hasattr(attachment, "displayName") and attachment.displayName:
                        text_parts.append(attachment.displayName)

            # Extract other properties that might contain PII
            # Email addresses from various properties
            email_properties = [
                "senderEmail",
                "senderEmailAddress",
                "senderName",
                "receivedRepresentingEmail",
                "receivedRepresentingEmailAddress",
                "sentRepresentingEmail",
                "sentRepresentingEmailAddress",
            ]

            for prop_name in email_properties:
                prop_value = getattr(msg, prop_name, None)
                if prop_value:
                    text_parts.append(str(prop_value))

            # Close the message file
            msg.close()

        except Exception as e:
            # Re-raise with context
            raise Exception(f"Error processing MSG file: {str(e)}") from e

        return " ".join(text_parts)

    def _extract_text_from_html(self, html_content: str) -> str:
        """Extract plain text from HTML content.

        Removes HTML tags and extracts text content.
        Uses simple regex approach for basic HTML tag removal.

        Args:
            html_content: HTML content as string

        Returns:
            Plain text extracted from HTML
        """
        if not html_content:
            return ""

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", html_content)

        # Decode HTML entities (basic ones)
        html_entities = {
            "&nbsp;": " ",
            "&amp;": "&",
            "&lt;": "<",
            "&gt;": ">",
            "&quot;": '"',
            "&apos;": "'",
        }
        for entity, char in html_entities.items():
            text = text.replace(entity, char)

        # Clean up whitespace
        text = " ".join(text.split())

        return text

    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle MSG files."""
        return extension.lower() == ".msg"
