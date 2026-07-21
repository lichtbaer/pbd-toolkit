"""Thread-local counters for content skipped during extraction/detection.

File processors and detection engines run inside per-worker threads managed by
``core.scan_runner``, but they don't have access to the per-scan ``Statistics``
instance — extending every file processor's ``extract_text(file_path)`` interface
(and every engine's ``detect(...)``) to thread a ``Statistics`` reference through
would touch a couple dozen files for a narrow observability win. Instead, callers
record skips against this thread-local counter, and ``core.processor.TextProcessor``
drains the calling thread's counts into ``Statistics`` after each file. Because the
counters are thread-local and each scanner worker thread processes one file at a
time, concurrent worker threads never interleave counts.
"""

import threading

_local = threading.local()


def record_skip(reason: str, count: int = 1) -> None:
    """Record that *count* records/entries were skipped for *reason*, on this thread."""
    counts: dict[str, int] | None = getattr(_local, "counts", None)
    if counts is None:
        counts = {}
        _local.counts = counts
    counts[reason] = counts.get(reason, 0) + count


def drain() -> dict[str, int]:
    """Return and clear the calling thread's accumulated skip counts."""
    counts: dict[str, int] | None = getattr(_local, "counts", None)
    if not counts:
        return {}
    _local.counts = {}
    return counts
