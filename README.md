# PII Toolkit (Fork)

> **⚠️ This is an unofficial fork of the HBDI PII Toolkit. This project is not maintained by or affiliated with the Hessian Commissioner for Data Protection and Freedom of Information (HBDI).**

## Overview

The PII Toolkit is a command-line tool for scanning directories and identifying potentially personally identifiable information (PII) within files. It supports multiple detection methods (regex and AI-based NER) and a wide range of file formats.

## Quick Start

```bash
# Minimal runtime dependencies (regex + basic processors)
python3 -m pip install -r requirements.txt

# Recommended for contributors: install feature extras
python3 -m pip install -e ".[dev,office,images,magic,llm]"

# Optional (if you want these engines available locally):
# python3 -m pip install -e ".[gliner,spacy]"

# Basic usage
python3 main.py scan /path/to/scan --regex --ner

# Or, after installation
pii-toolkit scan /path/to/scan --regex --ner
```

## Documentation

**📚 Comprehensive documentation is available via MkDocs:**

```bash
# Install documentation dependencies
pip install mkdocs mkdocs-material

# Serve documentation locally
mkdocs serve
```

Then open `http://127.0.0.1:8000` in your browser.

**Or view the documentation files directly in the `docs/` directory.**

## Key Features

- **Multiple Detection Methods**: 
  - Regular expressions for structured PII
  - AI-powered Named Entity Recognition (GLiNER, spaCy)
  - LLM-based detection (**recommended: `--pydantic-ai`**, legacy flags kept for compatibility)
  - **Multimodal image detection** (GPT-4 Vision, local models via vLLM/LocalAI)
- **Wide File Format Support**: PDF, DOCX, HTML, TXT, CSV, JSON, XLSX, XLS, PPTX, ODT, RTF, ODS, EML, MSG, XML, YAML, and **image formats** (JPEG, PNG, GIF, BMP, TIFF, WebP)
- **File Type Detection**: Optional magic number detection for files without or with incorrect extensions
- **Flexible Output Formats**: CSV, JSON, **JSONL**, and Excel (XLSX)
- **Advanced Features**: Whitelist support, progress tracking, detailed logging
- **CLI Options**: Verbose mode (`-v`), quiet mode (`-q`), config file support (`--config`), structured output (`--summary-format`)
- **Professional Architecture**: Modular design, dependency injection, no global variables
- **Privacy-Focused**: Support for local models (vLLM, LocalAI) for complete data privacy

## Installation

See [Installation Guide](docs/getting-started/installation.md) for detailed instructions.

## Usage

```bash
# Basic text-based detection
python3 main.py scan /var/data-leak/ --regex --ner --format json --outname "scan-2024"

# With magic number file type detection
python3 main.py scan /var/data-leak/ --regex --use-magic-detection

# With multimodal image detection (OpenAI)
python3 main.py scan /var/images/ --multimodal --multimodal-api-key YOUR_KEY

# LLM-based detection (recommended unified engine)
python3 main.py scan /var/data-leak/ --pydantic-ai --pydantic-ai-provider openai \
  --pydantic-ai-api-key YOUR_KEY --pydantic-ai-model gpt-4o-mini

# With local multimodal models (vLLM)
python3 main.py scan /var/images/ --multimodal \
    --multimodal-api-base http://localhost:8000/v1 \
    --multimodal-model microsoft/llava-1.6-vicuna-7b
```

See [User Guide](docs/user-guide/cli.md) for complete usage documentation.

## Original Project

This fork is based on the **pbD-Toolkit** (Personenbezogene Daten Toolkit) developed by the Hessian Commissioner for Data Protection and Freedom of Information (HBDI).

- **Original Repository**: [hessen-datenschutz/pbd-toolkit](https://github.com/hessen-datenschutz/pbd-toolkit)
- **Original Website**: [datenschutz.hessen.de](https://datenschutz.hessen.de)

## Privacy and Security

This project is designed with privacy in mind:

- **No telemetry**: The project code does not collect or transmit any data
- **Local processing**: All analysis is performed locally (text-based detection)
- **Local image processing**: Support for local multimodal models (vLLM, LocalAI) - images never leave your infrastructure
- **Telemetry disabled**: Dependencies with telemetry (HuggingFace, PyTorch) are automatically configured to disable telemetry
- **User-initiated network calls**: Network connections are only made when explicitly using external APIs (OpenAI, Ollama) with user-provided credentials
- **Privacy-first**: Use local models for sensitive data - see [Open-Source Models Guide](docs/user-guide/open-source-models.md)

For detailed security and privacy analysis, see [Security and Privacy Analysis](SECURITY_AND_PRIVACY_ANALYSIS.md).

## Disclaimer

This fork is provided "as is" without warranty of any kind. The maintainers of this fork are not responsible for any issues, data loss, or compliance problems. Users should verify that this fork meets their requirements and complies with applicable data protection regulations.

## License

Please refer to the [LICENSE](LICENSE) file for license information.

## Contributing

Contributions are welcome! See [Contributing Guide](docs/about/contributing.md) for details.

---

**For complete documentation, please refer to the [MkDocs documentation](docs/index.md) or build it locally with `mkdocs serve`.**
