"""Shared, minimal input-validation helpers.

Internal module: not part of the public API. Every check raises ``ValueError``
with a message naming the offending quantity, so callers get a clear reason
for rejection rather than a downstream NaN or a silent garbage result.
"""

from __future__ import annotations

import math


def require_finite_number(value: float, name: str) -> float:
    """Reject non-numeric, NaN, or infinite values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a real number, got {value!r}")
    value = float(value)
    if math.isnan(value) or math.isinf(value):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return value


def require_positive_finite(value: float, name: str) -> float:
    """Reject non-positive, NaN, or infinite values (value must be > 0)."""
    value = require_finite_number(value, name)
    if value <= 0.0:
        raise ValueError(f"{name} must be positive (> 0), got {value!r}")
    return value


def require_nonnegative_finite(value: float, name: str) -> float:
    """Reject negative, NaN, or infinite values (value must be >= 0)."""
    value = require_finite_number(value, name)
    if value < 0.0:
        raise ValueError(f"{name} must be non-negative (>= 0), got {value!r}")
    return value


def require_positive_absolute_temperature(value: float, name: str) -> float:
    """Reject non-physical absolute temperatures.

    Temperatures in this package are always absolute (kelvin), so a valid
    value must be finite and strictly greater than 0 K.
    """
    return require_positive_finite(value, name)
