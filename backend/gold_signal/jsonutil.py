"""JSON-safe payloads (no NaN / inf)."""

from __future__ import annotations

import math
from typing import Any


def sanitize(obj: Any) -> Any:
    if obj is None:
        return None
    try:
        import numpy as np

        if isinstance(obj, np.generic):
            return sanitize(obj.item())
    except ImportError:
        pass
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {str(k): sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize(v) for v in obj]
    return obj
