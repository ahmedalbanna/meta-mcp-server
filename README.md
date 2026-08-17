# Meta Marketing MCP Server

خادم MCP شامل باللغة Python لإدارة التسويق على **فيسبوك وإنستغرام** عبر `facebook-business` SDK و `FastMCP`.

## المزايا (87 أداة + 3 موارد + 2 مطالبات)

| الوحدة | الأدوات |
|---|---|
| الاكتشاف `discovery` | list_pages, list_ad_accounts, discover_ig_user, debug_access_token, config_status |
| الحملات `campaigns` | list, get, create, update_status, update_budget, delete |
| المجموعات `adsets` | list, get, create, update_status, update_budget, update_targeting |
| الإعلانات `ads` | list, get, create, update_status, create_creative, upload_image, upload_video |
| التحليلات `insights` | account / campaign / adset / ad (date_preset + metrics مخصصة) |
| التقارير `reports` | generate_campaign_report, account_summary, generate_instagram_report, generate_page_report |
| الجماهير `audiences` | list, create, add_users, remove_users, create_lookalike |
| الصفحات `pages` | get_info, list_posts, publish_text, publish_photo, schedule, update_post_caption, **delete_post**, post_insights, post_comments, reply_comment, delete_comment, albums, album_photos, get_insights, **update_cover** |
| إنستغرام `instagram` | get_account, list_media, get_media, hashtag_search, hashtag_media, mentions, get_media_children, download_media, publish_photo/video/reel/carousel, update_media_caption, insights, comments, reply_comment, delete_comment, hide_comment, add_media_comment, delete_media |
| الأتمتة `automation` | list_rules, create_rule, create_simple_rule, delete_rule, history |
| المحفظة `finance` | get_balance, get_spend_cap, update_spend_cap, get_transactions, get_payment_methods, get_business_info, list_account_users, assign_user, remove_user |

> أدوات الصفحات تستخدم **توكن الصفحة** (مشتق تلقائيًا من `FB_ACCESS_TOKEN` عبر `me/accounts`).
> لذلك `list_page_posts` و `publish_page_photo` و `update_page_post_caption` و `delete_page_post`
> تعمل حتى لو كان توكن النظام بلا صلاحية نشر مباشرة على الصفحة.

## المتطلبات

- Python 3.10+
- Access Token بصلاحيات:
  - `ads_management`, `ads_read`, `business_management`
  - `pages_read_engagement`, `pages_manage_posts`, `pages_manage_ads`
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
| `FB_IG_USER_ID` | معرف Instagram Business — اكتشفه بأداة `discover_ig_user` |
| `FB_ENABLE_WRITES` | `false` = منع كل عمليات الكتابة (افتراضي آمن) |
| `FB_DRY_RUN` | `true` = محاكاة الكتابة بدون إرسال |
| `FB_ADS_ALLOW_ACTIVATE` | `true` = السماح بتفعيل الحملات (متطلب أمان إضافي) |
| `FB_ADS_MAX_DAILY_BUDGET` / `FB_ADS_MAX_LIFETIME_BUDGET` | حدود الإنفاق بالسنات (0 = بدون حد) |

> كل عمليات الكتابة تتجاوز 3 حراس أمان: تفعيل الكتابة، حدّ الميزانية، وسماح التفعيل.
> اكتشاف المعرفات: `list_pages` ← `list_ad_accounts` ← `discover_ig_user` ثم عبّئ `.env` وأعد تشغيل الخادم.

## التشغيل والاختبار

```bash
# وضع التطوير مع Inspector (فتح المتصفح)
mcp dev server.py

# اختبار البروتوكول مباشرة (سطر الأوامر)
python server.py
```

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
- التوكن يُقرأ من `.env` فقط ولا يظهر في الكود. لا تشاركه ولا ترفعه على GitHub.
- بعض أدوات القواعد التلقائية وطرق الدفع تعتمد على دعم Meta للحقول؛ عند الفشل تُعاد رسالة إرشادية.

## هيكل المشروع

```
server.py                # نقطة الدخول
src/
  config.py              # تحميل .env والتحقق (أسماء FB_*)
  helpers.py             # تهيئة SDK + تحويل + أخطاء + api_call + حراس الكتابة
  discovery.py           # اكتشاف المعرّفات (pages / ad_accounts / IG / token / config)
  campaigns.py adsets.py ads.py
  insights.py reports.py
  audiences.py pages.py instagram.py
  automation.py finance.py
  resources_prompts.py
```
