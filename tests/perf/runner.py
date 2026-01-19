import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


SCENARIO_DEFAULTS = {
    "summary_format": "json",
    "output_format": "json",
    "runs": 1,
}


@dataclass
class ScenarioResult:
    name: str
    run_index: int
    return_code: int
    duration_seconds: float
    summary: Optional[dict[str, Any]]
    stdout_tail: str
    stderr_tail: str
    command: list[str]


def load_scenarios(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "YAML scenarios require PyYAML. Use JSON or install pyyaml."
            ) from exc
        data = yaml.safe_load(raw)
    else:
        data = json.loads(raw)

    if isinstance(data, dict) and "scenarios" in data:
        scenarios = data["scenarios"]
    else:
        scenarios = data

    if not isinstance(scenarios, list):
        raise ValueError("Scenario file must contain a list of scenarios.")
    return scenarios


def ensure_summary_arg(args: list[str], summary_format: str) -> list[str]:
    if "--summary-format" in args:
        return args
    return args + ["--summary-format", summary_format]


def ensure_output_args(args: list[str], output_format: str, output_dir: str) -> list[str]:
    if "--format" not in args:
        args = args + ["--format", output_format]
    if "--output-dir" not in args:
        args = args + ["--output-dir", output_dir]
    return args


def extract_json_summary(stdout: str) -> Optional[dict[str, Any]]:
    for idx in range(len(stdout) - 1, -1, -1):
        if stdout[idx] == "{":
            candidate = stdout[idx:]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    return None


def truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def build_filtered_dataset(
    source: Path,
    destination: Path,
    exclude_extensions: set[str],
) -> None:
    for root, dirs, files in os.walk(source):
        relative_root = Path(root).relative_to(source)
        target_root = destination / relative_root
        target_root.mkdir(parents=True, exist_ok=True)
        for filename in files:
            ext = Path(filename).suffix.lower()
            if ext in exclude_extensions:
                continue
            src_file = Path(root) / filename
            dest_file = target_root / filename
            shutil.copy2(src_file, dest_file)


def run_scenario(
    scenario: dict[str, Any],
    run_index: int,
    reports_dir: Path,
    base_dir: Path,
) -> ScenarioResult:
    scenario_name = scenario["name"]
    path = scenario["path"]
    args = list(scenario.get("args", []))
    stop_count = scenario.get("stop_count")
    summary_format = scenario.get("summary_format", SCENARIO_DEFAULTS["summary_format"])
    output_format = scenario.get("output_format", SCENARIO_DEFAULTS["output_format"])
    output_dir = scenario.get("output_dir", str(reports_dir / "output"))
    exclude_extensions = set()
    for ext in scenario.get("exclude_extensions", []):
        if not isinstance(ext, str):
            continue
        normalized = ext.strip().lower()
        if not normalized:
            continue
        if not normalized.startswith("."):
            normalized = f".{normalized}"
        exclude_extensions.add(normalized)

    if stop_count is not None:
        args += ["--stop-count", str(stop_count)]

    args = ensure_summary_arg(args, summary_format)
    args = ensure_output_args(args, output_format, output_dir)

    temp_dataset_dir = None
    scan_path = path
    if exclude_extensions:
        temp_root = reports_dir / "_datasets" / f"{scenario_name}_run{run_index}"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)
        build_filtered_dataset(Path(path), temp_root, exclude_extensions)
        temp_dataset_dir = temp_root
        scan_path = str(temp_root)

    command = [sys.executable, "main.py", "scan", "--path", scan_path] + args
    env = os.environ.copy()
    if "--openai-api-base" in args:
        base_index = args.index("--openai-api-base")
        if base_index + 1 < len(args):
            openai_base = args[base_index + 1]
            env["OPENAI_BASE_URL"] = openai_base
            env["OPENAI_API_BASE"] = openai_base
    if "--ollama" in args:
        ollama_base = "http://localhost:11434"
        if "--ollama-url" in args:
            url_index = args.index("--ollama-url")
            if url_index + 1 < len(args):
                ollama_base = args[url_index + 1]
        env["OLLAMA_BASE_URL"] = ollama_base

    start = time.perf_counter()
    proc = subprocess.run(
        command,
        cwd=base_dir,
        capture_output=True,
        text=True,
        env=env,
    )
    duration = time.perf_counter() - start
    if temp_dataset_dir is not None:
        shutil.rmtree(temp_dataset_dir, ignore_errors=True)

    summary = extract_json_summary(proc.stdout)

    result = ScenarioResult(
        name=scenario_name,
        run_index=run_index,
        return_code=proc.returncode,
        duration_seconds=duration,
        summary=summary,
        stdout_tail=truncate(proc.stdout),
        stderr_tail=truncate(proc.stderr),
        command=command,
    )

    report_path = reports_dir / f"{scenario_name}_run{run_index}.json"
    report_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run E2E performance scenarios.")
    parser.add_argument(
        "--scenarios",
        default="tests/perf/scenarios.json",
        help="Path to scenarios JSON/YAML.",
    )
    parser.add_argument("--list", action="store_true", help="List scenarios only.")
    parser.add_argument("--scenario", help="Run a single scenario by name.")
    parser.add_argument("--all", action="store_true", help="Run all scenarios.")
    parser.add_argument(
        "--reports-dir",
        default="tests/perf/reports",
        help="Directory to write report JSON files.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first failed scenario.",
    )

    args = parser.parse_args()
    base_dir = Path(__file__).resolve().parents[2]
    scenario_path = base_dir / args.scenarios
    reports_dir = base_dir / args.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)

    scenarios = load_scenarios(scenario_path)
    scenarios_by_name = {s["name"]: s for s in scenarios}

    if args.list:
        for name in sorted(scenarios_by_name.keys()):
            print(name)
        return 0

    if args.scenario:
        if args.scenario not in scenarios_by_name:
            print(f"Unknown scenario: {args.scenario}", file=sys.stderr)
            return 2
        run_list = [scenarios_by_name[args.scenario]]
    elif args.all:
        run_list = scenarios
    else:
        print("Specify --scenario or --all (or --list).", file=sys.stderr)
        return 2

    results: list[ScenarioResult] = []
    run_started = datetime.now(timezone.utc).isoformat()
    for scenario in run_list:
        runs = int(scenario.get("runs", SCENARIO_DEFAULTS["runs"]))
        for run_index in range(1, runs + 1):
            result = run_scenario(scenario, run_index, reports_dir, base_dir)
            results.append(result)
            if result.return_code != 0 and args.fail_fast:
                break

        if any(r.return_code != 0 for r in results) and args.fail_fast:
            break

    summary_report = {
        "run_started": run_started,
        "run_finished": datetime.now(timezone.utc).isoformat(),
        "scenario_count": len(run_list),
        "results": [asdict(r) for r in results],
    }
    summary_path = reports_dir / "summary.json"
    summary_path.write_text(json.dumps(summary_report, indent=2), encoding="utf-8")

    failed = [r for r in results if r.return_code != 0 or r.summary is None]
    if failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
