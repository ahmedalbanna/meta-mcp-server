# Services Layer — `src/services/`

> Phase B/C: business logic extracted from module tools into dedicated service classes.
> Each service receives a `Services` container (dependency injection) and exposes plain
> methods that the module `register()` functions delegate to.

## Architecture

```
server.py
  └─ Services.default()  (config, api adapter, storage, clock)
       └─ module.register(mcp, services)
            └─ ModuleService(services)
                 └─ services.api.get/post/delete(...)   # MetaApiClient port
                 └─ services.config.*                   # Pydantic BaseSettings
                 └─ services.storage.*                  # Storage port (SQLite)
```

## Services container (`src/core/services.py`)

| Field | Type | Description |
|---|---|---|
| `config` | `Config` | Pydantic settings from `.env`. |
| `api` | `MetaApiClient` | Graph API adapter (port `src/core/ports.py`). |
| `storage` | `Storage` | SQLite storage port (`src/persistence.py`). |
| `clock` | `Clock` | System clock (`src/infra/clock.py`). |
| `throttle` | `Throttle` | Optional adaptive throttle. |

```python
from src.core.services import Services

services = Services.default()
# services.config.fb_ad_account_id
# services.api.get(f"{acct}/insights", params)
```

## Available services

| Service module | Class | Backs module |
|---|---|---|
| `ads_service` | `AdsService` | `ads` |
| `adsets_service` | `AdsetsService` | `adsets` |
| `analytics_service` | `AnalyticsService` | `analytics` |
| `audiences_service` | `AudiencesService` | `audiences` |
| `automation_service` | `AutomationService` | `automation` |
| `breakdowns_service` | `BreakdownsService` | `breakdowns` |
| `business_service` | `BusinessService` | `business` |
| `campaigns_service` | `CampaignsService` | `campaigns` |
| `catalog_service` | `CatalogService` | `catalog` |
| `competitor_service` | `CompetitorService` | `competitors` |
| `competitor_content_service` | `CompetitorContentService` | `competitor_content` |
| `competitor_catalog_service` | `CompetitorCatalogService` | `competitor_catalog` |
| `content_tools_service` | `ContentToolsService` | `content_tools` |
| `creatives_service` | `CreativesService` | `creatives` |
| `cross_platform_service` | `CrossPlatformService` | `cross_platform` |
| `discovery_service` | `DiscoveryService` | `discovery` |
| `events_service` | `EventsService` | `events` |
| `finance_service` | `FinanceService` | `finance` |
| `insights_service` | `InsightsService` | `insights` |
| `instagram_service` | `InstagramService` | `instagram` |
| `leads_service` | `LeadsService` | `leads` |
| `media_hosting_service` | `MediaHostingService` | `media_hosting` |
| `media_tools_service` | `MediaToolsService` | `media_tools` |
| `messenger_service` | `MessengerService` | `messenger` |
| `metrics_service` | `MetricsService` | `metrics` |
| `page_builder_service` | `PageBuilderService` | `page_builder` |
| `pages_service` | `PagesService` | `pages` |
| `reports_service` | `ReportsService` | `reports` |
| `scheduler_service` | `SchedulerService` | `scheduler` |
| `webhook_automations_service` | `WebhookAutomationsService` | `webhook_automations` |
| `whatsapp_service` | `WhatsAppService` | `whatsapp` |
| `yemen_bundle_service` | `YemenBundleService` | `yemen_bundle` |

Shell services (TODO: extract logic):
- `hashtags_service`, `media_hosting_service`

## Ports (`src/core/ports.py`)

| Port | Methods |
|---|---|
| `MetaApiClient` | `get(path, params)`, `post(path, params)`, `delete(path, params)`, `page_get(page_id, params)`, `page_post(page_id, params)`, `page_delete(page_id, params)` |
| `Storage` | `upsert_daily_fact(...)`, `query_daily_facts(...)`, `query_daily_facts_all_entities(...)`, `upsert_competitor_snapshot(...)`, `query_competitor_snapshots(...)`, `upsert_monthly_snapshot(...)` |
| `Clock` | `now()`, `today()` |
| `Throttle` | `acquire()`, `release()` |
