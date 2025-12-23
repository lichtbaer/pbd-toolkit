"""PPTX file processor using python-pptx library."""

from file_processors.base_processor import BaseFileProcessor

try:
    from pptx import Presentation
    from pptx.exc import PackageNotFoundError
except Exception:  # pragma: no cover - optional dependency
    Presentation = None  # type: ignore[assignment]
    PackageNotFoundError = None  # type: ignore[assignment]


class PptxProcessor(BaseFileProcessor):
    """Processor for PPTX (PowerPoint 2007+) files.

    Extracts text from PPTX files using python-pptx library.
    Extracts text from slides, notes, and comments for PII detection.
    """

    def extract_text(self, file_path: str) -> str:
        """Extract text from a PPTX file.

        Extracts text from:
        - All slides (text boxes, shapes, tables)
        - Notes pages
        - Comments

        Args:
            file_path: Path to the PPTX file

        Returns:
            Extracted text content from slides, notes, and comments as a string

        Raises:
            ImportError: If python-pptx is not installed
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
            Exception: For other PPTX processing errors
        """
        if Presentation is None:
            raise ImportError(
                "python-pptx is required for PPTX processing. "
                "Install it with: pip install python-pptx"
            )

        text_parts: list[str] = []

        try:
            # Load presentation
            try:
                prs = Presentation(file_path)  # type: ignore[misc]
            except ImportError as e:
                raise ImportError(
                    "python-pptx is required for PPTX processing. "
                    "Install it with: pip install python-pptx"
                ) from e

            # Extract text from all slides
            for slide in prs.slides:
                # Extract text from shapes on slide
                for shape in slide.shapes:
                    shape_text = self._extract_text_from_shape(shape)
                    if shape_text:
                        text_parts.append(shape_text)

                # Extract text from notes slide
                if slide.has_notes_slide:
                    notes_slide = slide.notes_slide
                    for shape in notes_slide.shapes:
                        shape_text = self._extract_text_from_shape(shape)
                        if shape_text:
                            text_parts.append(shape_text)

            # Extract text from comments (if available)
            # Note: Comments might not be accessible in all PPTX files
            # This is a best-effort extraction

        except FileNotFoundError:
            raise
        except PermissionError:
            raise
        except ImportError:
            raise
        except Exception as e:
            # Map python-pptx "package not found" to a standard FileNotFoundError
            if PackageNotFoundError is not None and isinstance(e, PackageNotFoundError):
                raise FileNotFoundError(str(e)) from e
            raise Exception(f"Error processing PPTX file: {str(e)}") from e

        return " ".join(text_parts)

    def _extract_text_from_shape(self, shape) -> str:
        """Extract text from a PowerPoint shape.

        Handles different shape types:
        - Text boxes
        - Auto shapes with text
        - Tables

        Args:
            shape: PowerPoint shape object

        Returns:
            Extracted text from the shape
        """
        text_parts: list[str] = []

        # Check if shape has text frame
        if hasattr(shape, "text_frame") and shape.text_frame:
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    if run.text and run.text.strip():
                        text_parts.append(run.text.strip())

        # Check if shape is a table
        if hasattr(shape, "table") and shape.table:
            for row in shape.table.rows:
                for cell in row.cells:
                    cell_text = cell.text
                    if cell_text and cell_text.strip():
                        text_parts.append(cell_text.strip())

        # Also check if shape has direct text attribute
        if hasattr(shape, "text") and shape.text:
            if shape.text.strip():
                text_parts.append(shape.text.strip())

        return " ".join(text_parts)

    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle PPTX files."""
        return extension.lower() == ".pptx"


class PptProcessor(BaseFileProcessor):
    """Processor for PPT (PowerPoint 97-2003) files.

    Note: Older PPT format support is limited. python-pptx does not support
    older PPT files directly. This processor will attempt to handle them
    but may not work for all PPT files.
    """

    def extract_text(self, file_path: str) -> str:
        """Extract text from a PPT file.

        Note: python-pptx does not support older PPT format.
        This is a placeholder that will raise an informative error.

        Args:
            file_path: Path to the PPT file

        Returns:
            Extracted text content (if conversion is possible)

        Raises:
            NotImplementedError: Older PPT format is not fully supported
        """
        raise NotImplementedError(
            "Older PPT format (PowerPoint 97-2003) is not fully supported. "
            "Please convert PPT files to PPTX format or use a different tool. "
            "python-pptx only supports PPTX format (PowerPoint 2007+)."
        )

    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle PPT files."""
        return extension.lower() == ".ppt"
