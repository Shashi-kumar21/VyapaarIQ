"""Load ``config.yaml`` once; tests may pass an override dict."""

from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).with_name("config.yaml")


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def get_config() -> dict[str, Any]:
    """Return a deep copy so callers cannot mutate the cached config."""
    return copy.deepcopy(_load())
