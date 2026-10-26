"""Tests for src/content_tools — captions, posting time, hashtags, calendar."""

import json
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from src import content_tools
from tests.conftest import Recorder


@pytest.fixture
def recorder():
    r = Recorder()
    content_tools.register(r)
    return r


# ---------------------------------------------------------------------------
# generate_post_caption
# ---------------------------------------------------------------------------


def test_generate_caption_template_path_with_price_and_hashtags(recorder):
    out = json.loads(
        recorder.tools["generate_post_caption"](
            product="طقم كارتير المسمار", price=4500, old_price=24000, style="sales"
        )
    )
    assert out["source"] == "template"
    assert "طقم كارتير المسمار" in out["caption"]
    assert "4,500" in out["caption"] and "24,000" in out["caption"]
    assert "سعر العرض" in out["caption"]
    assert any("كارتير" in h for h in out["hashtags"])
    assert "#Butterfly" in out["hashtags"]
    assert out["full_text"].endswith(" ".join(out["hashtags"]))


def test_generate_caption_minimal_style_and_english(recorder):
    out = json.loads(
        recorder.tools["generate_post_caption"](product="Swarovski Set", price=12000, style="minimal", language="en")
    )
    assert out["language"] == "en"
    assert "Butterfly" in out["caption"]
    assert "12,000" in out["caption"]
    assert len(out["caption"]) < 120


def test_generate_caption_llm_path(recorder):
    llm_payload = json.dumps(
        {
            "caption": "✨ طقم ديور بضمان سنة — الكمية محدودة",
            "hashtags": ["#ديور", "#أطقم"],
            "cta": "للطلب رسائل الصفحة",
        }
    )
    with mock.patch.object(content_tools, "call_llm", return_value=llm_payload):
        out = json.loads(recorder.tools["generate_post_caption"](product="طقم ديور", price=7000, style="sales"))
    assert out["source"] == "llm"
    assert out["cta"] == "للطلب رسائل الصفحة"
    assert out["hashtags"] == ["#ديور", "#أطقم"]


def test_generate_caption_falls_back_when_llm_returns_garbage(recorder):
    with mock.patch.object(content_tools, "call_llm", return_value="not json"):
        out = json.loads(recorder.tools["generate_post_caption"](product="طقم زركون", price=1500))
    assert out["source"] == "template"
    assert "زركون" in out["caption"]


def test_generate_caption_requires_product(recorder):
    out = json.loads(recorder.tools["generate_post_caption"](product=""))
    assert "error" in out


# ---------------------------------------------------------------------------
# best_posting_time
# ---------------------------------------------------------------------------


def _published_posts(*specs):
    """specs: (post_id, hours_ago, message) -> dicts like published_posts returns."""
    out = []
    for pid, hours, msg in specs:
        dt = datetime.now(timezone.utc) - timedelta(hours=hours)
        out.append({"id": pid, "created_time": dt.isoformat(), "message": msg})
    return out


def test_best_posting_time_ranks_slots_by_engagement(recorder):
    posts = _published_posts(("p1", 20, "a"), ("p2", 26, "b"), ("p3", 24, "c"))
    with (
        mock.patch.object(content_tools, "page_api_call", return_value={"data": posts}),
        mock.patch.object(content_tools, "_post_engagement", side_effect=[50, 10, 30]),
    ):
        out = json.loads(recorder.tools["best_posting_time"](days=30))

    assert out["analyzed_posts"] == 3
    assert out["best_slots"][0]["avg_engagement"] == 50
    assert out["recommendation"].startswith("انشر على")
    assert len(out["worst_slots"]) >= 1


def test_best_posting_time_handles_no_posts(recorder):
    with mock.patch.object(content_tools, "page_api_call", return_value={"data": []}):
        out = json.loads(recorder.tools["best_posting_time"](days=30))
    assert "error" in out


def test_best_posting_time_surfaces_api_error(recorder):
    with mock.patch.object(content_tools, "page_api_call", side_effect=Exception("403 forbidden")):
        out = json.loads(recorder.tools["best_posting_time"](days=30))
    assert "403" in out["error"]


def test_best_posting_time_rejects_bad_window(recorder):
    out = json.loads(recorder.tools["best_posting_time"](days=0))
    assert "error" in out


# ---------------------------------------------------------------------------
# hashtag_analyzer
# ---------------------------------------------------------------------------


def test_hashtag_analyzer_aggregates_by_tag(recorder):
    posts = _published_posts(
        ("p1", 20, "طقم جديد #كارتير #استيل"),
        ("p2", 26, "عرض #كارتير #صنعاء"),
        ("p3", 30, "بدون وسوم"),
    )
    with (
        mock.patch.object(content_tools, "page_api_call", return_value={"data": posts}),
        mock.patch.object(content_tools, "_post_engagement", side_effect=[100, 40, 0]),
    ):
        out = json.loads(recorder.tools["hashtag_analyzer"](days=60))

    tags = {r["hashtag"]: r for r in out["top_hashtags"]}
    assert out["unique_hashtags"] == 3
    assert tags["#كارتير"]["uses"] == 2
    assert tags["#كارتير"]["avg_engagement"] == 70.0
    assert tags["#كارتير"]["total_engagement"] == 140
    assert tags["#استيل"]["uses"] == 1
    assert tags["#استيل"]["avg_engagement"] == 100.0  # highest single-post average wins
    assert "#استيل" in out["recommendation"]
    assert "#صنعاء" in out["recommendation"]  # named as the one to avoid


def test_hashtag_analyzer_no_hashtags(recorder):
    posts = _published_posts(("p1", 20, "بدون"))
    with mock.patch.object(content_tools, "page_api_call", return_value={"data": posts}):
        out = json.loads(recorder.tools["hashtag_analyzer"](days=60))
    assert "message" in out


def test_is_contact_hashtag_separates_phones_from_marketing_tags():
    assert content_tools._is_contact_hashtag("#+967777000123")
    assert content_tools._is_contact_hashtag("#0777000000")
    assert not content_tools._is_contact_hashtag("#كارتير")
    assert not content_tools._is_contact_hashtag("#Dior2026")  # letters still dominate
    assert not content_tools._is_contact_hashtag("#Butterfly")


def test_hashtag_analyzer_skips_contact_hashtags(recorder):
    posts = _published_posts(
        ("p1", 20, "للطلب #+967777000111 #كارتير"),
        ("p2", 26, "عرض #777000222 #صنعاء"),
    )
    with (
        mock.patch.object(content_tools, "page_api_call", return_value={"data": posts}),
        mock.patch.object(content_tools, "_post_engagement", side_effect=[80, 40]),
    ):
        out = json.loads(recorder.tools["hashtag_analyzer"](days=60))

    tags = {r["hashtag"] for r in out["top_hashtags"]}
    assert tags == {"#كارتير", "#صنعاء"}
    assert out["skipped_contact_hashtags"] == 2
    assert "#+967777000111" not in out["recommendation"]


def test_hashtag_analyzer_reports_when_all_tags_are_contact_info(recorder):
    posts = _published_posts(("p1", 20, "للطلب #+967777000111 #777000222"))
    with (
        mock.patch.object(content_tools, "page_api_call", return_value={"data": posts}),
        mock.patch.object(content_tools, "_post_engagement", return_value=10),
    ):
        out = json.loads(recorder.tools["hashtag_analyzer"](days=60))

    assert "message" in out
    assert out["skipped_contact_hashtags"] == 2
    assert "استُبعد" in out["message"]


# ---------------------------------------------------------------------------
# content_calendar
# ---------------------------------------------------------------------------


def test_content_calendar_plans_week(recorder):
    out = json.loads(recorder.tools["content_calendar"](week_start="2026-10-26", posts_per_week=5))
    assert len(out["plan"]) == 7
    assert out["posts_planned"] == 5
    post_days = [d for d in out["plan"] if d["is_post_day"]]
    assert len(post_days) == 5
    assert all("time" in d for d in post_days)
    assert any(d["weekday"] == "الخميس" for d in post_days)
    assert out["plan"][0]["date"] == "2026-10-26"
    assert out["rules"][0].startswith("لا صور مفردة")


def test_content_calendar_rejects_bad_date(recorder):
    out = json.loads(recorder.tools["content_calendar"](week_start="not-a-date"))
    assert "error" in out


def test_content_calendar_caps_posts(recorder):
    out = json.loads(recorder.tools["content_calendar"](posts_per_week=99))
    assert out["posts_planned"] == 7


# ---------------------------------------------------------------------------
# auto_reply_comments
# ---------------------------------------------------------------------------


def test_auto_reply_comments_persists_the_rule(recorder):
    stored = {}

    def _save(rules):
        stored["rules"] = rules

    with (
        mock.patch("src.webhook_automations._load_rules", return_value=[]),
        mock.patch("src.webhook_automations._save_rules", side_effect=_save),
    ):
        out = json.loads(recorder.tools["auto_reply_comments"](keyword="سعر", reply="أهلاً! السعر في الرسائل 📩"))

    assert out["configured"] is True
    assert out["rule_id"]
    assert out["rule"]["keyword"] == "سعر"
    assert out["rule"]["trigger"] == "comment_keyword"
    assert out["rule"]["action_params"]["message"].endswith("📩")
    assert out["rule"]["enabled"] is True
    # the rule really reached the webhook_automations store
    assert stored["rules"][0]["keyword"] == "سعر"
    assert stored["rules"][0]["action_params"]["message"].endswith("📩")


def test_auto_reply_comments_can_be_disabled(recorder):
    with (
        mock.patch("src.webhook_automations._load_rules", return_value=[]),
        mock.patch("src.webhook_automations._save_rules"),
    ):
        out = json.loads(recorder.tools["auto_reply_comments"](keyword="كم", reply="x", enabled=False))
    assert out["rule"]["enabled"] is False


def test_auto_reply_comments_requires_args(recorder):
    assert "error" in json.loads(recorder.tools["auto_reply_comments"](keyword="", reply="x"))
    assert "error" in json.loads(recorder.tools["auto_reply_comments"](keyword="سعر", reply=""))


# ---------------------------------------------------------------------------
# registration surface
# ---------------------------------------------------------------------------


def test_module_registers_tools_resources_prompts(recorder):
    assert set(recorder.tools) == {
        "generate_post_caption",
        "best_posting_time",
        "hashtag_analyzer",
        "content_calendar",
        "auto_reply_comments",
    }
    assert len(recorder.resources) >= 2
    assert len(recorder.prompts) >= 2
