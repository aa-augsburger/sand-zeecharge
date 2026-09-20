"""Shared validation at the simulation boundaries."""
import math


def finite(name: str, value: float, minimum: float | None = None,
           maximum: float | None = None, *, positive: bool = False) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"{name} doit être un nombre fini")
    if positive and value <= 0:
        raise ValueError(f"{name} doit être strictement positif")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} doit être >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} doit être <= {maximum}")
