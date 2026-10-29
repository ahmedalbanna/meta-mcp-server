"""Media tools service (Phase B)."""

from __future__ import annotations

from typing import Any

from src.core.services import Services
from src.media_hosting import host_image, host_many, host_video


class MediaToolsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def host_image_url(self, file_path: str) -> dict[str, Any]:
        if not file_path:
            return {"error": "file_path مطلوب"}
        url = host_image(file_path)
        return {
            "file_path": file_path,
            "public_url": url,
            "permanent": "cloudinary.com" in url,
            "note": "استخدم هذا الرابط في image_url / image_hash" if "cloudinary" in url else "رابط مؤقت (72h) — اضبط CLOUDINARY_URL لدائم",
        }

    def host_video_url(self, file_path: str) -> dict[str, Any]:
        if not file_path:
            return {"error": "file_path مطلوب"}
        url = host_video(file_path)
        return {"file_path": file_path, "public_url": url, "permanent": "cloudinary.com" in url}

    def host_many_images(self, file_paths: str) -> dict[str, Any]:
        paths = [p.strip() for p in file_paths.split(",") if p.strip()]
        if not paths:
            return {"error": "file_paths مطلوب (مسارات مفصولة بفواصل)"}
        urls = host_many(paths)
        return {"count": len(urls), "urls": urls, "permanent": all("cloudinary.com" in u for u in urls)}
