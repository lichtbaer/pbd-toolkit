"""Analytics module for persistent PII scan result storage.

This module provides an optional SQLite-based analytics database that
stores scan session metadata and aggregated findings (no PII text) for
statistical analysis and dashboard consumption.

Usage::

    from analytics.store import AnalyticsStore

    store = AnalyticsStore()
    session_id = store.create_session(scan_path="/data", config_summary={...})
    store.record_finding(session_id, match)
    store.complete_session(session_id, statistics)
    store.close()
"""
