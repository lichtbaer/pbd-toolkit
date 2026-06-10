"""Precision / recall / F1 metrics for PII detection.

Matching model
--------------
A predicted finding counts as a true positive (TP) for a gold annotation when:

1. their **canonical** entity types are equal (raw engine labels are normalised via
   :func:`core.entity_types.canonical_for`), AND
2. their spans overlap.  When both items carry character offsets, overlap is the usual
   ``max(start) < min(end)``.  When offsets are missing (some engines, e.g. vector
   search, report whole chunks without precise offsets), the harness falls back to a
   case-insensitive text-containment check so that a chunk-level finding still credits
   the gold span it contains.

Matching is greedy and one-to-one: each gold annotation can be satisfied by at most one
prediction and vice versa.  Leftover gold annotations are false negatives (FN); leftover
predictions are false positives (FP).

Reported figures
----------------
- Per canonical type: precision, recall, F1, plus tp/fp/fn counts.
- ``micro``: pooled over all types (dominated by frequent types).
- ``macro``: unweighted mean of per-type F1 over types present in the gold set
  (treats rare types as equally important).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.entity_types import canonical_for


@dataclass
class Annotation:
    """A typed text span, used for both gold annotations and predictions.

    ``start`` / ``end`` are character offsets into the source document and may be
    ``None`` when an engine does not provide them (text-containment fallback applies).
    """

    type: str
    start: int | None = None
    end: int | None = None
    text: str = ""

    @property
    def canonical(self) -> str:
        return canonical_for(self.type)


def _spans_overlap(gold: Annotation, pred: Annotation) -> bool:
    """Return True if a gold annotation and a prediction refer to the same mention."""
    if (
        gold.start is not None
        and gold.end is not None
        and pred.start is not None
        and pred.end is not None
    ):
        return max(gold.start, pred.start) < min(gold.end, pred.end)
    # Offset fallback: credit a (possibly chunk-level) prediction whose text contains the
    # gold text, or vice versa.
    g = (gold.text or "").strip().lower()
    p = (pred.text or "").strip().lower()
    if not g or not p:
        return False
    return g in p or p in g


@dataclass
class TypeMetrics:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def as_dict(self) -> dict:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }


@dataclass
class EvaluationResult:
    """Aggregated metrics across a whole dataset."""

    per_type: dict[str, TypeMetrics] = field(default_factory=dict)

    @property
    def micro(self) -> TypeMetrics:
        pooled = TypeMetrics()
        for m in self.per_type.values():
            pooled.tp += m.tp
            pooled.fp += m.fp
            pooled.fn += m.fn
        return pooled

    @property
    def macro_f1(self) -> float:
        # Macro average over types that appear in the gold set (tp + fn > 0).
        gold_types = [m for m in self.per_type.values() if (m.tp + m.fn) > 0]
        if not gold_types:
            return 0.0
        return sum(m.f1 for m in gold_types) / len(gold_types)

    def f1_for(self, canonical_type: str) -> float:
        m = self.per_type.get(canonical_type)
        return m.f1 if m else 0.0

    def as_dict(self) -> dict:
        micro = self.micro
        return {
            "per_type": {t: m.as_dict() for t, m in sorted(self.per_type.items())},
            "micro": {
                **micro.as_dict(),
                "precision": round(micro.precision, 4),
                "recall": round(micro.recall, 4),
                "f1": round(micro.f1, 4),
            },
            "macro_f1": round(self.macro_f1, 4),
        }


def evaluate_document(
    gold: list[Annotation], pred: list[Annotation]
) -> dict[str, TypeMetrics]:
    """Compute per-type TP/FP/FN for a single document via greedy one-to-one matching."""
    counts: dict[str, TypeMetrics] = {}

    def bucket(canonical: str) -> TypeMetrics:
        return counts.setdefault(canonical, TypeMetrics())

    used_pred: set[int] = set()
    # Greedy: match each gold annotation to the first unused, type-compatible, overlapping
    # prediction.
    for g in gold:
        g_canon = g.canonical
        matched = False
        for i, p in enumerate(pred):
            if i in used_pred:
                continue
            if p.canonical != g_canon:
                continue
            if _spans_overlap(g, p):
                used_pred.add(i)
                bucket(g_canon).tp += 1
                matched = True
                break
        if not matched:
            bucket(g_canon).fn += 1

    # Any prediction not matched to a gold annotation is a false positive.
    for i, p in enumerate(pred):
        if i not in used_pred:
            bucket(p.canonical).fp += 1

    return counts


def evaluate(
    documents: list[tuple[list[Annotation], list[Annotation]]],
) -> EvaluationResult:
    """Aggregate per-type metrics over a list of (gold, pred) document pairs."""
    result = EvaluationResult()
    for gold, pred in documents:
        doc_counts = evaluate_document(gold, pred)
        for canonical, m in doc_counts.items():
            agg = result.per_type.setdefault(canonical, TypeMetrics())
            agg.tp += m.tp
            agg.fp += m.fp
            agg.fn += m.fn
    return result
