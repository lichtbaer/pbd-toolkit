"""File type detection using magic numbers (file headers)."""

import os
from typing import Optional


class FileTypeDetector:
    """Detects file types using magic numbers (file headers).
    
    Supports multiple detection methods:
    - python-magic (requires libmagic system library, more accurate)
    - filetype (pure Python fallback, no system dependencies)
    """
    
    def __init__(self, enabled: bool = True):
        """Initialize detector.
        
        Args:
            enabled: Whether magic number detection is enabled
        """
        self.enabled = enabled
        self._magic = None
        self._filetype = None
        
        if enabled:
            self._init_magic()
    
    def _init_magic(self) -> None:
        """Initialize magic number detection libraries.
        
        Tries python-magic first (more accurate), falls back to filetype.
        """
        # Try python-magic first (more accurate)
        try:
            import magic
            self._magic = magic.Magic(mime=True)
        except ImportError:
            pass
        except Exception:
            # python-magic might be installed but libmagic not available
            pass
        
        # Fallback to filetype (pure Python)
        if not self._magic:
            try:
                import filetype
                self._filetype = filetype
            except ImportError:
                pass
    
    def detect_type(self, file_path: str) -> Optional[str]:
        """Detect file type using magic numbers.
        
        Args:
            file_path: Path to the file
            
        Returns:
            MIME type string (e.g., 'application/pdf') or None if detection fails
        """
        if not self.enabled:
            return None
        
        if not os.path.exists(file_path):
            return None
        
        # Try python-magic first
        if self._magic:
            try:
                return self._magic.from_file(file_path)
            except Exception:
                pass
        
        # Fallback to filetype
        if self._filetype:
            try:
                kind = self._filetype.guess(file_path)
                if kind:
                    return kind.mime
            except Exception:
                pass
        
        return None
    
    def get_extension_from_mime(self, mime_type: str) -> Optional[str]:
        """Get likely file extension from MIME type.
        
        Args:
            mime_type: MIME type string
            
        Returns:
            File extension (e.g., '.pdf') or None
        """
        mime_to_ext = {
            # Documents
            'application/pdf': '.pdf',
            'application/msword': '.doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'application/vnd.oasis.opendocument.text': '.odt',
            'application/rtf': '.rtf',
            # Spreadsheets
            'application/vnd.ms-excel': '.xls',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
            'application/vnd.oasis.opendocument.spreadsheet': '.ods',
            # Presentations
            'application/vnd.ms-powerpoint': '.ppt',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
            # Web formats
            'text/html': '.html',
            'text/xml': '.xml',
            'application/xml': '.xml',
            # Data formats
            'text/plain': '.txt',
            'text/csv': '.csv',
            'application/json': '.json',
            'application/yaml': '.yaml',
            'text/yaml': '.yaml',
            # Email
            'message/rfc822': '.eml',
            'application/vnd.ms-outlook': '.msg',
            'application/mbox': '.mbox',
            'text/mbox': '.mbox',
            # Archives
            'application/zip': '.zip',
            'application/x-zip-compressed': '.zip',
            # Databases
            'application/x-sqlite3': '.sqlite',
            'application/vnd.sqlite3': '.sqlite',
            'application/x-sqlite': '.sqlite',
            # Contacts
            'text/vcard': '.vcf',
            'text/x-vcard': '.vcf',
            'text/directory': '.vcf',
            # Configuration
            'text/x-properties': '.properties',
            # Calendar
            'text/calendar': '.ics',
            'text/x-calendar': '.ics',
            # Markdown
            'text/markdown': '.md',
            'text/x-markdown': '.md',
            # Images
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/bmp': '.bmp',
            'image/tiff': '.tiff',
            'image/webp': '.webp',
        }
        return mime_to_ext.get(mime_type)
    
    def is_available(self) -> bool:
        """Check if magic number detection is available.
        
        Returns:
            True if at least one detection library is available
        """
        return self._magic is not None or self._filetype is not None
