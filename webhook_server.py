"""Meta Webhook receiver (FastAPI): verify + ingest real-time events.

Run:  python webhook_server.py
Endpoint: GET  /webhook/meta   (verification handshake)
          POST /webhook/meta   (event ingestion)

Received events are stored as JSON files under reports/webhooks/.
"""

import hashlib
import hmac
import json
import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from src.core.config import APP_SECRET, MCP_HTTP_TOKEN, META_WEBHOOK_VERIFY_TOKEN, REPORT_DIR, WEBHOOK_PORT

log = logging.getLogger("meta-mcp.webhook")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start scheduler daemon on startup (Phase 8.3) — runs due tasks every 60s."""
    try:
        from src.scheduler import _get_apscheduler

        sched = _get_apscheduler()
        if sched is not None:
            log.info("APScheduler started with DB %s", sched)
        import asyncio

        async def _loop():
            while True:
                await asyncio.sleep(60)
                try:
                    from src.scheduler import _dispatch_tool, _load_tasks, _save_tasks

                    tasks = _load_tasks()
                    now = int(__import__("time").time())
                    due = [t for t in tasks if t.get("status") == "scheduled" and int(t.get("run_at", 0)) <= now]
                    if due:
                        for task in due:
                            try:
                                await asyncio.to_thread(_dispatch_tool, task.get("tool_name") or "", task.get("params") or {})
                                task["status"] = "done"
                                task["executed_at"] = now
                            except Exception as e:
                                task["status"] = "failed"
                                task["error"] = str(e)
                        _save_tasks(tasks)
                        log.info("scheduler daemon: executed %d tasks", len(due))
                except Exception as e:
                    log.debug("scheduler loop error: %s", e)

        _scheduler_tasks.append(asyncio.create_task(_loop()))
        log.info("scheduler daemon started (60s loop)")
    except Exception as e:
        log.debug("scheduler daemon not started: %s", e)
    yield


app = FastAPI(title="Meta Marketing Webhook Receiver", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Metrics via src.metrics (Phase 4.1) + local verify counter
_metrics = {"webhook_events_total": 0, "webhook_events_failed": 0, "webhook_verify_total": 0}
_metrics_lock = threading.Lock()
_start_time = datetime.now(timezone.utc)
_MAX_WEBHOOK_FILES = 500  # rotation limit (Phase 4.5)
_scheduler_tasks: list[Any] = []


def verify_webhook_token(hub_mode: str = "", hub_verify_token: str = "") -> bool:
    """Validate the Meta verification handshake (mode=subscribe + matching token)."""
    return (
        hub_mode == "subscribe"
        and bool(hub_verify_token)
        and hub_verify_token == META_WEBHOOK_VERIFY_TOKEN
    )


def verify_signature(body: bytes, signature: str) -> bool:
    """Validate the X-Hub-Signature-256 HMAC SHA256 signature Meta sends.

    Returns True when the signature is valid. When no APP_SECRET is configured
    (e.g. local/dev runs) validation is skipped so the server still starts.
    """
    if not APP_SECRET:
        log.warning("APP_SECRET غير مضبوط — تخطي التحقق من توقيع Webhook (وضع التطوير فقط)")
        return True
    if not signature:
        return False
    expected = (
        "sha256="
        + hmac.new(APP_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    )
    return hmac.compare_digest(expected, signature)


def save_webhook_event(payload: dict, report_dir=None) -> str:
    """Persist a received event payload as JSON and return its file path."""
    target = report_dir or (REPORT_DIR / "webhooks")
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    path = target / f"event_{stamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    # Rotation: keep max 500 files (Phase 4.5)
    try:
        files = sorted(target.glob("event_*.json"))
        if len(files) > _MAX_WEBHOOK_FILES:
            for old in files[: len(files) - _MAX_WEBHOOK_FILES]:
                try:
                    old.unlink()
                except Exception:
                    pass
    except Exception:
        pass
    return str(path)


@app.get("/webhook/meta")
def webhook_verify(
    hub_mode: str = Query("", alias="hub.mode"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
    hub_challenge: str = Query("", alias="hub.challenge"),
):
    """Meta subscription verification handshake."""
    with _metrics_lock:
        _metrics["webhook_verify_total"] += 1
    if verify_webhook_token(hub_mode, hub_verify_token):
        return PlainTextResponse(hub_challenge)
    return JSONResponse({"error": "verification token mismatch"}, status_code=403)


@app.get("/metrics")
def metrics():
    """Prometheus-style metrics (Phase 4.1) — combines src.metrics + webhook counters."""
    try:
        from src.metrics import render_prometheus

        base = render_prometheus()
    except Exception:
        base = ""
    uptime = (datetime.now(timezone.utc) - _start_time).total_seconds()
    # Append webhook-specific counters for backwards-compat
    extra = [
        "# HELP webhook_verify_total Total verification handshakes",
        "# TYPE webhook_verify_total counter",
        f"webhook_verify_total {_metrics['webhook_verify_total']}",
        "# HELP webhook_events_failed_total Failed webhook ingestions",
        "# TYPE webhook_events_failed_total counter",
        f"webhook_events_failed_total {_metrics['webhook_events_failed']}",
        "# HELP webhook_files_total Current webhook files on disk",
        "# TYPE webhook_files_total gauge",
        f"webhook_files_total {len(list((REPORT_DIR / 'webhooks').glob('event_*.json'))) if (REPORT_DIR / 'webhooks').exists() else 0}",
        f"process_uptime_seconds {uptime:.0f}",
    ]
    return PlainTextResponse(base + "\n".join(extra) + "\n", media_type="text/plain")


@app.get("/dashboard")
def dashboard(request: Request):
    """Tiny HTML dashboard for recent webhook events (Phase 4.3, read-only)."""
    # Optional bearer token auth via FB_MCP_TOKEN
    if MCP_HTTP_TOKEN:
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {MCP_HTTP_TOKEN}":
            return JSONResponse({"error": "unauthorized"}, status_code=401)
    webhook_dir = REPORT_DIR / "webhooks"
    files = []
    if webhook_dir.exists():
        files = sorted(webhook_dir.glob("event_*.json"), reverse=True)[:20]
    rows = ""
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            preview = json.dumps(data, ensure_ascii=False)[:300]
            cid = data.get("_correlation_id", "")
            rows += f"<tr><td>{f.name}<br><small>{cid}</small></td><td><pre>{preview}</pre></td></tr>"
        except Exception as e:
            preview = f"error: {e}"
            rows += f"<tr><td>{f.name}</td><td><pre>{preview}</pre></td></tr>"
    if not rows:
        rows = "<tr><td colspan=2>لا توجد أحداث بعد</td></tr>"
    # Gather metrics snapshot
    try:
        from src.events import get_queued_events
        from src.metrics import get_snapshot
        from src.throttle import concurrent_count

        snap = get_snapshot()
        queue = len(get_queued_events(500))
        throttle = concurrent_count()
        uptime = (datetime.now(timezone.utc) - _start_time).total_seconds()
        tool_total = sum(snap.get("tool_calls", {}).values()) if snap.get("tool_calls") else 0
        metrics_html = f"<p>المقاييس: webhook_total={_metrics['webhook_events_total']} | failed={_metrics['webhook_events_failed']} | verify={_metrics['webhook_verify_total']} | queue={queue} | throttle={throttle} | tools={tool_total} | uptime={uptime:.0f}s — <a href='/metrics'>/metrics</a> | <a href='/health'>/health</a></p>"
    except Exception:
        metrics_html = f"<p>المقاييس: webhook_total={_metrics['webhook_events_total']} — <a href='/metrics'>/metrics</a></p>"
    html = f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>Webhook Dashboard</title>
    <style>body{{font-family:system-ui;max-width:900px;margin:2rem auto}}table{{width:100%;border-collapse:collapse}}td,th{{border:1px solid #ddd;padding:8px}}pre{{white-space:pre-wrap;word-break:break-word}} .badge{{background:#eee;padding:2px 6px;border-radius:4px;font-size:0.8em}}</style></head>
    <body><h1>لوحة Webhooks</h1><p>الأحداث الأخيرة من <code>{webhook_dir}</code></p>
    {metrics_html}
    <table><tr><th>الملف / correlation</th><th>المحتوى</th></tr>{rows}</table>
    <p style="margin-top:2rem;color:#666">Phase 4 — Observability & Scale — <span class="badge">v1.3</span> — حد التوازي {__import__('os').getenv('FB_MAX_CONCURRENT','4')} — Adaptive throttle {"مفعّل" if __import__('os').getenv('FB_ADAPTIVE_THROTTLE','true').lower() in ('1','true','yes','on') else "معطّل"}</p></body></html>"""
    from fastapi.responses import HTMLResponse

    return HTMLResponse(html)


@app.get("/health")
def health():
    """Liveness probe."""
    return {"status": "ok", "uptime": (datetime.now(timezone.utc) - _start_time).total_seconds()}


@app.post("/webhook/meta")
async def webhook_receive(request: Request):
    """Receive a Meta event batch and store it for later processing."""
    # Correlation id for tracing (Phase 4.2)
    import uuid

    from src.utils import set_correlation_id

    cid = request.headers.get("x-correlation-id") or f"wh-{uuid.uuid4().hex[:8]}"
    set_correlation_id(cid)
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")
    if not verify_signature(body, signature):
        with _metrics_lock:
            _metrics["webhook_events_failed"] += 1
        try:
            from src.metrics import inc_webhook

            inc_webhook("failed")
        except Exception:
            pass
        log.warning("رُفض حدث Webhook بسبب توقيع غير صالح correlation_id=%s", cid)
        return JSONResponse({"error": "invalid signature"}, status_code=403)
    try:
        payload = json.loads(body) if body else {}
    except Exception:
        with _metrics_lock:
            _metrics["webhook_events_failed"] += 1
        try:
            from src.metrics import inc_webhook

            inc_webhook("failed")
        except Exception:
            pass
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)
    try:
        with _metrics_lock:
            _metrics["webhook_events_total"] += 1
        try:
            from src.metrics import inc_webhook

            inc_webhook("received")
        except Exception:
            pass
        # annotate event with correlation
        if isinstance(payload, dict):
            payload["_correlation_id"] = cid
        saved = save_webhook_event(payload)
        log.info("استُلم حدث Webhook وحُفظ في %s correlation_id=%s", saved, cid)
        try:
            from src.events import push_webhook_event
            push_webhook_event(payload)
        except Exception:
            pass
        # Optional auto-run webhook automations if enabled (Phase 3.1 + 4)
        try:
            import os

            if os.getenv("FB_AUTO_RUN_WEBHOOK_AUTOMATIONS", "false").lower() in ("1", "true", "yes", "on"):
                from src.webhook_automations import _load_rules

                # Only run if there are enabled rules; actual execution is via MCP tool for safety
                # We just log that automations would run
                rules = [r for r in _load_rules() if r.get("enabled")]
                if rules:
                    log.info("webhook automations: %d rules would run for %s", len(rules), cid)
        except Exception:
            pass
        return {"received": True, "saved": saved, "correlation_id": cid}
    except Exception as e:
        with _metrics_lock:
            _metrics["webhook_events_failed"] += 1
        try:
            from src.metrics import inc_webhook

            inc_webhook("failed")
        except Exception:
            pass
        log.error("فشل حفظ حدث Webhook: %s correlation_id=%s", e, cid)
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    if not META_WEBHOOK_VERIFY_TOKEN:
        log.error("حدد FB_META_WEBHOOK_VERIFY_TOKEN في .env ثم أعد التشغيل.")
        raise SystemExit(1)
    log.info("تشغيل مستقبل Webhooks على المنفذ %s", WEBHOOK_PORT)
    uvicorn.run(app, host="0.0.0.0", port=WEBHOOK_PORT)
