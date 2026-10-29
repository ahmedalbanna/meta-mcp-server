"""Reports service (Phase B)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.core.services import Services
from src.reports import IG_MEDIA_METRICS, _to_numeric, _write_csv, _write_excel
from src.utils import sanitize_filename, sanitize_path


class ReportsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api

    def fetch_campaign_rows(self, object_id: str, preset: str, metrics: list) -> list:
        data = self.api.get(f"{object_id}/insights", {"date_preset": preset, "fields": ["campaign_name", *metrics]})
        rows = []
        for item in data.get("data", []) if isinstance(data, dict) else []:
            row = {"campaign_name": item.get("campaign_name", "N/A")}
            for m in metrics:
                row[m] = item.get(m, 0)
            rows.append(row)
        return rows

    def fetch_instagram_report_rows(self, limit: int = 25) -> list:
        ig = self.config.instagram_business_id
        media = self.api.get(f"{ig}/media", {"fields": "id,caption,media_type,timestamp,permalink", "limit": limit})
        rows = []
        for item in media.get("data", []) if isinstance(media, dict) else []:
            mid = item.get("id")
            caption = item.get("caption", "")
            row = {
                "id": mid,
                "caption": caption,
                "media_type": item.get("media_type", ""),
                "timestamp": item.get("timestamp", ""),
                "permalink": item.get("permalink", ""),
            }
            try:
                insights = self.api.get(f"{mid}/insights", {"metric": ",".join(IG_MEDIA_METRICS)})
                for ins in insights.get("data", []) if isinstance(insights, dict) else []:
                    name = ins.get("name", "")
                    values = ins.get("values", [])
                    row[name] = values[-1].get("value", 0) if values else 0
            except Exception:
                pass
            rows.append(row)
        return rows

    def account_summary(self, date_preset: str = "last_30d") -> dict[str, Any]:
        acct = self.config.fb_ad_account_id
        data = self.api.get(
            f"{acct}/insights",
            {
                "date_preset": date_preset,
                "fields": "campaign_name,spend,impressions,clicks,ctr,cpc,reach",
            },
        )
        rows = []
        for item in data.get("data", []) if isinstance(data, dict) else []:
            row = {"campaign_name": item.get("campaign_name", "N/A")}
            for m in ["spend", "impressions", "clicks", "ctr", "cpc", "reach"]:
                row[m] = item.get(m, 0)
            rows.append(row)
        if not rows:
            return {"message": "لا توجد بيانات", "date_preset": date_preset}
        metrics = ["spend", "impressions", "clicks", "ctr", "cpc", "reach"]
        summary: dict[str, Any] = {"date_preset": date_preset, "campaigns": len(rows)}
        for m in metrics:
            total = sum(_to_numeric(r.get(m, 0)) for r in rows)
            summary[f"total_{m}"] = round(total, 4)
        spend = float(summary.get("total_spend", 0) or 0)
        clicks = float(summary.get("total_clicks", 0) or 0)
        if clicks:
            summary["avg_cpc"] = round(spend / clicks, 4)
        best = max(rows, key=lambda r: _to_numeric(r.get("spend", 0)))
        summary["top_campaign"] = best.get("campaign_name", "N/A")
        return summary

    def generate_page_report(self, format: str = "csv", filename: str = "") -> dict[str, Any]:
        from src.utils import to_dict as _td

        report_dir = self.config.report_dir or Path("reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        info = self.api.page_get(
            self.config.page_id,
            {"fields": "name,fan_count,category,about,link"},
        )
        data = _td(info)
        rows = [data]
        base = filename or "page_report"
        if filename:
            try:
                base = sanitize_filename(base)
            except ValueError as e:
                return {"error": f"اسم ملف غير صالح: {e}"}
        if format == "excel":
            path = report_dir / f"{base}.xlsx"
            _write_excel(path, rows)
        else:
            path = report_dir / f"{base}.csv"
            _write_csv(path, rows)
        return {"success": True, "file": str(path), "rows": len(rows)}

    def export_report_to_google_sheets(
        self, filename: str, spreadsheet_id: str, worksheet: str = "Sheet1", credentials_path: str = ""
    ) -> dict[str, Any]:
        if not filename:
            return {"error": "filename مطلوب"}
        if not spreadsheet_id:
            return {"error": "spreadsheet_id مطلوب"}
        report_dir = self.config.report_dir or Path("reports")
        try:
            csv_path = sanitize_path(filename, report_dir)
        except ValueError as e:
            return {"error": f"مسار غير صالح: {e}"}
        if not csv_path.is_file():
            alt = sanitize_path(filename + ".csv", report_dir) if not filename.endswith(".csv") else None
            if alt and alt.is_file():
                csv_path = alt
            else:
                return {"error": f"الملف غير موجود: {csv_path}"}
        with csv_path.open("r", encoding="utf-8", newline="") as fh:
            import csv as _csv

            reader = list(_csv.reader(fh))
        if not reader:
            return {"error": "الملف فارغ"}
        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError:
            return {
                "error": "gspread غير مثبت. ثبّت: pip install gspread google-auth",
                "hint": "أو صدّر يدويًا عبر تحميل CSV إلى Sheets",
                "csv_file": str(csv_path),
                "rows": len(reader) - 1,
            }
        cred_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        if not cred_path or not Path(cred_path).is_file():
            return {
                "error": "ملف credentials غير موجود. حدد credentials_path أو اضبط GOOGLE_APPLICATION_CREDENTIALS",
                "hint": "أنشئ Service Account في Google Cloud > APIs & Services > Credentials",
            }
        creds = Credentials.from_service_account_file(
            cred_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        client = gspread.authorize(creds)
        sh = client.open_by_key(spreadsheet_id)
        try:
            ws = sh.worksheet(worksheet)
            ws.clear()
        except Exception:
            ws = sh.add_worksheet(title=worksheet, rows=len(reader) + 10, cols=len(reader[0]) + 5)
        ws.update(reader)
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "worksheet": worksheet,
            "rows": len(reader) - 1,
            "csv_source": str(csv_path),
        }
