# Implementation Checklist

## Feature 1: Magic Number File Type Detection

### Dependencies
- [ ] Add `python-magic>=0.4.27` to `requirements.txt`
- [ ] Add `filetype>=1.2.0` as optional fallback to `requirements.txt`
- [ ] Document system dependencies (libmagic) in installation docs

### Core Implementation
- [ ] Create `core/file_type_detector.py`
  - [ ] Implement `FileTypeDetector` class
  - [ ] Add `detect_type()` method
  - [ ] Add `get_extension_from_mime()` method
  - [ ] Handle both python-magic and filetype libraries
  - [ ] Add proper error handling

### Integration
- [ ] Update `core/scanner.py`
  - [ ] Add magic detection to `FileScanner.scan()`
  - [ ] Handle files without extensions
  - [ ] Use detected MIME type for processor selection
- [ ] Update `file_processors/registry.py`
  - [ ] Modify `get_processor()` to accept MIME type
  - [ ] Add MIME type matching logic
- [ ] Update `file_processors/base_processor.py`
  - [ ] Add `mime_type` parameter to `can_process()`
- [ ] Update processors that should support MIME type detection
  - [ ] `TextProcessor`
  - [ ] Others as needed

### Configuration
- [ ] Update `config.py`
  - [ ] Add `use_magic_detection: bool = False`
  - [ ] Add `magic_detection_fallback: bool = True`
- [ ] Update `setup.py` (or CLI argument parser)
  - [ ] Add `--use-magic-detection` argument
  - [ ] Add `--magic-fallback` argument
  - [ ] Pass to Config creation

### Testing
- [ ] Create test file with wrong extension
- [ ] Create test file without extension
- [ ] Test with binary files
- [ ] Test fallback behavior
- [ ] Test performance impact
- [ ] Test error handling (missing library, corrupted files)

### Documentation
- [ ] Update `docs/user-guide/file-formats.md`
  - [ ] Document magic number detection feature
  - [ ] Explain when it's useful
- [ ] Update `docs/getting-started/installation.md`
  - [ ] Document system dependencies
  - [ ] Document optional dependencies
- [ ] Update `docs/developer/architecture.md`
  - [ ] Document FileTypeDetector integration
- [ ] Update `README.md`
  - [ ] Add magic detection to features list

---

## Feature 2: Multimodal Image Recognition

### Dependencies
- [ ] Add `Pillow>=10.0.0` to `requirements.txt` (optional, for image validation)
- [ ] Verify `requests>=2.31.0` is in requirements.txt

### Core Implementation
- [ ] Create `file_processors/image_processor.py`
  - [ ] Implement `ImageProcessor` class
  - [ ] Add `extract_text()` method (placeholder)
  - [ ] Add `get_image_base64()` method
  - [ ] Add `get_image_mime_type()` method
  - [ ] Implement `can_process()` with extension and MIME type support
  - [ ] Support: JPEG, PNG, GIF, BMP, TIFF, WebP

- [ ] Create `core/engines/multimodal_engine.py`
  - [ ] Implement `MultimodalEngine` class
  - [ ] Add `detect()` method with image_path parameter
  - [ ] Implement API communication (OpenAI-compatible)
  - [ ] Add `_create_prompt()` method
  - [ ] Add `_parse_response()` method
  - [ ] Add `is_available()` method
  - [ ] Handle base64 image encoding
  - [ ] Support multiple image formats
  - [ ] Add proper error handling

### Integration
- [ ] Register `ImageProcessor` in `file_processors/__init__.py`
- [ ] Register `MultimodalEngine` in `core/engines/__init__.py`
- [ ] Update `core/processor.py`
  - [ ] Detect image files in `process_file()`
  - [ ] Call multimodal engine for images
  - [ ] Skip text extraction for images (or add OCR later)
  - [ ] Handle multimodal results
- [ ] Update `core/processor.py` `_get_enabled_engines()`
  - [ ] Add "multimodal" when enabled

### Configuration
- [ ] Update `config.py`
  - [ ] Add `use_multimodal: bool = False`
  - [ ] Add `multimodal_api_base: str | None = None`
  - [ ] Add `multimodal_api_key: str | None = None`
  - [ ] Add `multimodal_model: str = "gpt-4-vision-preview"`
  - [ ] Add `multimodal_timeout: int = 60`
- [ ] Update `setup.py` (or CLI argument parser)
  - [ ] Add `--multimodal` argument
  - [ ] Add `--multimodal-api-base` argument
  - [ ] Add `--multimodal-api-key` argument
  - [ ] Add `--multimodal-model` argument
  - [ ] Add `--multimodal-timeout` argument
  - [ ] Pass to Config creation

### Testing
- [ ] Test with JPEG images
- [ ] Test with PNG images
- [ ] Test with other supported formats
- [ ] Test with images containing different PII types
  - [ ] Names on documents
  - [ ] Email addresses
  - [ ] Phone numbers
  - [ ] Addresses
  - [ ] ID numbers
- [ ] Test API error handling
  - [ ] Invalid API key
  - [ ] Network errors
  - [ ] Timeout handling
  - [ ] Invalid response format
- [ ] Test with local vLLM endpoint
- [ ] Test with LocalAI endpoint
- [ ] Test performance and rate limiting
- [ ] Test with large images
- [ ] Test with corrupted images

### Documentation
- [ ] Update `docs/user-guide/detection-methods.md`
  - [ ] Add section on multimodal image detection
  - [ ] Explain how it works
  - [ ] List supported image formats
  - [ ] Provide configuration examples
  - [ ] Add usage examples
- [ ] Create `docs/user-guide/open-source-models.md`
  - [ ] Overview of open-source multimodal models
  - [ ] vLLM setup instructions
  - [ ] LocalAI setup instructions
  - [ ] Configuration examples
  - [ ] Model recommendations
  - [ ] Troubleshooting guide
- [ ] Update `docs/getting-started/installation.md`
  - [ ] Document multimodal dependencies
  - [ ] Add notes on OpenAI-compatible APIs
  - [ ] Add information about open-source alternatives
- [ ] Update `docs/getting-started/configuration.md`
  - [ ] Document multimodal configuration options
- [ ] Update `docs/developer/engines.md`
  - [ ] Document MultimodalEngine
  - [ ] Add examples
- [ ] Update `docs/developer/adding-processors.md`
  - [ ] Reference ImageProcessor as example
- [ ] Update `README.md`
  - [ ] Add image recognition to features
  - [ ] Mention OpenAI-compatible API support
  - [ ] Mention open-source model support (vLLM, LocalAI)
- [ ] Update `docs/SECURITY_AND_PRIVACY_ANALYSIS.md`
  - [ ] Document privacy implications of sending images to APIs
  - [ ] Recommend local models for sensitive data

### Additional Considerations
- [ ] Add rate limiting for API calls
- [ ] Add retry logic for transient failures
- [ ] Consider image size limits
- [ ] Consider image preprocessing (resize for large images)
- [ ] Add logging for API calls (without sensitive data)
- [ ] Document cost considerations
- [ ] Add privacy warnings in documentation

---

## General Tasks

### Code Quality
- [ ] Run linter on all new files
- [ ] Fix any linting errors
- [ ] Ensure code follows project style guidelines
- [ ] Add type hints where missing
- [ ] Add docstrings to all public methods

### Testing
- [ ] Ensure all tests pass
- [ ] Add integration tests
- [ ] Test error scenarios
- [ ] Test edge cases

### Documentation
- [ ] Review all documentation updates
- [ ] Ensure examples are correct
- [ ] Check for broken links
- [ ] Verify installation instructions work

### Final Review
- [ ] Code review
- [ ] Documentation review
- [ ] Test on different platforms (Linux, Windows, macOS)
- [ ] Performance testing
- [ ] Security review (especially for API key handling)

---

## Notes

- Magic detection should be optional to avoid performance impact
- Image processing may be slower - consider async/batch processing
- API costs can be high - document cost considerations
- Privacy: Images sent to external APIs - document privacy implications
- Rate limiting important for API calls
- Robust error handling required for API failures
