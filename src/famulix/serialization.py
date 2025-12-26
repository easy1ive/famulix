"""Common JSON serialization utilities for famulix."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from typing import Any


class FamulixJSONEncoder(json.JSONEncoder):
    """JSON encoder with famulix-specific type support."""

    def default(self, obj: Any) -> Any:
        if is_dataclass(obj) and not isinstance(obj, type):
            return asdict(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, set):
            return sorted(list(obj))
        if isinstance(obj, bytes):
            return obj.hex()
        return super().default(obj)


def to_json(obj: Any, *, indent: int | None = None) -> str:
    """Serialize object to JSON string with famulix type support."""
    return json.dumps(obj, cls=FamulixJSONEncoder, indent=indent, ensure_ascii=False)


def from_json(s: str) -> Any:
    """Deserialize JSON string to object."""
    return json.loads(s)
