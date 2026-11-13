"""Describe JSON-like Garmin payloads by key structure only (no values)."""

from __future__ import annotations

from typing import Any


def describe_value_shape(value: Any, *, max_depth: int = 8, depth: int = 0) -> Any:
    if depth >= max_depth:
        return type(value).__name__
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, dict):
        return {
            key: describe_value_shape(value[key], max_depth=max_depth, depth=depth + 1)
            for key in sorted(value)
        }
    if isinstance(value, list):
        if not value:
            return ["list", "empty"]
        head = describe_value_shape(value[0], max_depth=max_depth, depth=depth + 1)
        if len(value) == 1:
            return ["list", head]
        return ["list", head, f"len={len(value)}"]
    return type(value).__name__
