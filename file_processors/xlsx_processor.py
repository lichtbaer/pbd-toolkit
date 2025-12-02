"""XLSX/XLS file processor using openpyxl and xlrd libraries."""

from typing import Optional
from file_processors.base_processor import BaseFileProcessor


class XlsxProcessor(BaseFileProcessor):
    """Processor for XLSX (Excel 2007+) files.
    
    Extracts text from XLSX files using openpyxl library.
    Extracts all cell values from all sheets for PII detection.
    """
    
    def extract_text(self, file_path: str) -> str:
        """Extract text from an XLSX file.
        
        Extracts all cell values from all worksheets in the workbook.
        Only extracts actual values, not formulas.
        
        Args:
            file_path: Path to the XLSX file
            
        Returns:
            Extracted text content from all cells as a string
            
        Raises:
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
            Exception: For other XLSX processing errors
        """
        try:
            from openpyxl import load_workbook
        except ImportError:
            raise ImportError(
                "openpyxl is required for XLSX processing. "
                "Install it with: pip install openpyxl"
            )
        
        text_parts: list[str] = []
        
        try:
            # Load workbook (read-only mode for better performance)
            workbook = load_workbook(file_path, read_only=True, data_only=True)
            
            # Process all sheets
            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                
                # Iterate through all cells
                for row in sheet.iter_rows(values_only=True):
                    for cell_value in row:
                        if cell_value is not None:
                            # Convert to string and add if not empty
                            cell_str = str(cell_value).strip()
                            if cell_str:
                                text_parts.append(cell_str)
            
            workbook.close()
            
        except Exception as e:
            raise Exception(f"Error processing XLSX file: {str(e)}") from e
        
        return ' '.join(text_parts)
    
    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle XLSX files."""
        return extension.lower() == ".xlsx"


class XlsProcessor(BaseFileProcessor):
    """Processor for XLS (Excel 97-2003) files.
    
    Extracts text from older XLS files using xlrd library.
    Extracts all cell values from all sheets for PII detection.
    """
    
    def extract_text(self, file_path: str) -> str:
        """Extract text from an XLS file.
        
        Extracts all cell values from all worksheets in the workbook.
        
        Args:
            file_path: Path to the XLS file
            
        Returns:
            Extracted text content from all cells as a string
            
        Raises:
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
            ImportError: If xlrd is not installed
            Exception: For other XLS processing errors
        """
        try:
            import xlrd
        except ImportError:
            raise ImportError(
                "xlrd is required for XLS processing. "
                "Install it with: pip install xlrd"
            )
        
        text_parts: list[str] = []
        
        try:
            # Open workbook
            workbook = xlrd.open_workbook(file_path)
            
            # Process all sheets
            for sheet_index in range(workbook.nsheets):
                sheet = workbook.sheet_by_index(sheet_index)
                
                # Iterate through all cells
                for row_idx in range(sheet.nrows):
                    for col_idx in range(sheet.ncols):
                        cell = sheet.cell(row_idx, col_idx)
                        cell_value = cell.value
                        
                        if cell_value is not None:
                            # Convert to string and add if not empty
                            cell_str = str(cell_value).strip()
                            if cell_str:
                                text_parts.append(cell_str)
            
        except Exception as e:
            raise Exception(f"Error processing XLS file: {str(e)}") from e
        
        return ' '.join(text_parts)
    
    @staticmethod
    def can_process(extension: str) -> bool:
        """Check if this processor can handle XLS files."""
        return extension.lower() == ".xls"
