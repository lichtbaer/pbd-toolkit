# Installation

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- (Optional) Virtual environment (recommended)

## Basic Installation

### 1. Clone or Download the Repository

```bash
git clone <repository-url>
cd pii-toolkit-fork
```

### 2. Create Virtual Environment (Recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note**: Some dependencies are optional:
- `python-magic` / `filetype`: For magic number file type detection (see [File Formats](../user-guide/file-formats.md#magic-number-detection-optional))
- `Pillow`: For image processing validation (optional)
- `spacy`: For spaCy NER engine (optional)
- `requests`: For Ollama and OpenAI-compatible engines (optional)

## Optional Features Setup

### Magic Number Detection

For file type detection using magic numbers (file headers), install system dependencies:

**Linux**:
```bash
sudo apt-get install libmagic1  # Debian/Ubuntu
sudo yum install file-devel     # RHEL/CentOS
```

**macOS**:
```bash
brew install libmagic
```

**Windows**:
```bash
pip install python-magic-bin
```

Then install Python package:
```bash
pip install python-magic
```

**Alternative (Pure Python, no system dependencies)**:
```bash
pip install filetype
```

See [File Formats Guide](../user-guide/file-formats.md#magic-number-detection-optional) for usage.

### Multimodal Image Detection

For PII detection in images, you have two options:

**Option 1: Use OpenAI API**
- Requires API key: Set `OPENAI_API_KEY` environment variable or use `--multimodal-api-key`
- No additional installation needed

**Option 2: Use Local Models (Recommended for Privacy)**
- Install vLLM: `pip install vllm`
- Or use LocalAI: See [Open-Source Models Guide](../user-guide/open-source-models.md)

See [Detection Methods](../user-guide/detection-methods.md#multimodal-image-detection-engine) and [Open-Source Models](../user-guide/open-source-models.md) for detailed setup.

### AI Model Setup (NER)

If you plan to use the AI-based Named Entity Recognition (NER) feature, you need to download the model:

### 1. Install HuggingFace CLI

```bash
pip install "huggingface_hub[cli]"
```

### 2. Authenticate with HuggingFace

```bash
hf auth login
```

### 3. Download the Model

```bash
hf download urchade/gliner_medium-v2.1
```

The model will be cached in your HuggingFace cache directory (typically `~/.cache/huggingface/`).

## Privacy and Telemetry

This project automatically disables telemetry in dependencies to ensure privacy:

- **HuggingFace telemetry**: Automatically disabled via `HF_HUB_DISABLE_TELEMETRY=1`
- **PyTorch telemetry**: Automatically disabled via `TORCH_DISABLE_TELEMETRY=1`
- **tqdm telemetry**: Disabled by default in recent versions

These settings are configured automatically when the application starts. No manual configuration is required.

For complete privacy, you can also set these environment variables in your shell profile:

```bash
# Add to ~/.bashrc or ~/.zshrc
export HF_HUB_DISABLE_TELEMETRY=1
export TORCH_DISABLE_TELEMETRY=1
```

For detailed security and privacy information, see [Security and Privacy Analysis](../SECURITY_AND_PRIVACY_ANALYSIS.md).

## Verify Installation

Test the installation:

```bash
python main.py --help
```

You should see the help message with available command-line options.

## Optional: Install MkDocs for Documentation

To build and view the documentation locally:

```bash
pip install mkdocs mkdocs-material
mkdocs serve
```

Then open `http://127.0.0.1:8000` in your browser.

## Troubleshooting

### Common Issues

**Import Errors**
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Verify Python version: `python --version` (should be 3.8+)

**Model Loading Errors**
- Check HuggingFace authentication: `hf auth login`
- Verify model download: `hf download urchade/gliner_medium-v2.1`
- Check available disk space (model is ~500MB)

**Permission Errors**
- On Linux/Mac, you may need to use `python3` instead of `python`
- Ensure you have write permissions for the output directory

**Missing Dependencies**
- Some file processors require additional libraries (e.g., `openpyxl` for Excel support)
- Install missing packages: `pip install <package-name>`

**Magic Detection Not Working**
- Linux: Install `libmagic1` system package
- macOS: Install via Homebrew: `brew install libmagic`
- Windows: Use `python-magic-bin` instead of `python-magic`
- Alternative: Use `filetype` (pure Python, no system dependencies)

**Multimodal Detection Errors**
- Check API key is set correctly
- Verify API endpoint is accessible: `curl http://localhost:8000/v1/models` (for local servers)
- For local models, ensure vLLM or LocalAI server is running
- See [Open-Source Models Guide](../user-guide/open-source-models.md) for troubleshooting
