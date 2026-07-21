"""MBOX mailbox processor for extracting emails from Unix mailboxes."""

import email
import logging
from collections.abc import Iterator

from core import skip_counters
from file_processors.base_processor import BaseFileProcessor

_logger = logging.getLogger(__name__)


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
            current_message: list[bytes] = []

            for line in f:
                # Check if this is a new message delimiter
                if line.startswith(b"From "):
                    # Process previous message if exists
                    if current_message:
                        try:
                            msg_text = self._process_message(b"".join(current_message))
                            if msg_text:
                                yield msg_text
                        except Exception as exc:
                            # Skip messages that can't be parsed
                            _logger.debug(
                                "Skipping unparseable message in MBOX: %s: %s",
                                file_path,
                                exc,
                            )
                            skip_counters.record_skip("mbox_message_unparseable")
                        current_message = []

                current_message.append(line)

            # Process last message
            if current_message:
                try:
                    msg_text = self._process_message(b"".join(current_message))
                    if msg_text:
                        yield msg_text
                except Exception as exc:
                    _logger.debug(
                        "Skipping unparseable message in MBOX: %s: %s",
                        file_path,
                        exc,
                    )
                    skip_counters.record_skip("mbox_message_unparseable")

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
                        if isinstance(payload, bytes):
                            try:
                                charset = part.get_content_charset() or "utf-8"
                                body_parts.append(
                                    payload.decode(charset, errors="replace")
                                )
                            except Exception as exc:
                                _logger.debug(
                                    "Failed to decode text/plain part: %s", exc
                                )
                    elif content_type == "text/html":
                        # Extract text from HTML (simple approach)
                        payload = part.get_payload(decode=True)
                        if isinstance(payload, bytes):
                            try:
                                charset = part.get_content_charset() or "utf-8"
                                html_text = payload.decode(charset, errors="replace")
                                # Simple HTML tag removal
                                import re

                                html_text = re.sub(r"<[^>]+>", "", html_text)
                                body_parts.append(html_text)
                            except Exception as exc:
                                _logger.debug(
                                    "Failed to decode text/html part: %s", exc
                                )
            else:
                # Single part message
                payload = msg.get_payload(decode=True)
                if isinstance(payload, bytes):
                    try:
                        charset = msg.get_content_charset() or "utf-8"
                        body_parts.append(payload.decode(charset, errors="replace"))
                    except Exception as exc:
                        _logger.debug(
                            "Failed to decode single-part message body: %s", exc
                        )

            # Combine headers and body
            result = "\n".join(headers)
            if body_parts:
                result += "\n\n" + "\n".join(body_parts)

            return result
        except Exception as exc:
            # Return raw text if parsing fails
            _logger.debug("Email message parse failed, using raw text: %s", exc)
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
            except Exception as exc:
                _logger.debug("Could not read file header for %s: %s", file_path, exc)

        return False
