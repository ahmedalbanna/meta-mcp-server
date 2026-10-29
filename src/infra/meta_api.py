"""Meta Graph API adapter implementing MetaApiClient port."""

from __future__ import annotations

from typing import Any

from src import helpers as _helpers


class MetaApiAdapter:
    def __init__(self, config: Any) -> None:
        self.config = config

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return _helpers.api_call("GET", path, params or {})  # type: ignore[no-any-return]

    def post(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return _helpers.api_call("POST", path, params or {})  # type: ignore[no-any-return]

    def delete(self, path: str) -> dict[str, Any]:
        return _helpers.api_call("DELETE", path)  # type: ignore[no-any-return]

    def page_get(self, page_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return _helpers.page_api_call("GET", page_id, params or {})  # type: ignore[no-any-return]

    def page_post(self, page_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return _helpers.page_api_call("POST", page_id, params or {})  # type: ignore[no-any-return]
