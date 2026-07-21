"""Tests for the thread-local skip-counter helper used by file processors/engines."""

import threading

from core import skip_counters


class TestSkipCounters:
    """Tests for record_skip/drain."""

    def setup_method(self):
        # Ensure no leftover state from a previous test leaks in (drain is a no-op
        # if nothing was recorded).
        skip_counters.drain()

    def test_drain_with_nothing_recorded_returns_empty_dict(self):
        assert skip_counters.drain() == {}

    def test_record_skip_accumulates_by_reason(self):
        skip_counters.record_skip("reason_a")
        skip_counters.record_skip("reason_a")
        skip_counters.record_skip("reason_b", count=3)

        assert skip_counters.drain() == {"reason_a": 2, "reason_b": 3}

    def test_drain_clears_state(self):
        skip_counters.record_skip("reason_a")
        assert skip_counters.drain() == {"reason_a": 1}
        # Second drain sees nothing left over.
        assert skip_counters.drain() == {}

    def test_counters_are_thread_local(self):
        """Skips recorded on one thread must not appear on another thread's drain."""
        skip_counters.record_skip("main_thread_reason")

        other_thread_result = {}

        def worker():
            # This thread has recorded nothing; it must not see the main thread's count.
            other_thread_result["before"] = skip_counters.drain()
            skip_counters.record_skip("worker_thread_reason")
            other_thread_result["after"] = skip_counters.drain()

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        assert other_thread_result["before"] == {}
        assert other_thread_result["after"] == {"worker_thread_reason": 1}
        # The main thread's own counter is untouched by the worker thread.
        assert skip_counters.drain() == {"main_thread_reason": 1}
