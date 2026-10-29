"""Content creation & optimization tools — captions, timing, calendar, hashtags.

These close the loop between *research* (competitors) and *publishing* (posts):
generate captions, find the best posting time, plan a content calendar, and
analyze which hashtags actually perform for our own account.
"""

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from src.config import PAGE_ID
from src.hashtags import all_hashtags, marketing_hashtags
from src.helpers import handle_error, json_dumps, page_api_call
from src.llm import call_llm
from src.throttle import concurrency_limit

logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 86400


def _parse_ts(value) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _fetch_our_posts(limit: int = 100, with_message: bool = False) -> tuple[list, str | None]:
    """Recent posts of OUR page via the page-scoped token.

    The user token cannot read /published_posts (needs Page Public Content
    Access), so this always routes through page_api_call — same pattern as
    competitors._fetch_published_posts. Returns (posts, error_or_none).
    """
    fields = "id,created_time" + (",message" if with_message else "")
    try:
        data = page_api_call("GET", f"{PAGE_ID}/published_posts", {"fields": fields, "limit": limit})
        return (data.get("data") or []), None
    except Exception as e:
        return [], str(e)[:200]


def _post_engagement(post_id: str) -> int:
    """Reactions + comments for one of our posts (0 when unavailable).

    Uses the page-scoped token and the limit(0) field form, which is what
    Graph API v26 accepts for summary counts.
    """
    try:
        data = page_api_call(
            "GET", post_id, {"fields": "reactions.limit(0).summary(true),comments.limit(0).summary(true)"}
        )
        if not isinstance(data, dict):
            return 0
        reacts = (((data.get("reactions") or {}).get("summary") or {}).get("total_count")) or 0
        comms = (((data.get("comments") or {}).get("summary") or {}).get("total_count")) or 0
        return reacts + comms
    except Exception:
        return 0


def register(mcp, services=None):
    """Register content-creation & optimization tools."""

    # ------------------------------------------------------------------
    # توليد كابشن
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def generate_post_caption(
        product: str,
        price: float = 0.0,
        old_price: float = 0.0,
        warranty: str = "",
        style: str = "sales",
        language: str = "ar",
        include_hashtags: bool = True,
        product_type: str = "jewelry",
    ) -> str:
        """توليد كابشن إنستغرام/فيسبوك جاهز لمنشور (عربي/إنجليزي).

        product: اسم المنتج (مثل "طقم كارتير المسمار")
        price: السعر (0 = بدون سعر)
        old_price: السعر القديم (للخصم — 0 = بدون خصم)
        warranty: نص الضمان (مثل "سنة ضد تغيّر اللون")
        style: sales | engaging | descriptive | minimal
        language: ar | en
        include_hashtags: إضافة 8-10 هاشتاغات مناسبة
        product_type: jewelry | accessories | perfume | bag

        يجرّب LLM إن وُجد OPENAI_API_KEY/ANTHROPIC_API_KEY، وإلا قالب ذكي.
        """
        try:
            if not product:
                return json_dumps({"error": "product مطلوب"})
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
                llm_result = call_llm(
                    llm_prompt,
                    system="You are a senior social-media copywriter for a Yemeni jewelry brand. Return valid JSON only.",
                )
                if llm_result:
                    import json as _j

                    parsed = _j.loads(llm_result)
                    if isinstance(parsed, dict) and parsed.get("caption"):
                        tags = parsed.get("hashtags") or []
                        tags = [str(t).strip() for t in tags if str(t).strip()][:12]
                        return json_dumps(
                            {
                                "product": product,
                                "style": style,
                                "language": lang,
                                "caption": parsed["caption"][:600],
                                "cta": parsed.get("cta", "للطلب رسائل الصفحة"),
                                "hashtags": tags,
                                "source": "llm",
                                "template_hint": "📋 انسخ في إنستغرام، عدّل الصور، انشر",
                            }
                        )
            except Exception:
                pass

            # --- Template path (always works) ---
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
                    f"💎 {product} — فخامة تليق بكِ ✨\n\nهل أعجبك هذا التصميم؟ اترك تعليقك 👇\n{price_line}\n📍 صنعاء"
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

            # hashtags
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

            return json_dumps(
                {
                    "product": product,
                    "style": style,
                    "language": lang,
                    "caption": caption,
                    "hashtags": hashtags,
                    "full_text": caption + "\n\n" + " ".join(hashtags),
                    "source": "template",
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "generate_post_caption"))

    # ------------------------------------------------------------------
    # أفضل وقت للنشر
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def best_posting_time(days: int = 30, metric: str = "engagement") -> str:
        """تحليل متى ننشر للحصول على أعلى تفاعل (من منشورات صفحتنا).

        days: نافذة التحليل (افتراضي 30)
        metric: engagement (إعجاب+تعليق) | likes | comments
        يرجّع: أفضل 5 slots (يوم + ساعة) + أسوأ 3 + توصية.
        """
        try:
            from src.core.services import Services
            from src.services.content_tools_service import ContentToolsService
            svc = ContentToolsService(services) if services is not None else ContentToolsService(Services.default())
            data = svc.best_posting_time(days, metric)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "best_posting_time"))

    # ------------------------------------------------------------------
    # تحليل هاشتاغات
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def hashtag_analyzer(days: int = 60) -> str:
        """تحليل أي هاشتاغات تجلب أعلى تفاعل (من منشورات صفحتنا) — تُستبعد وسوم معلومات التواصل (أرقام الهواتف).

        days: نافذة التحليل (افتراضي 60)
        يرجّع: قائمة هاشتاغات مرتبة بـ (متوسط تفاعل، عدد استخدام، أفضل منشور).
        """
        try:
            if days <= 0:
                return json_dumps({"error": "days يجب أن تكون > 0"})
            posts, err = _fetch_our_posts(limit=100, with_message=True)
            if not posts:
                return json_dumps({"error": err or "لا توجد منشورات", "days": days})
            tag_data: dict = defaultdict(lambda: {"count": 0, "engagements": []})
            skipped_contact = 0
            for p in posts:
                cid = str(p.get("id") or "")
                message = p.get("message") or ""
                tags = marketing_hashtags(message)
                skipped_contact += len(all_hashtags(message)) - len(tags)
                if not tags or not cid:
                    continue
                eng = _post_engagement(cid)
                for tag in set(tags):
                    tag_data[tag]["count"] += 1
                    tag_data[tag]["engagements"].append(eng)

            if not tag_data:
                message = "لا توجد هاشتاغات تسويقية في المنشورات"
                if skipped_contact:
                    message += f" (استُبعد {skipped_contact} وسم معلومات تواصل مثل أرقام الهواتف)"
                return json_dumps({"message": message, "days": days, "skipped_contact_hashtags": skipped_contact})

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
            return json_dumps(
                {
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
            )
        except Exception as e:
            return json_dumps(handle_error(e, "hashtag_analyzer"))

    # ------------------------------------------------------------------
    # تقويم المحتوى
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def content_calendar(week_start: str = "", posts_per_week: int = 5, include_stories: bool = True) -> str:
        """توليد تقويم محتوى لـ 7 أيام (منشورات + ستوريات) مع أوقات وأفكار.

        week_start: تاريخ البداية YYYY-MM-DD (افتراضي: اليوم)
        posts_per_week: عدد المنشورات (3-7، افتراضي 5)
        include_stories: تضمين ستوريات (افتراضي true)
        يرجّع: خطة يومية (نوع، وقت، فكرة، caption_hint، hashtags).
        """
        try:
            posts_per_week = max(1, min(posts_per_week, 7))
            if week_start:
                try:
                    start = datetime.strptime(week_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    return json_dumps({"error": "week_start يجب أن تكون YYYY-MM-DD"})
            else:
                start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

            # best slots (weekday offsets from week start): Thu, Tue, Sat, Mon, Wed
            best_slots = [(3, 20), (1, 20), (5, 21), (0, 19), (2, 20), (4, 20), (6, 18)]
            day_names = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]

            # pick exactly posts_per_week distinct day offsets, best days first
            post_offsets = [off for off, _ in best_slots[:posts_per_week]]
            for off in range(7):
                if len(post_offsets) >= posts_per_week:
                    break
                if off not in post_offsets:
                    post_offsets.append(off)
            hour_by_offset = dict(best_slots)

            # content mix: video + carousel + story (never a single static image)
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
                            "idea": _content_idea(i, post_type),
                            "caption_hint": "استخدم generate_post_caption(product=..., style='sales')",
                            "hashtag_hint": "hashtag_analyzer() → استخدم أفضل 8 هاشتاغات",
                        }
                    )
                else:
                    slot.update({"post_type": "—", "idea": "يوم راحة — ستوريات فقط (behind the scenes)"})
                if include_stories:
                    slot["story"] = _story_idea(i)
                plan.append(slot)

            return json_dumps(
                {
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
            )
        except Exception as e:
            return json_dumps(handle_error(e, "content_calendar"))

    # ------------------------------------------------------------------
    # رد تلقائي على تعليقات
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def auto_reply_comments(
        keyword: str,
        reply: str,
        page_id: str = "",
        enabled: bool = True,
    ) -> str:
        """إعداد رد تلقائي على تعليقات تحتوي كلمة مفتاحية.

        keyword: الكلمة (مثل "سعر", "كم", "كمية")
        reply: نص الرد (مثل "أهلاً! السعر في رسائل الصفحة 📩")
        page_id: معرف الصفحة (افتراضي FB_PAGE_ID)
        enabled: تفعيل/إيقاف

        يُنشئ webhook automation (trigger=comment_keyword) — يتطلب FB_AUTO_RUN_WEBHOOK_AUTOMATIONS.
        """
        try:
            if not keyword or not reply:
                return json_dumps({"error": "keyword و reply مطلوبان"})

            # Persist the rule through the webhook_automations store so the
            # running webhook server can act on it — same file, same schema.
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
            return json_dumps(
                {
                    "configured": True,
                    "rule_id": rule_id,
                    "rule": rule,
                    "total_rules": len(rules),
                    "note": "يتطلب FB_AUTO_RUN_WEBHOOK_AUTOMATIONS=true في .env و webhook_server.py يعمل",
                    "manage": "list_webhook_automations() للعرض | delete_webhook_automation(rule_id) للحذف",
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "auto_reply_comments"))

    @mcp.resource("content-tools://overview")
    async def content_tools_resource() -> str:
        """نظرة عامة على أدوات المحتوى."""
        try:
            return json_dumps(
                {
                    "module": "content_tools",
                    "resource": "content-tools://overview",
                    "tools": [
                        "generate_post_caption",
                        "best_posting_time",
                        "hashtag_analyzer",
                        "content_calendar",
                        "auto_reply_comments",
                    ],
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "content-tools://overview"))

    @mcp.prompt()
    def content_tools_prompt(topic: str = "content") -> str:
        """أدوات المحتوى."""
        return (
            f"ساعد في إنشاء محتوى لـ {topic} — generate_post_caption(product=...) ثم "
            "best_posting_time() لاختيار الوقت، ثم content_calendar() للتخطيط (وحدة content_tools)"
        )

    @mcp.resource("content-tools://templates")
    async def content_tools_extra_resource() -> str:
        """قوالب المحتوى."""
        try:
            return json_dumps(
                {
                    "module": "content_tools",
                    "resource": "content-tools://templates",
                    "weekly_plan": "5 منشورات/أسبوع (2 فيديو + 2 كاروسيل + 1 ستوري)",
                    "rules": ["لا صور مفردة", "السعر على الصورة", "ضمان سنة", "3-5/أسبوع"],
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "content-tools://templates"))

    @mcp.prompt()
    def content_plan_prompt(product: str = "") -> str:
        """خطة محتوى."""
        return (
            f"خطط 7 أيام منشورات لـ {product or 'Butterfly'} — استخدم content_calendar() ثم "
            "generate_post_caption() لكل منشور (وحدة content_tools)"
        )


def _content_idea(i: int, post_type: str) -> str:
    ideas = {
        0: "طقم رئيسي (كارتير/ديور) — فيديو فتح + سعر + ضمان",
        1: "تفاصيل close-up — ماكرو للتشطيب + 'ضمان سنة'",
        2: " behind-the-scenes — صنع/تغليف + CTA",
        3: "عرض نهاية الأسبوع — خصم ٢٤→٧ (كمية محدودة)",
        4: "شهادة عميلة (UGC) + صورة على الموديل",
        5: "تشكيلة المحل — 3-5 أطقم على مانيكينات",
        6: "ستوري: 'آخر يوم للعرض' + شريط السعر",
    }
    return ideas.get(i, "منشور إضافي")


def _story_idea(i: int) -> str:
    ideas = {
        0: "ستوري: 'صباح الخير — ما جديد اليوم' + صورة منتج",
        1: "ستوري: استطلاع 'أي لون تفضلين؟' (ذهبي/فضي)",
        2: "ستوري: 'الكمية محدودة' (countdown)",
        3: "ستوري: 'آخر يوم للعرض' + link",
        4: "ستوري: behind-the-scenes (تغليف)",
        5: "ستوري: 'شكراً للعميلات' + repost",
        6: "ستوري: 'أسبوع جديد — ما awaiting'",
    }
    return ideas.get(i, "ستوري إضافي")
