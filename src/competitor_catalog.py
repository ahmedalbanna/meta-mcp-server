"""Competitor -> draft catalog pipeline.

One call that answers "what are my competitors selling right now, and how do I
stock my own store with it?":

1. pulls every competitor's posts from the last N days (Instagram Business
   Discovery),
2. ranks each store's posts by engagement and keeps the top ones,
3. downloads the winning images into **one folder per store** plus a
   ``products.txt`` next to them describing every product,
4. builds a **catalog draft** (``catalog_draft.json`` + ``catalog_draft.md``)
   with name/price/description extracted from each caption,
5. optionally pushes those products into a Meta product catalog as
   ``visibility: staging`` — i.e. *draft*, invisible until published.

Legal/ethical note: competitor images are reference material. The draft keeps
their CDN URLs as placeholders; replace them with your own photography before
publishing anything.
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.competitor_content import (
    MEDIA_DOWNLOAD_DIR,
    download_image,
    fetch_business_media,
    oembed_image,
    parse_ts,
)
from src.config import ENABLE_WRITES, FB_ENABLE_OCR, INSTAGRAM_BUSINESS_ID
from src.helpers import api_call, handle_error, json_dumps, sanitize_filename, sanitize_path, write_guard
from src.ocr import ocr_price_for_image
from src.throttle import concurrency_limit

logger = logging.getLogger(__name__)

# Arabic-Indic digits -> Latin, so thousands prices parse the same way.
_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# "12 الف" / "12 ألف" -> thousands; "6500 ريال" -> absolute.
_THOUSANDS_RE = re.compile(r"(\d[\d.,]*)\s*(?:ألف|الف|ألاف)")
_RIYAL_RE = re.compile(r"(\d[\d.,]*)\s*(?:ريال|ر\.ي|ريال يمني|ريالاً)")

_REFERENCE_NOTE = "صور المنافسين = مرجع فقط؛ استبدليها بصور منتجاتكِ قبل النشر"


def _clean(text: str) -> str:
    return (text or "").translate(_DIGIT_MAP)


def _extract_price(caption: str) -> float | None:
    """Pull a price out of an Arabic caption (handles الف/ألف and Arabic digits)."""
    text = _clean(caption)
    m = _THOUSANDS_RE.search(text)
    if m:
        try:
            return round(float(m.group(1).replace(",", "")) * 1000, 2)
        except ValueError:
            pass
    m = _RIYAL_RE.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _product_name(caption: str, handle: str) -> str:
    """First meaningful caption line, trimmed — or a fallback name."""
    for line in (caption or "").split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or len(line) < 3:
            continue
        return line[:70]
    return f"منتج من {handle}"


def _write_store_report(folder: Path, handle: str, days: int, entries: list, downloaded: int) -> None:
    """Write products.txt next to the images (details per product)."""
    lines = [
        f"📦 تقرير منتجات المتجر: {handle}",
        f"🗓️ النافذة: آخر {days} يوم | 📥 الصور المنزّلة: {downloaded}",
        "=" * 60,
        "",
    ]
    for e in entries:
        lines += [
            f"#{e['rank']} {e['name']}",
            f"   📅 التاريخ: {e['date']}",
            f"   ❤️ تفاعل: {e['likes']} إعجاب + {e['comments']} تعليق ({e['engagement']})",
            f"   🖼️ النوع: {e['media_type']}",
        ]
        if e["price"] is not None:
            lines.append(f"   💰 السعر المستخرج: {e['price']:,.0f} ريال")
        lines += [
            f"   🔗 الرابط: {e['permalink']}",
            f"   🖼️ الصور: {', '.join(e['image_files']) or '(لم تُنزّل)'}",
            f"   📝 الكابشن: {e['caption'][:400] or '(بدون)'}",
            "",
        ]
    lines += ["=" * 60, _REFERENCE_NOTE]
    (folder / "products.txt").write_text("\n".join(lines), encoding="utf-8")


def _write_catalog_draft(out_root: Path, draft: list) -> tuple[Path, Path]:
    """Persist the catalog draft as JSON + readable Markdown."""
    json_path = out_root / "catalog_draft.json"
    md_path = out_root / "catalog_draft.md"
    json_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 🛒 مسودة كتالوج Butterfly — من منتجات المنافسين",
        "",
        f"**{len(draft)} منتج** مستخرج من {len({d['source_store'] for d in draft})} متاجر منافسة",
        "",
        "> ⚠️ صور المنافسين مرجعية فقط — استبدليها بصور منتجاتكِ قبل النشر.",
        "",
        "| # | المنتج | السعر | المتجر المصدر | تفاعل | الصور |",
        "|---|---|---|---|---|---|",
    ]
    for i, d in enumerate(draft, 1):
        price = f"{d['price']:,.0f} ريال" if d["price"] else "—"
        eng = d.get("source_engagement", 0)
        lines.append(f"| {i} | {d['name'][:45]} | {price} | {d['source_store']} | {eng} | {len(d['image_files'])} |")
    lines += ["", "---", ""]
    for i, d in enumerate(draft, 1):
        lines += [
            f"## {i}. {d['name']}",
            f"- **المتجر المصدر:** {d['source_store']} ({d['source_permalink']})",
            f"- **السعر المستخرج:** {d['price'] or '—'}",
            f"- **التفاعل:** {d['source_engagement']} (إعجاب + تعليق) بتاريخ {d['date']}",
            f"- **الصور المحلية:** {', '.join(d['image_files']) or '—'}",
            f"- **رابط الصورة (CDN):** {d['image_url'] or '—'}",
            f"- **الكابشن الأصلي:** {(d['description'] or '')[:300] or '—'}",
            "",
        ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def register(mcp, services=None):
    """Register the competitor -> draft-catalog pipeline tools."""

    def _collect(handle: str, days: int, top_n: int, out_root: Path) -> tuple[list, dict]:
        """Steps 1-3 for one store: rank, download, report. Returns (entries, summary)."""
        media = fetch_business_media(handle.lstrip("@"))
        if not media:
            return [], {"handle": handle, "error": "لا توجد منشورات (تحقق من الاسم/أنه حساب أعمال عام)"}

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        dated = [(dt, m) for dt, m in ((parse_ts(m.get("timestamp")), m) for m in media) if dt and dt >= cutoff]
        if not dated:
            stamps = [t for t in (parse_ts(m.get("timestamp")) for m in media) if t]
            oldest = min(stamps).strftime("%Y-%m-%d") if stamps else "—"
            return [], {
                "handle": handle,
                "error": f"لا منشورات ضمن آخر {days} يوم (أقدم متاح: {oldest})",
                "fetched": len(media),
            }

        ranked = sorted(
            dated,
            key=lambda x: (x[1].get("like_count") or 0) + (x[1].get("comments_count") or 0),
            reverse=True,
        )[:top_n]

        folder = sanitize_path(sanitize_filename(handle.lstrip("@")), out_root)
        folder.mkdir(parents=True, exist_ok=True)

        entries = []
        downloaded = 0
        for i, (dt, post) in enumerate(ranked, 1):
            shortcode = post["permalink"].rstrip("/").split("/")[-1]
            likes = post.get("like_count") or 0
            comments = post.get("comments_count") or 0
            caption = post.get("caption") or ""
            entry = {
                "rank": i,
                "handle": handle,
                "name": _product_name(caption, handle),
                "price": _extract_price(caption),
                "date": dt.strftime("%Y-%m-%d"),
                "likes": likes,
                "comments": comments,
                "engagement": likes + comments,
                "media_type": post.get("media_type"),
                "permalink": post.get("permalink"),
                "caption": caption,
                "image_url": None,
                "image_files": [],
                "local_folder": str(folder),
            }
            try:
                img = oembed_image(post["permalink"])
                if img:
                    entry["image_url"] = img
                    local = folder / f"{i:02d}_{likes}likes_{shortcode}.jpg"
                    if download_image(img, local):
                        entry["image_files"].append(local.name)
                        downloaded += 1
            except Exception as e:
                entry["image_error"] = str(e)[:120]

            # OCR price fallback/supplement (Phase 2.1)
            entry["price_source"] = "caption" if entry["price"] is not None else None
            if entry["price"] is None and FB_ENABLE_OCR and (entry.get("image_url") or entry["image_files"]):
                try:
                    src_img = str(folder / entry["image_files"][0]) if entry["image_files"] else entry.get("image_url")
                    ocr_res = ocr_price_for_image(src_img) if src_img else {"prices": []}
                    prices = ocr_res.get("prices") or []
                    if prices:
                        entry["price"] = prices[0]
                        entry["price_source"] = "ocr"
                        entry["ocr_prices"] = prices
                except Exception as e:
                    entry["ocr_error"] = str(e)[:120]
            entries.append(entry)

        _write_store_report(folder, handle, days, entries, downloaded)
        summary = {
            "handle": handle,
            "fetched": len(media),
            "in_window": len(dated),
            "downloaded_images": downloaded,
            "folder": str(folder),
            "report": str(folder / "products.txt"),
            "top_engagement": entries[0]["engagement"] if entries else 0,
        }
        return entries, summary

    @mcp.tool()
    @concurrency_limit()
    def build_competitor_catalog(
        handles: str,
        days: int = 30,
        top_n: int = 5,
        out_dir: str = "",
        push_to_meta: bool = False,
        catalog_id: str = "",
    ) -> str:
        """خط أنابيب كامل: اسحب أفضل منتجات كل منافس (آخر N يوم) وابنِ مسودة كتالوج.

        handles: أسماء حسابات المنافسين مفصولة بفواصل (مثل "elegant.po1,bood2005moo")
        days: نافذة الاستخراج بالأيام (افتراضي 30)
        top_n: أفضل كم منتج من كل متجر (1-10)
        out_dir: مجلد الخرج (افتراضي media/competitors)
        push_to_meta: إنشاء المنتجات في كتالوج ميتا كـ **مسودة** (visibility=staging)
        catalog_id: معرف الكتالوج (مطلوب فقط عند push_to_meta=true)

        يُنفّذ 5 خطوات: (1) سحب منشورات كل متجر خلال النافذة، (2) ترتيبها بالتفاعل،
        (3) تنزيل الصور في مجلد منفصل لكل متجر + ملف products.txt بجانبها،
        (4) بناء مسودة كتالوج catalog_draft.json/md، (5) اختيارياً: دفع المنتجات
        لكتالوج ميتا كمسودة غير منشورة. ⚠️ صور المنافسين مرجعية فقط.
        """
        try:
            if not handles or not handles.strip():
                return json_dumps({"error": "حدد متاجر المنافسين (handles)"})
            if days <= 0 or top_n <= 0:
                return json_dumps({"error": "days و top_n يجب أن تكون أكبر من صفر"})
            if top_n > 10:
                return json_dumps({"error": "الحد الأقصى 10 منتجات لكل متجر"})
            if not INSTAGRAM_BUSINESS_ID:
                return json_dumps({"error": "اضبط FB_IG_USER_ID في .env (حسابنا يجب أن يكون Instagram Business)"})
            if push_to_meta and not catalog_id:
                return json_dumps({"error": "push_to_meta=true يحتاج catalog_id (معرف كتالوج Butterfly)"})

            handle_list = [h.strip().lstrip("@") for h in handles.split(",") if h.strip()]
            if len(handle_list) > 10:
                return json_dumps({"error": "الحد الأقصى 10 متاجر في التشغيل الواحد"})

            out_root = (
                sanitize_path(out_dir, MEDIA_DOWNLOAD_DIR.parent)
                if out_dir
                else sanitize_path("competitors", MEDIA_DOWNLOAD_DIR.parent)
            )
            out_root.mkdir(parents=True, exist_ok=True)

            draft: list = []
            stores: list = []
            for handle in handle_list:
                entries, summary = _collect(handle, days, top_n, out_root)
                stores.append(summary)
                for e in entries:
                    draft.append(
                        {
                            "name": e["name"],
                            "price": e["price"],
                            "price_source": e.get("price_source"),
                            "currency": "YER",
                            "description": (e["caption"] or "")[:600],
                            "image_url": e["image_url"],
                            "image_files": e["image_files"],
                            "local_folder": e["local_folder"],
                            "source_store": e["handle"],
                            "source_permalink": e["permalink"],
                            "source_engagement": e["engagement"],
                            "date": e["date"],
                            "brand": "Butterfly",
                            "condition": "new",
                            "product_type": "jewelry",
                            "status": "draft",
                        }
                    )

            json_path, md_path = _write_catalog_draft(out_root, draft)

            pushed = []
            if push_to_meta and draft:
                if not ENABLE_WRITES:
                    pushed.append(
                        {
                            "error": "عمليات الكتابة معطلة (FB_ENABLE_WRITES=false). فعّلها في .env ثم أعد تشغيل الخادم.",
                            "guard": True,
                        }
                    )
                else:
                    for d in draft:
                        params = {
                            "name": d["name"],
                            "price": str(round(d["price"], 2)) if d["price"] else "0",
                            "currency": d["currency"],
                            "description": d["description"],
                            "availability": "in stock",
                            "brand": d["brand"],
                            "condition": d["condition"],
                            "product_type": d["product_type"],
                            "visibility": "staging",  # draft — not publicly visible
                        }
                        if d["image_url"]:
                            params["image_url"] = d["image_url"]
                        try:
                            res = api_call("POST", f"{catalog_id}/products", params)
                            pushed.append({"name": d["name"], "id": res.get("id"), "visibility": "staging"})
                        except Exception as e:
                            pushed.append({"name": d["name"], "error": str(e)[:150]})

            return json_dumps(
                {
                    "window_days": days,
                    "stores_requested": len(handle_list),
                    "stores_with_data": sum(1 for s in stores if "error" not in s),
                    "stores": stores,
                    "products_in_draft": len(draft),
                    "draft_files": {"json": str(json_path), "markdown": str(md_path)},
                    "pushed_to_meta": pushed or None,
                    "note": _REFERENCE_NOTE,
                    "next_step": (
                        "راجع catalog_draft.md ثم publish_catalog_draft(catalog_id) بعد استبدال الصور"
                        if pushed
                        else "راجع catalog_draft.md — للنشر لاحقاً مرّري push_to_meta=true مع catalog_id"
                    ),
                }
            )
        except ValueError as e:
            return json_dumps({"error": f"مسار غير صالح: {e}"})
        except Exception as e:
            return json_dumps(handle_error(e, "build_competitor_catalog"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def publish_catalog_draft(catalog_id: str, product_ids: str = "") -> str:
        """نشر مسودات الكتالوج: تحويل visibility من staging إلى published."""
        try:
            from src.core.services import Services
            from src.services.competitor_catalog_service import CompetitorCatalogService
            svc = CompetitorCatalogService(services) if services is not None else CompetitorCatalogService(Services.default())
            return json_dumps(svc.publish_drafts(catalog_id, product_ids))
        except Exception as e:
            return json_dumps(handle_error(e, "publish_catalog_draft"))
    @mcp.tool()
    @concurrency_limit()
    def list_catalog_drafts(catalog_id: str, limit: int = 50) -> str:
        """عرض منتجات المسودة (visibility=staging) في كتالوج — قبل النشر."""
        try:
            from src.core.services import Services
            from src.services.competitor_catalog_service import CompetitorCatalogService
            svc = CompetitorCatalogService(services) if services is not None else CompetitorCatalogService(Services.default())
            return json_dumps(svc.list_drafts(catalog_id, limit))
        except Exception as e:
            return json_dumps(handle_error(e, "list_catalog_drafts"))
    @mcp.resource("competitor-catalog://pipeline")
    async def competitor_catalog_resource() -> str:
        """خط أنابيب كتالوج المنافسين."""
        try:
            return json_dumps(
                {
                    "module": "competitor_catalog",
                    "resource": "competitor-catalog://pipeline",
                    "steps": [
                        "build_competitor_catalog(handles, days, top_n) — السحب + الترتيب + التنزيل + المسودة",
                        "list_catalog_drafts(catalog_id) — مراجعة المسودات",
                        "publish_catalog_draft(catalog_id) — النشر بعد استبدال الصور",
                    ],
                    "note": _REFERENCE_NOTE,
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "competitor-catalog://pipeline"))

    @mcp.prompt()
    def competitor_catalog_prompt(handles: str = "") -> str:
        """بناء كتالوج من المنافسين."""
        return (
            f"ابنِ مسودة كتالوج من أفضل منتجات المتاجر ({handles or 'حدد المتاجر'}) خلال آخر 30 يوماً — "
            "رتّبها بالتفاعل، استخرج الأسماء والأسعار، وجهّزها كمسودة قبل النشر (وحدة competitor_catalog)"
        )

    @mcp.resource("competitor-catalog://checklist")
    async def competitor_catalog_extra_resource() -> str:
        """قائمة تحقق قبل النشر."""
        try:
            return json_dumps(
                {
                    "module": "competitor_catalog",
                    "resource": "competitor-catalog://checklist",
                    "before_publishing": [
                        "استبدال صور المنافسين بصور منتجاتكِ",
                        "مراجعة السعر المستخرج من الكابشن",
                        "إضافة sku/retailer_id خاص بكِ",
                        "التحقق من التوفر الفعلي للمخزون",
                    ],
                    "note": _REFERENCE_NOTE,
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "competitor-catalog://checklist"))

    @mcp.prompt()
    def catalog_review_prompt(product: str = "") -> str:
        """مراجعة منتج قبل النشر."""
        return (
            f"راجع المنتج ({product or 'من المسودة'}) قبل نشره في كتالوج Butterfly — "
            "الاسم، السعر، الوصف، الصور (يجب أن تكون صوركِ)، والتوفر (وحدة competitor_catalog)"
        )
