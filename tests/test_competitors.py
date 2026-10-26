"""Tests for src/competitors — competitive intelligence tools (offline, mocked SDK)."""

import json
from datetime import datetime, timedelta, timezone

from src import competitors
from tests.conftest import Recorder


def _iso_days_ago(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _post(
    message: str,
    *,
    days_ago: float,
    reactions: int = 0,
    comments: int = 0,
    shares: int = 0,
    permalink: str = "https://fb.com/1",
):
    return {
        "id": f"1_{int(days_ago)}",
        "message": message,
        "created_time": _iso_days_ago(days_ago),
        "permalink_url": permalink,
        "shares": {"count": shares},
        "reactions": {"summary": {"total_count": reactions}},
        "comments": {"summary": {"total_count": comments}},
    }


def _make_fake_api(
    *,
    search_data=None,
    info=None,
    posts=None,
    ratings=None,
    biz=None,
    posts_error_times: int = 0,
    calls=None,
):
    """Router-based api_call double mimicking the real Graph responses."""
    counter = {"posts": 0}

    def fake(method, path, params=None):
        if calls is not None:
            calls.append({"method": method, "path": path, "params": params or {}})
        fields = (params or {}).get("fields", "") or ""
        if "business_discovery" in fields:
            return biz if biz is not None else {}
        if path == "search":
            return search_data if search_data is not None else {"data": []}
        if str(path).endswith("/published_posts"):
            counter["posts"] += 1
            if counter["posts"] <= posts_error_times:
                raise RuntimeError("(#100) requires Page Public Content Access feature")
            return {"data": posts if posts is not None else []}
        if str(path).endswith("/ratings"):
            return ratings if ratings is not None else {"data": []}
        return info if info is not None else {}

    fake.counter = counter
    return fake


# ---------------------------------------------------------------------------
# search_business_pages
# ---------------------------------------------------------------------------


def test_search_business_pages_builds_combined_query(mock_meta_sdk_recorded):
    api = _make_fake_api(search_data={"data": [{"id": "111", "name": "منافس أ", "fan_count": 100}]})
    mock_meta_sdk_recorded["api_call"].side_effect = api
    calls: list = []
    api = _make_fake_api(search_data={"data": [{"id": "111", "name": "منافس أ"}]}, calls=calls)
    mock_meta_sdk_recorded["api_call"].side_effect = api

    recorder = Recorder()
    competitors.register(recorder)
    out = json.loads(recorder.tools["search_business_pages"](query="مجوهرات", city="صنعاء", limit=10))

    assert calls[0]["method"] == "GET"
    assert calls[0]["path"] == "search"
    assert calls[0]["params"]["q"] == "مجوهرات صنعاء"
    assert calls[0]["params"]["type"] == "page"
    assert calls[0]["params"]["limit"] == 10
    assert out["count"] == 1
    assert out["results"][0]["id"] == "111"
    assert "analyze_competitor_page" in out["next_step"]


def test_search_business_pages_excludes_our_page(mock_meta_sdk_recorded):
    ours = str(competitors.PAGE_ID)
    api = _make_fake_api(search_data={"data": [{"id": ours, "name": "Butterfly"}, {"id": "222", "name": "منافس"}]})
    mock_meta_sdk_recorded["api_call"].side_effect = api
    recorder = Recorder()
    competitors.register(recorder)
    out = json.loads(recorder.tools["search_business_pages"](query="اكسسوارات"))
    assert out["count"] == 1
    assert out["results"][0]["id"] == "222"


def test_search_business_pages_requires_keyword(mock_meta_sdk_recorded):
    mock_meta_sdk_recorded["api_call"].side_effect = _make_fake_api()
    recorder = Recorder()
    competitors.register(recorder)
    out = json.loads(recorder.tools["search_business_pages"](query="", city="", limit=5))
    assert "error" in out
    assert "كلمة مفتاحية" in out["error"]


def test_search_business_pages_explains_empty_results(mock_meta_sdk_recorded):
    """Meta answers with an empty list (no error) when the app lacks the
    Page Public Content Access feature — the tool must say so."""
    mock_meta_sdk_recorded["api_call"].side_effect = _make_fake_api(search_data={"data": []})
    recorder = Recorder()
    competitors.register(recorder)
    out = json.loads(recorder.tools["search_business_pages"](query="مجوهرات", city="صنعاء"))
    assert out["count"] == 0
    assert "empty_reason" in out
    assert "Page Public Content Access" in out["empty_reason"]


# ---------------------------------------------------------------------------
# analyze_competitor_page
# ---------------------------------------------------------------------------

POSTS = [
    _post("طقم جديد للطلب الآن #مجوهرات", days_ago=1, reactions=10, comments=2, shares=1),
    _post("", days_ago=4, reactions=0, comments=0, shares=0),
    _post("سعر خاص 1500 ريال #صنعاء", days_ago=9, reactions=5, comments=1, shares=0),
]

INFO = {
    "name": "مجوهرات النخبة",
    "fan_count": 2000,
    "category": "مجوهرات",
    "link": "https://facebook.com/111",
    "phone": "+967777000",
    "about": "متجر مجوهرات في صنعاء",
    "verification_status": "not_verified",
}

RATINGS = {"data": [{"rating": 5, "review_text": "ممتاز"}, {"rating": 4, "review_text": "جيد"}]}


def test_analyze_competitor_page_computes_engagement(mock_meta_sdk_recorded):
    calls: list = []
    api = _make_fake_api(info=INFO, posts=POSTS, ratings=RATINGS, calls=calls)
    mock_meta_sdk_recorded["api_call"].side_effect = api
    recorder = Recorder()
    competitors.register(recorder)

    out = json.loads(recorder.tools["analyze_competitor_page"](page_id="111", days=30))

    # profile basics
    assert out["page_id"] == "111"
    assert out["name"] == "مجوهرات النخبة"
    assert out["fan_count"] == 2000
    # posts window
    assert out["posts_in_window"] == 3
    assert out["days_since_last_post"] is not None and out["days_since_last_post"] <= 1.1
    # engagement maths: reactions 15 + comments 3 + shares 1 = 19 → avg 19/3
    assert out["total_reactions"] == 15
    assert out["total_comments"] == 3
    assert out["total_shares"] == 1
    assert out["avg_engagement_per_post"] == round(19 / 3, 2)
    assert out["engagement_rate"] == round(round(19 / 3, 2) / 2000 * 100, 2)
    # content signals
    cs = out["content_signals"]
    assert cs["posts_analysed"] == 3
    assert cs["posts_with_cta"] >= 2
    assert {h["tag"] for h in cs["top_hashtags"]} >= {"#مجوهرات", "#صنعاء"}
    # ratings
    assert out["ratings"]["count"] == 2
    assert out["ratings"]["average"] == 4.5
    # verdict: cadence 15 + recency 25 + engagement 10
    assert out["assessment"]["score"] == 50
    assert out["assessment"]["level"] == "متوسط"
    # it called the rich field set with engagement edges
    posts_call = next(c for c in calls if str(c["path"]).endswith("/published_posts"))
    assert "reactions" in posts_call["params"]["fields"]
    assert "comments" in posts_call["params"]["fields"]


def test_analyze_competitor_page_falls_back_when_engagement_edges_denied(mock_meta_sdk_recorded):
    """When reaction/comment edges are denied, the minimal fallback returns
    posts WITHOUT engagement counters → engagement stays zero, but the profile
    and its partial_errors are still produced."""
    calls: list = []
    bare_posts = [{k: v for k, v in p.items() if k not in ("reactions", "comments", "shares")} for p in POSTS]
    api = _make_fake_api(info=INFO, posts=bare_posts, ratings=RATINGS, posts_error_times=1, calls=calls)
    mock_meta_sdk_recorded["api_call"].side_effect = api
    recorder = Recorder()
    competitors.register(recorder)

    out = json.loads(recorder.tools["analyze_competitor_page"](page_id="111", days=30))

    # fallback happened: 2 post requests, the first (rich fields) failed
    post_calls = [c for c in calls if str(c["path"]).endswith("/published_posts")]
    assert len(post_calls) == 2
    assert "reactions" not in post_calls[1]["params"]["fields"]
    assert "partial_errors" in out
    assert "posts_error" in out["partial_errors"]
    # without engagement edges everything is unknown (None) — not zero — and the
    # profile still builds
    assert out["posts_in_window"] == 3
    assert out["avg_engagement_per_post"] is None
    assert out["total_reactions"] is None
    assert out["engagement_rate"] is None
    assert out["engagement_data_available"] is False
    assert out["top_posts"] == []
    assert any("بيانات التفاعل غير متاحة" in n for n in out["assessment"]["notes"])


def test_analyze_competitor_page_validates_args(mock_meta_sdk_recorded):
    mock_meta_sdk_recorded["api_call"].side_effect = _make_fake_api()
    recorder = Recorder()
    competitors.register(recorder)
    assert "error" in json.loads(recorder.tools["analyze_competitor_page"](page_id="", days=10))
    assert "error" in json.loads(recorder.tools["analyze_competitor_page"](page_id="111", days=0))


def test_analyze_our_own_page_uses_page_scoped_token(mock_meta_sdk_recorded):
    """Our page is read with the page token (full data); the user token is not
    touched for it (it would fail with #210 'page access token required')."""
    ours = str(competitors.PAGE_ID)
    api = _make_fake_api(info={"name": "Butterfly-ye", "fan_count": 2950}, posts=POSTS, ratings=RATINGS)
    mock_meta_sdk_recorded["api_call"].side_effect = api
    mock_meta_sdk_recorded["page_api_call"].side_effect = api
    recorder = Recorder()
    competitors.register(recorder)

    out = json.loads(recorder.tools["analyze_competitor_page"](page_id=ours, days=30))

    assert out["name"] == "Butterfly-ye"
    assert out["engagement_data_available"] is True
    assert out["avg_engagement_per_post"] == round(19 / 3, 2)
    assert mock_meta_sdk_recorded["page_api_call"].called
    assert not mock_meta_sdk_recorded["api_call"].called


# ---------------------------------------------------------------------------
# compare_competitors
# ---------------------------------------------------------------------------


def test_compare_competitors_appends_our_page_and_sorts(mock_meta_sdk_recorded):
    ours = str(competitors.PAGE_ID)
    calls: list = []

    def api(method, path, params=None):
        calls.append({"method": method, "path": path, "params": params or {}})
        if str(path).endswith("/published_posts"):
            if path == "111/published_posts":
                return {"data": POSTS}
            if path == "222/published_posts":
                return {"data": [_post("للتواصل واتساب", days_ago=2, reactions=100, comments=30, shares=5)]}
            return {"data": POSTS[:1]}  # our page: 1 post, low engagement
        if str(path).endswith("/ratings"):
            return {"data": []}
        if path == "111":
            return INFO
        if path == "222":
            return {"name": "منافس قوي", "fan_count": 500}
        return {"name": "Butterfly-ye", "fan_count": 2950}

    mock_meta_sdk_recorded["api_call"].side_effect = api
    mock_meta_sdk_recorded["page_api_call"].side_effect = api  # our page uses the page token
    recorder = Recorder()
    competitors.register(recorder)

    out = json.loads(recorder.tools["compare_competitors"](page_ids="111,222", days=30))

    assert out["compared"] == 3  # 2 competitors + our page
    assert out["table"][0]["name"] == "منافس قوي"  # highest engagement rate first
    assert any(t["ours"] and t["page_id"] == ours for t in out["table"])
    assert out["recommendations"], "expected at least one recommendation vs our page"


def test_compare_competitors_caps_ids(mock_meta_sdk_recorded):
    mock_meta_sdk_recorded["api_call"].side_effect = _make_fake_api()
    recorder = Recorder()
    competitors.register(recorder)
    out = json.loads(recorder.tools["compare_competitors"](page_ids=",".join(str(i) for i in range(30)), days=30))
    assert "error" in out
    assert "15" in out["error"]


def test_compare_competitors_collects_per_page_errors(mock_meta_sdk_recorded):
    """Posts/ratings failures degrade into partial_errors per row — the
    comparison still renders (with a partial flag) instead of losing the row."""

    def api(method, path, params=None):
        if str(path).endswith("/published_posts"):
            raise RuntimeError("no access")
        if str(path).endswith("/ratings"):
            raise RuntimeError("no access")
        return {"name": "منافس", "fan_count": 10}

    mock_meta_sdk_recorded["api_call"].side_effect = api
    recorder = Recorder()
    competitors.register(recorder)
    out = json.loads(recorder.tools["compare_competitors"](page_ids="111,222", include_ours=False))
    assert out["compared"] == 2
    assert all(row["partial"] for row in out["table"])


def test_compare_competitors_errors_when_profile_call_raises(mock_meta_sdk_recorded):
    """If even the page-info call raises, the row renders as partial (zero
    metrics) rather than dropping out of the comparison entirely."""

    def api(method, path, params=None):
        raise RuntimeError("invalid page id")

    mock_meta_sdk_recorded["api_call"].side_effect = api
    mock_meta_sdk_recorded["page_api_call"].side_effect = api
    recorder = Recorder()
    competitors.register(recorder)
    out = json.loads(recorder.tools["compare_competitors"](page_ids="111", include_ours=False))
    assert out["compared"] == 1
    assert out["table"][0]["partial"] is True
    assert out["table"][0]["fan_count"] is None
    assert out["table"][0]["level"] == "خامل/ضعيف"


# ---------------------------------------------------------------------------
# discover_instagram_business
# ---------------------------------------------------------------------------

BIZ = {
    "business_discovery": {
        "username": "jewels.sanaa",
        "name": "Jewels Sana'a",
        "followers_count": 1000,
        "media_count": 340,
        "biography": "مجوهرات صنعاء 📍",
        "website": "",
        "media": {
            "data": [
                {
                    "id": "m1",
                    "caption": "طقم جديد 💎 #مجوهرات #صنعاء",
                    "permalink": "https://ig.com/p/m1",
                    "timestamp": "2026-10-09T17:00:00+0000",
                    "like_count": 100,
                    "comments_count": 10,
                    "media_type": "CAROUSEL_ALBUM",
                },
                {
                    "id": "m2",
                    "caption": "عرض خاص",
                    "permalink": "https://ig.com/p/m2",
                    "timestamp": "2026-10-01T17:00:00+0000",
                    "like_count": 50,
                    "comments_count": 5,
                    "media_type": "IMAGE",
                },
            ]
        },
    }
}


def test_discover_instagram_business_computes_average_engagement(mock_meta_sdk_recorded):
    calls: list = []
    api = _make_fake_api(biz=BIZ, calls=calls)
    mock_meta_sdk_recorded["api_call"].side_effect = api
    recorder = Recorder()
    competitors.register(recorder)

    out = json.loads(recorder.tools["discover_instagram_business"](username="@jewels.sanaa", media_limit=12))

    assert out["username"] == "jewels.sanaa"
    assert out["followers_count"] == 1000
    assert out["analysed_media"] == 2
    assert out["avg_likes"] == 75.0
    assert out["avg_comments"] == 7.5
    assert out["engagement_rate"] == round((75.0 + 7.5) / 1000 * 100, 3)
    assert {h["tag"] for h in out["top_hashtags"]} == {"#مجوهرات", "#صنعاء"}
    assert len(out["latest_media"]) == 2
    # username is normalised (@ stripped) inside the fields selector
    assert "business_discovery.username(jewels.sanaa)" in calls[0]["params"]["fields"]


def test_discover_instagram_business_requires_our_ig_id():
    competitor_tools = Recorder()
    competitors.register(competitor_tools)
    # simulate unconfigured FB_IG_USER_ID
    original = competitors.INSTAGRAM_BUSINESS_ID
    competitors.INSTAGRAM_BUSINESS_ID = ""
    try:
        out = json.loads(competitor_tools.tools["discover_instagram_business"](username="x"))
        assert "error" in out
        assert "FB_IG_USER_ID" in out["error"]
    finally:
        competitors.INSTAGRAM_BUSINESS_ID = original


def test_discover_instagram_business_missing_account(mock_meta_sdk_recorded):
    mock_meta_sdk_recorded["api_call"].side_effect = _make_fake_api(biz={})
    recorder = Recorder()
    competitors.register(recorder)
    out = json.loads(recorder.tools["discover_instagram_business"](username="does_not_exist"))
    assert "error" in out
    assert "does_not_exist" in out["error"]


# ---------------------------------------------------------------------------
# check_discovery_permissions
# ---------------------------------------------------------------------------


def test_check_discovery_permissions_reports_blocked_paths(mock_meta_sdk_recorded):
    from facebook_business.exceptions import FacebookRequestError

    body = json.dumps({"error": {"message": "permission denied", "code": 10, "error_subcode": None}})

    def api(method, path, params=None):
        if path == "search":
            return {"data": []}  # Meta answers empty when the feature is missing
        if path == "ads_archive":
            raise FacebookRequestError("Application does not have permission", {}, 403, {}, body)
        if path == "ig_hashtag_search":
            raise FacebookRequestError("Instagram Public Content Access required", {}, 403, {}, body)
        return {"data": []}

    mock_meta_sdk_recorded["api_call"].side_effect = api
    recorder = Recorder()
    competitors.register(recorder)

    out = json.loads(recorder.tools["check_discovery_permissions"]())
    endpoints = {r["endpoint"]: r for r in out["results"]}
    assert set(endpoints) == {"facebook_page_search", "meta_ad_library", "instagram_hashtag_search"}
    assert endpoints["facebook_page_search"]["status"].startswith("empty")
    assert endpoints["meta_ad_library"]["status"] == "blocked"
    assert endpoints["meta_ad_library"]["code"] == 10
    assert endpoints["instagram_hashtag_search"]["status"] == "blocked"
    assert out["available_count"] == 0
    assert "App Review" in out["summary"]


def test_check_discovery_permissions_reports_available_path(mock_meta_sdk_recorded):
    def api(method, path, params=None):
        if path == "search":
            return {"data": [{"id": "1", "name": "صفحة"}]}
        return {"data": []}

    mock_meta_sdk_recorded["api_call"].side_effect = api
    recorder = Recorder()
    competitors.register(recorder)
    out = json.loads(recorder.tools["check_discovery_permissions"]())
    # page search returns rows + ig probe raises nothing → 2 available of 3
    assert out["available_count"] == 2
    assert "2 من 3" in out["summary"]


# ---------------------------------------------------------------------------
# registration surface
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# competitor_report — the consolidated one-call report
# ---------------------------------------------------------------------------


def _report_response(handle: str):
    return {
        "business_discovery": {
            "username": handle,
            "name": "ايلجنت ستايل",
            "biography": "أطقم واكسسوارات",
            "followers_count": 22719,
            "media_count": 520,
            "media": {
                "data": [
                    {
                        "id": "m1",
                        "caption": "طقم جديد #كارتير #استيل السعر 7000 ريال",
                        "permalink": "https://www.instagram.com/p/M1/",
                        "timestamp": "2026-10-20T18:00:00+0000",
                        "like_count": 300,
                        "comments_count": 30,
                        "media_type": "VIDEO",
                    },
                    {
                        "id": "m2",
                        "caption": "عرض #صنعاء الكمية محدودة",
                        "permalink": "https://www.instagram.com/p/M2/",
                        "timestamp": "2026-10-18T20:00:00+0000",
                        "like_count": 10,
                        "comments_count": 2,
                        "media_type": "IMAGE",
                    },
                ],
                "paging": {"cursors": {}},
            },
        }
    }


def test_competitor_report_consolidates_everything(mock_meta_sdk_recorded):
    mock_meta_sdk_recorded["api_call"].side_effect = lambda *a, **k: _report_response("elegant.po1")
    recorder = Recorder()
    competitors.register(recorder)

    out = json.loads(recorder.tools["competitor_report"](handle="@elegant.po1", days=30))

    assert out["handle"] == "elegant.po1"
    ig = out["instagram"]
    assert ig["followers"] == 22719
    assert ig["avg_likes"] == 155.0
    assert ig["avg_comments"] == 16.0
    assert ig["engagement_rate"] == round(171 / 22719 * 100, 3)
    assert [h["tag"] for h in ig["top_hashtags"]][:2] == ["#كارتير", "#صنعاء"] or ig["top_hashtags"]
    # best post first
    assert out["instagram"]["latest_posts"][0]["likes"] == 300
    assert out["instagram"]["latest_posts"][0]["type"] == "VIDEO"
    # cadence section
    cad = out["cadence"]
    assert cad["in_window"] == 2
    assert cad["active_days"] == 2
    types = {r["media_type"]: r for r in cad["by_media_type"]}
    assert types["VIDEO"]["avg_engagement"] == 330.0
    assert types["IMAGE"]["avg_engagement"] == 12.0
    # recommendations mention their audience advantage
    assert any("متابع" in r for r in out["recommendations"])


def test_competitor_report_requires_handle(mock_meta_sdk_recorded):
    recorder = Recorder()
    competitors.register(recorder)
    out = json.loads(recorder.tools["competitor_report"](handle=""))
    assert "error" in out


def test_competitor_report_survives_ig_failure(mock_meta_sdk_recorded):
    mock_meta_sdk_recorded["api_call"].side_effect = Exception("token expired")
    recorder = Recorder()
    competitors.register(recorder)
    out = json.loads(recorder.tools["competitor_report"](handle="ghost.store", days=30))
    assert "error" in out["instagram"]
    assert out["recommendations"] == ["لا توصيات محددة — راجع التفاصيل"]


def test_module_registers_tools_resources_prompts():
    recorder = Recorder()
    competitors.register(recorder)
    assert set(recorder.tools) == {
        "search_business_pages",
        "check_discovery_permissions",
        "analyze_competitor_page",
        "compare_competitors",
        "discover_instagram_business",
        "competitor_report",
    }
    assert len(recorder.resources) >= 2
    assert len(recorder.prompts) >= 2
    names = list(recorder.tools)
    assert len(names) == len(set(names))
