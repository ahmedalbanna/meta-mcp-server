import csv
import logging
from collections import Counter
from pathlib import Path

from src.config import (
    AD_ACCOUNT_ID,
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


def register(mcp, services=None):
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
        mode: str = "overwrite",
    ) -> str:
        """
        توليد تقرير أداء على مستوى الحملات كملف CSV أو Excel.
        format: csv | excel. filename: اسم الملف (بدون امتداد).
        mode: overwrite | append (incremental — يلحق الصفوف بملف موجود بدلاً من الكتابة فوقه)
        """
        try:
            ensure_report_dir()
            metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
            from src.core.services import Services
            from src.services.reports_service import ReportsService

            _rsvc = ReportsService(services) if services is not None else ReportsService(Services.default())
            rows = _rsvc.fetch_campaign_rows(AD_ACCOUNT_ID, date_preset, metric_list)
            base = filename or f"campaign_report_{date_preset}"
            if filename:
                try:
                    base = sanitize_filename(base)
                except ValueError as e:
                    return json_dumps({"error": f"اسم ملف غير صالح: {e}"})
            # Incremental append: merge with existing file if mode=append
            if mode == "append":
                ext = ".xlsx" if format == "excel" else ".csv"
                path = Path(REPORT_DIR) / f"{base}{ext}"
                if path.exists() and format == "csv":
                    try:
                        existing = []
                        with path.open("r", encoding="utf-8", newline="") as fh:
                            reader = csv.DictReader(fh)
                            existing = list(reader)
                        # Deduplicate by campaign_name
                        seen = {r.get("campaign_name") for r in existing}
                        rows = existing + [r for r in rows if r.get("campaign_name") not in seen]
                    except Exception:
                        pass
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
            from src.core.services import Services
            from src.services.reports_service import ReportsService

            svc = ReportsService(services) if services is not None else ReportsService(Services.default())
            out = svc.account_summary(date_preset)
            return json_dumps(out)
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
            from src.helpers import init_meta_api

            init_meta_api()
            from src.core.services import Services
            from src.services.reports_service import ReportsService

            _rsvc = ReportsService(services) if services is not None else ReportsService(Services.default())
            raw_rows = _rsvc.fetch_instagram_report_rows(limit)
            rows = []
            for item in raw_rows:
                caption = item.get("caption", "") or ""
                caption_short = (
                    (caption[:CAPTION_TRUNCATE_LENGTH] + "...") if len(caption) > CAPTION_TRUNCATE_LENGTH else caption
                )
                item["caption"] = caption_short
                rows.append(item)

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
            from src.core.services import Services
            from src.services.reports_service import ReportsService

            svc = ReportsService(services) if services is not None else ReportsService(Services.default())
            out = svc.generate_page_report(format, filename)
            return json_dumps(out)
        except Exception as e:
            return json_dumps(handle_error(e, "generate_page_report"))

    @mcp.tool()
    @concurrency_limit()
    def export_report_to_google_sheets(
        filename: str,
        spreadsheet_id: str,
        worksheet: str = "Sheet1",
        credentials_path: str = "",
    ) -> str:
        """
        تصدير تقرير CSV موجود إلى Google Sheets.
        filename: اسم الملف داخل reports/ (مثال campaign_report_last_30d.csv) أو مسار نسبي
        spreadsheet_id: معرف جدول Google Sheets (من الرابط)
        worksheet: اسم الورقة الهدف (تُنشأ إن لم توجد)
        credentials_path: مسار JSON لحساب الخدمة (اختياري — افتراضي GOOGLE_APPLICATION_CREDENTIALS)
        يتطلب: pip install gspread google-auth
        """
        try:
            from src.core.services import Services
            from src.services.reports_service import ReportsService

            svc = ReportsService(services) if services is not None else ReportsService(Services.default())
            out = svc.export_report_to_google_sheets(filename, spreadsheet_id, worksheet, credentials_path)
            return json_dumps(out)
        except Exception as e:
            return json_dumps(handle_error(e, "export_report_to_google_sheets"))

    @mcp.resource("reports://overview")
    async def reports_resource() -> str:
        """قائمة التقارير."""
        try:
            # Lightweight per-module overview (calls existing list tool pattern)
            return json_dumps({"module": "reports", "resource": "reports://overview", "hint": "قائمة التقارير"})
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "reports://overview"))

    @mcp.prompt()
    def report_customization_prompt(topic: str = "reports") -> str:
        """تخصيص تقرير."""
        return "ساعد في تخصيص تقرير لـ " + topic + " — خصص تقرير {report_type} (وحدة reports)"

    @mcp.prompt()
    def marketing_report_prompt(date_range: str) -> str:
        """إنشاء تقرير أداء تسويقي."""
        return (
            f"أُنشئ تقرير أداء تسويقي مفصل للفترة: {date_range}. "
            "استخدم أدوات التحليلات (get_campaign_insights وغيرها) واذكر: الإنفاق، النقرات، "
            "نسبة النقر (CTR)، التكلفة لكل نقرة (CPC)، وأفضل الحملات أداءً، مع توصيات للتحسين."
        )

    @mcp.resource("reports://templates")
    async def reports_extra_resource() -> str:
        """قوالب التقارير."""
        try:
            return json_dumps({"module": "reports", "resource": "reports://templates", "hint": "قوالب التقارير"})
        except Exception as e:
            from src.helpers import handle_error

            return json_dumps(handle_error(e, "reports://templates"))

    @mcp.prompt()
    def report_schedule_prompt(topic: str = "reports") -> str:
        """جدولة تقرير."""
        return "ساعد في جدولة تقرير لـ " + topic + " — جدول تقرير {report_type} (وحدة reports)"
