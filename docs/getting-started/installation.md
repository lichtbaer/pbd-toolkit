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

## AI Model Setup (Optional)

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
