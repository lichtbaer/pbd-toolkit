"""MBOX mailbox processor for extracting emails from Unix mailboxes."""

import email
from typing import Iterator
from file_processors.base_processor import BaseFileProcessor


class MboxProcessor(BaseFileProcessor):
    """Processor for MBOX mailbox files.

    Extracts emails from Unix mailbox format (MBOX).
    Used by Thunderbird, Gmail exports, and other mail clients.
    """

    def extract_text(self, file_path: str) -> Iterator[str]:
        """Extract text from MBOX mailbox file.

        Args:
            file_path: Path to the MBOX file

        Yields:
            Text content from each email in the mailbox

        Raises:
            UnicodeDecodeError: If file encoding cannot be decoded
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
        """
        with open(file_path, "rb") as f:
            # MBOX format: emails separated by "From " lines
            current_message = []

            for line in f:
                # Check if this is a new message delimiter
                if line.startswith(b"From "):
                    # Process previous message if exists
                    if current_message:
                        try:
                            msg_text = self._process_message(b"".join(current_message))
                            if msg_text:
                                yield msg_text
                        except Exception:
                            # Skip messages that can't be parsed
                            pass
                        current_message = []

                current_message.append(line)

            # Process last message
            if current_message:
                try:
                    msg_text = self._process_message(b"".join(current_message))
                    if msg_text:
                        yield msg_text
                except Exception:
                    pass

    def _process_message(self, message_bytes: bytes) -> str:
        """Process a single email message.

        Args:
            message_bytes: Raw email message bytes

        Returns:
            Extracted text from email
        """
        try:
            # Parse email message
            msg = email.message_from_bytes(message_bytes)

            # Extract headers
            headers = []
            for header in ["From", "To", "Cc", "Bcc", "Subject", "Date"]:
                value = msg.get(header, "")
                if value:
                    headers.append(f"{header}: {value}")

            # Extract body
            body_parts = []

            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            try:
                                charset = part.get_content_charset() or "utf-8"
                                body_parts.append(
                                    payload.decode(charset, errors="replace")
                                )
                            except Exception:
                                pass
                    elif content_type == "text/html":
                        # Extract text from HTML (simple approach)
                        payload = part.get_payload(decode=True)
                        if payload:
                            try:
                                charset = part.get_content_charset() or "utf-8"
                                html_text = payload.decode(charset, errors="replace")
                                # Simple HTML tag removal
                                import re

                                html_text = re.sub(r"<[^>]+>", "", html_text)
                                body_parts.append(html_text)
                            except Exception:
                                pass
            else:
                # Single part message
                payload = msg.get_payload(decode=True)
                if payload:
                    try:
                        charset = msg.get_content_charset() or "utf-8"
                        body_parts.append(payload.decode(charset, errors="replace"))
                    except Exception:
                        pass

            # Combine headers and body
            result = "\n".join(headers)
            if body_parts:
                result += "\n\n" + "\n".join(body_parts)

            return result
        except Exception:
            # Return raw text if parsing fails
            try:
                return message_bytes.decode("utf-8", errors="replace")
            except Exception:
                return message_bytes.decode("latin-1", errors="replace")

    @staticmethod
    def can_process(extension: str, file_path: str = "", mime_type: str = "") -> bool:
        """Check if this processor can handle the file.

        Args:
            extension: File extension
            file_path: Full path to the file
            mime_type: Detected MIME type

        Returns:
            True if file is an MBOX mailbox, False otherwise
        """
        if extension.lower() == ".mbox":
            return True

        if mime_type:
            return mime_type in ["application/mbox", "text/mbox"]

        # Check file content if file_path is provided
        if file_path:
            try:
                with open(file_path, "rb") as f:
                    first_line = f.readline()
                    # MBOX files typically start with "From " followed by email address
                    if first_line.startswith(b"From "):
                        return True
            except Exception:
                pass

        return False
