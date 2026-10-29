"""Content tools service (Phase B)."""

from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import src.content_tools as _ct
from src.core.services import Services
from src.hashtags import all_hashtags, marketing_hashtags

logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 86400
_WEEKDAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]


class ContentToolsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config

    def generate_post_caption(
        self,
        product: str,
        price: float = 0.0,
        old_price: float = 0.0,
        warranty: str = "",
        style: str = "sales",
        language: str = "ar",
        include_hashtags: bool = True,
        product_type: str = "jewelry",
    ) -> dict[str, Any]:
        if not product:
            return {"error": "product مطلوب"}
        style = style.strip().lower()
        lang = language.strip().lower()
        if lang not in ("ar", "en"):
            lang = "ar"
        if style not in ("sales", "engaging", "descriptive", "minimal"):
            style = "sales"

        # --- LLM path ---
        try:
            llm_prompt = (
                f"Generate an Instagram post caption in {lang} with style '{style}' for product '{product}'. "
                f"Price: {price} YER"
                + (f", old price {old_price} YER (discount)" if old_price else "")
                + ". "
                + (f"Warranty: {warranty}. " if warranty else "")
                + "Include a CTA, scarcity/urgency, and 8-10 relevant hashtags for the Yemeni jewelry market. "
                "Return JSON with keys: caption (string), hashtags (array of strings), cta (string). "
                "Keep caption <= 400 chars, hashtags in Arabic + English mix."
            )
            llm_result = _ct.call_llm(  # type: ignore[attr-defined]
                llm_prompt,
                system="You are a senior social-media copywriter for a Yemeni jewelry brand. Return valid JSON only.",
            )
            if llm_result:
                parsed = json.loads(llm_result)
                if isinstance(parsed, dict) and parsed.get("caption"):
                    tags = parsed.get("hashtags") or []
                    tags = [str(t).strip() for t in tags if str(t).strip()][:12]
                    return {
                        "product": product,
                        "style": style,
                        "language": lang,
                        "caption": parsed["caption"][:600],
                        "cta": parsed.get("cta", "للطلب رسائل الصفحة"),
                        "hashtags": tags,
                        "source": "llm",
                        "template_hint": "📋 انسخ في إنستغرام، عدّل الصور، انشر",
                    }
        except Exception:
            pass

        # --- Template path ---
        price_line = ""
        if price and old_price and old_price > price:
            price_line = f"💰 السعر السابق: {old_price:,.0f} ريال\n🎀 سعر العرض: {price:,.0f} ريال فقط"
        elif price:
            price_line = f"💰 السعر: {price:,.0f} ريال"
        warranty_line = f"🛡️ {warranty}" if warranty else "🛡️ ضمان سنة ضد تغيّر اللون"
        scarcity = "⚡ الكمية محدودة" if style == "sales" else ""

        ar_templates = {
            "sales": (
                f"✨ عرض خاص على {product} 🦋\n\n"
                f"{price_line}\n"
                f"{warranty_line}\n"
                f"{scarcity}\n\n"
                f"📍 صنعاء | 🚚 توصيل لجميع المحافظات\n"
                f"📩 للطلب: رسائل الصفحة أو واتساب"
            ),
            "engaging": (
                f"💎 {product} — فخامة تليق بكِ ✨\nهل أعجبك هذا التصميم؟ اترك تعليقك 👇\n{price_line}\n📍 صنعاء"
            ),
            "descriptive": (
                f"✨ {product}\n\n"
                f"تفاصيل راقية، جودة عالية، أناقة لا تُقاوم.\n"
                f"{price_line}\n"
                f"{warranty_line}\n"
                f"📍 صنعاء | 🚚 توصيل"
            ),
            "minimal": f"✨ {product} — {price_line} #Butterfly",
        }
        en_templates = {
            "sales": f"✨ Special offer on {product}! 🦋\n\n{price_line}\n{warranty_line}\n⚡ Limited quantity\n📩 DM to order",
            "engaging": f"💎 {product} — elegance that fits you ✨\n\nWhat do you think? Comment below 👇",
            "descriptive": f"✨ {product}\n\nRefined details, high quality, irresistible elegance.\n{price_line}\n{warranty_line}",
            "minimal": f"✨ {product} — {price_line} #Butterfly",
        }
        templates = ar_templates if lang == "ar" else en_templates
        caption = templates.get(style, templates["sales"])

        hashtags: list[str] = []
        if include_hashtags:
            base = ["#Butterfly", "#اكسسوارات_نسائية", "#مجوهرات", "#صنعاء", "#أناقة_أنثوية"]
            if "كارتير" in product or "cartier" in product.lower():
                base += ["#طقم_كارتير", "#استيل"]
            if "سواروفسكي" in product.lower() or "swarovski" in product.lower():
                base += ["#سواروفسكي", "#زركون"]
            if "خناق" in product or "jhumka" in product.lower():
                base += ["#خناق_هندي", "#مجوهرات_صنعاء"]
            if "ديور" in product or "dior" in product.lower():
                base += ["#طقم_ديور", "#أطقم_نسائية"]
            if "زركون" in product:
                base += ["#زركون", "#مجوهرات_صنعاء"]
            if "استيل" in product or "steel" in product.lower():
                base += ["#استيل_مقاوم_للصدأ", "#بديل_الذهب"]
            hashtags = list(dict.fromkeys(base))[:12]

        return {
            "product": product,
            "style": style,
            "language": lang,
            "caption": caption,
            "hashtags": hashtags,
            "full_text": caption + "\n\n" + " ".join(hashtags),
            "source": "template",
        }

    def best_posting_time(self, days: int = 30, metric: str = "engagement") -> Any:
        if days <= 0:
            return {"error": "days يجب أن تكون > 0"}
        posts, err = _ct._fetch_our_posts(limit=100)
        if not posts:
            return {"error": err or "لا توجد منشورات", "metric": metric}
        rows: list[dict[str, Any]] = []
        for p in posts:
            cid = str(p.get("id") or "")
            dt = _ct._parse_ts(p.get("created_time"))
            if not dt or not cid:
                continue
            rows.append({"dt": dt, "engagement": _ct._post_engagement(cid)})
        if not rows:
            return {"error": "لا توجد منشورات", "metric": metric}
        buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
        for r in rows:
            key = (r["dt"].weekday(), r["dt"].hour)
            buckets[key].append(r["engagement"])
        slots: list[dict[str, Any]] = []
        for (wd, hr), vals in buckets.items():
            slots.append(
                {
                    "weekday": _WEEKDAYS[wd],
                    "weekday_num": wd,
                    "hour": hr,
                    "hour_label": f"{hr:02d}:00",
                    "posts": len(vals),
                    "avg_engagement": round(sum(vals) / len(vals), 1),
                    "total_engagement": sum(vals),
                }
            )
        slots.sort(key=lambda s: (s["avg_engagement"], s["posts"]), reverse=True)
        best = slots[:5]
        worst = sorted(slots, key=lambda s: s["avg_engagement"])[:3]
        return {
            "analyzed_posts": len(rows),
            "best_slots": best,
            "worst_slots": worst,
            "recommendation": (
                f"انشر على {best[0]['weekday']} في {best[0]['hour_label']} (متوسط تفاعل {best[0]['avg_engagement']})"
                if best
                else "لا توجد بيانات كافية"
            ),
            "note": "يُوصى بـ 3-5 منشورات/أسبوع في أفضل Slots (لا 6 في يوم واحد)",
        }

    def hashtag_analyzer(self, days: int = 60) -> dict[str, Any]:
        if days <= 0:
            return {"error": "days يجب أن تكون > 0"}
        posts, err = _ct._fetch_our_posts(limit=100, with_message=True)
        if not posts:
            return {"error": err or "لا توجد منشورات", "days": days}
        tag_data: dict = defaultdict(lambda: {"count": 0, "engagements": []})
        skipped_contact = 0
        for p in posts:
            cid = str(p.get("id") or "")
            message = p.get("message") or ""
            tags = marketing_hashtags(message)
            skipped_contact += len(all_hashtags(message)) - len(tags)
            if not tags or not cid:
                continue
            eng = _ct._post_engagement(cid)
            for tag in set(tags):
                tag_data[tag]["count"] += 1
                tag_data[tag]["engagements"].append(eng)

        if not tag_data:
            message = "لا توجد هاشتاغات تسويقية في المنشورات"
            if skipped_contact:
                message += f" (استُبعد {skipped_contact} وسم معلومات تواصل مثل أرقام الهواتف)"
            return {"message": message, "days": days, "skipped_contact_hashtags": skipped_contact}

        rows = []
        for tag, d in tag_data.items():
            vals = d["engagements"]
            rows.append(
                {
                    "hashtag": tag,
                    "uses": d["count"],
                    "avg_engagement": round(sum(vals) / len(vals), 1),
                    "total_engagement": sum(vals),
                    "best": max(vals) if vals else 0,
                }
            )
        rows.sort(key=lambda r: (r["avg_engagement"], r["uses"]), reverse=True)
        return {
            "analyzed_posts": len(posts),
            "unique_hashtags": len(rows),
            "skipped_contact_hashtags": skipped_contact,
            "top_hashtags": rows[:20],
            "weak_hashtags": [r for r in rows if r["avg_engagement"] < 2][:10],
            "recommendation": (
                f"ركّز على {rows[0]['hashtag']} (متوسط {rows[0]['avg_engagement']}) "
                f"وتجنب {rows[-1]['hashtag']} (متوسط {rows[-1]['avg_engagement']})"
                if rows
                else "لا بيانات"
            ),
        }

    def content_calendar(
        self, week_start: str = "", posts_per_week: int = 5, include_stories: bool = True
    ) -> dict[str, Any]:
        posts_per_week = max(1, min(posts_per_week, 7))
        if week_start:
            try:
                start = datetime.strptime(week_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                return {"error": "week_start يجب أن تكون YYYY-MM-DD"}
        else:
            start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        best_slots = [(3, 20), (1, 20), (5, 21), (0, 19), (2, 20), (4, 20), (6, 18)]
        day_names = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]

        post_offsets = [off for off, _ in best_slots[:posts_per_week]]
        for off in range(7):
            if len(post_offsets) >= posts_per_week:
                break
            if off not in post_offsets:
                post_offsets.append(off)
        hour_by_offset = dict(best_slots)

        mix = ["🎬 فيديو", "📸 كاروسيل", "🎬 فيديو", "📸 كاروسيل", "📱 ستوري", "📸 كاروسيل", "🎬 فيديو"]

        plan = []
        for i in range(7):
            day = start + timedelta(days=i)
            wd = day.weekday()
            slot = {
                "date": day.strftime("%Y-%m-%d"),
                "weekday": day_names[wd],
                "is_post_day": i in post_offsets,
            }
            if i in post_offsets:
                post_type = mix[post_offsets.index(i)]
                slot.update(
                    {
                        "post_type": post_type,
                        "time": f"{hour_by_offset.get(i, 20):02d}:00",
                        "idea": _ct._content_idea(i, post_type),
                        "caption_hint": "استخدم generate_post_caption(product=..., style='sales')",
                        "hashtag_hint": "hashtag_analyzer() → استخدم أفضل 8 هاشتاغات",
                    }
                )
            else:
                slot.update({"post_type": "—", "idea": "يوم راحة — ستوريات فقط (behind the scenes)"})
            if include_stories:
                slot["story"] = _ct._story_idea(i)
            plan.append(slot)

        return {
            "week_start": start.strftime("%Y-%m-%d"),
            "posts_planned": posts_per_week,
            "plan": plan,
            "rules": [
                "لا صور مفردة (20× أقل تفاعل)",
                "السعر يُكتب على الصورة",
                "ضمان سنة في كل منشور",
                "3-5 منشورات/أسبوع (لا 6 في يوم)",
            ],
            "next_step": "generate_post_caption(product=...) for each planned post",
        }

    def auto_reply_comments(self, keyword: str, reply: str, page_id: str = "", enabled: bool = True) -> dict[str, Any]:
        if not keyword or not reply:
            return {"error": "keyword و reply مطلوبان"}
        from src import webhook_automations

        rules = webhook_automations._load_rules()
        rule_id = uuid.uuid4().hex[:12]
        rule = {
            "id": rule_id,
            "name": f"auto-reply: {keyword}",
            "trigger": "comment_keyword",
            "keyword": keyword,
            "action_type": "reply_comment",
            "action_params": {"message": reply},
            "enabled": enabled,
        }
        rules.append(rule)
        webhook_automations._save_rules(rules)
        return {
            "configured": True,
            "rule_id": rule_id,
            "rule": rule,
            "total_rules": len(rules),
            "note": "يتطلب FB_AUTO_RUN_WEBHOOK_AUTOMATIONS=true في .env و webhook_server.py يعمل",
            "manage": "list_webhook_automations() للعرض | delete_webhook_automation(rule_id) للحذف",
        }
