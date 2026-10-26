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


def _post_mock(post_id: str, hours_ago: int):
    """A post object that behaves like a Meta SDK object for to_dict()."""
    dt = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    m = mock.Mock()
    m.export_all_data.return_value = {"id": post_id, "created_time": dt.isoformat()}
    return m


def test_best_posting_time_ranks_slots_by_engagement(recorder):
    posts = [_post_mock("p1", 20), _post_mock("p2", 26), _post_mock("p3", 24)]
    with (
        mock.patch.object(content_tools, "_page") as page,
        mock.patch.object(content_tools, "_post_engagement", side_effect=[50, 10, 30]),
    ):
        page.return_value.get_posts.return_value = posts
        out = json.loads(recorder.tools["best_posting_time"](days=30))

    assert out["analyzed_posts"] == 3
    assert out["best_slots"][0]["avg_engagement"] == 50
    assert out["recommendation"].startswith("انشر على")
    assert len(out["worst_slots"]) >= 1


def test_best_posting_time_handles_no_posts(recorder):
    with mock.patch.object(content_tools, "_page") as page:
        page.return_value.get_posts.return_value = []
        out = json.loads(recorder.tools["best_posting_time"](days=30))
    assert "error" in out


def test_best_posting_time_rejects_bad_window(recorder):
    out = json.loads(recorder.tools["best_posting_time"](days=0))
    assert "error" in out


# ---------------------------------------------------------------------------
# hashtag_analyzer
# ---------------------------------------------------------------------------


def test_hashtag_analyzer_aggregates_by_tag(recorder):
    posts = [
        {"id": "p1", "message": "طقم جديد #كارتير #استيل"},
        {"id": "p2", "message": "عرض #كارتير #صنعاء"},
        {"id": "p3", "message": "بدون وسوم"},
    ]
    with (
        mock.patch.object(content_tools, "_page") as page,
        mock.patch.object(content_tools, "_post_engagement", side_effect=[100, 40, 0]),
    ):
        page.return_value.get_posts.return_value = posts
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
    with mock.patch.object(content_tools, "_page") as page:
        page.return_value.get_posts.return_value = [{"id": "p1", "message": "بدون"}]
        out = json.loads(recorder.tools["hashtag_analyzer"](days=60))
    assert "message" in out


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


def test_auto_reply_comments_configures_rule(recorder):
    out = json.loads(recorder.tools["auto_reply_comments"](keyword="سعر", reply="أهلاً! السعر في الرسائل 📩"))
    assert out["configured"] is True
    assert out["rule"]["keyword"] == "سعر"
    assert out["rule"]["trigger"] == "comment_keyword"
    assert json.loads(out["rule"]["action_params_json"])["message"].endswith("📩")


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
