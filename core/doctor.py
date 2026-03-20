"""Configuration and environment validation ("doctor") utilities."""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

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


def check_api_connectivity(
    endpoints: dict[str, str],
    timeout: int = 5,
) -> list[DoctorIssue]:
    """Test HTTP connectivity to the given named endpoints.

    Args:
        endpoints: Mapping of ``name -> url`` to probe (HTTP GET).
        timeout: Per-request timeout in seconds.

    Returns:
        List of DoctorIssues with level "info" (reachable) or "warning"
        (unreachable / error).
    """
    issues: list[DoctorIssue] = []
    try:
        import requests  # type: ignore
    except ImportError:
        issues.append(
            DoctorIssue(
                "warning",
                "Cannot test API connectivity: 'requests' library not installed.",
            )
        )
        return issues

    for name, url in endpoints.items():
        try:
            resp = requests.get(url, timeout=timeout)
            issues.append(
                DoctorIssue(
                    "info",
                    f"API endpoint reachable: {name} ({url}) → HTTP {resp.status_code}",
                )
            )
        except Exception as exc:
            issues.append(
                DoctorIssue(
                    "warning",
                    f"API endpoint NOT reachable: {name} ({url}) — {exc}",
                )
            )

    return issues


def run_benchmark(
    text: str = "Max Mustermann, IBAN DE89370400440532013000, max@example.com",
) -> list[DoctorIssue]:
    """Run a quick benchmark: push *text* through all locally available engines.

    Only engines that can be initialised without network access are tested
    (regex always runs; GLiNER and spaCy run if installed).

    Returns:
        List of DoctorIssues with timing results.
    """
    issues: list[DoctorIssue] = []

    # --- Regex engine ---
    try:
        from core.resources import load_config_types as _lct

        cfg = _lct()
        regex_entries = cfg.get("regex", [])
        if regex_entries:
            patterns = [r"{}".format(e["expression"]) for e in regex_entries]
            combined = "(" + ")|(".join(patterns) + ")"
            pattern = re.compile(combined, flags=re.IGNORECASE)
            t0 = time.perf_counter()
            matches = list(pattern.finditer(text))
            elapsed = time.perf_counter() - t0
            issues.append(
                DoctorIssue(
                    "info",
                    f"Benchmark regex: {len(matches)} match(es) in {elapsed * 1000:.2f} ms",
                )
            )
    except Exception as exc:
        issues.append(DoctorIssue("warning", f"Benchmark regex failed: {exc}"))

    # --- GLiNER engine (optional) ---
    try:
        import gliner  # noqa: F401
        from core.resources import load_config_types as _lct2

        cfg2 = _lct2()
        labels = [c["term"] for c in cfg2.get("ai-ner", [])]
        if labels:
            try:
                import constants
                from gliner import GLiNER  # type: ignore

                model = GLiNER.from_pretrained(constants.NER_MODEL_NAME)
                t0 = time.perf_counter()
                entities = model.predict_entities(text, labels, threshold=0.5)
                elapsed = time.perf_counter() - t0
                issues.append(
                    DoctorIssue(
                        "info",
                        f"Benchmark GLiNER: {len(entities)} entity/entities in {elapsed * 1000:.2f} ms",
                    )
                )
            except Exception as exc:
                issues.append(
                    DoctorIssue("warning", f"Benchmark GLiNER model run failed: {exc}")
                )
        else:
            issues.append(
                DoctorIssue("info", "Benchmark GLiNER: skipped (no labels configured)")
            )
    except ImportError:
        issues.append(DoctorIssue("info", "Benchmark GLiNER: skipped (not installed)"))

    # --- spaCy engine (optional) ---
    try:
        import spacy  # noqa: F401

        try:
            import constants as _const

            model_name = getattr(_const, "SPACY_MODEL_NAME", "de_core_news_lg")
            nlp = spacy.load(model_name)
            t0 = time.perf_counter()
            doc = nlp(text)
            elapsed = time.perf_counter() - t0
            entities = [ent for ent in doc.ents]
            issues.append(
                DoctorIssue(
                    "info",
                    f"Benchmark spaCy ({model_name}): {len(entities)} entity/entities in {elapsed * 1000:.2f} ms",
                )
            )
        except Exception as exc:
            issues.append(
                DoctorIssue("warning", f"Benchmark spaCy model run failed: {exc}")
            )
    except ImportError:
        issues.append(DoctorIssue("info", "Benchmark spaCy: skipped (not installed)"))

    return issues


def run_doctor(
    api_endpoints: Optional[dict[str, str]] = None,
    run_bench: bool = False,
) -> DoctorReport:
    """Run best-effort validation of config_types + optional feature deps.

    Args:
        api_endpoints: Optional mapping of name → URL to probe for connectivity.
            If provided, HTTP GET requests are made to each URL.
        run_bench: If True, run a quick engine benchmark with a dummy text.

    Returns:
        DoctorReport with issues and details.
    """
    issues: list[DoctorIssue] = []
    details: dict[str, Any] = {}

    # --- Python version ---
    py_ver = sys.version_info
    py_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    if py_ver < (3, 10):
        issues.append(
            DoctorIssue(
                "error", f"Python {py_str} is too old. Python 3.10+ is required."
            )
        )
    else:
        issues.append(DoctorIssue("info", f"Python version: {py_str} ✓"))
    details["python_version"] = py_str

    # --- Load config_types.json ---
    try:
        cfg = load_config_types()
    except Exception as e:
        return DoctorReport(
            ok=False,
            issues=[DoctorIssue("error", f"Failed to load config_types.json: {e}")],
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
    regex_entries = (
        cfg.get("regex", []) if isinstance(cfg.get("regex", None), list) else []
    )
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
            issues.append(
                DoctorIssue("error", f"regex[{idx}] missing/invalid 'expression'")
            )
        else:
            patterns.append(expr)
            try:
                re.compile(expr)
            except re.error as e:
                compile_errors += 1
                issues.append(
                    DoctorIssue("error", f"regex[{idx}] '{label}': invalid regex: {e}")
                )

        if not isinstance(pos, int):
            issues.append(
                DoctorIssue(
                    "warning",
                    f"regex[{idx}] '{label}': missing/invalid regex_compiled_pos",
                )
            )
        else:
            if pos in seen_pos:
                issues.append(
                    DoctorIssue(
                        "warning", f"Duplicate regex_compiled_pos={pos} ('{label}')"
                    )
                )
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
            issues.append(
                DoctorIssue("error", f"Combined regex failed to compile: {e}")
            )

    details["regex_count"] = len(regex_entries)
    if compile_errors == 0 and regex_entries:
        issues.append(
            DoctorIssue(
                "info",
                f"All {len(regex_entries)} regex pattern(s) compile successfully ✓",
            )
        )

    # --- Optional dependency checks with version info ---
    dep_results: dict[str, str] = {}

    def _check_import(mod: str, feature: str, install_hint: str = "") -> None:
        try:
            imported = __import__(mod)
            ver = getattr(imported, "__version__", None) or getattr(
                imported, "version", None
            )
            ver_str = f" v{ver}" if ver else ""
            issues.append(
                DoctorIssue("info", f"[OK] {feature}: '{mod}'{ver_str} installed ✓")
            )
            dep_results[mod] = ver_str.strip() or "installed"
        except Exception:
            hint = f" Install with: {install_hint}" if install_hint else ""
            issues.append(
                DoctorIssue(
                    "info",
                    f"[--] Optional dependency not installed for {feature}: '{mod}'.{hint}",
                )
            )
            dep_results[mod] = "not installed"

    _check_import("gliner", "GLiNER NER (--ner)", "pip install gliner")
    _check_import("spacy", "spaCy NER (--spacy-ner)", "pip install spacy")
    _check_import(
        "pydantic_ai", "PydanticAI LLM (--pydantic-ai)", "pip install pydantic-ai"
    )
    _check_import(
        "requests", "multimodal/OpenAI-compatible LLM", "pip install requests"
    )
    _check_import("pdfminer", "PDF processing", "pip install pdfminer.six")
    _check_import("docx", "DOCX processing", "pip install python-docx")
    _check_import("openpyxl", "XLSX processing", "pip install openpyxl")
    _check_import("bs4", "HTML processing", "pip install beautifulsoup4")
    _check_import("defusedxml", "Secure XML parsing", "pip install defusedxml")
    _check_import("PIL", "Image processing (multimodal)", "pip install Pillow")
    _check_import(
        "sentence_transformers",
        "Vector search (--vector-search)",
        "pip install sentence-transformers",
    )
    _check_import("magic", "Magic file detection (--use-magic-detection)", "pip install python-magic")
    _check_import("fastapi", "REST API (pii-toolkit serve)", "pip install fastapi")
    _check_import("yaml", "YAML config files", "pip install pyyaml")

    details["dependencies"] = dep_results

    # --- GPU / CUDA availability ---
    try:
        import torch

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            cuda_ver = torch.version.cuda or "unknown"
            issues.append(
                DoctorIssue(
                    "info",
                    f"GPU available: {gpu_name} (CUDA {cuda_ver}) ✓",
                )
            )
            details["gpu"] = {"available": True, "name": gpu_name, "cuda": cuda_ver}
        else:
            issues.append(
                DoctorIssue(
                    "info",
                    "No GPU detected. NER models will run on CPU (slower).",
                )
            )
            details["gpu"] = {"available": False}
    except ImportError:
        issues.append(
            DoctorIssue("info", "PyTorch not installed — GPU detection skipped.")
        )
        details["gpu"] = {"available": False, "reason": "torch not installed"}

    # --- Output directory disk space ---
    try:
        import shutil

        output_path = Path("./output/")
        check_path = output_path if output_path.exists() else Path(".")
        disk_usage = shutil.disk_usage(check_path)
        free_gb = disk_usage.free / (1024**3)
        if free_gb < 1.0:
            issues.append(
                DoctorIssue(
                    "warning",
                    f"Low disk space in output directory: {free_gb:.1f} GB free",
                )
            )
        else:
            issues.append(
                DoctorIssue(
                    "info",
                    f"Disk space in output directory: {free_gb:.1f} GB free ✓",
                )
            )
        details["disk_free_gb"] = round(free_gb, 1)
    except Exception:
        pass

    # Multimodal (OpenAI-compatible) local UX hint (best-effort, no network calls).
    issues.append(
        DoctorIssue(
            "info",
            "For local image detection use an OpenAI-compatible server (vLLM/LocalAI) "
            "and set --multimodal-api-base like http://localhost:8000/v1 (vLLM) or "
            "http://localhost:8080/v1 (LocalAI).",
        )
    )

    # --- Check whether repo root and packaged config are in sync (developer hygiene) ---
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
            else:
                issues.append(
                    DoctorIssue(
                        "info",
                        "config_types.json: repo root and core/ copies are in sync ✓",
                    )
                )
    except Exception:
        pass

    # --- API connectivity tests (optional, only when endpoints provided) ---
    if api_endpoints:
        connectivity_issues = check_api_connectivity(api_endpoints)
        issues.extend(connectivity_issues)
        details["api_endpoints_tested"] = list(api_endpoints.keys())

    # --- Engine benchmark (optional) ---
    if run_bench:
        bench_issues = run_benchmark()
        issues.extend(bench_issues)
        details["benchmark_run"] = True
    else:
        details["benchmark_run"] = False

    ok = not any(i.level == "error" for i in issues)
    return DoctorReport(ok=ok, issues=issues, details=details)
