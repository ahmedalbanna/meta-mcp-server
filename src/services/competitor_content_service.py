"""Competitor content service (Phase B)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from src.competitor_content import fetch_business_media, parse_ts
from src.config import INSTAGRAM_BUSINESS_ID
from src.core.services import Services


class CompetitorContentService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def analyze_cadence(self, handle: str, days: int = 30, pages: int = 3) -> dict[str, Any]:
        if not handle:
            raise ValueError("handle مطلوب")
        if not INSTAGRAM_BUSINESS_ID:
            raise ValueError("اضبط FB_IG_USER_ID في .env")
        media = fetch_business_media(handle.lstrip("@"), pages=max(1, min(pages, 6)))
        if not media:
            return {"error": f"لا توجد منشورات للحساب {handle}"}

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        by_day: dict = defaultdict(list)
        by_type: dict = defaultdict(list)
        in_window = 0
        for m in media:
            dt = parse_ts(m.get("timestamp"))
            if not dt or dt < cutoff:
                continue
            in_window += 1
            eng = (m.get("like_count") or 0) + (m.get("comments_count") or 0)
            by_day[dt.strftime("%Y-%m-%d")].append(eng)
            by_type[m.get("media_type") or "UNKNOWN"].append(eng)

        if not in_window:
            return {"error": f"لا منشورات ضمن آخر {days} يوم", "handle": handle, "fetched": len(media)}

        day_rows = sorted(
            ({"date": day, "posts": len(vals), "avg_engagement": round(sum(vals) / len(vals), 1),
              "max_engagement": max(vals)} for day, vals in by_day.items()),
            key=lambda r: r["avg_engagement"], reverse=True,
        )
        type_rows = sorted(
            ({"media_type": t, "posts": len(vals), "avg_engagement": round(sum(vals) / len(vals), 1),
              "max_engagement": max(vals)} for t, vals in by_type.items()),
            key=lambda r: r["avg_engagement"], reverse=True,
        )
        span_days = len(by_day) or 1
        return {
            "handle": handle,
            "window_days": days,
            "fetched_posts": len(media),
            "posts_in_window": in_window,
            "active_days": span_days,
            "avg_posts_per_active_day": round(in_window / span_days, 1),
            "best_days": day_rows[:5],
            "worst_days": day_rows[-3:],
            "by_media_type": type_rows,
            "insight": (
                f"أفضل نوع: {type_rows[0]['media_type']} "
                f"(متوسط {type_rows[0]['avg_engagement']}) — "
                f"الأضعف: {type_rows[-1]['media_type']} "
                f"(متوسط {type_rows[-1]['avg_engagement']})"
                if len(type_rows) > 1
                else "نوع محتوى واحد فقط في النافذة"
            ),
        }

    def resolve_post_url(self, url: str) -> dict[str, Any]:
        import html as html_lib
        import re as _re

        import requests  # type: ignore[import-untyped]

        from src.competitor_content import _HEADERS
        if not url or "instagram.com" not in url:
            raise ValueError("أدخل رابط إنستغرام صالحاً (يحتوي instagram.com)")
        out: dict[str, Any] = {"url": url}
        try:
            er = requests.get("https://www.instagram.com/api/v1/oembed/", params={"url": url},
                              headers=_HEADERS, timeout=40)
            er.raise_for_status()
            embed = er.json()
            if embed.get("author_name"):
                out["username"] = embed["author_name"]
                out["author_url"] = embed.get("author_url")
                out["author_id"] = embed.get("author_id")
                out["media_id"] = embed.get("media_id")
                out["caption"] = (embed.get("title") or "").strip()[:500]
                out["image_url"] = embed.get("thumbnail_url")
                out["image_size"] = [embed.get("thumbnail_width"), embed.get("thumbnail_height")]
                out["source"] = "oembed"
        except Exception:
            pass
        try:
            r = requests.get(url, headers=_HEADERS, timeout=40)
            r.raise_for_status()
            page = r.text
            m = _re.search(r'<meta property="og:url" content="https://www\.instagram\.com/([^/]+)/(p|reel)/([^/]+)/', page)
            if m:
                out["username"] = out.get("username") or m.group(1)
                out["shortcode"] = m.group(3)
            m = _re.search(r"instagram://media\?id=(\d+)", page)
            if m:
                out["media_id"] = out.get("media_id") or m.group(1)
            m = _re.search(r'instapp:owner_user_id" content="(\d+)"', page)
            if m:
                out["owner_user_id"] = m.group(1)
            m = _re.search(
                r'name="description" content="(\d[\d,]*) likes?, (\d[\d,]*) comments? - ([^ ]+) on ([^:]+): &quot;(.*?)&quot;',
                page, _re.S,
            )
            if m:
                out["likes"] = int(m.group(1).replace(",", ""))
                out["comments"] = int(m.group(2).replace(",", ""))
                out["date"] = m.group(4).strip()
                if "source" in out:
                    out["source"] = "html+oembed"
                else:
                    out["source"] = "html"
            m = _re.search(r'<meta property="og:image" content="([^"]+)"', page)
            if m:
                out["image_url"] = out.get("image_url") or html_lib.unescape(m.group(1))
        except Exception:
            pass
        if not out.get("username"):
            raise ValueError("تعذّر استخراج بيانات المنشور — قد يكون محذوفاً أو خاصاً")
        out["next_step"] = "discover_instagram_business(username) لتحليل الحساب كاملاً"
        return out

    def download_top_posts(self, handle: str, days: int = 30, top_n: int = 10, out_dir: str = "") -> dict[str, Any]:
        import json as _json

        from src.competitor_content import (
            MEDIA_DOWNLOAD_DIR,
            download_image,
            fetch_business_media,
            oembed_image,
            parse_ts,
        )
        from src.config import INSTAGRAM_BUSINESS_ID
        from src.helpers import sanitize_filename, sanitize_path
        if not handle:
            raise ValueError("handle مطلوب")
        if days <= 0 or top_n <= 0:
            raise ValueError("days و top_n يجب أن تكون أكبر من صفر")
        if top_n > 25:
            raise ValueError("الحد الأقصى 25 منشور للتنزيل الواحد")
        if not INSTAGRAM_BUSINESS_ID:
            raise ValueError("اضبط FB_IG_USER_ID في .env (حسابنا يجب أن يكون Instagram Business)")
        media = fetch_business_media(handle.lstrip("@"), pages=3)
        if not media:
            raise ValueError(f"لا توجد منشورات للحساب {handle}")
        cutoff = __import__("datetime").datetime.now(__import__("datetime").timezone.utc) - __import__("datetime").timedelta(days=days)
        dated = []
        for m in media:
            dt = parse_ts(m.get("timestamp"))
            if dt and dt >= cutoff:
                dated.append((dt, m))
        if not dated:
            raise ValueError(f"لا منشورات ضمن آخر {days} يوم")
        ranked = sorted(dated, key=lambda x: (x[1].get("like_count") or 0) + (x[1].get("comments_count") or 0), reverse=True)[:top_n]
        folder = f"competitors/{sanitize_filename(handle.lstrip('@'))}"
        target = (sanitize_path(out_dir, MEDIA_DOWNLOAD_DIR.parent) if out_dir else sanitize_path(folder, MEDIA_DOWNLOAD_DIR.parent))
        target.mkdir(parents=True, exist_ok=True)
        manifest = []
        downloaded = 0
        for i, (dt, post) in enumerate(ranked, 1):
            shortcode = post["permalink"].rstrip("/").split("/")[-1]
            likes = post.get("like_count") or 0
            comments = post.get("comments_count") or 0
            entry = {"rank": i, "date": dt.strftime("%Y-%m-%d"), "permalink": post.get("permalink"),
                    "likes": likes, "comments": comments, "media_type": post.get("media_type"),
                    "caption": (post.get("caption") or "")[:300], "file": None}
            try:
                img = oembed_image(post["permalink"])
                if img:
                    local = target / f"{i:02d}_{likes}likes_{shortcode}.jpg"
                    size = download_image(img, local)
                    if size:
                        entry["file"] = local.name
                        downloaded += 1
            except Exception as e:
                entry["error"] = str(e)[:120]
            manifest.append(entry)
        (target / "manifest.json").write_text(_json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "handle": handle,
            "window_days": days,
            "fetched_posts": len(media),
            "posts_in_window": len(dated),
            "requested": top_n,
            "downloaded": downloaded,
            "out_dir": str(target),
            "manifest": str(target / "manifest.json"),
            "note": "reference only",
            "top_posts": [{"rank": m["rank"], "date": m["date"], "likes": m["likes"],
                          "comments": m["comments"], "file": m["file"], "caption": m["caption"]} for m in manifest],
        }
