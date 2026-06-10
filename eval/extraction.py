"""Extraction-quality evaluation harness.

Detection quality (``eval/runner.py``) measures how well the engines find PII in
*already-extracted* text.  It says nothing about whether the file processors pulled
the right text out of a document in the first place — yet a missed table cell or a
fused paragraph silently caps recall before any engine runs.

This harness closes that gap.  It runs the real :class:`FileProcessorRegistry`
extraction path over a manifest of source files and checks, per file, which
*expected* text snippets actually appear in the extracted text (extraction recall),
and that none of the optional *forbidden* snippets leak in.

Manifest format (JSON)::

    {
      "documents": [
        {
          "file": "contacts.csv",
          "expected": ["IBAN: DE89 3704 0044 0532 0130 00", "Name: Max Mustermann"],
          "forbidden": []
        }
      ]
    }

``file`` is resolved relative to the manifest's directory.  All PII in shipped
fixtures must be synthetic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from file_processors import FileProcessorRegistry


@dataclass
class ExtractionDoc:
    file: str
    expected: list[str]
    forbidden: list[str] = field(default_factory=list)


@dataclass
class FileResult:
    file: str
    expected: int
    found: int
    missing: list[str]
    forbidden_hits: list[str]


@dataclass
class ExtractionResult:
    per_file: list[FileResult]

    @property
    def total_expected(self) -> int:
        return sum(r.expected for r in self.per_file)

    @property
    def total_found(self) -> int:
        return sum(r.found for r in self.per_file)

    @property
    def forbidden_hits(self) -> int:
        return sum(len(r.forbidden_hits) for r in self.per_file)

    @property
    def recall(self) -> float:
        """Fraction of expected snippets that were extracted (1.0 if none expected)."""
        total = self.total_expected
        return round(self.total_found / total, 4) if total else 1.0

    def as_dict(self) -> dict:
        return {
            "total_expected": self.total_expected,
            "total_found": self.total_found,
            "recall": self.recall,
            "forbidden_hits": self.forbidden_hits,
            "per_file": [
                {
                    "file": r.file,
                    "expected": r.expected,
                    "found": r.found,
                    "missing": r.missing,
                    "forbidden_hits": r.forbidden_hits,
                }
                for r in self.per_file
            ],
        }


def load_extraction_manifest(path: str | Path) -> tuple[list[ExtractionDoc], Path]:
    """Load an extraction manifest; returns the docs and the base directory.

    Raises:
        FileNotFoundError: if the manifest does not exist.
        ValueError: if the manifest structure is malformed.
    """
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    docs_raw = raw.get("documents") if isinstance(raw, dict) else raw
    if not isinstance(docs_raw, list):
        raise ValueError("Manifest must contain a 'documents' list")

    docs: list[ExtractionDoc] = []
    for i, item in enumerate(docs_raw):
        if not isinstance(item, dict) or "file" not in item:
            raise ValueError(f"Manifest document #{i} must be an object with a 'file'")
        docs.append(
            ExtractionDoc(
                file=str(item["file"]),
                expected=list(item.get("expected", [])),
                forbidden=list(item.get("forbidden", [])),
            )
        )
    return docs, p.parent


def extract_text(path: str | Path) -> str:
    """Extract text from a file through the real processor registry.

    Joins iterator-based processors (PDF, ZIP, …) into a single string so callers
    can do simple substring checks.
    """
    p = Path(path)
    processor = FileProcessorRegistry.get_processor(p.suffix, str(p), "")
    if processor is None:
        return ""
    result = processor.extract_text(str(p))
    if isinstance(result, str):
        return result
    return "\n".join(chunk for chunk in result)


def run_extraction_eval(manifest_path: str | Path) -> ExtractionResult:
    """Run extraction over every file in the manifest and score snippet recall."""
    docs, base_dir = load_extraction_manifest(manifest_path)

    per_file: list[FileResult] = []
    for doc in docs:
        text = extract_text(base_dir / doc.file)
        missing = [s for s in doc.expected if s not in text]
        forbidden_hits = [s for s in doc.forbidden if s in text]
        per_file.append(
            FileResult(
                file=doc.file,
                expected=len(doc.expected),
                found=len(doc.expected) - len(missing),
                missing=missing,
                forbidden_hits=forbidden_hits,
            )
        )
    return ExtractionResult(per_file=per_file)
