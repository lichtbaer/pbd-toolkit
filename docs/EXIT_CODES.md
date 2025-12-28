# Exit Codes

The PII Toolkit uses standardized exit codes to indicate the result of execution. This allows scripts and automation tools to programmatically determine the outcome.

## Exit Code Definitions

| Code | Constant | Description |
|------|----------|-------------|
| 0 | `EXIT_SUCCESS` | Success - Analysis completed without errors |
| 1 | `EXIT_GENERAL_ERROR` | General error - Unspecified error occurred |
| 2 | `EXIT_INVALID_ARGUMENTS` | Invalid arguments - Command-line arguments are invalid or missing |
| 3 | `EXIT_FILE_ACCESS_ERROR` | File access error - Cannot access files or directories |
| 4 | `EXIT_CONFIGURATION_ERROR` | Configuration error - Configuration is invalid or NER model failed to load |

## Usage Examples

### Bash Script
```bash
#!/bin/bash
python main.py scan /data --regex --ner

case $? in
    0) echo "Analysis completed successfully" ;;
    1) echo "General error occurred" ;;
    2) echo "Invalid arguments" ;;
    3) echo "File access error" ;;
    4) echo "Configuration error" ;;
esac
```

### Python Script
```python
import subprocess
import sys

result = subprocess.run(
    ["python", "main.py", "scan", "/data", "--regex", "--ner"],
    capture_output=True
)

if result.returncode == 0:
    print("Success")
elif result.returncode == constants.EXIT_CONFIGURATION_ERROR:
    print("Configuration error")
else:
    print(f"Error: {result.returncode}")
```

## When Each Code is Used

### EXIT_SUCCESS (0)
- Analysis completed successfully
- All files processed (or stopped at stop-count)
- Output files written successfully

### EXIT_GENERAL_ERROR (1)
- Unexpected errors during processing
- Output file writing failed
- Other unhandled exceptions

### EXIT_INVALID_ARGUMENTS (2)
- Missing required `scan <path>` argument
- Invalid path (does not exist, not a directory, not readable)
- Neither `--regex` nor `--ner` specified
- Invalid output format specified

### EXIT_FILE_ACCESS_ERROR (3)
- Currently not used (reserved for future use)
- Could be used for permission errors, file corruption, etc.

### EXIT_CONFIGURATION_ERROR (4)
- NER model failed to load
- Configuration file parsing failed
- Invalid configuration settings
- Missing required dependencies

## Implementation

Exit codes are defined in `constants.py`:

```python
EXIT_SUCCESS = 0
EXIT_GENERAL_ERROR = 1
EXIT_INVALID_ARGUMENTS = 2
EXIT_FILE_ACCESS_ERROR = 3
EXIT_CONFIGURATION_ERROR = 4
```

And used in `main.py`:

```python
import sys
import constants

# On error:
sys.exit(constants.EXIT_CONFIGURATION_ERROR)

# On success:
sys.exit(constants.EXIT_SUCCESS)
```

## Best Practices

1. **Always check exit codes** in automation scripts
2. **Use constants** instead of magic numbers
3. **Document exit codes** in your scripts
4. **Handle each code appropriately** based on your use case
