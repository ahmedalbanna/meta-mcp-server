"""Media hosting tools — expose src/media_hosting.py as MCP tools.

Local images/videos (in media/) need a **public URL** before they can be used in
FB/IG posts, ad creatives, or catalog products. These tools upload them to
Cloudinary (permanent) with an uguu.se fallback (72h) and return the URL.
"""

import logging
from pathlib import Path

from src.helpers import json_dumps, sanitize_path
from src.throttle import concurrency_limit

logger = logging.getLogger(__name__)

MEDIA_ROOT = Path(__file__).resolve().parent.parent / "media"


def register(mcp, services=None):
    """Register media-hosting tools."""

    @mcp.tool()
    @concurrency_limit()
    def host_image_url(file_path: str) -> str:
        """رفع صورة محلية إلى استضافة عامة وإرجاع رابط URL.

        file_path: مسار الصورة (مثل "media/image1.jpeg" أو "/home/frappe/meta-mcp-server/media/x.jpg")
        يفضّل Cloudinary (دائم) إن كان مضبوطاً، وإلا uguu.se (72 ساعة).
        استخدمه قبل publish_instagram_photo / publish_page_photo / create_product.
        """
        try:
            from src.core.services import Services
            from src.services.media_tools_service import MediaToolsService
            svc = MediaToolsService(services) if services is not None else MediaToolsService(Services.default())
            return json_dumps(svc.host_image_url(file_path))
        except Exception as e:
            return json_dumps({"error": f"host_image: {e}"})

    @mcp.tool()
    @concurrency_limit()
    def host_video_url(file_path: str) -> str:
        """رفع فيديو محلي إلى استضافة عامة وإرجاع رابط URL."""
        try:
            from src.core.services import Services
            from src.services.media_tools_service import MediaToolsService
            svc = MediaToolsService(services) if services is not None else MediaToolsService(Services.default())
            return json_dumps(svc.host_video_url(file_path))
        except Exception as e:
            return json_dumps({"error": f"host_video: {e}"})

    @mcp.tool()
    @concurrency_limit()
    def host_many_images(file_paths: str) -> str:
        """رفع عدة صور دفعة واحدة (مسارات مفصولة بفواصل) وإرجاع روابطها."""
        try:
            from src.core.services import Services
            from src.services.media_tools_service import MediaToolsService
            svc = MediaToolsService(services) if services is not None else MediaToolsService(Services.default())
            return json_dumps(svc.host_many_images(file_paths))
        except Exception as e:
            return json_dumps({"error": f"host_many: {e}"})

    @mcp.tool()
    @concurrency_limit()
    def list_local_media(subdir: str = "", extensions: str = ".jpg,.jpeg,.png,.webp,.mp4,.mov") -> str:
        """قائمة ملفات الوسائط المحلية في media/ (أو مجلد فرعي)."""
        try:
            allowed = MEDIA_ROOT
            if subdir:
                try:
                    target = sanitize_path(subdir, allowed)
                except ValueError as e:
                    return json_dumps({"error": f"مسار غير صالح: {e}"})
            else:
                target = allowed
            if not target.exists():
                return json_dumps({"error": f"المجلد غير موجود: {target}", "root": str(MEDIA_ROOT)})
            exts = {e.strip().lower() for e in extensions.split(",") if e.strip()}
            files = sorted(
                [p for p in target.rglob("*") if p.is_file() and p.suffix.lower() in exts],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            rows = [
                {
                    "path": str(p.relative_to(MEDIA_ROOT.parent)),
                    "name": p.name,
                    "size_kb": round(p.stat().st_size / 1024, 1),
                    "modified": p.stat().st_mtime,
                }
                for p in files[:200]
            ]
            return json_dumps(
                {
                    "root": str(MEDIA_ROOT),
                    "scanned": str(target),
                    "count": len(rows),
                    "files": rows,
                    "hint": "استخدم host_image_url(path) لرفع أي ملف إلى URL عام",
                }
            )
        except Exception as e:
            return json_dumps({"error": f"list_local_media: {e}"})

    @mcp.resource("media://overview")
    async def media_resource() -> str:
        """نظرة عامة على الوسائط."""
        try:
            return json_dumps(
                {
                    "module": "media_tools",
                    "resource": "media://overview",
                    "tools": ["host_image_url", "host_video_url", "host_many_images", "list_local_media"],
                    "root": str(MEDIA_ROOT),
                }
            )
        except Exception as e:
            return json_dumps({"error": f"media://overview: {e}"})

    @mcp.prompt()
    def media_prompt(topic: str = "media") -> str:
        """رفع وسائط."""
        return (
            f"ساعد في رفع وسائط لـ {topic} — host_image_url(path) لإنشاء URL عام، "
            "ثم publish_instagram_photo(image_url=...) أو create_product(image_url=...)"
        )

    @mcp.resource("media://templates")
    async def media_extra_resource() -> str:
        """قوالب الوسائط."""
        try:
            return json_dumps(
                {
                    "module": "media_tools",
                    "resource": "media://templates",
                    "flow": ["list_local_media()", "host_image_url(path)", "publish_instagram_photo(image_url=...)"],
                }
            )
        except Exception as e:
            return json_dumps({"error": f"media://templates: {e}"})

    @mcp.prompt()
    def media_upload_prompt(topic: str = "media") -> str:
        """رفع وسائط."""
        return f"ساعد في رفع وسائط لـ {topic} — تحقق من CLOUDINARY_URL لاستضافة دائمة (وحدة media_tools)"
