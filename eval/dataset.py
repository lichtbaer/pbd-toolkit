"""Loading and validation of annotated ground-truth datasets.

Dataset format (JSON)
---------------------
A dataset is a JSON list of document objects::

    [
      {
        "id": "doc-001",
        "text": "Max Mustermann, IBAN DE89 3704 0044 0532 0130 00",
        "annotations": [
          {"type": "PERSON", "start": 0, "end": 14, "text": "Max Mustermann"},
          {"type": "IBAN", "start": 21, "end": 48, "text": "DE89 3704 0044 0532 0130 00"}
        ]
      },
      ...
    ]

``type`` should be a canonical entity type (see ``core.entity_types``); raw engine
labels are accepted too and normalised on load.  ``start`` / ``end`` are optional but
recommended — when present they are validated against ``text``.  All PII in shipped
datasets must be synthetic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from core.entity_types import canonical_for
from eval.metrics import Annotation


@dataclass
class Document:
    id: str
    text: str
    annotations: list[Annotation]


def _parse_annotation(raw: dict, doc_id: str) -> Annotation:
    if "type" not in raw:
        raise ValueError(f"Annotation in document '{doc_id}' is missing 'type'")
    start = raw.get("start")
    end = raw.get("end")
    text = raw.get("text", "")
    return Annotation(
        type=canonical_for(raw["type"]),
        start=int(start) if start is not None else None,
        end=int(end) if end is not None else None,
        text=text,
    )


def load_dataset(path: str | Path) -> list[Document]:
    """Load and validate an annotated dataset from a JSON file.

    Raises:
        FileNotFoundError: if the path does not exist.
        ValueError: if the structure is malformed or an offset/text mismatch is found.
    """
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))

    if isinstance(raw, dict) and "documents" in raw:
        raw = raw["documents"]
    if not isinstance(raw, list):
        raise ValueError("Dataset must be a JSON list of document objects")

    documents: list[Document] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Document #{i} is not an object")
        doc_id = str(item.get("id", f"doc-{i}"))
        text = item.get("text", "")
        if not isinstance(text, str):
            raise ValueError(f"Document '{doc_id}' has non-string 'text'")
        ann_raw = item.get("annotations", [])
        if not isinstance(ann_raw, list):
            raise ValueError(f"Document '{doc_id}' 'annotations' must be a list")

        annotations = [_parse_annotation(a, doc_id) for a in ann_raw]

        # Validate offsets against text where provided to catch dataset drift early.
        for a in annotations:
            if a.start is not None and a.end is not None and a.text:
                if text[a.start : a.end] != a.text:
                    raise ValueError(
                        f"Document '{doc_id}': annotation offset/text mismatch for "
                        f"{a.type!r} at [{a.start}:{a.end}] "
                        f"(expected {a.text!r}, found {text[a.start : a.end]!r})"
                    )

        documents.append(Document(id=doc_id, text=text, annotations=annotations))

    return documents
