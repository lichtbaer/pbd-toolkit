# Security and Privacy Analysis

## Executive Summary

This document provides a comprehensive security and privacy analysis of the PII Toolkit project, with particular focus on telemetry functions and data collection mechanisms in dependencies.

**Overall Assessment**: The project itself does not implement any telemetry or data collection. However, some dependencies may have telemetry enabled by default. Recommendations are provided to ensure complete privacy compliance.

## 1. Project Code Analysis

### 1.1 Network Calls in Project Code

The project makes network calls only in the following scenarios:

1. **OpenAI-compatible API** (`core/engines/openai_engine.py`):
   - Only when `--openai-compatible` flag is used
   - User-initiated and user-configured
   - Sends data to user-specified API endpoint
   - Uses API key from config or `OPENAI_API_KEY` environment variable

2. **Ollama API** (`core/engines/ollama_engine.py`):
   - Only when `--ollama` flag is used
   - Defaults to `http://localhost:11434` (local)
   - User-initiated and user-configured
   - No external data transmission unless user configures remote endpoint

3. **GLiNER Model Loading** (`config.py`):
   - Uses `GLiNER.from_pretrained()` which may download models from HuggingFace
   - Only when `--ner` flag is used
   - Model caching is local (`~/.cache/huggingface/`)

**Conclusion**: All network calls are user-initiated and configurable. No automatic telemetry or data collection in project code.

### 1.2 Data Collection

- **Statistics**: All statistics are local only (file counts, processing times, match counts)
- **Logging**: All logs are written to local files (`output/` directory)
- **Output**: All results are written to local files (CSV, JSON, XLSX)
- **No external data transmission**: No code found that sends data to external servers

### 1.3 Environment Variables

The project uses the following environment variables:
- `LANGUAGE`: For internationalization (de/en)
- `OPENAI_API_KEY`: For OpenAI API authentication (optional, only if using OpenAI engine)

No telemetry-related environment variables are set or checked.

## 2. Dependency Analysis

### 2.1 Core Dependencies

#### python-docx (~=1.2.0)
- **Telemetry**: None known
- **Privacy**: Safe, processes local files only
- **Status**: ✅ No concerns

#### beautifulsoup4
- **Telemetry**: None known
- **Privacy**: Safe, HTML parsing library
- **Status**: ✅ No concerns

#### gliner (~=0.2.22)
- **Telemetry**: Uses HuggingFace Hub which has telemetry
- **Privacy**: Model downloads may be tracked by HuggingFace
- **Status**: ⚠️ **Requires attention** (see section 3.1)

#### pdfminer.six (==20250506)
- **Telemetry**: None known
- **Privacy**: Safe, local PDF parsing
- **Status**: ✅ No concerns

#### tqdm (~=4.66.0)
- **Telemetry**: Has optional telemetry (disabled by default in recent versions)
- **Privacy**: May send usage statistics if enabled
- **Status**: ⚠️ **Requires attention** (see section 3.2)

#### striprtf (~=0.0.26)
- **Telemetry**: None known
- **Privacy**: Safe, RTF parsing
- **Status**: ✅ No concerns

#### odfpy (~=1.4.1)
- **Telemetry**: None known
- **Privacy**: Safe, ODF file processing
- **Status**: ✅ No concerns

#### openpyxl (~=3.1.0)
- **Telemetry**: None known
- **Privacy**: Safe, Excel file processing
- **Status**: ✅ No concerns

#### xlrd (~=2.0.1)
- **Telemetry**: None known
- **Privacy**: Safe, Excel file reading
- **Status**: ✅ No concerns

#### extract-msg (~=0.41.0)
- **Telemetry**: None known
- **Privacy**: Safe, MSG file processing
- **Status**: ✅ No concerns

#### python-pptx (~=0.6.23)
- **Telemetry**: None known
- **Privacy**: Safe, PowerPoint file processing
- **Status**: ✅ No concerns

#### PyYAML (~=6.0.1)
- **Telemetry**: None known
- **Privacy**: Safe, YAML parsing
- **Status**: ✅ No concerns

### 2.2 Optional Dependencies

#### spacy (>=3.7.0)
- **Telemetry**: None known
- **Privacy**: Safe, local NLP processing
- **Status**: ✅ No concerns

#### requests (>=2.31.0)
- **Telemetry**: None known
- **Privacy**: Used only for user-initiated API calls
- **Status**: ✅ No concerns

## 3. Telemetry Concerns and Mitigations

### 3.1 HuggingFace Hub Telemetry

**Issue**: GLiNER uses HuggingFace Hub (`huggingface_hub`) which may collect telemetry data when downloading models.

**Impact**: 
- Model download requests may be logged by HuggingFace
- Usage statistics may be collected
- Requires HuggingFace account authentication (optional)

**Mitigation**:
1. Disable HuggingFace telemetry by setting environment variable:
   ```bash
   export HF_HUB_DISABLE_TELEMETRY=1
   ```

2. Use offline mode if models are already downloaded:
   ```bash
   export HF_HUB_OFFLINE=1
   ```

3. Download models manually and use local paths (if supported by GLiNER)

**Recommendation**: Add telemetry disabling to documentation and setup scripts.

### 3.2 tqdm Telemetry

**Issue**: tqdm has optional telemetry that may send usage statistics.

**Impact**: 
- Minimal (only if telemetry is explicitly enabled)
- Recent versions have telemetry disabled by default

**Mitigation**:
1. Disable tqdm telemetry:
   ```bash
   export TQDM_DISABLE=1  # Disables tqdm entirely
   # OR
   # Set in code: tqdm(..., disable=True)
   ```

2. Check tqdm version (4.66.0 should have telemetry disabled by default)

**Recommendation**: Verify tqdm configuration in code or add explicit disabling.

### 3.3 PyTorch (if used via GLiNER)

**Issue**: PyTorch may collect telemetry if installed.

**Impact**: 
- Model usage statistics
- Hardware information

**Mitigation**:
```bash
export TORCH_DISABLE_TELEMETRY=1
```

## 4. Security Considerations

### 4.1 Path Traversal Protection

**Status**: ✅ Implemented

The project includes path traversal protection in `config.py`:
```python
def validate_file_path(self, file_path: str) -> tuple[bool, str | None]:
    # Resolve to absolute paths to prevent path traversal
    real_base = os.path.realpath(self.path)
    real_file = os.path.realpath(file_path)
    
    # Check if file is within base directory
    if not real_file.startswith(real_base + os.sep) and real_file != real_base:
        return False, "Path traversal attempt detected"
```

### 4.2 File Size Limits

**Status**: ✅ Implemented

Maximum file size limit is enforced:
```python
max_file_size_mb: float = 500.0
```

### 4.3 API Key Handling

**Status**: ✅ Secure

- API keys are read from environment variables or config
- No hardcoded credentials
- Keys are not logged (only warnings if missing)

### 4.4 Input Validation

**Status**: ✅ Good

- Path validation implemented
- File extension validation
- Error handling for malformed files

## 5. Recommendations

### 5.1 Immediate Actions

1. **Add telemetry disabling to setup**:
   - Create `.env.example` with telemetry disabling flags
   - Add to documentation
   - Add to installation instructions

2. **Update documentation**:
   - Add privacy section to README
   - Document all environment variables
   - Explain telemetry implications

3. **Code improvements**:
   - Explicitly disable tqdm telemetry in code
   - Add HuggingFace telemetry disabling check
   - Add PyTorch telemetry disabling (if applicable)

### 5.2 Documentation Updates

Add to `docs/getting-started/installation.md`:

```markdown
## Privacy and Telemetry

To ensure complete privacy, disable telemetry in dependencies:

```bash
# Disable HuggingFace telemetry
export HF_HUB_DISABLE_TELEMETRY=1

# Disable PyTorch telemetry (if using GPU)
export TORCH_DISABLE_TELEMETRY=1
```

Add these to your shell profile (`.bashrc`, `.zshrc`) for permanent effect.
```

### 5.3 Code Changes

1. **Add telemetry check in `config.py`**:
   ```python
   def _load_ner_model(self) -> None:
       # Disable HuggingFace telemetry
       os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')
       # ... rest of method
   ```

2. **Update `setup.py`** to check and warn about telemetry:
   ```python
   def __check_telemetry_settings():
       """Check and warn about telemetry settings."""
       if not os.getenv('HF_HUB_DISABLE_TELEMETRY'):
           logger.warning("HuggingFace telemetry may be enabled. Set HF_HUB_DISABLE_TELEMETRY=1 to disable.")
   ```

## 6. Compliance Checklist

- [x] No telemetry in project code
- [x] All network calls are user-initiated
- [x] All data stays local
- [x] Path traversal protection implemented
- [x] File size limits enforced
- [x] API keys handled securely
- [ ] HuggingFace telemetry explicitly disabled (recommended)
- [ ] tqdm telemetry explicitly disabled (recommended)
- [ ] Documentation updated with privacy information
- [ ] Environment variables documented

## 7. Summary

**Current Status**: The project code itself is privacy-compliant with no telemetry or data collection. However, some dependencies (HuggingFace Hub, potentially tqdm) may have telemetry enabled.

**Risk Level**: **Low to Medium**
- Low risk if dependencies are configured correctly
- Medium risk if telemetry is not explicitly disabled

**Action Required**: 
1. Disable telemetry in dependencies via environment variables
2. Update documentation
3. Add telemetry checks to setup code

**Overall Assessment**: The project is well-designed for privacy, but requires explicit telemetry disabling in dependencies for complete compliance.

---

**Last Updated**: 2025-01-27
**Analysis Version**: 1.0
