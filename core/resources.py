"""Helpers for loading packaged resources.

This module centralizes access to configuration assets such as `config_types.json`
so code does not depend on the current working directory.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def load_config_types() -> dict[str, Any]:
    """Load `config_types.json` from ``core/config_types.json``.

    Resolution order:
    1) ``core/config_types.json`` next to this module (editable / source installs)
    2) Packaged resource via ``importlib.resources`` (wheel installs)
    """
    # Direct path sibling: works for editable installs and direct source runs
    sibling = Path(__file__).resolve().parent / "config_types.json"
    if sibling.exists():
        return json.loads(sibling.read_text(encoding="utf-8"))

    try:
        # Python 3.9+: `importlib.resources.files`
        import importlib.resources as resources

        data = resources.files("core").joinpath("config_types.json").read_bytes()
        return json.loads(data.decode("utf-8"))
    except Exception as e:  # pragma: no cover
        raise FileNotFoundError(
            "Could not locate 'config_types.json' (core/ or packaged resource)."
        ) from e
