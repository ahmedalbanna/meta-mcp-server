"""Metrics service (Phase B)."""

from __future__ import annotations

from typing import Any

from src.core.services import Services


class MetricsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def get_metrics(self, format: str = "json") -> Any:
        from src.metrics import get_snapshot, render_prometheus
        if format.strip().lower() == "prometheus":
            return {"prometheus": render_prometheus()}
        snap = get_snapshot()
        tool_calls = {f"{k[0]}:{k[1]}": v for k, v in snap["tool_calls"].items()}
        return {
            "tool_calls": tool_calls,
            "api_calls": snap["api_calls"],
            "api_errors": snap["api_errors"],
            "rate_limits": snap["rate_limits"],
            "webhook_events": snap["webhook_events"],
            "uptime": round(snap["uptime"], 1),
            "tool_duration_samples": {k: len(v) for k, v in snap["tool_duration"].items()},
        }

    def get_prometheus(self) -> Any:
        from src.metrics import render_prometheus
        return {"prometheus": render_prometheus()}
