"""EML file processor using Python's built-in email module."""

import email
from email.policy import default
from file_processors.base_processor import BaseFileProcessor


class EmlProcessor(BaseFileProcessor):
    """Processor for EML (Email Message) files.
    
    Extracts text from EML files using Python's built-in email module.
    Extracts headers (From, To, Subject, etc.) and body content (both plain text and HTML).
    """
    
    def extract_text(self, file_path: str) -> str:
        """Extract text from an EML file.
        
        Args:
            file_path: Path to the EML file
            
        Returns:
            Extracted text content from headers and body
            
        Raises:
            email.errors.MessageError: If file is not a valid email message
            UnicodeDecodeError: If file encoding cannot be decoded
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
            Exception: For other EML processing errors
        """
        text_parts: list[str] = []
        
        try:
            with open(file_path, 'rb') as eml_file:
                msg = email.message_from_bytes(eml_file.read(), policy=default)
            
            # Extract headers (these often contain PII)
            headers_to_extract = [
                'From', 'To', 'Cc', 'Bcc', 'Reply-To', 'Subject',
                'Return-Path', 'Sender', 'Received'
            ]
            
            for header_name in headers_to_extract:
                header_value = msg.get(header_name)
                if header_value:
                    text_parts.append(str(header_value))
            
            # Extract body content
            body_text = self._extract_body_text(msg)
            if body_text:
                text_parts.append(body_text)
            
        except Exception as e:
            # Re-raise with context
            raise Exception(f"Error processing EML file: {str(e)}") from e
        
        return ' '.join(text_parts)
    
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
                
                if content_type == 'text/plain':
                    payload = part.get_payload(decode=True)
                    if payload:
                        try:
                            # Try to decode with charset from part
                            charset = part.get_content_charset() or 'utf-8'
                            text = payload.decode(charset, errors='replace')
                            text_parts.append(text)
                        except (UnicodeDecodeError, LookupError):
                            # Fallback to utf-8 with error replacement
                            text = payload.decode('utf-8', errors='replace')
                            text_parts.append(text)
                
                elif content_type == 'text/html':
                    # Extract text from HTML (simple approach - just get the text)
                    payload = part.get_payload(decode=True)
                    if payload:
                        try:
                            charset = part.get_content_charset() or 'utf-8'
                            html_content = payload.decode(charset, errors='replace')
                            # Simple HTML tag removal (basic approach)
                            # For better results, could use BeautifulSoup, but keeping it simple
                            import re
                            # Remove HTML tags
                            text = re.sub(r'<[^>]+>', ' ', html_content)
                            # Clean up whitespace
                            text = ' '.join(text.split())
                            if text.strip():
                                text_parts.append(text)
                        except (UnicodeDecodeError, LookupError):
                            pass
        else:
            # Single part message
            payload = msg.get_payload(decode=True)
            if payload:
                try:
                    charset = msg.get_content_charset() or 'utf-8'
                    text = payload.decode(charset, errors='replace')
                    text_parts.append(text)
                except (UnicodeDecodeError, LookupError):
                    text = payload.decode('utf-8', errors='replace')
                    text_parts.append(text)
        
        return ' '.join(text_parts)
    
    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle EML files."""
        return extension.lower() == ".eml"
