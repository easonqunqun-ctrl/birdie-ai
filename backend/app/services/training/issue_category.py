"""M10-05 · issue → drill category 映射加载."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

_MAPPING_PATH = Path(__file__).with_name("issue_to_category.yaml")


@lru_cache(maxsize=1)
def load_issue_category_map() -> dict[str, str]:
    raw = yaml.safe_load(_MAPPING_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


def category_for_issue(issue_type: str) -> str | None:
    return load_issue_category_map().get(issue_type)
