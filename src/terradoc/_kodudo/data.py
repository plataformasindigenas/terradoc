"""Data loader (inlined from kodudo)."""

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import DataError


@dataclass(frozen=True)
class LoadedData:
    raw: tuple[dict[str, Any], ...]
    meta: dict[str, Any]
    has_meta: bool

    def __len__(self) -> int:
        return len(self.raw)

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.raw)


def load_data(path: str | Path) -> LoadedData:
    path = Path(path)
    if not path.exists():
        raise DataError(f"Data file not found: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            content = json.load(f)
    except json.JSONDecodeError as e:
        raise DataError(f"Invalid JSON in {path}: {e}") from e
    except OSError as e:
        raise DataError(f"Cannot read {path}: {e}") from e

    if isinstance(content, list):
        return LoadedData(raw=tuple(content), meta={}, has_meta=False)
    if not isinstance(content, dict):
        raise DataError("Invalid JSON format: expected object or array")
    if "meta" in content and "data" in content:
        meta = content["meta"]
        data = content["data"]
        if not isinstance(meta, dict):
            raise DataError("'meta' must be an object")
        if not isinstance(data, list):
            raise DataError("'data' must be an array")
        return LoadedData(raw=tuple(data), meta=meta, has_meta=True)
    for key in ("data", "records", "items", "results"):
        if key in content and isinstance(content[key], list):
            return LoadedData(raw=tuple(content[key]), meta={}, has_meta=False)
    raise DataError("Invalid JSON format: expected array or object with 'meta'/'data' keys")
