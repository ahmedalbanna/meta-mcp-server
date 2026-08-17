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

from src.config import APP_SECRET, META_WEBHOOK_VERIFY_TOKEN, REPORT_DIR, WEBHOOK_PORT

log = logging.getLogger("meta-mcp.webhook")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="Meta Marketing Webhook Receiver", version="1.0.0")


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
    if verify_webhook_token(hub_mode, hub_verify_token):
        return PlainTextResponse(hub_challenge)
    return JSONResponse({"error": "verification token mismatch"}, status_code=403)


@app.post("/webhook/meta")
async def webhook_receive(request: Request):
    """Receive a Meta event batch and store it for later processing."""
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")
    if not verify_signature(body, signature):
        log.warning("رُفض حدث Webhook بسبب توقيع غير صالح")
        return JSONResponse({"error": "invalid signature"}, status_code=403)
    try:
        payload = json.loads(body) if body else {}
    except Exception:
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)
    try:
        saved = save_webhook_event(payload)
        log.info("استُلم حدث Webhook وحُفظ في %s", saved)
        return {"received": True, "saved": saved}
    except Exception as e:
        log.error("فشل حفظ حدث Webhook: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    if not META_WEBHOOK_VERIFY_TOKEN:
        log.error("حدد FB_META_WEBHOOK_VERIFY_TOKEN في .env ثم أعد التشغيل.")
        raise SystemExit(1)
    log.info("تشغيل مستقبل Webhooks على المنفذ %s", WEBHOOK_PORT)
    uvicorn.run(app, host="0.0.0.0", port=WEBHOOK_PORT)
