import csv
import logging
from collections import Counter
from pathlib import Path

from src.config import (
    AD_ACCOUNT_ID,
    INSTAGRAM_BUSINESS_ID,
    PAGE_ID,
    REPORT_DIR,
    ensure_report_dir,
)

logger = logging.getLogger(__name__)

DEFAULT_METRICS = ["spend", "impressions", "clicks", "ctr", "cpc", "reach"]

IG_MEDIA_METRICS = [
    "reach",
    "likes",
    "comments",
    "saved",
    "shares",
    "total_interactions",
]

CAPTION_TRUNCATE_LENGTH = 120


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_excel(path: Path, rows: list[dict]) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    if not rows:
        wb.save(path)
        return
    headers = list(rows[0].keys())
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    wb.save(path)


def _to_numeric(val) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _summarise(rows: list[dict], metrics: list) -> dict:
    if not rows:
        return {}
    summary: dict[str, float | int | str] = {"campaigns": len(rows)}
    for m in metrics:
        total = sum(_to_numeric(r.get(m, 0)) for r in rows)
        summary[f"total_{m}"] = round(total, 4)
        if m == "clicks" and total:
            spend = sum(_to_numeric(r.get("spend", 0)) for r in rows)
            summary["avg_cpc"] = round(spend / total, 4)
    return summary


def register(mcp):
    """Register reports tools."""

    from facebook_business.adobjects.adaccount import AdAccount

    from src.helpers import handle_error, json_dumps, sanitize_filename
    from src.throttle import concurrency_limit

    ensure_report_dir()

    def _fetch_rows(object_id: str, preset: str, metrics: list) -> list:
        ad_account = AdAccount(object_id)
        insights = ad_account.get_insights(params={"date_preset": preset, "fields": ["campaign_name", *metrics]})
        rows = []
        for item in insights:
            data = item.export_all_data()
            row = {"campaign_name": data.get("campaign_name", "N/A")}
            for m in metrics:
                row[m] = data.get(m, 0)
            rows.append(row)
        return rows

    @mcp.tool()
    @concurrency_limit()
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
            base = filename or f"campaign_report_{date_preset}"
            if filename:
                try:
                    base = sanitize_filename(base)
                except ValueError as e:
                    return json_dumps({"error": f"اسم ملف غير صالح: {e}"})
            if format == "excel":
                path = Path(REPORT_DIR) / f"{base}.xlsx"
                _write_excel(path, rows)
            else:
                path = Path(REPORT_DIR) / f"{base}.csv"
                _write_csv(path, rows)
            return json_dumps(
                {
                    "success": True,
                    "file": str(path),
                    "rows": len(rows),
                    "summary": _summarise(rows, metric_list),
                }
            )
        except Exception as e:
            return json_dumps(handle_error(e, "generate_campaign_report"))

    @mcp.tool()
    @concurrency_limit()
    def account_summary(date_preset: str = "last_30d") -> str:
        """ملخص أداء الحساب الإعلاني خلال فترة."""
        try:
            rows = _fetch_rows(AD_ACCOUNT_ID, date_preset, DEFAULT_METRICS)
            if not rows:
                return json_dumps({"message": "لا توجد بيانات", "date_preset": date_preset})
            summary: dict[str, float | int | str] = {
                "date_preset": date_preset,
                "campaigns": len(rows),
            }
            for m in DEFAULT_METRICS:
                total = sum(_to_numeric(r.get(m, 0)) for r in rows)
                summary[f"total_{m}"] = round(total, 4)
            spend = float(summary.get("total_spend", 0) or 0)
            clicks = float(summary.get("total_clicks", 0) or 0)
            if clicks:
                summary["avg_cpc"] = round(spend / clicks, 4)
            best = max(rows, key=lambda r: _to_numeric(r.get("spend", 0)))
            summary["top_campaign"] = best.get("campaign_name", "N/A")
            return json_dumps(summary)
        except Exception as e:
            return json_dumps(handle_error(e, "account_summary"))

    @mcp.tool()
    @concurrency_limit()
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
                caption_short = (
                    (caption[:CAPTION_TRUNCATE_LENGTH] + "...") if len(caption) > CAPTION_TRUNCATE_LENGTH else caption
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
                except Exception as e:
                    logger.warning("Failed to fetch insights for media %s: %s", mid, e)
                rows.append(row)

            base = filename or "instagram_report"
            if filename:
                try:
                    base = sanitize_filename(base)
                except ValueError as e:
                    return json_dumps({"error": f"اسم ملف غير صالح: {e}"})
            if format == "excel":
                path = Path(REPORT_DIR) / f"{base}.xlsx"
                _write_excel(path, rows)
            else:
                path = Path(REPORT_DIR) / f"{base}.csv"
                _write_csv(path, rows)

            type_counts = Counter(r.get("media_type", "") for r in rows)
            summary = {
                "success": True,
                "file": str(path),
                "posts": len(rows),
                "media_types": dict(type_counts),
            }
            if rows and "total_interactions" in rows[0]:
                interactions = [_to_numeric(r.get("total_interactions", 0)) for r in rows]
                summary["avg_engagement"] = round(sum(interactions) / len(interactions), 1)
                summary["total_engagement"] = int(sum(interactions))
                if "reach" in rows[0]:
                    reach_vals = [_to_numeric(r.get("reach", 0)) for r in rows]
                    summary["avg_reach"] = round(sum(reach_vals) / len(reach_vals), 0)
            return json_dumps(summary)
        except Exception as e:
            return json_dumps(handle_error(e, "generate_instagram_report"))

    @mcp.tool()
    @concurrency_limit()
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
            from facebook_business.adobjects.page import Page

            from src.helpers import to_dict

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
            rows = [data]
            base = filename or "page_report"
            if filename:
                try:
                    base = sanitize_filename(base)
                except ValueError as e:
                    return json_dumps({"error": f"اسم ملف غير صالح: {e}"})
            if format == "excel":
                path = Path(REPORT_DIR) / f"{base}.xlsx"
                _write_excel(path, rows)
            else:
                path = Path(REPORT_DIR) / f"{base}.csv"
                _write_csv(path, rows)
            return json_dumps({"success": True, "file": str(path), "rows": len(rows)})
        except Exception as e:
            return json_dumps(handle_error(e, "generate_page_report"))
