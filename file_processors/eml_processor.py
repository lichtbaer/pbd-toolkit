"""EML file processor using Python's built-in email module."""

import email
import logging
import os
import tempfile
from email.policy import default

from core import skip_counters
from file_processors.base_processor import BaseFileProcessor

_logger = logging.getLogger(__name__)

# Limits for recursive attachment extraction (defence against decompression bombs
# and message/rfc822 loops).
_MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024  # 50 MB per attachment
_MAX_ATTACHMENTS = 50  # per message
_MAX_ATTACHMENT_DEPTH = 3  # nested .eml within .eml within .eml


class EmlProcessor(BaseFileProcessor):
    """Processor for EML (Email Message) files.

    Extracts text from EML files using Python's built-in email module.
    Extracts headers (From, To, Subject, etc.), body content (plain text and HTML),
    and recursively extracts text from attachments by routing each attachment back
    through the file-processor registry (so a PDF or spreadsheet attached to an email
    is scanned for PII just like a standalone file).
    """

    def extract_text(self, file_path: str, *, _depth: int = 0) -> str:
        """Extract text from an EML file.

        Args:
            file_path: Path to the EML file
            _depth: Internal recursion depth for nested .eml attachments.

        Returns:
            Extracted text content from headers, body and attachments

        Raises:
            email.errors.MessageError: If file is not a valid email message
            UnicodeDecodeError: If file encoding cannot be decoded
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
            Exception: For other EML processing errors
        """
        text_parts: list[str] = []

        try:
            with open(file_path, "rb") as eml_file:
                msg = email.message_from_bytes(eml_file.read(), policy=default)

            # Extract headers (these often contain PII)
            headers_to_extract = [
                "From",
                "To",
                "Cc",
                "Bcc",
                "Reply-To",
                "Subject",
                "Return-Path",
                "Sender",
                "Received",
            ]

            for header_name in headers_to_extract:
                header_value = msg.get(header_name)
                if header_value:
                    text_parts.append(str(header_value))

            # Extract body content
            body_text = self._extract_body_text(msg)
            if body_text:
                text_parts.append(body_text)

            # Recursively extract text from attachments
            text_parts.extend(self._extract_attachments(msg, _depth))

        except FileNotFoundError:
            raise
        except PermissionError:
            raise
        except Exception as e:
            # Re-raise with context
            raise Exception(f"Error processing EML file: {str(e)}") from e

        return " ".join(text_parts)

    def _extract_attachments(
        self, msg: email.message.EmailMessage, depth: int
    ) -> list[str]:
        """Extract text from attachments by routing them through the registry.

        Body parts (text/plain, text/html) are already handled by
        ``_extract_body_text`` and skipped here.  Each remaining attachment is written
        to a temporary file and dispatched to the matching file processor, so attached
        PDFs, spreadsheets, documents, etc. are scanned for PII as well.
        """
        if depth >= _MAX_ATTACHMENT_DEPTH:
            return []

        # Lazy import avoids a circular import (registry imports this module).
        from file_processors.registry import FileProcessorRegistry

        parts: list[str] = []
        count = 0
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            filename = part.get_filename()
            disposition = (part.get_content_disposition() or "").lower()
            is_attachment = disposition == "attachment" or filename is not None
            if not is_attachment:
                continue
            # Body text parts are covered elsewhere; avoid double extraction.
            if part.get_content_type() in ("text/plain", "text/html"):
                continue

            payload = part.get_payload(decode=True)
            if not payload:
                continue
            if len(payload) > _MAX_ATTACHMENT_BYTES:
                _logger.warning(
                    "Skipping oversized email attachment (%d MB): %s",
                    len(payload) // (1024 * 1024),
                    filename or "<unnamed>",
                )
                skip_counters.record_skip("eml_attachment_oversized")
                continue

            count += 1
            if count > _MAX_ATTACHMENTS:
                _logger.warning(
                    "Too many attachments; stopping at %d", _MAX_ATTACHMENTS
                )
                skip_counters.record_skip("eml_attachment_limit_reached")
                break

            text = self._extract_attachment_payload(
                FileProcessorRegistry, payload, filename, part.get_content_type(), depth
            )
            if text and text.strip():
                parts.append(f"[Attachment: {filename or 'unnamed'}]\n{text}")

        return parts

    def _extract_attachment_payload(
        self,
        registry,
        payload: bytes,
        filename: str | None,
        content_type: str,
        depth: int,
    ) -> str:
        """Write *payload* to a temp file and extract text via the matching processor."""
        ext = os.path.splitext(filename)[1].lower() if filename else ""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=ext or ".bin", delete=False) as tmp:
                tmp.write(payload)
                tmp_path = tmp.name

            processor = registry.get_processor(ext, tmp_path, content_type)
            if processor is None:
                return ""

            # Nested .eml: pass recursion depth to enforce the depth limit.
            if isinstance(processor, EmlProcessor):
                result = processor.extract_text(tmp_path, _depth=depth + 1)
            else:
                result = processor.extract_text(tmp_path)

            if isinstance(result, str):
                return result
            return "\n".join(chunk for chunk in result)
        except Exception as exc:
            _logger.debug("Skipping unreadable email attachment %s: %s", filename, exc)
            skip_counters.record_skip("eml_attachment_unreadable")
            return ""
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError as exc:
                    _logger.debug("Failed to remove temp file %s: %s", tmp_path, exc)

    def _extract_body_text(self, msg: email.message.EmailMessage) -> str:
        """Extract text from email body, handling multipart messages.

        Args:
            msg: Email message object

        Returns:
            Extracted text from body
        """
        text_parts: list[str] = []

        if msg.is_multipart():
            # Handle multipart messages (may contain both plain text and HTML)
            for part in msg.walk():
                content_type = part.get_content_type()

                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        try:
                            # Try to decode with charset from part
                            charset = part.get_content_charset() or "utf-8"
                            text = payload.decode(charset, errors="replace")
                            text_parts.append(text)
                        except (UnicodeDecodeError, LookupError):
                            # Fallback to utf-8 with error replacement
                            text = payload.decode("utf-8", errors="replace")
                            text_parts.append(text)

                elif content_type == "text/html":
                    # Extract text from HTML (simple approach - just get the text)
                    payload = part.get_payload(decode=True)
                    if payload:
                        try:
                            charset = part.get_content_charset() or "utf-8"
                            html_content = payload.decode(charset, errors="replace")
                        except (UnicodeDecodeError, LookupError) as exc:
                            # Unknown/unsupported charset name: fall back to utf-8
                            # rather than silently dropping the whole HTML body,
                            # matching the text/plain branch above.
                            _logger.debug(
                                "Falling back to utf-8 for text/html part (charset=%r): %s",
                                charset,
                                exc,
                            )
                            html_content = payload.decode("utf-8", errors="replace")
                        # Simple HTML tag removal (basic approach)
                        # For better results, could use BeautifulSoup, but keeping it simple
                        import re

                        # Remove HTML tags
                        text = re.sub(r"<[^>]+>", " ", html_content)
                        # Clean up whitespace
                        text = " ".join(text.split())
                        if text.strip():
                            text_parts.append(text)
        else:
            # Single part message
            payload = msg.get_payload(decode=True)
            if payload:
                try:
                    charset = msg.get_content_charset() or "utf-8"
                    text = payload.decode(charset, errors="replace")
                    text_parts.append(text)
                except (UnicodeDecodeError, LookupError):
                    text = payload.decode("utf-8", errors="replace")
                    text_parts.append(text)

        return " ".join(text_parts)

    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle EML files."""
        return extension.lower() == ".eml"
