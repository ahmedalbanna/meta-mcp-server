"""Permanent media hosting — Cloudinary (years) with uguu.se fallback (72h).

Uses CLOUDINARY_URL cloudinary://api_key:api_secret@cloud_name  or
CLOUDINARY_CLOUD_NAME + API_KEY + API_SECRET.
If not configured, falls back to uguu.se (free, temporary) — warns in logs.

All local media/*.jpeg uploads for FB/IG now go through host_image() which prefers
permanent hosting. Fixes catalog 38981123561474624 image expiry.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlparse

import requests  # type: ignore[import-untyped]

from src.config import (
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_URL,
)

logger = logging.getLogger(__name__)


def _validate_hosted_url(url: str) -> str:
    """Ensure a hosted URL is an absolute https URL with a host."""
    if not isinstance(url, str) or not url:
        raise ValueError("hosted url must be a non-empty string")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"hosted url must be an https URL with a host: {url!r}")
    return url


def _parse_cloudinary_url(url: str) -> tuple[str, str, str] | None:
    """Parse cloudinary://api_key:api_secret@cloud_name -> (cloud_name, api_key, api_secret)."""
    if not url or not url.startswith("cloudinary://"):
        return None
    try:
        # cloudinary://123:abc@mycloud
        creds, cloud = url[len("cloudinary://") :].split("@", 1)
        api_key, api_secret = creds.split(":", 1)
        return cloud.strip(), api_key.strip(), api_secret.strip()
    except Exception:
        return None


def _upload_cloudinary(file_path: Path, resource_type: str = "image") -> str | None:
    """Upload to Cloudinary, return secure_url, or None on failure/not configured."""
    cloud = api_key = secret = None
    parsed = _parse_cloudinary_url(CLOUDINARY_URL)
    if parsed:
        cloud, api_key, secret = parsed
    elif CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
        cloud, api_key, secret = CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
    else:
        return None

    # Cloudinary signed upload (no preset) — POST https://api.cloudinary.com/v1_1/<cloud>/<resource_type>/upload
    url = f"https://api.cloudinary.com/v1_1/{cloud}/{resource_type}/upload"
    timestamp = int(time.time())
    # signature = sha1("timestamp=<ts><api_secret>")
    to_sign = f"timestamp={timestamp}{secret}"
    signature = hashlib.sha1(to_sign.encode()).hexdigest()

    try:
        with open(file_path, "rb") as f:
            r = requests.post(
                url,
                data={"api_key": api_key, "timestamp": timestamp, "signature": signature},
                files={"file": f},
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            secure = data.get("secure_url") or data.get("url")
            if secure:
                secure = str(secure).replace("http://", "https://")
                try:
                    return _validate_hosted_url(secure)
                except ValueError as e:
                    logger.warning("Cloudinary returned invalid url for %s: %s", file_path.name, e)
                    return None
            logger.warning("Cloudinary response no url: %s", data)
            return None
    except Exception as e:
        logger.warning("Cloudinary upload failed for %s: %s — falling back to uguu.se", file_path.name, e)
        return None


def _upload_uguu(file_path: Path) -> str:
    """Fallback: uguu.se — free, 72h expiry, no credentials."""
    with open(file_path, "rb") as f:
        r = requests.post("https://uguu.se/upload.php", files={"files[]": f}, timeout=60)
        r.raise_for_status()
        data = r.json()
        if not data.get("success") or not data.get("files"):
            raise RuntimeError(f"uguu upload failed: {data}")
        url = str(data["files"][0]["url"]).replace("http://", "https://")
        logger.warning("Used TEMPORARY hosting uguu.se (72h) for %s — set CLOUDINARY_URL for permanent", file_path.name)
        return _validate_hosted_url(url)


def host_image(file_path: str | Path) -> str:
    """Host local image → permanent public URL (Cloudinary if configured, else uguu fallback)."""
    p = Path(file_path)
    if not p.exists():
        # try relative to project root
        alt = Path(__file__).resolve().parent.parent / str(file_path)
        if alt.exists():
            p = alt
        else:
            raise FileNotFoundError(f"host_image: file not found: {file_path}")
    # Try Cloudinary first
    url = _upload_cloudinary(p, "image")
    if url:
        return url
    return _upload_uguu(p)


def host_video(file_path: str | Path) -> str:
    """Host local video → permanent public URL (Cloudinary video if configured, else uguu)."""
    p = Path(file_path)
    if not p.exists():
        alt = Path(__file__).resolve().parent.parent / str(file_path)
        if alt.exists():
            p = alt
        else:
            raise FileNotFoundError(f"host_video: file not found: {file_path}")
    url = _upload_cloudinary(p, "video")
    if url:
        return url
    # uguu supports video too (up to ~100MB)
    return _upload_uguu(p)


def host_many(paths: Sequence[str | Path]) -> list[str]:
    """Host multiple images, return public URLs in same order."""
    return [host_image(p) for p in paths]
