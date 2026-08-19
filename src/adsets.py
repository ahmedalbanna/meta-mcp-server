import json

from src.config import AD_ACCOUNT_ID


def register(mcp):
    """Register ad set tools."""

    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.adset import AdSet
    from facebook_business.adobjects.campaign import Campaign

    from src.helpers import handle_error, json_dumps, to_dict, write_guard
    from src.throttle import concurrency_limit

    @mcp.tool()
    @concurrency_limit()
    def list_adsets(campaign_id: str = "", limit: int = 25) -> str:
        """قائمة المجموعات الإعلانية (يمكن تحديد حملة معينة)."""
        try:
            params = {
                "fields": [
                    AdSet.Field.name,
                    AdSet.Field.status,
                    AdSet.Field.targeting,
                    AdSet.Field.daily_budget,
                    AdSet.Field.lifetime_budget,
                    AdSet.Field.optimization_goal,
                    AdSet.Field.billing_event,
                    AdSet.Field.id,
                ],
                "limit": limit,
            }
            if campaign_id:
                adsets = Campaign(campaign_id).get_ad_sets(params=params)
            else:
                adsets = AdAccount(AD_ACCOUNT_ID).get_ad_sets(params=params)
            return json_dumps([to_dict(a) for a in adsets])
        except Exception as e:
            return json_dumps(handle_error(e, "list_adsets"))

    @mcp.tool()
    @concurrency_limit()
    def get_adset(adset_id: str) -> str:
        """تفاصيل مجموعة إعلانية واحدة."""
        try:
            adset = AdSet(adset_id)
            info = adset.api_get(
                fields=[
                    AdSet.Field.name,
                    AdSet.Field.status,
                    AdSet.Field.targeting,
                    AdSet.Field.daily_budget,
                    AdSet.Field.lifetime_budget,
                    AdSet.Field.optimization_goal,
                    AdSet.Field.billing_event,
                    AdSet.Field.bid_amount,
                    AdSet.Field.pacing_type,
                    AdSet.Field.start_time,
                    AdSet.Field.end_time,
                ]
            )
            return json_dumps(to_dict(info))
        except Exception as e:
            return json_dumps(handle_error(e, "get_adset"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def create_adset(
        campaign_id: str,
        name: str,
        daily_budget: int = 0,
        optimization_goal: str = "LINK_CLICKS",
        billing_event: str = "IMPRESSIONS",
        targeting: str = "",
        status: str = "PAUSED",
        bid_amount: int = 0,
    ) -> str:
        """
        إنشاء مجموعة إعلانية داخل حملة.
        targeting: JSON نصي مثل {"geo_locations":{"countries":["US"]},"age_min":18,"age_max":65}
        bid_amount: سقف عرض إلزامي لهذه الحسابات (بالعملة الصغرى). 0 يستخدم LOWEST_COST_WITHOUT_CAP.
        """
        try:
            if not targeting:
                targeting = json_dumps({"geo_locations": {"countries": ["US"]}})
            target = json.loads(targeting)
            target.setdefault("targeting_automation", {"advantage_audience": 0})
            targeting = json_dumps(target)
            account = AdAccount(AD_ACCOUNT_ID)
            params = {
                AdSet.Field.name: name,
                AdSet.Field.optimization_goal: optimization_goal,
                AdSet.Field.billing_event: billing_event,
                AdSet.Field.targeting: targeting,
                AdSet.Field.status: status,
                "campaign_id": campaign_id,
            }
            if daily_budget and daily_budget > 0:
                params[AdSet.Field.daily_budget] = daily_budget
            if bid_amount and bid_amount > 0:
                params[AdSet.Field.bid_strategy] = "LOWEST_COST_WITH_BID_CAP"
                params[AdSet.Field.bid_amount] = bid_amount
            else:
                params[AdSet.Field.bid_strategy] = "LOWEST_COST_WITHOUT_CAP"
            adset = account.create_ad_set(params=params)
            return json_dumps(to_dict(adset))
        except Exception as e:
            return json_dumps(handle_error(e, "create_adset"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_adset_status(adset_id: str, status: str) -> str:
        """تغيير حالة مجموعة إعلانية (ACTIVE, PAUSED, DELETED, ARCHIVED)."""
        try:
            adset = AdSet(adset_id)
            adset.api_update(params={AdSet.Field.status: status})
            return json_dumps({"success": True, "adset_id": adset_id, "new_status": status})
        except Exception as e:
            return json_dumps(handle_error(e, "update_adset_status"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_adset_budget(adset_id: str, daily_budget: int = 0, lifetime_budget: int = 0) -> str:
        """تعديل ميزانية مجموعة إعلانية (بالعملة الصغرى)."""
        try:
            adset = AdSet(adset_id)
            params = {}
            if daily_budget and daily_budget > 0:
                params[AdSet.Field.daily_budget] = daily_budget
            if lifetime_budget and lifetime_budget > 0:
                params[AdSet.Field.lifetime_budget] = lifetime_budget
            if not params:
                return json_dumps({"error": "حدد ميزانية يومية أو إجمالية"})
            adset.api_update(params=params)
            return json_dumps({"success": True, "adset_id": adset_id, "result": params})
        except Exception as e:
            return json_dumps(handle_error(e, "update_adset_budget"))

    @mcp.tool()
    @concurrency_limit()
    @write_guard
    def update_adset_targeting(adset_id: str, targeting: str) -> str:
        """
        تعديل استهداف مجموعة إعلانية.
        targeting: JSON نصي مثل {"geo_locations":{"countries":["EG"]},"age_min":18,"interests":[]}
        """
        try:
            target = json.loads(targeting)
            target.setdefault("targeting_automation", {"advantage_audience": 0})
            adset = AdSet(adset_id)
            adset.api_update(params={AdSet.Field.targeting: json_dumps(target)})
            return json_dumps({"success": True, "adset_id": adset_id, "targeting": target})
        except Exception as e:
            return json_dumps(handle_error(e, "update_adset_targeting"))
