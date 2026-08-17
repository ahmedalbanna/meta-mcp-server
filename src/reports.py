import csv
from pathlib import Path

import pandas as pd

from src.config import (
    AD_ACCOUNT_ID,
    INSTAGRAM_BUSINESS_ID,
    PAGE_ID,
    REPORT_DIR,
    ensure_report_dir,
)

DEFAULT_METRICS = ["spend", "impressions", "clicks", "ctr", "cpc", "reach"]

IG_MEDIA_METRICS = [
    "reach",
    "likes",
    "comments",
    "saved",
    "shares",
    "total_interactions",
]


def register(mcp):
    """Register reports tools."""

    from facebook_business.adobjects.adaccount import AdAccount

    from src.helpers import handle_error, json_dumps

    ensure_report_dir()

    def _fetch_rows(object_id: str, preset: str, metrics: list) -> list:
        ad_account = AdAccount(object_id)
        insights = ad_account.get_insights(
            params={"date_preset": preset, "fields": ["campaign_name"] + metrics}
        )
        rows = []
        for item in insights:
            data = item.export_all_data()
            row = {"campaign_name": data.get("campaign_name", "N/A")}
            for m in metrics:
                row[m] = data.get(m, 0)
            rows.append(row)
        return rows

    def _summarise(df: pd.DataFrame, metrics: list) -> dict:
        if df.empty:
            return {}
        summary = {"campaigns": int(df.shape[0])}
        for m in metrics:
            numeric = pd.to_numeric(df[m], errors="coerce").fillna(0)
            summary[f"total_{m}"] = float(numeric.sum())
            if m == "clicks" and numeric.sum():
                spend_col = (
                    df["spend"]
                    if "spend" in df.columns
                    else pd.Series(0, index=df.index)
                )
                spend = pd.to_numeric(spend_col, errors="coerce").fillna(0).sum()
                summary["avg_cpc"] = round(spend / numeric.sum(), 4)
        return summary

    @mcp.tool()
    def generate_campaign_report(
        date_preset: str = "last_30d",
        metrics: str = ",".join(DEFAULT_METRICS),
        format: str = "csv",
        filename: str = "",
    ) -> str:
        """
        توليد تقرير أداء على مستوى الحملات كملف CSV أو Excel.
        format: csv | excel. filename: اسم الملف (بدون امتداد).
        """
        try:
            ensure_report_dir()
            metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
            rows = _fetch_rows(AD_ACCOUNT_ID, date_preset, metric_list)
            df = pd.DataFrame(rows)
            base = filename or f"campaign_report_{date_preset}"
            if format == "excel":
                path = Path(REPORT_DIR) / f"{base}.xlsx"
                df.to_excel(path, index=False)
            else:
                path = Path(REPORT_DIR) / f"{base}.csv"
                df.to_csv(path, index=False)
            return json_dumps(
                {
                    "success": True,
                    "file": str(path),
                    "rows": int(df.shape[0]),
                    "summary": _summarise(df, metric_list),
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "generate_campaign_report"))

    @mcp.tool()
    def account_summary(date_preset: str = "last_30d") -> str:
        """ملخص أداء الحساب الإعلاني خلال فترة."""
        try:
            rows = _fetch_rows(AD_ACCOUNT_ID, date_preset, DEFAULT_METRICS)
            df = pd.DataFrame(rows)
            if df.empty:
                return json_dumps(
                    {"message": "لا توجد بيانات", "date_preset": date_preset}
                )
            summary = {
                "date_preset": date_preset,
                "campaigns": int(df.shape[0]),
            }
            for m in DEFAULT_METRICS:
                numeric = pd.to_numeric(df[m], errors="coerce").fillna(0)
                summary[f"total_{m}"] = float(numeric.sum())
            spend = summary.get("total_spend", 0)
            clicks = summary.get("total_clicks", 0)
            if clicks:
                summary["avg_cpc"] = round(spend / clicks, 4)
            summary["top_campaign"] = str(
                df.loc[
                    pd.to_numeric(df["spend"], errors="coerce").fillna(0).idxmax(),
                    "campaign_name",
                ]
                if not df.empty
                else "N/A"
            )
            return json_dumps(summary)
        except Exception as e:
            return json_dumps(handle_error(e, "account_summary"))

    @mcp.tool()
    def generate_instagram_report(
        limit: int = 25,
        format: str = "csv",
        filename: str = "",
    ) -> str:
        """
        توليد تقرير أداء منشورات إنستغرام كملف CSV أو Excel.
        يجمّع تحليلات (reach, likes, comments, saves, shares) + الكابشن لكل منشور.
        format: csv | excel. filename: اسم الملف (بدون امتداد).
        """
        try:
            ensure_report_dir()
            from src.helpers import api_call, init_meta_api

            init_meta_api()
            media = api_call(
                "GET",
                f"{INSTAGRAM_BUSINESS_ID}/media",
                {"fields": "id,caption,media_type,timestamp,permalink", "limit": limit},
            )
            rows = []
            for item in media.get("data", []):
                mid = item.get("id")
                caption = item.get("caption", "")
                # Truncate caption for CSV readability
                caption_short = (
                    (caption[:120] + "...") if len(caption) > 120 else caption
                )
                row = {
                    "id": mid,
                    "caption": caption_short,
                    "media_type": item.get("media_type", ""),
                    "timestamp": item.get("timestamp", ""),
                    "permalink": item.get("permalink", ""),
                }
                try:
                    insights = api_call(
                        "GET",
                        f"{mid}/insights",
                        {"metric": ",".join(IG_MEDIA_METRICS)},
                    )
                    for ins in insights.get("data", []):
                        name = ins.get("name", "")
                        values = ins.get("values", [])
                        row[name] = values[-1].get("value", 0) if values else 0
                except Exception:
                    pass
                rows.append(row)

            df = pd.DataFrame(rows)
            base = filename or "instagram_report"
            if format == "excel":
                path = Path(REPORT_DIR) / f"{base}.xlsx"
                df.to_excel(path, index=False)
            else:
                path = Path(REPORT_DIR) / f"{base}.csv"
                df.to_csv(path, index=False)

            # Summary stats
            summary = {
                "success": True,
                "file": str(path),
                "posts": int(df.shape[0]),
                "media_types": df["media_type"].value_counts().to_dict()
                if not df.empty
                else {},
            }
            if not df.empty and "total_interactions" in df.columns:
                interactions = pd.to_numeric(
                    df["total_interactions"], errors="coerce"
                ).fillna(0)
                summary["avg_engagement"] = round(float(interactions.mean()), 1)
                summary["total_engagement"] = int(interactions.sum())
                if "reach" in df.columns:
                    reach = pd.to_numeric(df["reach"], errors="coerce").fillna(0)
                    summary["avg_reach"] = round(float(reach.mean()), 0)
            return json_dumps(summary)
        except Exception as e:
            return json_dumps(handle_error(e, "generate_instagram_report"))

    @mcp.tool()
    def generate_page_report(
        format: str = "csv",
        filename: str = "",
    ) -> str:
        """
        توليد تقرير معلومات صفحة فيسبوك كملف CSV أو Excel.
        format: csv | excel. filename: اسم الملف (بدون امتداد).
        """
        try:
            ensure_report_dir()
            from src.helpers import to_dict
            from facebook_business.adobjects.page import Page

            page = Page(PAGE_ID)
            info = page.api_get(
                fields=[
                    Page.Field.name,
                    Page.Field.fan_count,
                    Page.Field.category,
                    Page.Field.about,
                    Page.Field.link,
                ]
            )
            data = to_dict(info)
            df = pd.DataFrame([data])
            base = filename or "page_report"
            if format == "excel":
                path = Path(REPORT_DIR) / f"{base}.xlsx"
                df.to_excel(path, index=False)
            else:
                path = Path(REPORT_DIR) / f"{base}.csv"
                df.to_csv(path, index=False)
            return json_dumps(
                {"success": True, "file": str(path), "rows": int(df.shape[0])}
            )
        except Exception as e:
            return json_dumps(handle_error(e, "generate_page_report"))
