"""Domain errors and standard error envelope."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    NO_DATA = "NO_DATA"
    PERMISSION = "PERMISSION"
    RATE_LIMIT = "RATE_LIMIT"
    INVALID_INPUT = "INVALID_INPUT"
    NOT_FOUND = "NOT_FOUND"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class MetaError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        context: str = "",
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.context = context
        self.retry_after = retry_after


def to_envelope(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, MetaError):
        out: dict[str, Any] = {
            "error": exc.message,
            "context": exc.context,
            "code": exc.code.value,
        }
        if exc.retry_after is not None:
            out["retry_after"] = exc.retry_after
        return out
    return {
        "error": str(exc),
        "context": "",
        "code": ErrorCode.UNKNOWN.value,
    }


def envelope_json(exc: Exception) -> str:
    return json.dumps(to_envelope(exc), ensure_ascii=False)
