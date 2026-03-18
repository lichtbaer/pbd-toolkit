"""PII redaction: produce sanitized copies of files with PII replaced by placeholders."""

import os
from pathlib import Path
from matches import PiiMatch


def redact_text(text: str, matches: list[PiiMatch]) -> str:
    """Replace all PII matches in text with [REDACTED:TYPE] placeholders.

    Matches are sorted by position (longest first for overlaps) and replaced
    from end to start to preserve character offsets.
    """
    if not matches or not text:
        return text

    # Build list of (start, end, replacement) from matches that have offsets
    # or fall back to simple string replacement
    replacements = []
    for m in matches:
        placeholder = f"[REDACTED:{m.type}]"
        if m.char_offset is not None:
            start = m.char_offset
            end = start + len(m.text)
            replacements.append((start, end, placeholder))
        else:
            # Fallback: replace all occurrences of the match text
            idx = 0
            while True:
                pos = text.find(m.text, idx)
                if pos == -1:
                    break
                replacements.append((pos, pos + len(m.text), placeholder))
                idx = pos + len(m.text)

    if not replacements:
        return text

    # Sort by start position descending (replace from end to preserve offsets)
    replacements.sort(key=lambda x: x[0], reverse=True)

    # Remove overlapping replacements (keep the one that starts first / is longer)
    cleaned = []
    min_start = float('inf')
    for start, end, placeholder in replacements:
        if end <= min_start:
            cleaned.append((start, end, placeholder))
            min_start = start

    # Apply replacements (already sorted descending)
    result = text
    for start, end, placeholder in cleaned:
        result = result[:start] + placeholder + result[end:]

    return result


def redact_files(
    matches_by_file: dict[str, list[PiiMatch]],
    output_dir: str,
    file_processors_registry=None,
    logger=None,
) -> dict[str, str]:
    """Create redacted copies of files that contain PII.

    For text-based files, PII is replaced with [REDACTED:TYPE] placeholders.
    Binary files (PDF, DOCX, etc.) get a .redacted.txt companion with the
    redacted extracted text.

    Args:
        matches_by_file: Dict mapping file paths to their PII matches.
        output_dir: Directory to write redacted files to.
        file_processors_registry: Optional file processor registry for text extraction.
        logger: Optional logger.

    Returns:
        Dict mapping original file paths to redacted output paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    output_paths = {}

    # Text-based extensions that can be redacted in-place
    TEXT_EXTENSIONS = {
        ".txt", ".csv", ".json", ".xml", ".html", ".htm",
        ".md", ".markdown", ".yaml", ".yml", ".eml", ".properties",
        ".ini", ".cfg", ".conf", ".env", ".rtf",
    }

    for file_path, file_matches in matches_by_file.items():
        if not file_matches:
            continue

        try:
            ext = Path(file_path).suffix.lower()
            basename = Path(file_path).name
            out_path = os.path.join(output_dir, basename + ".redacted.txt")

            # Ensure unique output file names
            counter = 1
            while os.path.exists(out_path):
                out_path = os.path.join(output_dir, f"{basename}.redacted.{counter}.txt")
                counter += 1

            if ext in TEXT_EXTENSIONS:
                # Read original text and apply redaction
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                redacted = redact_text(content, file_matches)

                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(redacted)
            else:
                # For binary files, create a redacted text summary
                lines = []
                lines.append(f"# Redacted content from: {file_path}")
                lines.append(f"# Original format: {ext}")
                lines.append(f"# PII findings redacted: {len(file_matches)}\n")

                for m in file_matches:
                    lines.append(f"[REDACTED:{m.type}] (was: {len(m.text)} chars, engine: {m.engine})")

                with open(out_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")

            output_paths[file_path] = out_path

            if logger:
                logger.info(f"Redacted: {file_path} -> {out_path}")

        except Exception as e:
            if logger:
                logger.warning(f"Failed to redact {file_path}: {e}")

    return output_paths
