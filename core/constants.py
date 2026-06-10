"""Constants used throughout the application."""

# Toolkit version (best-effort; CLI uses package metadata when installed).
VERSION: str = "1.0.0"

# PDFs with broken text embeddings (e.g. scanned without OCR, or print-to-PDF with
# embedded fonts not mapped to Unicode) produce garbled strings of a few characters.
# Texts shorter than this threshold are silently skipped rather than polluting output
# with meaningless matches.
MIN_PDF_TEXT_LENGTH: int = 10

# 0.5 is the GLiNER default threshold: below it the model's self-assessed confidence
# is too low to trust as a PII finding; above it, precision is acceptable for audits.
# Operators can lower the threshold (–-ner-threshold) to increase recall at the cost
# of more false positives, or raise it to reduce noise in clean datasets.
NER_THRESHOLD: float = 0.5

# GLiNER medium model: multilingual, 125 M parameters, runs on CPU without GPU.
# Chosen because it achieves a good precision/recall balance for European PII
# (names, locations, organisations) without requiring a GPU or internet access at
# scan time – critical for air-gapped GDPR audit environments.
NER_MODEL_NAME: str = "urchade/gliner_medium-v2.1"

# OCR settings (only used when the optional ``[ocr]`` extra is installed and a scanned
# PDF page has no embedded text). Tesseract language string – "deu+eng" recognises both
# German and English text, matching the toolkit's primary (German) document focus.
# Requires the matching Tesseract language packs (e.g. ``tesseract-ocr-deu``) to be
# installed on the system. Overridable per deployment via the ``PBD_OCR_LANG`` env var.
OCR_LANGUAGES: str = "deu+eng"

# Rasterisation resolution for OCR. 300 DPI markedly improves recognition accuracy over
# pdf2image's ~200 DPI default at the cost of more memory/time per page. Overridable via
# the ``PBD_OCR_DPI`` env var.
OCR_DPI: int = 300

# Convert rasterised pages to greyscale before OCR. Generally neutral-to-positive for
# Tesseract accuracy and reduces memory; no extra dependency.
OCR_GRAYSCALE: bool = True

# Configuration file path
CONFIG_FILE: str = "config_types.json"

# Output directory
OUTPUT_DIR: str = "./output/"

# Force CPU for NER processing (set to True to disable GPU even if available)
FORCE_CPU: bool = False

# Exit codes
EXIT_SUCCESS = 0
EXIT_GENERAL_ERROR = 1
EXIT_INVALID_ARGUMENTS = 2
EXIT_FILE_ACCESS_ERROR = 3
EXIT_CONFIGURATION_ERROR = 4
EXIT_FINDINGS_ABOVE_THRESHOLD = 5  # findings at or above --fail-on-severity level found
