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
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from src.config import APP_SECRET, MCP_HTTP_TOKEN, META_WEBHOOK_VERIFY_TOKEN, REPORT_DIR, WEBHOOK_PORT

log = logging.getLogger("meta-mcp.webhook")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="Meta Marketing Webhook Receiver", version="1.0.0")

# Simple in-memory metrics (Phase 4.1)
_metrics = {"webhook_events_total": 0, "webhook_events_failed": 0, "webhook_verify_total": 0}
_start_time = datetime.now(timezone.utc)


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
    return str(path)


@app.get("/webhook/meta")
def webhook_verify(
    hub_mode: str = "",
    hub_verify_token: str = "",
    hub_challenge: str = "",
):
    """Meta subscription verification handshake."""
    _metrics["webhook_verify_total"] += 1
    if verify_webhook_token(hub_mode, hub_verify_token):
        return PlainTextResponse(hub_challenge)
    return JSONResponse({"error": "verification token mismatch"}, status_code=403)


@app.get("/metrics")
def metrics():
    """Prometheus-style metrics (Phase 4.1)."""
    from src.throttle import concurrent_count

    uptime = (datetime.now(timezone.utc) - _start_time).total_seconds()
    lines = [
        "# HELP webhook_events_total Total webhook events received",
        "# TYPE webhook_events_total counter",
        f"webhook_events_total {_metrics['webhook_events_total']}",
        "# HELP webhook_events_failed Total failed webhook ingestions",
        "# TYPE webhook_events_failed counter",
        f"webhook_events_failed {_metrics['webhook_events_failed']}",
        "# HELP webhook_verify_total Total verification handshakes",
        "# TYPE webhook_verify_total counter",
        f"webhook_verify_total {_metrics['webhook_verify_total']}",
        "# HELP throttle_concurrent Current concurrent Graph API calls",
        "# TYPE throttle_concurrent gauge",
        f"throttle_concurrent {concurrent_count()}",
        "# HELP process_uptime_seconds Uptime of webhook receiver",
        "# TYPE process_uptime_seconds gauge",
        f"process_uptime_seconds {uptime:.0f}",
    ]
    return PlainTextResponse("\n".join(lines), media_type="text/plain")


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
        except Exception as e:
            preview = f"error: {e}"
        rows += f"<tr><td>{f.name}</td><td><pre>{preview}</pre></td></tr>"
    if not rows:
        rows = "<tr><td colspan=2>لا توجد أحداث بعد</td></tr>"
    html = f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>Webhook Dashboard</title>
    <style>body{{font-family:system-ui;max-width:900px;margin:2rem auto}}table{{width:100%;border-collapse:collapse}}td,th{{border:1px solid #ddd;padding:8px}}pre{{white-space:pre-wrap;word-break:break-word}}</style></head>
    <body><h1>لوحة Webhooks</h1><p>الأحداث الأخيرة من <code>{webhook_dir}</code> — <a href="/metrics">/metrics</a></p>
    <table><tr><th>الملف</th><th>المحتوى</th></tr>{rows}</table>
    <p>المقاييس: webhook_events_total={_metrics['webhook_events_total']} | concurrent={0} | uptime={0:.0f}s</p></body></html>"""
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

    cid = request.headers.get("x-correlation-id") or f"wh-{uuid.uuid4().hex[:8]}"
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")
    if not verify_signature(body, signature):
        _metrics["webhook_events_failed"] += 1
        log.warning("رُفض حدث Webhook بسبب توقيع غير صالح correlation_id=%s", cid)
        return JSONResponse({"error": "invalid signature"}, status_code=403)
    try:
        payload = json.loads(body) if body else {}
    except Exception:
        _metrics["webhook_events_failed"] += 1
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)
    try:
        _metrics["webhook_events_total"] += 1
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
        return {"received": True, "saved": saved, "correlation_id": cid}
    except Exception as e:
        _metrics["webhook_events_failed"] += 1
        log.error("فشل حفظ حدث Webhook: %s correlation_id=%s", e, cid)
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    if not META_WEBHOOK_VERIFY_TOKEN:
        log.error("حدد FB_META_WEBHOOK_VERIFY_TOKEN في .env ثم أعد التشغيل.")
        raise SystemExit(1)
    log.info("تشغيل مستقبل Webhooks على المنفذ %s", WEBHOOK_PORT)
    uvicorn.run(app, host="0.0.0.0", port=WEBHOOK_PORT)
