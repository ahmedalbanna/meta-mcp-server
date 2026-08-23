from src.config import AD_ACCOUNT_ID
from src.utils import normalize_pii

LOOKALIKE_TYPES = ["SIMILARITY", "REACH", "CUSTOM_RATIO"]
RETENTION_SECONDS_90D = 7776000


def register(mcp):
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
    def list_custom_audiences(limit: int = 25) -> str:
        """قائمة الجماهير المخصصة في الحساب."""
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            audiences = account.get_custom_audiences(
                params={
                    "fields": [
                        CustomAudience.Field.name,
                        CustomAudience.Field.subtype,
                        "approximate_count",
                        CustomAudience.Field.id,
                    ],
                    "limit": limit,
                }
            )
            return json_dumps([to_dict(a) for a in audiences])
        except Exception as e:
            return json_dumps(handle_error(e, "list_custom_audiences"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_custom_audience(
        name: str, description: str = "", customer_file_source: str = "BOTH_USER_AND_PARTNER_PROVIDED"
    ) -> str:
        """إنشاء جمهور مخصص جديد."""
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            audience = account.create_custom_audience(
                params={
                    CustomAudience.Field.name: name,
                    CustomAudience.Field.subtype: "CUSTOM",
                    CustomAudience.Field.description: description,
                    "customer_file_source": customer_file_source,
                }
            )
            return json_dumps(to_dict(audience))
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
            audience = CustomAudience(audience_id)
            schema, users = _build_user_schema(emails, phone_numbers, user_ids, hash_pii)
            if not users:
                return json_dumps({"error": "قدّم بريدًا أو أرقام هواتف أو معرفات"})
            result = audience.add_users(schema=schema, users=users)
            return json_dumps(
                {
                    "success": True,
                    "audience_id": audience_id,
                    "added": len(users),
                    "hashed": hash_pii,
                    "result": to_dict(result),
                }
            )
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
            audience = CustomAudience(audience_id)
            schema, users = _build_user_schema(emails, phone_numbers, user_ids, hash_pii)
            if not users:
                return json_dumps({"error": "قدّم بريدًا أو أرقام هواتف أو معرفات"})
            result = audience.remove_users(schema=schema, users=users)
            return json_dumps(
                {
                    "success": True,
                    "audience_id": audience_id,
                    "removed": len(users),
                    "hashed": hash_pii,
                    "result": to_dict(result),
                }
            )
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
            audience = CustomAudience(audience_id)
            audience.api_read(
                fields=[
                    "id",
                    "name",
                    "description",
                    "approximate_count",
                    "customer_file_source",
                    "delivery_info",
                    "status",
                    "time_created",
                    "time_updated",
                ]
            )
            return json_dumps(to_dict(audience))
        except Exception as e:
            return json_dumps(handle_error(e, "get_custom_audience_insights"))
