from src.config import AD_ACCOUNT_ID


def register(mcp):
    """Register custom audience tools."""

    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.customaudience import CustomAudience

    from src.helpers import handle_error, json_dumps, to_dict, write_guard

    @mcp.tool()
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
    @write_guard
    def create_custom_audience(name: str, description: str = "") -> str:
        """إنشاء جمهور مخصص جديد."""
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            audience = account.create_custom_audience(
                params={
                    CustomAudience.Field.name: name,
                    CustomAudience.Field.subtype: "CUSTOM",
                    CustomAudience.Field.description: description,
                }
            )
            return json_dumps(to_dict(audience))
        except Exception as e:
            return json_dumps(handle_error(e, "create_custom_audience"))

    @mcp.tool()
    @write_guard
    def add_users_to_custom_audience(
        audience_id: str,
        emails: str = "",
        phone_numbers: str = "",
        user_ids: str = "",
    ) -> str:
        """
        إضافة مستخدمين إلى جمهور مخصص.
        مرّر القيم مفصولة بفواصل: emails="a@x.com,b@y.com" أو phone_numbers="+20100,+20101"
        """
        try:
            audience = CustomAudience(audience_id)
            schema = []
            users = []
            if emails:
                schema.append("EMAIL")
                users.extend(e.strip() for e in emails.split(",") if e.strip())
            if phone_numbers:
                schema.append("PHONE")
                users.extend(p.strip() for p in phone_numbers.split(",") if p.strip())
            if user_ids:
                schema.append("ID")
                users.extend(u.strip() for u in user_ids.split(",") if u.strip())
            if not users:
                return json_dumps({"error": "قدّم بريدًا أو أرقام هواتف أو معرفات"})
            result = audience.add_users(schema=schema, users=users)
            return json_dumps({"success": True, "audience_id": audience_id, "added": len(users), "result": to_dict(result)})
        except Exception as e:
            return json_dumps(handle_error(e, "add_users_to_custom_audience"))

    @mcp.tool()
    @write_guard
    def remove_users_from_custom_audience(
        audience_id: str,
        emails: str = "",
        phone_numbers: str = "",
        user_ids: str = "",
    ) -> str:
        """إزالة مستخدمين من جمهور مخصص (نفس صيغة الإضافة)."""
        try:
            audience = CustomAudience(audience_id)
            schema = []
            users = []
            if emails:
                schema.append("EMAIL")
                users.extend(e.strip() for e in emails.split(",") if e.strip())
            if phone_numbers:
                schema.append("PHONE")
                users.extend(p.strip() for p in phone_numbers.split(",") if p.strip())
            if user_ids:
                schema.append("ID")
                users.extend(u.strip() for u in user_ids.split(",") if u.strip())
            if not users:
                return json_dumps({"error": "قدّم بريدًا أو أرقام هواتف أو معرفات"})
            result = audience.remove_users(schema=schema, users=users)
            return json_dumps({"success": True, "audience_id": audience_id, "removed": len(users), "result": to_dict(result)})
        except Exception as e:
            return json_dumps(handle_error(e, "remove_users_from_custom_audience"))

    @mcp.tool()
    @write_guard
    def create_lookalike_audience(
        source_audience_id: str,
        name: str,
        country: str = "US",
        ratio: float = 0.01,
        description: str = "",
    ) -> str:
        """
        إنشاء جمهور مشابه (Lookalike) من جمهور مصدر.
        ratio: نسبة الحجم من 0.01 إلى 0.20.
        """
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            audience = account.create_custom_audience(
                params={
                    CustomAudience.Field.name: name,
                    CustomAudience.Field.subtype: "LOOKALIKE",
                    CustomAudience.Field.description: description,
                    CustomAudience.Field.lookalike_spec: json_dumps(
                        {
                            "origin_audience_id": source_audience_id,
                            "ratio": ratio,
                            "country": country,
                        }
                    ),
                }
            )
            return json_dumps(to_dict(audience))
        except Exception as e:
            return json_dumps(handle_error(e, "create_lookalike_audience"))
