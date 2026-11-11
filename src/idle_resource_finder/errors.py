"""Exception class for all idle-resource-finder errors."""

from __future__ import annotations

from typing import Literal

ErrorCode = Literal[
    "input_too_large",
    "invalid_json",
    "too_many_resources",
    "invalid_resource",
    "duplicate_id",
    "invalid_now",
]


class IdleError(Exception):
    """Base error for the library with a machine-readable code."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        if len(message) > 200:
            message = message[:197] + "..."
        super().__init__(message)
        self.code = code
        self.message = message
