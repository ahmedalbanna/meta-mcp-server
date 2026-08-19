from src.config import AD_ACCOUNT_ID


def register(mcp):
    """Register campaigns tools."""

    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.campaign import Campaign

    from src.helpers import handle_error, json_dumps, to_dict, write_guard
    from src.throttle import concurrency_limit

    @mcp.tool()
    @concurrency_limit()
    def list_campaigns(status: str = "", limit: int = 25) -> str:
        """
        قائمة الحملات الإعلانية في الحساب.
        status اختياري: ACTIVE, PAUSED, DELETED, ARCHIVED
        """
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            params = {
                "fields": [
                    Campaign.Field.name,
                    Campaign.Field.status,
                    Campaign.Field.objective,
                    Campaign.Field.daily_budget,
                    Campaign.Field.lifetime_budget,
                    Campaign.Field.created_time,
                    Campaign.Field.id,
                ],
                "limit": limit,
            }
            if status:
                params["filtering"] = json_dumps(
                    [{"field": "status", "operator": "EQUAL", "value": status}]
                )
            campaigns = account.get_campaigns(params=params)
            return json_dumps([to_dict(c) for c in campaigns])
        except Exception as e:
            return json_dumps(handle_error(e, "list_campaigns"))

    @mcp.tool()
    @concurrency_limit()
    def get_campaign(campaign_id: str) -> str:
        """تفاصيل حملة واحدة."""
        try:
            campaign = Campaign(campaign_id)
            info = campaign.api_get(
                fields=[
                    Campaign.Field.name,
                    Campaign.Field.status,
                    Campaign.Field.objective,
                    Campaign.Field.daily_budget,
                    Campaign.Field.lifetime_budget,
                    Campaign.Field.buying_type,
                    Campaign.Field.created_time,
                    Campaign.Field.updated_time,
                ]
            )
            return json_dumps(to_dict(info))
        except Exception as e:
            return json_dumps(handle_error(e, "get_campaign"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_campaign(
        name: str,
        objective: str = "OUTCOME_TRAFFIC",
        daily_budget: int = 0,
        lifetime_budget: int = 0,
        status: str = "PAUSED",
    ) -> str:
        """
        إنشاء حملة جديدة.
        objective: OUTCOME_TRAFFIC, OUTCOME_ENGAGEMENT, OUTCOME_AWARENESS,
                   CONVERSIONS, LEAD_GENERATION, OUTCOME_SALES...
        الميزانية بالعملة الصغرى (مثال 1000 = 10 دولار). حدد daily_budget أو lifetime_budget.
        """
        try:
            account = AdAccount(AD_ACCOUNT_ID)
            params = {
                Campaign.Field.name: name,
                Campaign.Field.objective: objective,
                Campaign.Field.status: status,
                Campaign.Field.special_ad_categories: [],
                "is_adset_budget_sharing_enabled": False,
            }
            if daily_budget and daily_budget > 0:
                params[Campaign.Field.daily_budget] = daily_budget
            if lifetime_budget and lifetime_budget > 0:
                params[Campaign.Field.lifetime_budget] = lifetime_budget
            if not (daily_budget or lifetime_budget):
                return json_dumps({"error": "يجب تحديد ميزانية يومية أو إجمالية"})
            campaign = account.create_campaign(params=params)
            return json_dumps(to_dict(campaign))
        except Exception as e:
            return json_dumps(handle_error(e, "create_campaign"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_campaign_status(campaign_id: str, status: str) -> str:
        """
        تغيير حالة حملة.
        status: ACTIVE, PAUSED, DELETED, ARCHIVED
        """
        try:
            valid = {"ACTIVE", "PAUSED", "DELETED", "ARCHIVED"}
            status = status.upper()
            if status not in valid:
                return json_dumps({"error": f"status غير صالح. القيم: {', '.join(sorted(valid))}"})
            campaign = Campaign(campaign_id)
            result = campaign.api_update(params={Campaign.Field.status: status})
            return json_dumps(
                {"success": True, "campaign_id": campaign_id, "new_status": status, "result": to_dict(result)}
            )
        except Exception as e:
            return json_dumps(handle_error(e, "update_campaign_status"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_campaign_budget(campaign_id: str, daily_budget: int = 0, lifetime_budget: int = 0) -> str:
        """تعديل ميزانية حملة (بالعملة الصغرى)."""
        try:
            campaign = Campaign(campaign_id)
            params = {}
            if daily_budget and daily_budget > 0:
                params[Campaign.Field.daily_budget] = daily_budget
            if lifetime_budget and lifetime_budget > 0:
                params[Campaign.Field.lifetime_budget] = lifetime_budget
            if not params:
                return json_dumps({"error": "حدد ميزانية يومية أو إجمالية"})
            result = campaign.api_update(params=params)
            return json_dumps({"success": True, "campaign_id": campaign_id, "result": to_dict(result)})
        except Exception as e:
            return json_dumps(handle_error(e, "update_campaign_budget"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def delete_campaign(campaign_id: str) -> str:
        """حذف حملة نهائيًا."""
        try:
            campaign = Campaign(campaign_id)
            result = campaign.api_delete()
            return json_dumps({"success": True, "campaign_id": campaign_id, "result": to_dict(result)})
        except Exception as e:
            return json_dumps(handle_error(e, "delete_campaign"))
