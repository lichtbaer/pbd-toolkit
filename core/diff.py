"""Scan result comparison (diff) for tracking PII findings over time."""

import json
from pathlib import Path
from typing import Any


def load_findings(file_path: str) -> list[dict]:
    """Load findings from a JSON or JSONL file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.suffix == ".jsonl":
        findings = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                # Skip metadata lines
                if "_metadata" in data:
                    continue
                findings.append(data)
        return findings
    else:
        # JSON format
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "findings" in data:
            return data["findings"]
        if isinstance(data, list):
            return data
        return []


def _finding_key(finding: dict) -> tuple:
    """Create a comparison key for a finding."""
    return (finding.get("file", ""), finding.get("type", ""), finding.get("text", ""))


def compute_diff(old_findings: list[dict], new_findings: list[dict]) -> dict[str, Any]:
    """Compare two sets of findings and return a diff report."""
    old_keys = {}
    for f in old_findings:
        key = _finding_key(f)
        old_keys[key] = f

    new_keys = {}
    for f in new_findings:
        key = _finding_key(f)
        new_keys[key] = f

    old_set = set(old_keys.keys())
    new_set = set(new_keys.keys())

    added_keys = new_set - old_set
    removed_keys = old_set - new_set
    unchanged_keys = old_set & new_set

    added = [new_keys[k] for k in sorted(added_keys)]
    removed = [old_keys[k] for k in sorted(removed_keys)]
    unchanged = [new_keys[k] for k in sorted(unchanged_keys)]

    # Severity distribution for added findings
    added_severity = {}
    for f in added:
        sev = f.get("severity", "UNKNOWN")
        added_severity[sev] = added_severity.get(sev, 0) + 1

    removed_severity = {}
    for f in removed:
        sev = f.get("severity", "UNKNOWN")
        removed_severity[sev] = removed_severity.get(sev, 0) + 1

    return {
        "summary": {
            "old_total": len(old_findings),
            "new_total": len(new_findings),
            "added": len(added),
            "removed": len(removed),
            "unchanged": len(unchanged),
        },
        "added_by_severity": added_severity,
        "removed_by_severity": removed_severity,
        "added_findings": added,
        "removed_findings": removed,
    }
