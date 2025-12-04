# Feature Integration Plan

## Overview

This document outlines the integration plan for two new features:
1. **File Type Detection via Magic Numbers** - Optional file type detection using file headers (magic numbers)
2. **Image Recognition via Multimodal Models** - PII detection in images using OpenAI-compatible multimodal models

## Feature 1: Magic Number File Type Detection

### Objective
Add optional file type detection using magic numbers (file headers) to identify file types more accurately than relying solely on file extensions.

### Current State
- File type detection is currently based on file extensions (`.pdf`, `.docx`, etc.)
- The `FileScanner` class extracts extensions using `os.path.splitext()`
- `FileProcessorRegistry.get_processor()` matches processors based on extension
- Some processors (like `TextProcessor`) already use MIME type checking as fallback

### Proposed Implementation

#### 1.1 Add Python-Magic Library Dependency
- **Library**: `python-magic` (wrapper for libmagic) or `python-magic-bin` (Windows)
- **Alternative**: `filetype` (pure Python, no system dependencies)
- **Recommendation**: Use `python-magic` for better accuracy, with `filetype` as fallback

#### 1.2 Create Magic Number Detection Module
**File**: `core/file_type_detector.py`

```python
"""File type detection using magic numbers."""

from typing import Optional
import os

class FileTypeDetector:
    """Detects file types using magic numbers (file headers)."""
    
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
    
    def _init_magic(self):
        """Initialize magic number detection libraries."""
        # Try python-magic first (more accurate)
        try:
            import magic
            self._magic = magic.Magic(mime=True)
        except ImportError:
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
            'application/pdf': '.pdf',
            'application/msword': '.doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'application/vnd.ms-excel': '.xls',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
            'text/html': '.html',
            'text/plain': '.txt',
            'text/csv': '.csv',
            'application/json': '.json',
            'application/xml': '.xml',
            'text/xml': '.xml',
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/bmp': '.bmp',
            'image/tiff': '.tiff',
            # Add more mappings as needed
        }
        return mime_to_ext.get(mime_type)
```

#### 1.3 Integrate into FileScanner
**File**: `core/scanner.py`

Modify `FileScanner.scan()` to optionally use magic number detection:
- Add `use_magic_detection` parameter to `Config`
- When enabled, call `FileTypeDetector.detect_type()` for files without extension or when extension doesn't match any processor
- Use detected MIME type to find appropriate processor

#### 1.4 Update FileProcessorRegistry
**File**: `file_processors/registry.py`

Enhance `get_processor()` to:
- Accept optional MIME type parameter
- Check processors that support MIME type detection
- Fall back to extension-based matching if magic detection fails

#### 1.5 Update BaseFileProcessor
**File**: `file_processors/base_processor.py`

Add optional MIME type support to `can_process()`:
```python
@staticmethod
def can_process(extension: str, file_path: str = "", mime_type: str = "") -> bool:
    """Check if this processor can handle the file.
    
    Args:
        extension: File extension
        file_path: Full file path
        mime_type: Detected MIME type (optional)
    """
    # Existing implementation
```

#### 1.6 Configuration Changes
**File**: `config.py`

Add to `Config` class:
```python
use_magic_detection: bool = False  # Enable magic number detection
magic_detection_fallback: bool = True  # Use magic detection when extension fails
```

#### 1.7 CLI Arguments
**File**: `setup.py` (or wherever CLI args are parsed)

Add:
- `--use-magic-detection`: Enable magic number detection
- `--magic-fallback`: Use magic detection as fallback when extension doesn't match

### Testing Strategy
1. Test with files that have incorrect extensions
2. Test with files without extensions
3. Test with binary files that look like text files
4. Test fallback behavior when magic detection fails
5. Test performance impact

### Dependencies
- `python-magic>=0.4.27` or `python-magic-bin>=0.4.14` (Windows)
- `filetype>=1.2.0` (optional fallback)

---

## Feature 2: Image Recognition via Multimodal Models

### Objective
Add PII detection in images using OpenAI-compatible multimodal models (e.g., GPT-4 Vision, Claude 3, or open-source alternatives via vLLM/LocalAI).

### Current State
- Detection engines work with text content only
- No image processing capabilities
- OpenAI-compatible engine exists but only for text

### Proposed Implementation

#### 2.1 Create Image File Processor
**File**: `file_processors/image_processor.py`

```python
"""Image file processor for extracting text and metadata from images."""

from typing import Optional
from file_processors.base_processor import BaseFileProcessor
import base64
import os

class ImageProcessor(BaseFileProcessor):
    """Processor for image files.
    
    Extracts image data for multimodal model processing.
    """
    
    SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']
    
    def extract_text(self, file_path: str) -> str:
        """Extract image data as base64 for multimodal processing.
        
        Note: This doesn't extract actual text, but prepares image
        for multimodal model processing. The actual text extraction
        happens in the multimodal detection engine.
        
        Args:
            file_path: Path to image file
            
        Returns:
            Base64-encoded image data (as placeholder - actual processing in engine)
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
            with open(file_path, 'rb') as img_file:
                img_data = img_file.read()
                return base64.b64encode(img_data).decode('utf-8')
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
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.tiff': 'image/tiff',
            '.webp': 'image/webp',
        }
        return mime_types.get(ext)
    
    @staticmethod
    def can_process(extension: str, file_path: str = "", mime_type: str = "") -> bool:
        """Check if this processor can handle the file.
        
        Args:
            extension: File extension
            file_path: Full file path
            mime_type: Detected MIME type
        """
        if extension.lower() in ImageProcessor.SUPPORTED_EXTENSIONS:
            return True
        if mime_type and mime_type.startswith('image/'):
            return True
        return False
```

#### 2.2 Create Multimodal Detection Engine
**File**: `core/engines/multimodal_engine.py`

```python
"""Multimodal detection engine for image analysis."""

import base64
import json
import os
from typing import Optional, List
from core.engines.base import DetectionEngine, DetectionResult
from config import Config


class MultimodalEngine:
    """Multimodal detection engine for images using OpenAI-compatible APIs.
    
    Supports:
    - OpenAI GPT-4 Vision
    - Anthropic Claude 3
    - Local models via vLLM
    - LocalAI compatible endpoints
    """
    
    name = "multimodal"
    
    def __init__(self, config: Config):
        """Initialize multimodal engine.
        
        Args:
            config: Configuration object with API settings
        """
        self.config = config
        self.enabled = getattr(config, 'use_multimodal', False)
        self.api_base = getattr(config, 'multimodal_api_base', None) or \
                       getattr(config, 'openai_api_base', 'https://api.openai.com/v1')
        self.api_key = getattr(config, 'multimodal_api_key', None) or \
                      getattr(config, 'openai_api_key', None) or \
                      os.getenv('OPENAI_API_KEY')
        self.model = getattr(config, 'multimodal_model', 'gpt-4-vision-preview')
        self.timeout = getattr(config, 'multimodal_timeout', 60)
        self._available = None
    
    def detect(self, text: str, labels: Optional[List[str]] = None, 
               image_path: Optional[str] = None) -> List[DetectionResult]:
        """Detect PII in image.
        
        Args:
            text: Not used for images (kept for interface compatibility)
            labels: Optional list of entity types to detect
            image_path: Path to image file (required for image processing)
        
        Returns:
            List of detection results
        """
        if not self.enabled or not image_path:
            return []
        
        if not os.path.exists(image_path):
            self.config.logger.warning(f"Image file not found: {image_path}")
            return []
        
        # Read and encode image
        try:
            from file_processors.image_processor import ImageProcessor
            img_processor = ImageProcessor()
            image_base64 = img_processor.get_image_base64(image_path)
            image_mime = img_processor.get_image_mime_type(image_path)
            
            if not image_base64 or not image_mime:
                return []
        except Exception as e:
            self.config.logger.error(f"Failed to read image {image_path}: {e}")
            return []
        
        # Create prompt
        prompt = self._create_prompt(labels)
        
        # Call API
        try:
            import requests
            
            # Prepare messages with image
            messages = [
                {
                    "role": "system",
                    "content": "You are a PII detection expert. Analyze images and extract personally identifiable information. Always return valid JSON."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{image_mime};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]
            
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1,
                    "max_tokens": 1000
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            return self._parse_response(content, image_path)
            
        except ImportError:
            self.config.logger.warning("requests library not installed")
            return []
        except Exception as e:
            self.config.logger.warning(f"Multimodal detection failed: {e}")
            return []
    
    def _create_prompt(self, labels: Optional[List[str]]) -> str:
        """Create prompt for image analysis.
        
        Args:
            labels: Optional list of entity types
            
        Returns:
            Prompt string
        """
        label_list = ", ".join(labels) if labels else "all PII types"
        
        return f"""Analyze this image and extract all personally identifiable information (PII).

Entity types to detect: {label_list}

Look for:
- Names (on documents, badges, screens)
- Email addresses
- Phone numbers
- Addresses
- ID numbers (passport, driver's license, etc.)
- Credit card numbers
- Social security numbers
- Any other personally identifiable information

Return a JSON object with this exact structure:
{{
  "entities": [
    {{"text": "found text", "type": "entity_type", "confidence": 0.95, "location": "description of where in image"}}
  ]
}}"""
    
    def _parse_response(self, content: str, image_path: str) -> List[DetectionResult]:
        """Parse API response.
        
        Args:
            content: JSON response content
            image_path: Path to analyzed image
            
        Returns:
            List of detection results
        """
        try:
            data = json.loads(content)
            entities = data.get("entities", [])
            
            results = []
            for entity in entities:
                if isinstance(entity, dict) and "text" in entity:
                    results.append(DetectionResult(
                        text=entity.get("text", ""),
                        entity_type=entity.get("type", "UNKNOWN"),
                        confidence=entity.get("confidence"),
                        engine_name="multimodal",
                        metadata={
                            "model": self.model,
                            "image_path": image_path,
                            "location": entity.get("location", "")
                        }
                    ))
            
            return results
        except json.JSONDecodeError as e:
            self.config.logger.debug(f"Failed to parse multimodal JSON response: {e}")
            return []
        except Exception as e:
            self.config.logger.warning(f"Error parsing multimodal response: {e}")
            return []
    
    def is_available(self) -> bool:
        """Check if multimodal engine is available.
        
        Returns:
            True if enabled and API is accessible
        """
        if not self.enabled:
            return False
        
        if not self.api_key:
            return False
        
        if self._available is not None:
            return self._available
        
        try:
            import requests
            response = requests.get(
                f"{self.api_base}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5
            )
            self._available = response.status_code == 200
            return self._available
        except Exception:
            self._available = False
            return False
```

#### 2.3 Update TextProcessor for Image Handling
**File**: `core/processor.py`

Modify `process_file()` to:
- Detect if file is an image
- If multimodal engine is enabled, call it with image path
- Skip text extraction for images (or extract OCR text if available)

#### 2.4 Configuration Changes
**File**: `config.py`

Add to `Config` class:
```python
use_multimodal: bool = False  # Enable multimodal image detection
multimodal_api_base: str | None = None  # API base URL (defaults to openai_api_base)
multimodal_api_key: str | None = None  # API key (defaults to openai_api_key)
multimodal_model: str = "gpt-4-vision-preview"  # Model name
multimodal_timeout: int = 60  # Timeout in seconds
```

#### 2.5 CLI Arguments
**File**: `setup.py`

Add:
- `--multimodal`: Enable multimodal image detection
- `--multimodal-api-base`: Custom API base URL
- `--multimodal-api-key`: API key (or use OPENAI_API_KEY)
- `--multimodal-model`: Model name (default: gpt-4-vision-preview)

#### 2.6 Register Engine
**File**: `core/engines/__init__.py`

Add:
```python
try:
    from core.engines.multimodal_engine import MultimodalEngine
    EngineRegistry.register("multimodal", MultimodalEngine)
except ImportError:
    pass
```

#### 2.7 Register Image Processor
**File**: `file_processors/__init__.py`

Add:
```python
from file_processors.image_processor import ImageProcessor

# In _registered_processors:
ImageProcessor(),
```

### Documentation Updates

#### 2.8 Update Detection Methods Documentation
**File**: `docs/user-guide/detection-methods.md`

Add section on multimodal image detection:
- How it works
- Supported image formats
- Configuration options
- Examples

#### 2.9 Update Installation Documentation
**File**: `docs/getting-started/installation.md`

Add:
- Information about multimodal dependencies
- Notes on OpenAI-compatible APIs
- Information about open-source alternatives (vLLM, LocalAI)

#### 2.10 Create Open-Source Model Guide
**File**: `docs/user-guide/open-source-models.md` (new)

Content:
- Overview of open-source multimodal models
- vLLM setup instructions
- LocalAI setup instructions
- Configuration examples
- Model recommendations

#### 2.11 Update Main README
**File**: `README.md`

Add to features:
- Image recognition via multimodal models
- Support for OpenAI-compatible APIs
- Open-source model support (vLLM, LocalAI)

### Testing Strategy
1. Test with various image formats (JPEG, PNG, etc.)
2. Test with images containing different types of PII
3. Test API error handling
4. Test with local vLLM/LocalAI endpoints
5. Test performance and rate limiting
6. Test with large images

### Dependencies
- `requests>=2.31.0` (already in requirements.txt)
- `Pillow>=10.0.0` (for image validation, optional)

---

## Implementation Order

### Phase 1: Magic Number Detection
1. Add dependencies to `requirements.txt`
2. Create `FileTypeDetector` class
3. Integrate into `FileScanner`
4. Update `FileProcessorRegistry`
5. Add configuration options
6. Add CLI arguments
7. Write tests
8. Update documentation

### Phase 2: Multimodal Image Detection
1. Create `ImageProcessor` class
2. Create `MultimodalEngine` class
3. Register processor and engine
4. Update `TextProcessor` for image handling
5. Add configuration options
6. Add CLI arguments
7. Write tests
8. Update documentation
9. Create open-source model guide

---

## Configuration Example

```json
{
  "use_magic_detection": true,
  "magic_detection_fallback": true,
  "use_multimodal": true,
  "multimodal_api_base": "http://localhost:8000/v1",
  "multimodal_model": "llava-v1.6-vicuna-7b",
  "multimodal_timeout": 60
}
```

---

## Open-Source Model Support

### vLLM Setup
```bash
# Install vLLM
pip install vllm

# Start server with multimodal model
python -m vllm.entrypoints.openai.api_server \
    --model microsoft/llava-1.5-7b \
    --port 8000
```

### LocalAI Setup
```bash
# Using Docker
docker run -p 8080:8080 localai/localai:latest-aio-cuda

# Configure model in LocalAI
# See LocalAI documentation for multimodal model setup
```

### Configuration
```bash
python main.py \
    --path /path/to/images \
    --multimodal \
    --multimodal-api-base http://localhost:8000/v1 \
    --multimodal-model llava-v1.6-vicuna-7b
```

---

## Notes

1. **Magic Detection**: Should be optional to avoid performance impact on large scans
2. **Image Processing**: May be slower than text processing - consider async/batch processing
3. **API Costs**: Multimodal models can be expensive - document cost considerations
4. **Privacy**: Images are sent to external APIs - document privacy implications
5. **Rate Limiting**: Implement rate limiting for API calls
6. **Error Handling**: Robust error handling for API failures
7. **Fallback**: Text extraction from images (OCR) as fallback option

---

## Future Enhancements

1. **OCR Integration**: Use OCR (Tesseract, EasyOCR) to extract text from images before multimodal analysis
2. **Batch Processing**: Process multiple images in single API call (if supported)
3. **Image Preprocessing**: Resize/optimize images before sending to API
4. **Caching**: Cache image analysis results
5. **Local Models**: Direct integration with local multimodal models (without API)
