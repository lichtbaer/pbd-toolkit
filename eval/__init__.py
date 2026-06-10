"""Detection-quality evaluation harness.

Measures precision / recall / F1 of the detection engines against an annotated
ground-truth dataset, grouped by canonical entity type (see ``core.entity_types``).

The harness is deliberately import-light at package level so that ``eval.metrics`` and
``eval.dataset`` can be unit-tested without importing optional ML engine dependencies.
"""
