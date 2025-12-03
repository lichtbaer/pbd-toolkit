"""Constants used throughout the application."""

# Minimum text length for PDF processing (workaround for PDFs with messed-up text embeddings)
MIN_PDF_TEXT_LENGTH: int = 10

# NER model threshold for entity prediction
NER_THRESHOLD: float = 0.5

# NER model name
NER_MODEL_NAME: str = "urchade/gliner_medium-v2.1"

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
