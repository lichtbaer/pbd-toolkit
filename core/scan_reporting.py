"""Post-scan reporting and output generation.

Extracted from ``cli.py`` to reduce its size and improve maintainability.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import typer

from core import constants
from core.context import ApplicationContext
from core.exceptions import OutputError
from core.matches import PiiMatch, PiiMatchContainer
from core.severity import combined_file_risk
from core.statistics import Statistics


def compute_file_risk_scores(
    match_container: PiiMatchContainer,
) -> tuple[dict[str, str], dict[str, list[PiiMatch]]]:
    """Compute per-file risk scores using combination-risk escalation.

    Returns:
        Tuple of (file_risk_scores, matches_by_file).
    """
    file_risk_scores: dict[str, str] = {}
    matches_by_file = match_container.by_file()
    for fpath, file_matches in matches_by_file.items():
        pii_types = [m.type for m in file_matches if m.type]
        file_risk_scores[fpath] = combined_file_risk(pii_types)
    return file_risk_scores, matches_by_file


def build_output_metadata(
    context: ApplicationContext,
    errors: dict[str, list[str]],
    file_risk_scores: dict[str, str],
    matches_by_file: dict[str, list[PiiMatch]],
) -> dict[str, Any]:
    """Build the metadata dict passed to output writers."""
    return {
        "start_time": (
            context.statistics.start_time.isoformat()
            if context.statistics.start_time
            else None
        ),
        "end_time": (
            context.statistics.end_time.isoformat()
            if context.statistics.end_time
            else None
        ),
        "duration_seconds": context.statistics.duration_seconds,
        "path": context.config.path,
        "methods": {
            "regex": context.config.use_regex,
            "ner": context.config.use_ner,
            "spacy_ner": getattr(context.config, "use_spacy_ner", False),
            "ollama": getattr(context.config, "use_ollama", False),
            "openai_compatible": getattr(
                context.config, "use_openai_compatible", False
            ),
            "multimodal": getattr(context.config, "use_multimodal", False),
            "pydantic_ai": getattr(context.config, "use_pydantic_ai", False),
        },
        "total_files": context.statistics.total_files_found,
        "analyzed_files": context.statistics.files_processed,
        "matches_found": context.statistics.matches_found,
        "error_count": context.statistics.total_errors,
        "statistics": context.statistics.get_summary_dict(),
        "file_extensions": dict(
            sorted(
                context.statistics.extension_counts.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ),
        "errors": [
            {"type": error_type, "files": file_list}
            for error_type, file_list in errors.items()
        ],
        "file_risk_scores": {
            fpath: {
                "risk_level": risk,
                "match_count": len(matches_by_file.get(fpath, [])),
                "pii_types": list(
                    {m.type for m in matches_by_file.get(fpath, []) if m.type}
                ),
            }
            for fpath, risk in sorted(
                file_risk_scores.items(),
                key=lambda x: {
                    "CRITICAL": 4,
                    "HIGH": 3,
                    "MEDIUM": 2,
                    "LOW": 1,
                    "NONE": 0,
                }.get(x[1], 0),
                reverse=True,
            )
        },
    }


def write_output(
    context: ApplicationContext,
    output_metadata: dict[str, Any],
    csv_file_handle: object | None,
) -> None:
    """Write findings to the output writer and finalize."""
    if context.output_writer:
        if not context.output_writer.supports_streaming:
            for pm in context.match_container.pii_matches:
                context.output_writer.write_match(pm)
        try:
            context.output_writer.finalize(metadata=output_metadata)
        except OutputError as e:
            context.logger.error(f"Failed to write output: {e}")
            raise typer.Exit(code=constants.EXIT_GENERAL_ERROR)
    else:
        if csv_file_handle:
            csv_file_handle.close()


def log_scan_results(
    context: ApplicationContext,
    errors: dict[str, list[str]],
) -> None:
    """Write scan results to the logger."""
    context.logger.info(context._("Statistics"))
    context.logger.info("----------\n")
    context.logger.info(context._("The following file extensions have been found:"))
    for k, v in sorted(
        context.statistics.extension_counts.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        context.logger.info(f"{k:>10}: {v:>10} Dateien")
    context.logger.info(
        context._(
            "TOTAL: {} files.\nQUALIFIED: {} files (supported file extension)\n\n"
        ).format(
            context.statistics.total_files_found, context.statistics.files_processed
        )
    )

    context.logger.info(context._("Findings"))
    context.logger.info("--------\n")
    context.logger.info(context._("--> see *_findings.csv\n\n"))

    context.logger.info(context._("Errors"))
    context.logger.info("------\n")
    for k, v in errors.items():
        context.logger.info(f"\t{k}")
        for f in v:
            context.logger.info(f"\t\t{f}")

    context.logger.info("\n")
    context.logger.info(
        context._("Analysis finished at {}").format(context.statistics.end_time)
    )
    context.logger.info(
        context._("Performance of analysis: {} analyzed files per second").format(
            context.statistics.files_per_second
        )
    )

    # NER statistics
    if (
        context.config.use_ner
        and context.statistics.ner_stats.total_chunks_processed > 0
    ):
        context.logger.info("\n" + context._("NER Statistics"))
        context.logger.info("------------")
        context.logger.info(
            context._("Chunks processed: {}").format(
                context.statistics.ner_stats.total_chunks_processed
            )
        )
        context.logger.info(
            context._("Entities found: {}").format(
                context.statistics.ner_stats.total_entities_found
            )
        )
        context.logger.info(
            context._("Total NER processing time: {:.2f}s").format(
                context.statistics.ner_stats.total_processing_time
            )
        )
        context.logger.info(
            context._("Average time per chunk: {:.3f}s").format(
                context.statistics.avg_ner_time_per_chunk
            )
        )
        if context.statistics.ner_stats.entities_by_type:
            context.logger.info(context._("Entities by type:"))
            for entity_type, count in sorted(
                context.statistics.ner_stats.entities_by_type.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                context.logger.info(f"  {entity_type}: {count}")
        if context.statistics.ner_stats.errors > 0:
            context.logger.warning(
                context._("NER errors encountered: {}").format(
                    context.statistics.ner_stats.errors
                )
            )


def print_console_summary(
    context: ApplicationContext,
    errors: dict[str, list[str]],
    file_risk_scores: dict[str, str],
    matches_by_file: dict[str, list[PiiMatch]],
    output_file_path: str,
    output_dir: str,
    summary_format: str = "human",
) -> None:
    """Print the final summary to the console."""
    if summary_format == "json":
        summary_data = {
            "start_time": (
                context.statistics.start_time.isoformat()
                if context.statistics.start_time
                else None
            ),
            "end_time": (
                context.statistics.end_time.isoformat()
                if context.statistics.end_time
                else None
            ),
            "duration_seconds": context.statistics.duration_seconds,
            "statistics": {
                "files_scanned": context.statistics.total_files_found,
                "files_analyzed": context.statistics.files_processed,
                "matches_found": context.statistics.matches_found,
                "errors": context.statistics.total_errors,
                "throughput_files_per_sec": context.statistics.files_per_second,
            },
            "output_file": context.output_file_path or output_file_path,
            "output_directory": output_dir,
            "errors_summary": (
                {k: len(v) for k, v in errors.items()} if errors else {}
            ),
            "file_risk_scores": file_risk_scores,
        }
        typer.echo(json.dumps(summary_data, indent=2))
        return

    # Human-readable output
    typer.echo("\n" + "=" * 50)
    typer.echo(context._("Analysis Summary"))
    typer.echo("=" * 50)
    if context.statistics.start_time:
        typer.echo(
            f"{context._('Started:')}     {context.statistics.start_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    if context.statistics.end_time:
        typer.echo(
            f"{context._('Finished:')}    {context.statistics.end_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    typer.echo(f"{context._('Duration:')}    {context.statistics.duration}")
    typer.echo()
    typer.echo(context._("Statistics:"))
    typer.echo(
        f"  {context._('Files scanned:')}      {context.statistics.total_files_found:,}"
    )
    typer.echo(
        f"  {context._('Files analyzed:')}     {context.statistics.files_processed:,}"
    )
    typer.echo(
        f"  {context._('Matches found:')}      {context.statistics.matches_found:,}"
    )
    typer.echo(
        f"  {context._('Errors:')}             {context.statistics.total_errors:,}"
    )
    typer.echo()
    typer.echo(context._("Performance:"))
    typer.echo(
        f"  {context._('Throughput:')}         {context.statistics.files_per_second} {context._('files/sec')}"
    )
    typer.echo()
    if errors:
        typer.echo(context._("Errors Summary:"))
        for k, v in errors.items():
            typer.echo(f"  {k}: {len(v)} {context._('files')}")
        typer.echo()

    # Per-file risk summary
    if file_risk_scores:
        risk_distribution: dict[str, int] = {}
        for _risk_level in file_risk_scores.values():
            risk_distribution[_risk_level] = risk_distribution.get(_risk_level, 0) + 1

        typer.echo(context._("File Risk Assessment:"))
        for _rl in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            if _rl in risk_distribution:
                typer.echo(
                    f"  {_rl}: {risk_distribution[_rl]} {context._('files')}"
                )

        _risk_weight = {
            "CRITICAL": 4,
            "HIGH": 3,
            "MEDIUM": 2,
            "LOW": 1,
            "NONE": 0,
        }
        top_risk_files = sorted(
            file_risk_scores.items(),
            key=lambda x: _risk_weight.get(x[1], 0),
            reverse=True,
        )[:5]
        _high_risk = [
            (f, r) for f, r in top_risk_files if r in ("CRITICAL", "HIGH")
        ]
        if _high_risk:
            typer.echo()
            typer.echo(context._("Highest risk files:"))
            for _fpath, _risk in _high_risk:
                _match_count = len(matches_by_file.get(_fpath, []))
                _types = ", ".join(
                    sorted(
                        {
                            m.type
                            for m in matches_by_file.get(_fpath, [])
                            if m.type
                        }
                    )
                )
                typer.echo(
                    f"  [{_risk}] {_fpath} ({_match_count} findings: {_types})"
                )
            typer.echo()

        # Actionable recommendations
        _critical_count = risk_distribution.get("CRITICAL", 0)
        _high_count = risk_distribution.get("HIGH", 0)
        if _critical_count > 0 or _high_count > 0:
            typer.echo(context._("Recommended actions:"))
            if _critical_count > 0:
                typer.echo(
                    f"  ! {_critical_count} {context._('files with CRITICAL risk - immediate review recommended')}"
                )
            if _high_count > 0:
                typer.echo(
                    f"  ! {_high_count} {context._('files with HIGH risk - review recommended')}"
                )
            typer.echo()

    output_file = context.output_file_path or output_file_path
    typer.echo(f"{context._('Output file:')} {output_file}")
    typer.echo(f"{context._('Output directory:')} {output_dir}")
    typer.echo("=" * 50 + "\n")


def write_statistics_output(
    context: ApplicationContext,
    args: object,
    statistics_aggregator: object,
    output_dir: str,
    outslug: str,
) -> None:
    """Generate and write statistics output if statistics mode is enabled."""
    if statistics_aggregator is None:
        return

    # Determine output path
    if hasattr(args, "statistics_output") and args.statistics_output:
        statistics_file_path = args.statistics_output
    else:
        statistics_file_path = output_dir + outslug + "_statistics.json"

    aggregated_stats = statistics_aggregator.get_statistics()

    scan_metadata = {
        "scan_id": outslug,
        "start_time": (
            context.statistics.start_time.isoformat()
            if context.statistics.start_time
            else None
        ),
        "end_time": (
            context.statistics.end_time.isoformat()
            if context.statistics.end_time
            else None
        ),
        "duration_seconds": round(context.statistics.duration_seconds, 2),
        "scan_path": context.config.path,
        "detection_methods": {
            "regex": context.config.use_regex,
            "ner": context.config.use_ner,
            "spacy_ner": getattr(context.config, "use_spacy_ner", False),
            "ollama": getattr(context.config, "use_ollama", False),
            "openai_compatible": getattr(
                context.config, "use_openai_compatible", False
            ),
            "multimodal": getattr(context.config, "use_multimodal", False),
            "pydantic_ai": getattr(context.config, "use_pydantic_ai", False),
        },
        "total_files_scanned": context.statistics.total_files_found,
        "total_files_analyzed": context.statistics.files_processed,
        "total_matches_found": context.statistics.matches_found,
        "statistics_strict": bool(getattr(args, "statistics_strict", False)),
    }

    performance_metrics = {
        "files_per_second": context.statistics.files_per_second,
        "matches_per_second": round(
            (
                context.statistics.matches_found
                / context.statistics.duration_seconds
                if context.statistics.duration_seconds > 0
                else 0
            ),
            2,
        ),
        "processing_time_seconds": round(context.statistics.duration_seconds, 2),
    }

    if context.statistics.ner_stats.total_chunks_processed > 0:
        performance_metrics["ner_statistics"] = {
            "chunks_processed": context.statistics.ner_stats.total_chunks_processed,
            "entities_found": context.statistics.ner_stats.total_entities_found,
            "avg_time_per_chunk": round(
                context.statistics.avg_ner_time_per_chunk, 3
            ),
            "errors": context.statistics.ner_stats.errors,
        }

    from core.writers import PrivacyStatisticsWriter

    stats_writer = PrivacyStatisticsWriter(statistics_file_path)
    try:
        stats_writer.finalize(
            metadata={
                "statistics": aggregated_stats,
                "scan_metadata": scan_metadata,
                "performance_metrics": performance_metrics,
            }
        )
        context.logger.info(
            f"Privacy-focused statistics written to: {statistics_file_path}"
        )
    except OutputError as e:
        context.logger.error(f"Failed to write statistics output: {e}")


def finalize_analytics(
    analytics_store: object | None,
    analytics_session_id: str | None,
    context: ApplicationContext,
    logger: logging.Logger,
) -> None:
    """Complete analytics session with final statistics."""
    if not analytics_store or not analytics_session_id:
        return

    try:
        analytics_store.complete_session(
            session_id=analytics_session_id,
            total_files=context.statistics.total_files_found,
            files_processed=context.statistics.files_processed,
            total_matches=context.statistics.matches_found,
            total_errors=context.statistics.total_errors,
            duration_sec=context.statistics.duration_seconds,
        )
        for (
            engine_name,
            match_count,
        ) in context.statistics.matches_by_engine.items():
            analytics_store.record_engine_stats(
                session_id=analytics_session_id,
                engine=engine_name,
                matches_found=match_count,
            )
        for ext, ext_count in context.statistics.extension_counts.items():
            analytics_store.record_file_type_stats(
                session_id=analytics_session_id,
                extension=ext,
                files_scanned=ext_count,
            )
        analytics_store.close()
    except Exception as exc:
        logger.warning("Failed to finalize analytics session: %s", exc)
