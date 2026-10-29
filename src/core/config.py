"""Typed application configuration (Pydantic Settings)."""

from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # Credentials
    fb_access_token: str = Field(default="", alias="FB_ACCESS_TOKEN")
    fb_page_access_token: str = Field(default="", alias="FB_PAGE_ACCESS_TOKEN")
    fb_ad_account_id: str = Field(default="", alias="FB_AD_ACCOUNT_ID")
    fb_ad_account_ids: str = Field(default="", alias="FB_AD_ACCOUNT_IDS")
    fb_page_id: str = Field(default="", alias="FB_PAGE_ID")
    fb_ig_user_id: str = Field(default="", alias="FB_IG_USER_ID")
    fb_business_id: str = Field(default="", alias="FB_BUSINESS_ID")
    fb_commerce_account_id: str = Field(default="", alias="FB_COMMERCE_ACCOUNT_ID")
    fb_app_id: str = Field(default="", alias="FB_APP_ID")
    fb_app_secret: str = Field(default="", alias="FB_APP_SECRET")
    fb_waba_id: str = Field(default="", alias="FB_WABA_ID")
    fb_whatsapp_phone_number_id: str = Field(default="", alias="FB_WHATSAPP_PHONE_NUMBER_ID")

    fb_api_version: str = Field(default="v27.0", alias="FB_API_VERSION")
    graph_version: str = "v27.0"

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent.parent
    report_dir: Path | None = None

    # Guardrails
    enable_writes: bool = Field(default=False, alias="FB_ENABLE_WRITES")
    dry_run: bool = Field(default=False, alias="FB_DRY_RUN")
    ads_allow_activate: bool = Field(default=False, alias="FB_ADS_ALLOW_ACTIVATE")
    max_daily_budget: int = Field(default=0, alias="FB_ADS_MAX_DAILY_BUDGET")
    max_lifetime_budget: int = Field(default=0, alias="FB_ADS_MAX_LIFETIME_BUDGET")
    max_spend_cap: int = Field(default=0, alias="FB_ADS_MAX_SPEND_CAP")
    confirm_writes: bool = Field(default=False, alias="FB_CONFIRM_WRITES")

    # RBAC
    mcp_allowed_tasks: str = Field(default="ADVERTISE,ANALYZE,MANAGE,DRAFT", alias="FB_MCP_ALLOWED_TASKS")

    # Webhook
    meta_webhook_verify_token: str = Field(default="", alias="FB_META_WEBHOOK_VERIFY_TOKEN")
    webhook_port: int = Field(default=8080, alias="FB_WEBHOOK_PORT")

    # Scale
    max_concurrent: int = Field(default=4, alias="FB_MAX_CONCURRENT")
    adaptive_throttle: bool = Field(default=True, alias="FB_ADAPTIVE_THROTTLE")
    auto_run_webhook_automations: bool = Field(default=False, alias="FB_AUTO_RUN_WEBHOOK_AUTOMATIONS")

    # Scheduler
    scheduler_db_url: str = Field(default="", alias="FB_SCHEDULER_DB_URL")

    # Media hosting
    cloudinary_url: str = Field(default="", alias="CLOUDINARY_URL")
    cloudinary_cloud_name: str = Field(default="", alias="CLOUDINARY_CLOUD_NAME")
    cloudinary_api_key: str = Field(default="", alias="CLOUDINARY_API_KEY")
    cloudinary_api_secret: str = Field(default="", alias="CLOUDINARY_API_SECRET")
    s3_bucket: str = Field(default="", alias="S3_BUCKET")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")

    # Analytics / Yemen
    analytics_db_url: str = Field(default="sqlite:///reports/analytics.db", alias="FB_ANALYTICS_DB_URL")
    analytics_retention_days: int = Field(default=1110, alias="FB_ANALYTICS_RETENTION_DAYS")
    tz_name: str = Field(default="Asia/Aden", alias="FB_TZ")
    currency_default: str = Field(default="YER", alias="FB_CURRENCY_DEFAULT")
    phone_country_code: str = Field(default="+967", alias="FB_PHONE_COUNTRY_CODE")
    enable_ocr: bool = Field(default=False, alias="FB_ENABLE_OCR")
    cross_platform_tiktok: bool = Field(default=False, alias="FB_CROSS_PLATFORM_TIKTOK")
    cross_platform_whatsapp_scrape: bool = Field(default=False, alias="FB_CROSS_PLATFORM_WHATSAPP_SCRAPE")
    attribution_window: str = Field(default="7d_click_1d_view", alias="FB_ATTRIBUTION_WINDOW")

    @field_validator("graph_version", mode="before")
    @classmethod
    def _gv(cls, v):
        return v or "v27.0"

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        if not self.report_dir:
            self.report_dir = self.base_dir / "reports"  # type: ignore[operator]
        if not self.graph_version or self.graph_version == "v27.0":
            self.graph_version = self.fb_api_version or "v27.0"
        if not self.scheduler_db_url:
            self.scheduler_db_url = f"sqlite:///{(self.report_dir / 'scheduler.db').as_posix()}"
        # ad account ids list
        object.__setattr__(self, "_ad_account_ids", self._parse_ids())

    def _parse_ids(self) -> list[str]:
        ids = [s.strip() for s in self.fb_ad_account_ids.split(",") if s.strip()]
        if self.fb_ad_account_id and self.fb_ad_account_id not in ids:
            ids.insert(0, self.fb_ad_account_id)
        return ids

    @property
    def ad_account_ids(self) -> list[str]:
        return getattr(self, "_ad_account_ids", [])

    def resolve_ad_account_id(self, override: str = "") -> str:
        if override and override.strip():
            return override.strip()
        if self.ad_account_ids:
            return self.ad_account_ids[0]
        return self.fb_ad_account_id

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.tz_name)

    @property
    def allowed_tasks(self) -> list[str]:
        return [s.strip().upper() for s in self.mcp_allowed_tasks.split(",") if s.strip()]

    @property
    def access_token(self) -> str:
        return self.fb_access_token

    @property
    def page_id(self) -> str:
        return self.fb_page_id

    @property
    def instagram_business_id(self) -> str:
        return self.fb_ig_user_id

    @property
    def business_id(self) -> str:
        return self.fb_business_id
