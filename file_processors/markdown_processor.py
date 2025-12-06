"""Markdown file processor with enhanced PII detection."""

import re
from file_processors.base_processor import BaseFileProcessor


class MarkdownProcessor(BaseFileProcessor):
    """Processor for Markdown files with enhanced text extraction.
    
    Strips Markdown syntax while preserving text content.
    Handles code blocks separately as they may contain sensitive data.
    """
    
    def extract_text(self, file_path: str) -> str:
        """Extract text from Markdown file.
        
        Args:
            file_path: Path to the Markdown file
            
        Returns:
            Extracted text content with Markdown syntax removed
            
        Raises:
            UnicodeDecodeError: If file encoding cannot be decoded
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
        """
        with open(file_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        
        # Extract code blocks first (they may contain sensitive data)
        code_blocks = []
        code_block_pattern = r'```[\s\S]*?```|~~~[\s\S]*?~~~'
        code_matches = re.finditer(code_block_pattern, content)
        
        for match in code_matches:
            code_blocks.append(match.group())
            # Replace with placeholder
            content = content.replace(match.group(), f"[CODE_BLOCK_{len(code_blocks)}]", 1)
        
        # Remove inline code (keep content)
        content = re.sub(r'`([^`]+)`', r'\1', content)
        
        # Remove headers but keep text
        content = re.sub(r'^#{1,6}\s+(.+)$', r'\1', content, flags=re.MULTILINE)
        
        # Remove bold/italic markers but keep text
        content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)  # Bold
        content = re.sub(r'\*([^*]+)\*', r'\1', content)  # Italic
        content = re.sub(r'__([^_]+)__', r'\1', content)  # Bold (alt)
        content = re.sub(r'_([^_]+)_', r'\1', content)  # Italic (alt)
        
        # Remove links but keep text and URL
        content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 \2', content)
        
        # Remove images but keep alt text and URL
        content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'\1 \2', content)
        
        # Remove horizontal rules
        content = re.sub(r'^---+$', '', content, flags=re.MULTILINE)
        content = re.sub(r'^\*\*\*+$', '', content, flags=re.MULTILINE)
        
        # Remove list markers but keep text
        content = re.sub(r'^\s*[-*+]\s+', '', content, flags=re.MULTILINE)
        content = re.sub(r'^\s*\d+\.\s+', '', content, flags=re.MULTILINE)
        
        # Remove blockquotes but keep text
        content = re.sub(r'^>\s+', '', content, flags=re.MULTILINE)
        
        # Remove HTML tags if any
        content = re.sub(r'<[^>]+>', '', content)
        
        # Restore code blocks
        for i, code_block in enumerate(code_blocks):
            content = content.replace(f"[CODE_BLOCK_{i+1}]", f"\n{code_block}\n")
        
        # Clean up multiple blank lines
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        return content.strip()
    
    @staticmethod
    def can_process(extension: str, file_path: str = "", mime_type: str = "") -> bool:
        """Check if this processor can handle the file.
        
        Args:
            extension: File extension
            file_path: Full path to the file
            mime_type: Detected MIME type
            
        Returns:
            True if file is a Markdown file, False otherwise
        """
        if extension.lower() in [".md", ".markdown", ".mdown", ".mkd"]:
            return True
        
        if mime_type:
            return mime_type in [
                "text/markdown",
                "text/x-markdown"
            ]
        
        return False
