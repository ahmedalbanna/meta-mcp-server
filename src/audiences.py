import asyncio
import logging
import time

from src.config import AD_ACCOUNT_ID

logger = logging.getLogger(__name__)
from src.utils import normalize_pii

LOOKALIKE_TYPES = ["SIMILARITY", "REACH", "CUSTOM_RATIO"]
RETENTION_SECONDS_90D = 7776000


def register(mcp, services=None):
    """Register custom audience tools."""

    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.customaudience import CustomAudience

    from src.helpers import handle_error, json_dumps, sanitize_path, to_dict, write_guard
    from src.throttle import concurrency_limit

    def _split(items: str) -> list:
        return [i.strip() for i in (items or "").split(",") if i.strip()]

    def _build_user_schema(emails: str, phone_numbers: str, user_ids: str, hash_pii: bool):
        """Build (schema, users) from comma-separated PII strings."""
        schema = []
        users = []
        if emails:
            email_list = _split(emails)
            if hash_pii:
                schema.append("EMAIL_SHA256")
                users.extend(normalize_pii(email_list, "email"))
            else:
                schema.append("EMAIL")
                users.extend(email_list)
        if phone_numbers:
            phone_list = _split(phone_numbers)
            if hash_pii:
                schema.append("PHONE_SHA256")
                users.extend(normalize_pii(phone_list, "phone"))
            else:
                schema.append("PHONE")
                users.extend(phone_list)
        if user_ids:
            schema.append("ID")
            users.extend(_split(user_ids))
        return schema, users

    @mcp.tool()
    @concurrency_limit()
    def list_custom_audiences(limit: int = 25, ad_account_id: str = "") -> str:
        """قائمة الجماهير المخصصة في الحساب."""
        try:
            from src.core.services import Services
            from src.services.audiences_service import AudiencesService
            svc = AudiencesService(services) if services is not None else AudiencesService(Services.default())
            data = svc.list_custom_audiences(limit, ad_account_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "list_custom_audiences"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_custom_audience(
        name: str,
        description: str = "",
        customer_file_source: str = "BOTH_USER_AND_PARTNER_PROVIDED",
        ad_account_id: str = "",
    ) -> str:
        """إنشاء جمهور مخصص جديد."""
        try:
            from src.core.services import Services
            from src.services.audiences_service import AudiencesService
            svc = AudiencesService(services) if services is not None else AudiencesService(Services.default())
            return json_dumps(svc.create_custom_audience(name, description, customer_file_source, ad_account_id))
        except Exception as e:
            return json_dumps(handle_error(e, "create_custom_audience"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def add_users_to_custom_audience(
        audience_id: str,
        emails: str = "",
        phone_numbers: str = "",
        user_ids: str = "",
        hash_pii: bool = True,
    ) -> str:
        """
        إضافة مستخدمين إلى جمهور مخصص.
        مرّر القيم مفصولة بفواصل: emails="a@x.com,b@y.com" أو phone_numbers="+20100,+20101"
        hash_pii=true (الافتراضي): تُشفر البريد والهاتف SHA-256 قبل الإرسال (مواصفة Meta).
        """
        try:
            from src.core.services import Services
            from src.services.audiences_service import AudiencesService
            svc = AudiencesService(services) if services is not None else AudiencesService(Services.default())
            return json_dumps(svc.add_users(audience_id, emails, phone_numbers, user_ids, hash_pii))
        except Exception as e:
            return json_dumps(handle_error(e, "add_users_to_custom_audience"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def remove_users_from_custom_audience(
        audience_id: str,
        emails: str = "",
        phone_numbers: str = "",
        user_ids: str = "",
        hash_pii: bool = True,
    ) -> str:
        """إزالة مستخدمين من جمهور مخصص (نفس صيغة الإضافة)."""
        try:
            from src.core.services import Services
            from src.services.audiences_service import AudiencesService
            svc = AudiencesService(services) if services is not None else AudiencesService(Services.default())
            return json_dumps(svc.remove_users(audience_id, emails, phone_numbers, user_ids, hash_pii))
        except Exception as e:
            return json_dumps(handle_error(e, "remove_users_from_custom_audience"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def upload_custom_audience_csv(
        audience_id: str,
        csv_path: str,
        schema: str = "EMAIL,PHONE",
        has_header: bool = True,
        delimiter: str = ",",
    ) -> str:
        """
        رفع ملف CSV محلي إلى جمهور مخصص دفعة واحدة.
        csv_path: مسار ملف CSV على الخادم. schema: أعمدة البيانات مفصولة بفواصل
        (EMAIL, PHONE, ID...). كل البيانات تُشفَّر SHA-256 قبل الرفع.
        """
        try:
            import csv as _csv

            from src.config import BASE_DIR

            # Scope CSV reads to BASE_DIR (and subdirs) to prevent traversal outside project
            path = sanitize_path(csv_path, BASE_DIR)
            if not path.is_file():
                return json_dumps({"error": f"الملف غير موجود: {csv_path}"})
            schema_list = [s.strip().upper() for s in _split(schema)]
            if not schema_list:
                return json_dumps({"error": "schema فارغ. مثال: EMAIL,PHONE"})
            if any(s not in ("EMAIL", "PHONE", "ID") for s in schema_list):
                return json_dumps({"error": "schema يدعم فقط: EMAIL, PHONE, ID"})

            rows = []
            with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
                reader = _csv.reader(fh, delimiter=delimiter)
                for i, row in enumerate(reader):
                    if i == 0 and has_header:
                        continue
                    clean = [c.strip() for c in row]
                    if clean and any(clean):
                        rows.append(clean)

            users_by_schema: dict[str, list[str]] = {s: [] for s in schema_list}
            for row in rows:
                for idx, s in enumerate(schema_list):
                    if idx < len(row) and row[idx]:
                        users_by_schema[s].append(row[idx])

            api_schema = []
            users = []
            for s in schema_list:
                values = users_by_schema[s]
                if not values:
                    continue
                if s == "EMAIL":
                    api_schema.append("EMAIL_SHA256")
                    users.extend(normalize_pii(values, "email"))
                elif s == "PHONE":
                    api_schema.append("PHONE_SHA256")
                    users.extend(normalize_pii(values, "phone"))
                else:
                    api_schema.append("ID")
                    users.extend(values)
            if not users:
                return json_dumps({"error": "لا توجد بيانات صالحة في الملف"})
            result = CustomAudience(audience_id).add_users(schema=api_schema, users=users)
            return json_dumps(
                {
                    "success": True,
                    "audience_id": audience_id,
                    "added": len(users),
                    "rows": len(rows),
                    "result": to_dict(result),
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "upload_custom_audience_csv"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_lookalike_audience(
        source_audience_id: str = "",
        name: str = "",
        country: str = "US",
        ratio: float = 0.01,
        description: str = "",
        lookalike_type: str = "SIMILARITY",
        source_pixel_id: str = "",
        source_website_url: str = "",
    ) -> str:
        """
        إنشاء جمهور مشابه (Lookalike) من جمهور مصدر أو بكسل أو موقع.
        lookalike_type: SIMILARITY (شبيه) | REACH (وصول) | CUSTOM_RATIO (نسبة مخصصة).
        source_audience_id: معرّف الجمهور المصدر، أو source_pixel_id للجماهير الشبيهة
        المبنية على بكسل، أو source_website_url للجماهير المبنية على الموقع.
        ratio: نسبة الحجم من 0.01 إلى 0.20.
        """
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            seed_id = source_audience_id
            if not seed_id and (source_pixel_id or source_website_url):
                # A lookalike only accepts a Custom Audience ID as its seed
                # (origin_audience_id). Pixel/website sources must first become a
                # Website Custom Audience, whose ID we then use as the seed.
                if source_pixel_id:
                    rule = {
                        "inclusions": {
                            "operator": "or",
                            "rules": [
                                {
                                    "event_sources": [{"type": "pixel", "id": source_pixel_id}],
                                    "retention_seconds": RETENTION_SECONDS_90D,
                                    "filter": {"operator": "and", "filters": []},
                                }
                            ],
                        }
                    }
                    seed_params = {
                        CustomAudience.Field.name: f"{name} (Pixel Seed)",
                        CustomAudience.Field.subtype: "WEBSITE",
                        CustomAudience.Field.pixel_id: source_pixel_id,
                        CustomAudience.Field.rule: json_dumps(rule),
                    }
                else:
                    rule = {
                        "inclusions": {
                            "operator": "or",
                            "rules": [
                                {
                                    "event_sources": [{"type": "pixel", "id": source_website_url}],
                                    "retention_seconds": RETENTION_SECONDS_90D,
                                    "filter": {
                                        "operator": "and",
                                        "filters": [
                                            {
                                                "field": "url",
                                                "operator": "i_contains",
                                                "value": source_website_url,
                                            }
                                        ],
                                    },
                                }
                            ],
                        }
                    }
                    seed_params = {
                        CustomAudience.Field.name: f"{name} (Website Seed)",
                        CustomAudience.Field.subtype: "WEBSITE",
                        CustomAudience.Field.rule: json_dumps(rule),
                    }
                seed = account.create_custom_audience(params=seed_params)
                seed_id = seed["id"]
            if not seed_id:
                return json_dumps({"error": "حدد source_audience_id أو source_pixel_id أو source_website_url"})
            if not name:
                return json_dumps({"error": "حدد اسمًا للجمهور (name)"})
            ltype = lookalike_type.strip().upper()
            if ltype not in LOOKALIKE_TYPES:
                return json_dumps(
                    {"error": f"lookalike_type غير صالح: {lookalike_type}. الاختيارات: {', '.join(LOOKALIKE_TYPES)}"}
                )
            spec = {
                "origin_audience_id": seed_id,
                "ratio": ratio,
                "country": country,
                "type": ltype,
            }
            audience = account.create_custom_audience(
                params={
                    CustomAudience.Field.name: name,
                    CustomAudience.Field.subtype: "LOOKALIKE",
                    CustomAudience.Field.description: description,
                    CustomAudience.Field.lookalike_spec: json_dumps(spec),
                }
            )
            return json_dumps(to_dict(audience))
        except Exception as e:
            return json_dumps(handle_error(e, "create_lookalike_audience"))

    @mcp.tool()
    @concurrency_limit()
    def get_custom_audience_insights(audience_id: str) -> str:
        """تفاصيل جمهور مخصص: الحجم، المصدر، الحالة، تاريخ الإنشاء."""
        try:
            from src.core.services import Services
            from src.services.audiences_service import AudiencesService
            svc = AudiencesService(services) if services is not None else AudiencesService(Services.default())
            data = svc.get_custom_audience_insights(audience_id)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "get_custom_audience_insights"))

    # ------------------------------------------------------------------
    # Phase 3.4 — Audience intelligence
    # ------------------------------------------------------------------

    @mcp.tool()
    @concurrency_limit()
    def get_audience_overlap(audience_id_1: str, audience_id_2: str) -> str:
        """تقدير التداخل بين جمهورين (overlap) عبر approximate_count."""
        try:
            # Try native overlap endpoint first
            try:
                from src.helpers import api_call

                data = api_call(
                    "GET",
                    f"{AD_ACCOUNT_ID}/audience_overlap",
                    {"audience_ids": f"[{audience_id_1},{audience_id_2}]"},
                )
                if data and "data" in data:
                    return json_dumps(data)
            except Exception:
                pass
            # Fallback: fetch approximate counts and estimate
            a1 = CustomAudience(audience_id_1)
            a1.api_read(fields=["id", "name", "approximate_count"])
            d1 = to_dict(a1)
            a2 = CustomAudience(audience_id_2)
            a2.api_read(fields=["id", "name", "approximate_count"])
            d2 = to_dict(a2)
            c1 = int(d1.get("approximate_count") or 0)
            c2 = int(d2.get("approximate_count") or 0)
            # Simple heuristic: overlap ~ min(c1,c2)*0.15 (illustrative)
            est_overlap = int(min(c1, c2) * 0.15) if c1 and c2 else 0
            return json_dumps(
                {
                    "audience_1": {"id": audience_id_1, "name": d1.get("name"), "count": c1},
                    "audience_2": {"id": audience_id_2, "name": d2.get("name"), "count": c2},
                    "estimated_overlap": est_overlap,
                    "overlap_rate": round(est_overlap / max(c1, c2), 3) if max(c1, c2) else 0,
                    "note": "تقدير محلي؛ للحصول على دقة Meta استخدم audience_overlap إن كان متاحًا للحساب",
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "get_audience_overlap"))

    @mcp.tool()
    @concurrency_limit()
    def estimate_reach(targeting_json: str, optimization_goal: str = "REACH", page_id: str = "") -> str:
        """تقدير الوصول (Reach Estimate) لاستهداف معين."""
        try:
            import json as _json

            from src.config import PAGE_ID as _PID
            from src.helpers import api_call

            targeting = _json.loads(targeting_json) if targeting_json else {}
            if not isinstance(targeting, dict):
                return json_dumps({"error": "targeting_json يجب أن يكون كائن JSON"})
            params = {
                "targeting_spec": json_dumps(targeting),
                "optimization_goal": optimization_goal.strip().upper(),
            }
            # Some reach estimates require page_id
            pid = page_id or _PID
            if pid:
                params["page_id"] = pid
            data = api_call("GET", f"{AD_ACCOUNT_ID}/reachestimate", params)
            return json_dumps(data)
        except Exception as e:
            return json_dumps(handle_error(e, "estimate_reach: تأكد من صلاحيات ads_read وصيغة targeting_spec"))

    @mcp.tool()
    @concurrency_limit()
    def suggest_lookalike(source_audience_id: str, country: str = "US", ratio: float = 0.01) -> str:
        """اقتراح إعدادات Lookalike بناءً على حجم الجمهور المصدر."""
        try:
            audience = CustomAudience(source_audience_id)
            audience.api_read(fields=["id", "name", "approximate_count", "subtype"])
            d = to_dict(audience)
            count = int(d.get("approximate_count") or 0)
            subtype = d.get("subtype", "")
            # Heuristics per Meta best-practices: seed 1000-50000 ideal
            if count < 1000:
                recommendation = "الجمهور صغير جدًا (<1000). اجمع المزيد من البيانات أو استخدم مصدر أوسع."
                suggested_ratio = 0.01
            elif count < 10000:
                recommendation = "جيد للـ Lookalike دقيق (1%). استخدم SIMILARITY."
                suggested_ratio = 0.01
            elif count < 50000:
                recommendation = "ممتاز — يمكنك استخدام REACH أو نسبة 0.03-0.05 لتوسيع الوصول."
                suggested_ratio = 0.03
            else:
                recommendation = "جمهور كبير — استخدم CUSTOM_RATIO 0.05-0.10 مع اختبار A/B."
                suggested_ratio = 0.05
            # Override with provided ratio if explicit and valid
            if 0.01 <= ratio <= 0.20:
                suggested_ratio = ratio
            return json_dumps(
                {
                    "source": {"id": source_audience_id, "name": d.get("name"), "count": count, "subtype": subtype},
                    "suggested": {
                        "country": country,
                        "ratio": suggested_ratio,
                        "lookalike_type": "SIMILARITY"
                        if suggested_ratio <= 0.01
                        else "REACH"
                        if suggested_ratio <= 0.03
                        else "CUSTOM_RATIO",
                    },
                    "recommendation": recommendation,
                    "note": "أنشئ عبر create_lookalike_audience للحصول على الجمهور الفعلي",
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "suggest_lookalike"))

    @mcp.tool()
    @concurrency_limit()
    def suggest_targeting(
        product: str,
        country: str = "EG",
        age_min: int = 18,
        age_max: int = 65,
        interests: str = "",
        language: str = "ar",
    ) -> str:
        """
        اقتراح استهداف مدعوم بـ LLM لمنتج معين.
        interests: كلمات مفتاحية مفصولة بفواصل (مثال: fashion, shoes)
        language: ar | en
        """
        try:
            # Try LLM first
            try:
                from src.llm import call_llm

                prompt = (
                    f"Suggest Meta ads targeting for product '{product}' in {country}, age {age_min}-{age_max}, "
                    f"interests: {interests or 'general'}. Language {language}. "
                    "Return JSON with keys: geo_locations, age_min, age_max, gender, interests (list of {id,name}), "
                    "behaviors, targeting_automation. Keep it valid for Graph API create_adset."
                )
                system = "You are a Meta ads targeting expert. Return valid JSON only."
                llm_out = call_llm(prompt, system=system)
                if llm_out:
                    import json as _json2

                    try:
                        parsed = _json2.loads(llm_out)
                        if isinstance(parsed, dict) and "geo_locations" in parsed:
                            return json_dumps({"product": product, "targeting": parsed, "source": "llm"})
                    except Exception:
                        pass
            except Exception:
                pass

            # Fallback heuristic template
            interest_list = [i.strip() for i in interests.split(",") if i.strip()]
            # Simple mapping: each interest -> id placeholder (would need real interest search in prod)
            interests_payload = [{"id": f"interest_{i[:10]}", "name": i} for i in interest_list[:5]]
            targeting: dict = {
                "geo_locations": {"countries": [country.upper()]},
                "age_min": age_min,
                "age_max": age_max,
                "targeting_automation": {"advantage_audience": 0},
            }
            if interests_payload:
                targeting["interests"] = interests_payload
            # Gender heuristic
            if language == "ar":
                targeting["genders"] = [0]  # 0=all
            return json_dumps({"product": product, "targeting": targeting, "source": "template"})
        except Exception as e:
            return json_dumps(handle_error(e, "suggest_targeting"))

    @mcp.resource("audiences://overview")
    async def audiences_resource() -> str:
        """نظرة عامة على الجماهير."""
        try:
            # Lightweight per-module overview (calls existing list tool pattern)
            return json_dumps(
                {"module": "audiences", "resource": "audiences://overview", "hint": "نظرة عامة على الجماهير"}
            )
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "audiences://overview"))

    @mcp.prompt()
    def audience_builder_prompt(topic: str = "audiences") -> str:
        """بناء جمهور."""
        return "ساعد في بناء جمهور لـ " + topic + " — ابن جمهور لمنتج {product} (وحدة audiences)"

    @mcp.resource("audiences://list")
    async def audiences_list_resource() -> str:
        """قائمة الجماهير المخصصة."""
        try:

            def _fetch():
                account = AdAccount(AD_ACCOUNT_ID)
                return account.get_custom_audiences(params={"fields": ["name", "subtype", "approximate_count", "id"]})

            t0 = time.monotonic()
            audiences = await asyncio.to_thread(_fetch)
            elapsed = time.monotonic() - t0
            logger.info(
                "audiences://list fetched %d audiences in %.2fs",
                len(list(audiences)),
                elapsed,
            )
            return json_dumps([to_dict(a) for a in audiences])
        except Exception as e:
            from src.helpers import handle_error

            logger.exception("audiences://list failed")
            return json_dumps(handle_error(e, "audiences://list"))
