# PII Toolkit (Fork)

!!! warning "This is a Fork"
    **This is an unofficial fork of the HBDI PII Toolkit.** This project is not maintained by or affiliated with the Hessian Commissioner for Data Protection and Freedom of Information (HBDI). This fork may contain modifications, improvements, or changes that are not present in the original project.

   For the official project, please visit the [original repository](https://github.com/hessen-datenschutz/pbd-toolkit) or the [HBDI website](https://datenschutz.hessen.de).

## Overview

The PII Toolkit is a command-line tool designed to scan directories and identify potentially personally identifiable information (PII) within files. It supports multiple detection methods and file formats, making it useful for data leak analysis, privacy audits, and compliance checks.

## Key Features

- **Multiple Detection Methods**:
  - Regular expression-based pattern matching
  - AI-powered Named Entity Recognition (NER)

- **Wide File Format Support**:
  - Documents: PDF, DOCX, ODT, RTF
  - Spreadsheets: XLSX, XLS, ODS, CSV
  - Presentations: PPTX, PPT
  - Web: HTML, XML
  - Email: EML, MSG
  - Data: JSON, YAML
  - Plain text: TXT

- **Flexible Output Formats**:
  - CSV (default)
  - JSON (with metadata)
  - Excel (XLSX)

- **Advanced Features**:
  - Whitelist support for filtering false positives
  - Multi-threaded processing
  - Progress tracking
  - Detailed logging
  - Internationalization (German/English)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Basic usage
python main.py --path /path/to/scan --regex --ner

# With custom output
python main.py --path /path/to/scan --regex --format json --outname "scan-2024"
```

## Documentation Structure

- **[Getting Started](getting-started/installation.md)**: Installation and setup instructions
- **[User Guide](user-guide/cli.md)**: Complete usage documentation
- **[Developer Documentation](developer/architecture.md)**: Technical details for contributors
- **[About](about/project-status.md)**: Project status and contribution guidelines

## Original Project

This fork is based on the **pbD-Toolkit** (Personenbezogene Daten Toolkit) developed by the Hessian Commissioner for Data Protection and Freedom of Information (HBDI). The original project is maintained by HBDI's Department 3.2 (Technical Data Protection Audits).

### Original Project Information

- **Original Name**: pbD-Toolkit (PII Toolkit)
- **Original Maintainer**: Hessian Commissioner for Data Protection and Freedom of Information (HBDI)
- **Contact**: Department 3.2 - Technical Data Protection Audits
- **Website**: [datenschutz.hessen.de](https://datenschutz.hessen.de)

## Disclaimer

This fork is provided "as is" without warranty of any kind. The maintainers of this fork are not responsible for any issues, data loss, or compliance problems that may arise from using this software. Users should verify that this fork meets their requirements and complies with applicable data protection regulations.

## License

Please refer to the [LICENSE](../LICENSE) file for license information. This fork maintains the same license as the original project.
