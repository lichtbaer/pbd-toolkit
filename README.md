# PII Toolkit (Fork)

> **⚠️ This is an unofficial fork of the HBDI PII Toolkit. This project is not maintained by or affiliated with the Hessian Commissioner for Data Protection and Freedom of Information (HBDI).**

## Overview

The PII Toolkit is a command-line tool for scanning directories and identifying potentially personally identifiable information (PII) within files. It supports multiple detection methods (regex and AI-based NER) and a wide range of file formats.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Basic usage
python main.py --path /path/to/scan --regex --ner
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

- **Multiple Detection Methods**: Regular expressions and AI-powered Named Entity Recognition
- **Wide File Format Support**: PDF, DOCX, HTML, TXT, CSV, JSON, XLSX, and more
- **Flexible Output Formats**: CSV, JSON, and Excel (XLSX)
- **Advanced Features**: Whitelist support, multi-threaded processing, progress tracking
- **CLI Options**: Verbose mode (`-v`), quiet mode (`-q`), config file support (`--config`), structured output (`--summary-format`)
- **Professional Architecture**: Modular design, dependency injection, no global variables

## Installation

See [Installation Guide](docs/getting-started/installation.md) for detailed instructions.

## Usage

```bash
python main.py --path /var/data-leak/ --regex --ner --format json --outname "scan-2024"
```

See [User Guide](docs/user-guide/cli.md) for complete usage documentation.

## Original Project

This fork is based on the **pbD-Toolkit** (Personenbezogene Daten Toolkit) developed by the Hessian Commissioner for Data Protection and Freedom of Information (HBDI).

- **Original Repository**: [hessen-datenschutz/pbd-toolkit](https://github.com/hessen-datenschutz/pbd-toolkit)
- **Original Website**: [datenschutz.hessen.de](https://datenschutz.hessen.de)

## Disclaimer

This fork is provided "as is" without warranty of any kind. The maintainers of this fork are not responsible for any issues, data loss, or compliance problems. Users should verify that this fork meets their requirements and complies with applicable data protection regulations.

## License

Please refer to the [LICENSE](LICENSE) file for license information.

## Contributing

Contributions are welcome! See [Contributing Guide](docs/about/contributing.md) for details.

---

**For complete documentation, please refer to the [MkDocs documentation](docs/index.md) or build it locally with `mkdocs serve`.**
