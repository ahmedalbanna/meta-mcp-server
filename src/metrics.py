"""Central metrics: in-memory Prometheus counters/histograms.

Thread-safe, no external deps. Used by:
- src/throttle (concurrent gauge, rate-limit counter)
- src/helpers (api_call counter, error counter, duration histogram)
- webhook_server (webhook counters)
- src/mcp (tool call counter via decorator)

Exposed via webhook_server /metrics and via MCP tool get_metrics.
"""

import threading
import time
from collections import Counter, defaultdict

_lock = threading.Lock()

# Counters
_tool_calls: Counter = Counter()  # key: (tool, status) -> int
_tool_duration: defaultdict = defaultdict(list)  # tool -> list[durations]
_api_calls: Counter = Counter()  # key: method -> int
_api_errors: Counter = Counter()  # key: (code) -> int
_rate_limits: Counter = Counter()  # key: code -> int
_webhook_events: Counter = Counter()  # key: status -> int

_start = time.monotonic()


def inc_tool_call(tool: str, status: str = "ok") -> None:
    with _lock:
        _tool_calls[(tool, status)] += 1


def observe_tool_duration(tool: str, duration: float) -> None:
    with _lock:
        lst = _tool_duration[tool]
        lst.append(duration)
        # keep last 1000 samples to bound memory
        if len(lst) > 1000:
            lst[:] = lst[-1000:]


def inc_api_call(method: str = "GET") -> None:
    with _lock:
        _api_calls[method] += 1


def inc_api_error(code: str = "unknown") -> None:
    with _lock:
        _api_errors[code] += 1


def inc_rate_limit(code: int = 0) -> None:
    with _lock:
        _rate_limits[code] += 1


def inc_webhook(status: str = "received") -> None:
    with _lock:
        _webhook_events[status] += 1


def get_snapshot() -> dict:
    with _lock:
        return {
            "tool_calls": dict(_tool_calls),
            "tool_duration": {k: list(v) for k, v in _tool_duration.items()},
            "api_calls": dict(_api_calls),
            "api_errors": dict(_api_errors),
            "rate_limits": dict(_rate_limits),
            "webhook_events": dict(_webhook_events),
            "uptime": time.monotonic() - _start,
        }


def render_prometheus() -> str:
    """Render Prometheus text exposition format."""
    from src.throttle import concurrent_count

    snap = get_snapshot()
    lines = []
    lines.append("# HELP mcp_tool_calls_total Total MCP tool invocations")
    lines.append("# TYPE mcp_tool_calls_total counter")
    for (tool, status), cnt in snap["tool_calls"].items():
        lines.append(f'mcp_tool_calls_total{{tool="{tool}",status="{status}"}} {cnt}')
    lines.append("# HELP mcp_tool_duration_seconds MCP tool duration histogram (avg)")
    lines.append("# TYPE mcp_tool_duration_seconds summary")
    for tool, durations in snap["tool_duration"].items():
        if durations:
            avg = sum(durations) / len(durations)
            lines.append(f'mcp_tool_duration_seconds{{tool="{tool}",quantile="0.5"}} {avg:.3f}')
            lines.append(f'mcp_tool_duration_seconds_count{{tool="{tool}"}} {len(durations)}')
            lines.append(f'mcp_tool_duration_seconds_sum{{tool="{tool}"}} {sum(durations):.3f}')
    lines.append("# HELP meta_api_calls_total Meta Graph API calls")
    lines.append("# TYPE meta_api_calls_total counter")
    for method, cnt in snap["api_calls"].items():
        lines.append(f'meta_api_calls_total{{method="{method}"}} {cnt}')
    lines.append("# HELP meta_api_errors_total Meta API errors")
    lines.append("# TYPE meta_api_errors_total counter")
    for code, cnt in snap["api_errors"].items():
        lines.append(f'meta_api_errors_total{{code="{code}"}} {cnt}')
    lines.append("# HELP meta_rate_limit_total Rate limit hits")
    lines.append("# TYPE meta_rate_limit_total counter")
    for code, cnt in snap["rate_limits"].items():
        lines.append(f'meta_rate_limit_total{{code="{code}"}} {cnt}')
    lines.append("# HELP webhook_events_total Webhook events")
    lines.append("# TYPE webhook_events_total counter")
    for status, cnt in snap["webhook_events"].items():
        lines.append(f'webhook_events_total{{status="{status}"}} {cnt}')
    lines.append("# HELP throttle_concurrent Current concurrent Graph API calls")
    lines.append("# TYPE throttle_concurrent gauge")
    lines.append(f"throttle_concurrent {concurrent_count()}")
    lines.append("# HELP process_uptime_seconds Process uptime")
    lines.append("# TYPE process_uptime_seconds gauge")
    lines.append(f"process_uptime_seconds {snap['uptime']:.0f}")
    return "\n".join(lines) + "\n"


def metrics_tool_decorator(fn):
    """Decorator for MCP tools to auto-record metrics."""
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        tool = fn.__name__
        t0 = time.monotonic()
        try:
            result = fn(*args, **kwargs)
            # Heuristic: if result contains "error", count as error
            status = "error" if '"error"' in str(result) else "ok"
            inc_tool_call(tool, status)
            return result
        except Exception:
            inc_tool_call(tool, "exception")
            raise
        finally:
            observe_tool_duration(tool, time.monotonic() - t0)

    return wrapper


def register(mcp):
    """Register metrics MCP tools (Phase 4.1)."""

    from src.helpers import handle_error, json_dumps
    from src.throttle import concurrency_limit

    @mcp.tool()
    @concurrency_limit()
    def get_metrics(format: str = "json") -> str:
        """مقاييس الأداء الحالية (Prometheus أو JSON). format: json | prometheus"""
        try:
            if format.strip().lower() == "prometheus":
                return json_dumps({"prometheus": render_prometheus()})
            snap = get_snapshot()
            # Convert tuple keys to string for JSON
            tool_calls = {f"{k[0]}:{k[1]}": v for k, v in snap["tool_calls"].items()}
            return json_dumps(
                {
                    "tool_calls": tool_calls,
                    "api_calls": snap["api_calls"],
                    "api_errors": snap["api_errors"],
                    "rate_limits": snap["rate_limits"],
                    "webhook_events": snap["webhook_events"],
                    "uptime": round(snap["uptime"], 1),
                    "tool_duration_samples": {k: len(v) for k, v in snap["tool_duration"].items()},
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "get_metrics"))

    @mcp.tool()
    @concurrency_limit()
    def get_metrics_prometheus() -> str:
        """مقاييس بصيغة Prometheus exposition (مغلفة كـ JSON)."""
        try:
            return json_dumps({"prometheus": render_prometheus()})
        except Exception as e:
            return json_dumps({"error": str(e)})

    @mcp.tool()
    @concurrency_limit()
    def reset_metrics() -> str:
        """تصفير جميع المقاييس (للتطوير/الاختبار)."""
        try:
            global _tool_calls, _tool_duration, _api_calls, _api_errors, _rate_limits, _webhook_events, _start
            with _lock:
                _tool_calls.clear()
                _tool_duration.clear()
                _api_calls.clear()
                _api_errors.clear()
                _rate_limits.clear()
                _webhook_events.clear()
                _start = time.monotonic()
            return json_dumps({"success": True, "message": "تم تصفير المقاييس"})
        except Exception as e:
            return json_dumps(handle_error(e, "reset_metrics"))
