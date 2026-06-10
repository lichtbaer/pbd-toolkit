"""Run detection engines over a ground-truth dataset and report precision/recall/F1.

Predictions are produced through the real :class:`core.matches.PiiMatchContainer`
pipeline (canonical normalisation + structured checksum validation) so the measured
numbers reflect what the tool would actually report, not a bypass path.

Default engine set is ``regex`` only, which is deterministic and requires no model
downloads — this keeps the harness hermetic and CI-friendly.  Model-based engines
(``gliner``, ``spacy-ner``, ``vector-search``, ``pydantic-ai``) are opt-in.
"""

from __future__ import annotations

import logging

from core.config import Config
from core.entity_types import canonical_for
from core.matches import PiiMatchContainer
from eval.dataset import Document
from eval.metrics import Annotation, EvaluationResult, evaluate

_logger = logging.getLogger(__name__)

DEFAULT_ENGINES = ("regex",)

# Maps engine name to the Config flag that enables it.
_ENGINE_FLAGS: dict[str, str] = {
    "regex": "use_regex",
    "gliner": "use_ner",
    "spacy-ner": "use_spacy_ner",
    "vector-search": "use_vector_search",
    "pydantic-ai": "use_pydantic_ai",
}


def build_config(engines: list[str]) -> Config:
    """Build a Config with the requested engines enabled and regex compiled."""
    config = Config()
    for name in engines:
        flag = _ENGINE_FLAGS.get(name)
        if flag is None:
            raise ValueError(f"Unknown engine: {name}")
        setattr(config, flag, True)
    # Compile the combined regex alternation if regex is in play.
    if config.use_regex:
        config._load_regex_pattern()
    if config.use_ner:
        config._load_ner_model()
    return config


def _predictions_for_text(
    text: str, engines: list[str], config: Config
) -> list[Annotation]:
    """Run the enabled engines over one text and return normalised predictions."""
    from core.engines.registry import EngineRegistry

    container = PiiMatchContainer(validate_structured_findings=True)
    for name in engines:
        engine = EngineRegistry.get_engine(name, config)
        if engine is None or not engine.is_available():
            _logger.warning("Engine '%s' is unavailable, skipping", name)
            continue
        try:
            results = engine.detect(text)
        except Exception as exc:  # pragma: no cover - defensive
            _logger.warning("Engine '%s' failed on a document: %s", name, exc)
            continue
        container.add_detection_results(results, file_path="<eval>", source_text=text)

    predictions: list[Annotation] = []
    for pm in container.pii_matches:
        canonical = pm.metadata.get("canonical_type") or canonical_for(pm.type)
        start = pm.char_offset
        end = start + len(pm.text) if start is not None else None
        predictions.append(
            Annotation(type=canonical, start=start, end=end, text=pm.text)
        )
    return predictions


def run_evaluation(
    documents: list[Document], engines: list[str] | None = None
) -> EvaluationResult:
    """Evaluate the given engines over a dataset and return aggregated metrics."""
    engine_list = list(engines) if engines else list(DEFAULT_ENGINES)
    config = build_config(engine_list)

    pairs: list[tuple[list[Annotation], list[Annotation]]] = []
    for doc in documents:
        preds = _predictions_for_text(doc.text, engine_list, config)
        pairs.append((doc.annotations, preds))

    return evaluate(pairs)
