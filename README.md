# Meta Marketing MCP Server

خادم MCP شامل باللغة Python لإدارة التسويق على **فيسبوك وإنستغرام** عبر `facebook-business` SDK و `FastMCP`.

## المزايا (201 أداة + 44 موارد + 44 مطالبات)

| الوحدة | الأدوات |
|---|---|
| الاكتشاف `discovery` | list_pages, list_ad_accounts, discover_ig_user, debug_access_token, config_status |
| الحملات `campaigns` | list, get, create, update_status, update_budget, delete |
| المجموعات `adsets` | list, get, create, update_status, update_budget, update_targeting |
| الإعلانات `ads` | list, get, create, update_status, create_creative, upload_image, upload_video |
| التحليلات `insights` | account / campaign / adset / ad (date_preset + metrics مخصصة) |
| تجزئة التحليلات `breakdowns` | account / campaign / adset / ad مجزأة (عمر/جنس/دولة/موضع/جهاز) + time_increment + attribution |
| التقارير `reports` | generate_campaign_report, account_summary, generate_instagram_report, generate_page_report |
| الرصاص والنماذج `leads` | list_lead_gen_forms, get_lead_gen_form, get_form_leads, get_lead, create_lead_gen_form |
| الجماهير `audiences` | list, create, add_users (SHA-256), remove_users, upload_custom_audience_csv, create_lookalike (SIMILARITY/ENGAGEMENT/VALUE) |
| الصفحات `pages` | get_info, list_posts, publish_text, publish_photo, schedule, update_post_caption, delete_post, post_insights, post_comments, reply_comment, delete_comment, albums, album_photos, get_insights, update_cover, **events (list/get/create), ratings, roles, CTA (get/update)** |
| إنستغرام `instagram` | get_account, list_media, get_media, hashtag_search, hashtag_media, mentions, get_media_children, download_media, publish_photo/video/reel/carousel, update_media_caption, insights, comments, reply_comment, delete_comment, hide_comment, add_media_comment, delete_media, **stories, ban_commenter, mute_commenter, conversations (DMs), messages, send_dm** |
| ماسنجر `messenger` | list_conversations, get_conversation, list_conversation_messages, get_messenger_message, send_messenger_message, mark_messenger_seen, set_messenger_typing |
| واتساب `whatsapp` | list/get_phone_numbers, list/get_message_templates (معتمد)، create_template, send_text, send_template |
| الأتمتة `automation` | list_rules, create_rule, create_simple_rule, delete_rule, history |
| المحفظة `finance` | get_balance, get_spend_cap, update_spend_cap, get_transactions, get_payment_methods, get_business_info, list_account_users, assign_user, remove_user |
| الكتالوج والتجارة `catalog` | list/get/create/delete_catalog, get_catalog_settings, product_sets (list/get/create/delete), products (list/get/create/update/delete/batch), feeds (create/delete + get_uploads), commerce (get_merchant_settings, list/get_orders), get_catalog_insights |
| مستخدمو الأعمال `business` | list_business_users, get_business_user, invite_business_user, update_business_user_role, delete_business_user |
| الإبداع والمعاينات `creatives` | generate_ad_preview, generate_creative_preview, generate_creative_template |

> أدوات الصفحات تستخدم **توكن الصفحة** (مشتق تلقائيًا من `FB_ACCESS_TOKEN` عبر `me/accounts`).
> لذلك `list_page_posts` و `publish_page_photo` و `update_page_post_caption` و `delete_page_post`
> تعمل حتى لو كان توكن النظام بلا صلاحية نشر مباشرة على الصفحة.
> أدوات `messenger` تستخدم توكن الصفحة أيضًا، بينما تستخدم `instagram` و `whatsapp` توكن النظام.

## المتطلبات

- Python 3.10+
- Access Token بصلاحيات:
  - `ads_management`, `ads_read`, `business_management`
  - `pages_read_engagement`, `pages_manage_posts`, `pages_manage_ads`
  - `pages_messaging` (ماسنجر), `instagram_manage_messages` (رسائل إنستغرام المباشرة)
  - `whatsapp_business_management`, `whatsapp_business_messaging` (واتساب)
  - `instagram_basic`, `instagram_content_publish`, `instagram_manage_insights`
  - `read_insights`
  - للمحفظة: `business_management` + دور Admin/Finance Editor في Business Manager

## الإعداد

```bash
cd meta-mcp-server
cp .env.example .env
# املأ المفاتيح في .env (أسماء FB_* أدناه)
pip install -r requirements.txt
```

### متغيرات `.env`

| المتغير | الوصف |
|---|---|
| `FB_ACCESS_TOKEN` | توكن النظام (مطلوب) |
| `FB_PAGE_ACCESS_TOKEN` | (اختياري) توكن الصفحة الصريح — إن تُرك فارغًا يُشتق تلقائيًا من `me/accounts` |
| `FB_APP_ID`, `FB_APP_SECRET` | معرفات التطبيق (مطلوبان لأداة debug_access_token) |
| `FB_API_VERSION` | إصدار Graph API (افتراضي `v26.0`) |
| `FB_PAGE_ID` | معرف الصفحة — اكتشفه بأداة `list_pages` |
| `FB_AD_ACCOUNT_ID` | معرف الحساب الإعلاني (مثال `act_...`) — اكتشفه بأداة `list_ad_accounts` |
| `FB_AD_ACCOUNT_IDS` | قائمة حسابات إعلانية مفصولة بفواصل لـ multi-account (Phase 8.1) — مثال `act_1,act_2` |
| `FB_IG_USER_ID` | معرف Instagram Business — اكتشفه بأداة `discover_ig_user` |
| `FB_WABA_ID` | معرف حساب واتساب للأعمال (WABA) — مطلوب لأدوات `whatsapp` |
| `FB_WHATSAPP_PHONE_NUMBER_ID` | معرف رقم الهاتف المرسل في واتساب — مطلوب لإرسال الرسائل |
| `FB_BUSINESS_ID` | معرف النشاط التجاري — مطلوب لأدوات الكتالوج والتجارة (`catalog`) |
| `FB_COMMERCE_ACCOUNT_ID` | معرف حساب المتجر (اختياري) — لطلبات التجارة، يكتشف بأداة `get_commerce_merchant_settings` |
| `FB_META_WEBHOOK_VERIFY_TOKEN` | (اختياري) رمز تحقق استقبال Webhooks — مطلوب لتشغيل `webhook_server.py` |
| `FB_WEBHOOK_PORT` | (اختياري) منفذ خادم Webhooks (افتراضي `8080`) |
| `FB_ENABLE_WRITES` | `false` = منع كل عمليات الكتابة (افتراضي آمن) |
| `FB_DRY_RUN` | `true` = محاكاة الكتابة بدون إرسال (يُظهر `diff` المعاينة) |
| `FB_ADS_ALLOW_ACTIVATE` | `true` = السماح بتفعيل الحملات (متطلب أمان إضافي) |
| `FB_ADS_MAX_DAILY_BUDGET` / `FB_ADS_MAX_LIFETIME_BUDGET` | حدود الإنفاق بالسنات (0 = بدون حد) |
| `FB_MAX_CONCURRENT` | حد التوازي لطلبات Graph API (افتراضي `4`, نطاق 1–20) |
| `FB_CONFIRM_WRITES` | `true` = طلب `confirm='yes'` للعمليات الحذفية (حماية إضافية) |
| `FB_ADAPTIVE_THROTTLE` | `true` = تروق تكيفي عند Rate Limit (نوم إضافي + cooldown) |
| `FB_AUTO_RUN_WEBHOOK_AUTOMATIONS` | `true` = تشغيل أتمتة Webhook تلقائيًا عند استقبال حدث |
| `FB_MCP_ALLOWED_TASKS` | قائمة مهام RBAC مفصولة بفواصل (Phase 8.2) — مثال `ADVERTISE,ANALYZE` (افتراضي `ADVERTISE,ANALYZE,MANAGE,DRAFT`) |
| `FB_SCHEDULER_DB_URL` | رابط قاعدة بيانات المجدول (Phase 8.3) — افتراضي `sqlite:///reports/scheduler.db` |

> كل عمليات الكتابة تتجاوز 5 حراس أمان: تفعيل الكتابة، حدّ الميزانية، وسماح التفعيل، ودراي-رن مع معاينة الفروق، وتأكيد الحذف (`FB_CONFIRM_WRITES`).
> اكتشاف المعرفات: `list_pages` ← `list_ad_accounts` ← `discover_ig_user` ثم عبّئ `.env` وأعد تشغيل الخادم.

## التشغيل والاختبار

```bash
# وضع التطوير مع Inspector (فتح المتصفح)
mcp dev server.py

# اختبار البروتوكول مباشرة (سطر الأوامر)
python server.py

# فحص إعدادات .env (لا يطبع أي أسرار)
python scripts/validate_config.py
```

### الاختبارات الآلية

```bash
pip install -r requirements-dev.txt
pytest -q
```

الاختبارات لا تتصل بالإنترنت: تحاكي SDK بالكامل وتتحقق من تسجيل كل الوحدات
ومن أن كل أداة تعيد JSON صالحًا (`tests/test_server_import.py`,
`tests/test_utils.py`, `tests/test_tools_smoke.py`، و `tests/test_webhook.py`
لمستقبل الأحداث).

## استقبال Webhooks

خادم FastAPI مستقل يستقبل أحداث Meta في الوقت الفعلي ويخزّنها في `reports/webhooks/`:

```bash
# عيّن رمز التحقق في .env ثم شغّل:
FB_META_WEBHOOK_VERIFY_TOKEN=my_secret python webhook_server.py
```

- `GET /webhook/meta` — مصافحة التحقق (تُستخدم عند تسجيل التطبيق في Meta).
- `POST /webhook/meta` — استقبال الأحداث وحفظها JSON (مع `_correlation_id` و `FB_AUTO_RUN_WEBHOOK_AUTOMATIONS`).
- `GET /metrics` — مقاييس Prometheus (`mcp_tool_calls_total`, `meta_api_calls_total`, `throttle_concurrent`, `process_uptime_seconds`).
- `GET /dashboard` — لوحة HTML لآخر 20 حدثًا + المقاييس (تحمي بـ `FB_MCP_TOKEN` Bearer إن ضُبط) — `Phase 4.3`.
- `GET /health` — فحص حيوية.

أضف النقاط أعلاه كـ **Callback URL** لأي كائن مشترك (صفحة، Instagram، أداء الإعلانات...)
في Meta Developer، وعيّن `hub.verify_token` بنفس القيمة في `.env`.

> **Scale knobs (Phase 4.4):** `FB_MAX_CONCURRENT` (افتراضي 4، 1–20) + `FB_ADAPTIVE_THROTTLE=true` (cooldown 5s×attempt عند Rate Limit). التوازي محصور بـ `src/throttle.py:24` semaphore ويُقاس عبر `throttle_concurrent` في `/metrics`. استخدم `get_metrics` (MCP) أو `GET /metrics` لمراقبة `meta_rate_limit_total`.
> **Persistence (Phase 4.5):** `reports/webhooks/event_*.json` محفوظة بحد 500 ملف (أقدم ملف يُحذف تلقائيًا)، `reports/` و `media/` مربوطة كـ volume في `docker-compose.yml` (volumes `reports/` + `media/`).

## النشر باستخدام Docker

```bash
# بناء الصورة وتشغيل الحاوية (MCP + مستقبل Webhooks معًا)
docker compose up -d --build
```

| الخدمة | المنفذ داخل الحاوية | المنفذ على المضيف |
|---|---|---|
| MCP server (streamable-http) | 8000 | **18000** |
| Webhook receiver | 8080 | **18080** |

- **MCP endpoint:** `http://<host>:18000/mcp`
- **Webhook handshake:** `GET http://<host>:18080/webhook/meta?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...`
- **Webhook ingest:** `POST http://<host>:18080/webhook/meta`
- عدّل تعيين المنافذ في `docker-compose.yml` إن كانت 18000/18080 مشغولة على مضيفك.

المتغيرات تُقرأ من `.env` تلقائيًا (يُركَّب داخل الحاوية كـ `/app/.env:ro`)، ويجب ضبط `FB_META_WEBHOOK_VERIFY_TOKEN` و `FB_WEBHOOK_PORT=8080` فيه قبل تسجيل الـ Callback URL في Meta Developer.

> ملاحظة: `.dockerignore` يستثني الأسرار (`*.env`) ولا تُنسخ أبدًا داخل الصورة.

## الربط مع Claude Desktop

أضف إلى `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "meta-marketing-pro": {
      "command": "/path/to/venv/bin/python",
      "args": ["/teamspace/studios/this_studio/meta-mcp-server/server.py"],
      "env": {
        "FB_ACCESS_TOKEN": "ضع_التوكن_هنا",
        "FB_APP_ID": "1234567890",
        "FB_APP_SECRET": "سري_التطبيق",
        "FB_PAGE_ID": "1234567890",
        "FB_AD_ACCOUNT_ID": "act_123456789",
        "FB_IG_USER_ID": "1234567890"
      }
    }
  }
}
```

> استخدم المسار الكامل لمفسّر Python الذي ثبتّ عليه المكتبات (`which python`).

## الربط مع opencode

أضف إلى `opencode.json` في جذر المشروع:

```json
{
  "mcp": {
    "meta-marketing-pro": {
      "type": "local",
      "command": ["python", "server.py"],
      "environment": {
        "FB_ACCESS_TOKEN": "...",
        "FB_APP_ID": "...",
        "FB_APP_SECRET": "...",
        "FB_PAGE_ID": "...",
        "FB_AD_ACCOUNT_ID": "act_...",
        "FB_IG_USER_ID": "..."
      }
    }
  }
}
```

## ملاحظات وقيود

- **إضافة رصيد / تعديل بطاقات الدفع**: غير مدعومة عبر API — تتم يدويًا في Business Manager.
- **نشر إنستغرام** يتطلب صلاحية `instagram_content_publish` وحساب Instagram Business مرتبط بصفحة.
- **تعديل كابشن منشور إنستغرام منشور**: غير مدعوم نهائيًا من Meta Graph API. الحلول البديلة المتاحة: إضافة الكابشن كتعليق (`add_instagram_media_comment`) أو حذف المنشور وإعادة نشره (`delete_instagram_media` + publish).
- **تعديل نص منشور فيسبوك**: مدعوم عبر `update_page_post_caption`.
- **إنشاء إعلان** يتطلب صفحة مرتبطة بالحساب الإعلاني وصلاحيات عليها.
- **أدوات الإبداع**: `generate_ad_preview`/`generate_creative_preview` تتطلب صلاحيات الإعلانات (`ads_read`) وقد تُرجع HTML فقط في بعض الأشكال.
- **معالجة PII**: كل بريد/هاتف يُرسل إلى الجماهير المخصصة يُشفَّر SHA-256 افتراضيًا (`hash_pii=true`).
- **Webhooks**: يستقبل `webhook_server.py` الأحداث ويخزّنها — يحتاج رمز تحقق مطابقًا لما سجلته في Meta.
- التوكن يُقرأ من `.env` فقط ولا يظهر في الكود. لا تشاركه ولا ترفعه على GitHub.
- بعض أدوات القواعد التلقائية وطرق الدفع تعتمد على دعم Meta للحقول؛ عند الفشل تُعاد رسالة إرشادية.

## أفكار مستقبلية (خارج هذه النسخة)

- لوحة تحكم ويب لمراجعة أحداث Webhooks المخزنة.
- معالجة تلقائية للأحداث (رد فوري على التعليقات، تحديث الرصاص).
- تصدير التقارير إلى Google Sheets.

## هيكل المشروع

```
server.py                # نقطة الدخول
webhook_server.py        # مستقبل Webhooks (FastAPI)
src/
  config.py              # تحميل .env والتحقق (أسماء FB_*)
  helpers.py             # تهيئة SDK + تحويل + أخطاء + api_call + حراس الكتابة
  utils.py               # paginate + retry_on_rate_limit + normalize_pii + cached + سجلات
  discovery.py           # اكتشاف المعرّفات (pages / ad_accounts / IG / token / config)
  campaigns.py adsets.py ads.py
  insights.py breakdowns.py reports.py
  leads.py               # نماذج ورصاصات الجذب
  audiences.py pages.py instagram.py
  messenger.py           # محادثات صفحة Messenger (الوارد + الإرسال)
  whatsapp.py            # واتساب للأعمال (أرقام، قوالب، إرسال)
  automation.py finance.py
  catalog.py             # الكتالوجات / مجموعات المنتجات / المنتجات / الخلاصات / التجارة
  business.py            # مستخدمو Business Manager
  creatives.py           # معاينات الإعلان + قوالب إبداعية
  resources_prompts.py
tests/                   # اختبارات دون اتصال (pytest، SDK مُحاكى)
scripts/validate_config.py  # فحص إعدادات .env
```
