# Adding File Processors

This guide explains how to add support for new file formats by creating custom file processors.

## Overview

File processors are responsible for extracting text content from specific file formats. They follow a simple interface defined in `BaseFileProcessor`.

## Creating a New Processor

### Step 1: Create Processor Class

Create a new file in `file_processors/` directory, e.g., `myformat_processor.py`:

```python
from file_processors.base_processor import BaseFileProcessor

class MyFormatProcessor(BaseFileProcessor):
    """Processor for MyFormat files."""
    
    def can_process(self, extension: str, file_path: str = "") -> bool:
        """Check if this processor can handle the file."""
        return extension.lower() in ['.myformat', '.mf']
    
    def extract_text(self, file_path: str) -> str:
        """Extract text content from the file."""
        # Your extraction logic here
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Process content...
            return extracted_text
```

### Step 2: Register the Processor

In `file_processors/__init__.py`, import and register your processor:

```python
from file_processors.myformat_processor import MyFormatProcessor
from file_processors.registry import FileProcessorRegistry

# Register the processor
FileProcessorRegistry.register_class(MyFormatProcessor)
```

### Step 3: Handle Errors

Add proper error handling:

```python
def extract_text(self, file_path: str) -> str:
    """Extract text content from the file."""
    try:
        # Your extraction logic
        return extracted_text
    except UnicodeDecodeError:
        # Handle encoding errors
        raise
    except Exception as e:
        # Handle other errors
        raise RuntimeError(f"Failed to process {file_path}: {e}") from e
```

## Base Processor Interface

### `can_process(extension: str, file_path: str = "") -> bool`

Determines if this processor can handle a file.

**Parameters**:
- `extension`: File extension (e.g., '.pdf')
- `file_path`: Full path to file (optional, for MIME type detection)

**Returns**: `True` if processor can handle the file, `False` otherwise

### `extract_text(file_path: str) -> str`

Extracts text content from the file.

**Parameters**:
- `file_path`: Full path to the file

**Returns**: Extracted text as string

**Raises**: Various exceptions for errors (handled by main.py)

## Example: Simple Text Processor

```python
from file_processors.base_processor import BaseFileProcessor

class SimpleTextProcessor(BaseFileProcessor):
    """Processor for simple text files."""
    
    def can_process(self, extension: str, file_path: str = "") -> bool:
        return extension.lower() == '.txt'
    
    def extract_text(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
```

## Example: Complex Format Processor

```python
import some_library
from file_processors.base_processor import BaseFileProcessor

class ComplexFormatProcessor(BaseFileProcessor):
    """Processor for complex binary format."""
    
    def can_process(self, extension: str, file_path: str = "") -> bool:
        return extension.lower() in ['.complex', '.cf']
    
    def extract_text(self, file_path: str) -> str:
        try:
            # Open and parse the file
            with open(file_path, 'rb') as f:
                data = some_library.parse(f)
            
            # Extract text from various parts
            text_parts = []
            for section in data.sections:
                if section.has_text:
                    text_parts.append(section.text)
            
            return '\n'.join(text_parts)
            
        except some_library.ParseError as e:
            raise RuntimeError(f"Failed to parse {file_path}: {e}") from e
```

## Best Practices

### 1. Error Handling

- Catch format-specific errors
- Provide meaningful error messages
- Re-raise as `RuntimeError` with context

### 2. Encoding

- Handle various encodings (UTF-8, Latin-1, etc.)
- Use `errors='ignore'` or `errors='replace'` when appropriate
- Document encoding assumptions

### 3. Performance

- Process files efficiently
- Avoid loading entire file into memory for large files
- Consider chunked processing for very large files

### 4. Text Extraction

- Extract all relevant text
- Preserve structure when useful (newlines, paragraphs)
- Remove formatting codes when not needed
- Handle nested structures (tables, lists, etc.)

### 5. Testing

Create tests for your processor:

```python
def test_myformat_processor():
    processor = MyFormatProcessor()
    assert processor.can_process('.myformat')
    assert not processor.can_process('.pdf')
    
    text = processor.extract_text('test.myformat')
    assert len(text) > 0
```

## Chunked Processing (Advanced)

For very large files, you can yield text in chunks:

```python
def extract_text(self, file_path: str):
    """Extract text in chunks (generator)."""
    with open(file_path, 'r') as f:
        chunk = []
        for line in f:
            chunk.append(line)
            if len(chunk) >= 1000:  # Process in chunks of 1000 lines
                yield '\n'.join(chunk)
                chunk = []
        if chunk:
            yield '\n'.join(chunk)
```

**Note**: The main processing loop in `main.py` handles both string returns and generators.

## MIME Type Detection

For files without extensions, you can use MIME type detection:

```python
import mimetypes

def can_process(self, extension: str, file_path: str = "") -> bool:
    if extension.lower() == '.myformat':
        return True
    if file_path:
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type == 'application/myformat'
    return False
```

## Adding Dependencies

If your processor requires new dependencies:

1. Add to `requirements.txt`
2. Document in processor docstring
3. Handle `ImportError` gracefully:

```python
try:
    import my_library
except ImportError:
    my_library = None

class MyFormatProcessor(BaseFileProcessor):
    def can_process(self, extension: str, file_path: str = "") -> bool:
        if my_library is None:
            return False
        return extension.lower() == '.myformat'
```

## Integration Checklist

- [ ] Create processor class
- [ ] Implement `can_process()` method
- [ ] Implement `extract_text()` method
- [ ] Add error handling
- [ ] Register in `__init__.py`
- [ ] Add tests
- [ ] Update documentation
- [ ] Add dependencies to `requirements.txt` (if needed)
- [ ] Test with real files
- [ ] Handle edge cases (empty files, corrupted files, etc.)

## Examples in Codebase

See existing processors for reference:
- `text_processor.py`: Simple text file handling
- `pdf_processor.py`: Complex binary format with chunking
- `html_processor.py`: HTML parsing with BeautifulSoup
- `json_processor.py`: JSON parsing and text extraction
