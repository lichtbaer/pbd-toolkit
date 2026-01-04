"""Configuration and environment validation ("doctor") utilities."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.resources import load_config_types


@dataclass
class DoctorIssue:
    level: str  # "error" | "warning" | "info"
    message: str


@dataclass
class DoctorReport:
    ok: bool
    issues: list[DoctorIssue] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


def _try_load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_doctor() -> DoctorReport:
    """Run best-effort validation of config_types + optional feature deps."""
    issues: list[DoctorIssue] = []

    # Load config_types.json (repo root or packaged resource).
    try:
        cfg = load_config_types()
    except Exception as e:
        return DoctorReport(
            ok=False, issues=[DoctorIssue("error", f"Failed to load config_types.json: {e}")]
        )

    # Basic schema-ish checks
    for key in ("settings", "regex", "ai-ner"):
        if key not in cfg:
            issues.append(DoctorIssue("error", f"Missing top-level key: '{key}'"))

    if not isinstance(cfg.get("regex", None), list):
        issues.append(DoctorIssue("error", "config['regex'] must be a list"))
    if not isinstance(cfg.get("ai-ner", None), list):
        issues.append(DoctorIssue("error", "config['ai-ner'] must be a list"))

    # Validate regex entries + mapping contract + compile test
    regex_entries = cfg.get("regex", []) if isinstance(cfg.get("regex", None), list) else []
    seen_pos: set[int] = set()
    mapping_mismatch = 0
    compile_errors = 0
    patterns: list[str] = []

    for idx, entry in enumerate(regex_entries):
        if not isinstance(entry, dict):
            issues.append(DoctorIssue("error", f"regex[{idx}] must be an object"))
            continue

        label = entry.get("label")
        expr = entry.get("expression")
        pos = entry.get("regex_compiled_pos")

        if not isinstance(label, str) or not label:
            issues.append(DoctorIssue("error", f"regex[{idx}] missing/invalid 'label'"))
        if not isinstance(expr, str) or not expr:
            issues.append(DoctorIssue("error", f"regex[{idx}] missing/invalid 'expression'"))
        else:
            patterns.append(expr)
            try:
                re.compile(expr)
            except re.error as e:
                compile_errors += 1
                issues.append(DoctorIssue("error", f"regex[{idx}] '{label}': invalid regex: {e}"))

        if not isinstance(pos, int):
            issues.append(DoctorIssue("warning", f"regex[{idx}] '{label}': missing/invalid regex_compiled_pos"))
        else:
            if pos in seen_pos:
                issues.append(DoctorIssue("warning", f"Duplicate regex_compiled_pos={pos} ('{label}')"))
            seen_pos.add(pos)
            if pos != idx:
                mapping_mismatch += 1

    if mapping_mismatch:
        issues.append(
            DoctorIssue(
                "warning",
                f"{mapping_mismatch} regex entries have regex_compiled_pos that does not match their list index; "
                "match type mapping may be incorrect.",
            )
        )

    if patterns and compile_errors == 0:
        try:
            combined = "(" + ")|(".join(patterns) + ")"
            re.compile(combined, flags=re.IGNORECASE)
        except re.error as e:
            issues.append(DoctorIssue("error", f"Combined regex failed to compile: {e}"))

    # Optional dependency checks (best-effort)
    def _check_import(mod: str, feature: str) -> None:
        try:
            __import__(mod)
        except Exception:
            issues.append(DoctorIssue("info", f"Optional dependency not installed for {feature}: '{mod}'"))

    _check_import("gliner", "GLiNER NER (--ner)")
    _check_import("spacy", "spaCy NER (--spacy-ner)")
    _check_import("pydantic_ai", "PydanticAI LLM (--pydantic-ai / LLM features)")
    _check_import("requests", "multimodal/OpenAI-compatible LLM features")

    # Check whether repo root and packaged config are in sync (developer hygiene)
    try:
        repo_root = Path(__file__).resolve().parent.parent
        repo_cfg_path = repo_root / "config_types.json"
        core_cfg_path = repo_root / "core" / "config_types.json"
        if repo_cfg_path.exists() and core_cfg_path.exists():
            repo_cfg = _try_load_json(repo_cfg_path)
            core_cfg = _try_load_json(core_cfg_path)
            if repo_cfg != core_cfg:
                issues.append(
                    DoctorIssue(
                        "warning",
                        "Repo root 'config_types.json' and 'core/config_types.json' differ. "
                        "Installed wheels may behave differently from repo runs.",
                    )
                )
    except Exception:
        # Ignore hygiene check failures.
        pass

    ok = not any(i.level == "error" for i in issues)
    return DoctorReport(ok=ok, issues=issues, details={"regex_count": len(regex_entries)})

