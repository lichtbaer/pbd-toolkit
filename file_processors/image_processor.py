"""Image file processor for extracting text and metadata from images."""

import base64
import os
from typing import Optional
from file_processors.base_processor import BaseFileProcessor


class ImageProcessor(BaseFileProcessor):
    """Processor for image files.

    Extracts image data for multimodal model processing.
    Supports: JPEG, PNG, GIF, BMP, TIFF, WebP
    """

    SUPPORTED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"]

    def extract_text(self, file_path: str) -> str:
        """Extract image data as base64 for multimodal processing.

        Note: This doesn't extract actual text, but prepares image
        for multimodal model processing. The actual text extraction
        happens in the multimodal detection engine.

        Args:
            file_path: Path to image file

        Returns:
            Empty string (actual processing happens in multimodal engine)
        """
        # For now, return empty string - actual processing in engine
        # The engine will read the file directly
        return ""

    def get_image_base64(self, file_path: str) -> Optional[str]:
        """Get base64-encoded image data.

        Args:
            file_path: Path to image file

        Returns:
            Base64-encoded string or None if error
        """
        try:
            with open(file_path, "rb") as img_file:
                img_data = img_file.read()
                return base64.b64encode(img_data).decode("utf-8")
        except Exception:
            return None

    def get_image_mime_type(self, file_path: str) -> Optional[str]:
        """Get MIME type for image.

        Args:
            file_path: Path to image file

        Returns:
            MIME type string or None
        """
        ext = os.path.splitext(file_path)[1].lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
            ".webp": "image/webp",
        }
        return mime_types.get(ext)

    @staticmethod
    def can_process(extension: str, file_path: str = "", mime_type: str = "") -> bool:
        """Check if this processor can handle the file.

        Args:
            extension: File extension
            file_path: Full file path
            mime_type: Detected MIME type

        Returns:
            True if file is an image, False otherwise
        """
        # Check by extension
        if extension.lower() in ImageProcessor.SUPPORTED_EXTENSIONS:
            return True

        # Check by detected MIME type
        if mime_type and mime_type.startswith("image/"):
            return True

        return False
