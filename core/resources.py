"""Helpers for loading packaged resources.

This module centralizes access to configuration assets such as `config_types.json`
so code does not depend on the current working directory.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def _repo_root_config_path() -> Path:
    # /workspace/core/resources.py -> /workspace/core -> /workspace
    return Path(__file__).resolve().parent.parent / "config_types.json"


@lru_cache(maxsize=1)
def load_config_types() -> dict[str, Any]:
    """Load `config_types.json` from the best available location.

    Resolution order:
    1) Repo root `config_types.json` (developer workflow, editable installs)
    2) Packaged resource `core/config_types.json` (wheel installs)
    """
    repo_path = _repo_root_config_path()
    if repo_path.exists():
        return json.loads(repo_path.read_text(encoding="utf-8"))

    try:
        # Python 3.9+: `importlib.resources.files`
        import importlib.resources as resources

        data = resources.files("core").joinpath("config_types.json").read_bytes()
        return json.loads(data.decode("utf-8"))
    except Exception as e:  # pragma: no cover
        raise FileNotFoundError(
            "Could not locate 'config_types.json' (repo root or packaged resource)."
        ) from e

