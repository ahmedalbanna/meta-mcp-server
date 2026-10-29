"""Tests for src/competitor_content — post resolution, download, cadence."""

import json
from datetime import datetime, timedelta, timezone
from unittest import mock

from src import competitor_content
from tests.conftest import TEST_SERVICES, Recorder


def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _media_item(days_ago: float, likes: int, comments: int, mtype: str = "CAROUSEL_ALBUM", caption: str = ""):
    return {
        "id": f"m{int(days_ago * 100)}",
        "caption": caption,
        "permalink": f"https://www.instagram.com/p/CODE{int(days_ago)}/",
        "timestamp": _iso(days_ago),
        "like_count": likes,
        "comments_count": comments,
        "media_type": mtype,
    }


def _biz_response(items):
    return {"business_discovery": {"username": "x", "media": {"data": items, "paging": {"cursors": {}}}}}


def _item_on_fixed_day(days_ago: int, likes: int, comments: int, mtype: str = "CAROUSEL_ALBUM"):
    """Media item stamped at 12:00 UTC N days ago — deterministic day grouping."""
    dt = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
    return {
        "id": f"fixed{days_ago}_{likes}",
        "caption": "",
        "permalink": f"https://www.instagram.com/p/FIXED{days_ago}_{likes}/",
        "timestamp": dt.isoformat(),
        "like_count": likes,
        "comments_count": comments,
        "media_type": mtype,
    }


def _oembed_payload(**overrides):
    payload = {
        "author_name": "bood2005moo",
        "author_url": "https://www.instagram.com/bood2005moo",
        "author_id": "78088024837",
        "media_id": "3917424994060773466",
        "title": "عالم الذهب والمجوهرات 📍 صنعاء",
        "thumbnail_url": "https://scontent.example.com/thumb.jpg",
        "thumbnail_width": 640,
        "thumbnail_height": 480,
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# resolve_instagram_post_url
# ---------------------------------------------------------------------------

POST_HTML = """<html><head>
<meta property="og:url" content="https://www.instagram.com/bood2005moo/p/DZdfUbVOqha/" />
<meta property="og:image" content="https://scontent.example.com/img.jpg?stp=x&amp;oe=1" />
<meta property="al:ios:url" content="instagram://media?id=3917424994060773466" />
<meta property="instapp:owner_user_id" content="78088024837" />
<meta name="description" content="43 likes, 8 comments - bood2005moo on June 11, 2026&#x200e;: &quot;عالم الذهب والمجوهرات 📍 صنعاء&quot;. &#x200e;" />
</head></html>"""


def test_resolve_post_url_merges_oembed_and_html():
    """oEmbed provides identity/caption; the HTML page adds likes/comments."""
    recorder = Recorder()
    competitor_content.register(recorder, TEST_SERVICES)
    with mock.patch.object(competitor_content.requests, "get") as mget:
        mget.side_effect = [
            mock.Mock(status_code=200, json=lambda: _oembed_payload()),
            mock.Mock(status_code=200, text=POST_HTML),
        ]
        out = json.loads(recorder.tools["resolve_instagram_post_url"](url="https://www.instagram.com/p/DZdfUbVOqha/"))
    assert out["username"] == "bood2005moo"
    assert out["shortcode"] == "DZdfUbVOqha"
    assert out["media_id"] == "3917424994060773466"
    assert out["author_id"] == "78088024837"
    assert out["owner_user_id"] == "78088024837"
    assert out["likes"] == 43
    assert out["comments"] == 8
    assert "عالم الذهب" in out["caption"]
    assert out["image_url"] == "https://scontent.example.com/thumb.jpg"
    assert out["source"] == "html+oembed"
    assert "discover_instagram_business" in out["next_step"]


def test_resolve_post_url_oembed_only_when_html_is_a_shell():
    """Instagram often serves a stripped shell — oEmbed alone must still work."""
    recorder = Recorder()
    competitor_content.register(recorder, TEST_SERVICES)
    shell = "<html><head><meta property='og:title' content='x' /></head></html>"
    with mock.patch.object(competitor_content.requests, "get") as mget:
        mget.side_effect = [
            mock.Mock(status_code=200, json=lambda: _oembed_payload()),
            mock.Mock(status_code=200, text=shell),
        ]
        out = json.loads(recorder.tools["resolve_instagram_post_url"](url="https://www.instagram.com/p/ABC/"))
    assert out["username"] == "bood2005moo"
    assert out["author_id"] == "78088024837"
    assert out["source"] == "oembed"
    assert "likes" not in out  # stats unavailable from oEmbed


def test_resolve_post_url_html_only_when_oembed_fails():
    """If oEmbed is down, the HTML meta tags alone still identify the author."""
    recorder = Recorder()
    competitor_content.register(recorder, TEST_SERVICES)
    with mock.patch.object(competitor_content.requests, "get") as mget:
        mget.side_effect = [
            mock.Mock(status_code=500, json=lambda: {}),  # oembed fails
            mock.Mock(status_code=200, text=POST_HTML),
        ]
        out = json.loads(recorder.tools["resolve_instagram_post_url"](url="https://www.instagram.com/p/DZdfUbVOqha/"))
    assert out["username"] == "bood2005moo"
    assert out["likes"] == 43
    assert out["source"] == "html"


def test_resolve_post_url_rejects_non_instagram_url():
    recorder = Recorder()
    competitor_content.register(recorder, TEST_SERVICES)
    out = json.loads(recorder.tools["resolve_instagram_post_url"](url="https://example.com/x"))
    assert "error" in out
    assert "instagram.com" in out["error"]


def test_resolve_post_url_handles_private_or_missing_post():
    recorder = Recorder()
    competitor_content.register(recorder, TEST_SERVICES)
    with mock.patch.object(competitor_content.requests, "get") as mget:
        mget.return_value = mock.Mock(status_code=200, text="<html><head></head></html>", json=lambda: {})
        out = json.loads(recorder.tools["resolve_instagram_post_url"](url="https://www.instagram.com/p/GONE/"))
    assert "error" in out
    assert "تعذّر" in out["error"]


# ---------------------------------------------------------------------------
# download_top_competitor_posts
# ---------------------------------------------------------------------------


def test_download_top_filters_ranks_and_saves(mock_meta_sdk_recorded, tmp_path):
    items = [
        _media_item(1, 10, 2, "VIDEO", "فيديو"),
        _media_item(2, 300, 30, "VIDEO", "أفضل"),
        _media_item(3, 150, 9, "CAROUSEL_ALBUM"),
        _media_item(40, 999, 99, "IMAGE", "خارج النافذة"),
    ]
    mock_meta_sdk_recorded["api_call"].side_effect = lambda *a, **k: _biz_response(items)

    recorder = Recorder()
    competitor_content.register(recorder, TEST_SERVICES)
    out_dir = str(tmp_path / "competitor_dl")

    with (
        mock.patch.object(competitor_content.requests, "get") as mget,
        mock.patch.object(competitor_content, "MEDIA_DOWNLOAD_DIR", tmp_path),
    ):
        # oembed -> image url, then image download
        mget.side_effect = [
            mock.Mock(status_code=200, json=lambda: {"thumbnail_url": "https://scontent/x/p640x640/a.jpg"}),
            mock.Mock(status_code=200, content=b"x" * 5000),
        ]
        out = json.loads(
            recorder.tools["download_top_competitor_posts"](handle="@elegant.po1", days=30, top_n=2, out_dir=out_dir)
        )

    assert out["fetched_posts"] == 4
    assert out["posts_in_window"] == 3  # the 40-day-old post is filtered out
    assert out["downloaded"] == 1  # only one oembed mock provided
    assert out["top_posts"][0]["likes"] == 300
    assert out["top_posts"][0]["file"] == "01_300likes_CODE2.jpg"
    assert out["note"]
    # manifest written next to the images
    assert (tmp_path / "competitor_dl" / "manifest.json").exists()


def test_download_top_validates_args(mock_meta_sdk_recorded):
    mock_meta_sdk_recorded["api_call"].side_effect = lambda *a, **k: _biz_response([])
    recorder = Recorder()
    competitor_content.register(recorder, TEST_SERVICES)
    assert "error" in json.loads(recorder.tools["download_top_competitor_posts"](handle=""))
    assert "error" in json.loads(recorder.tools["download_top_competitor_posts"](handle="x", days=0))
    assert "error" in json.loads(recorder.tools["download_top_competitor_posts"](handle="x", top_n=99))


def test_download_top_reports_missing_account(mock_meta_sdk_recorded):
    mock_meta_sdk_recorded["api_call"].side_effect = lambda *a, **k: {"business_discovery": {}}
    recorder = Recorder()
    competitor_content.register(recorder, TEST_SERVICES)
    out = json.loads(recorder.tools["download_top_competitor_posts"](handle="nope"))
    assert "error" in out
    assert "nope" in out["error"]


# ---------------------------------------------------------------------------
# analyze_competitor_cadence
# ---------------------------------------------------------------------------


def test_cadence_analysis_groups_by_day_and_type(mock_meta_sdk_recorded):
    items = [
        _item_on_fixed_day(1, 300, 30, "VIDEO"),
        _item_on_fixed_day(1, 100, 10, "CAROUSEL_ALBUM"),
        _item_on_fixed_day(2, 5, 1, "IMAGE"),
        _item_on_fixed_day(2, 3, 0, "IMAGE"),
        _item_on_fixed_day(45, 999, 0, "VIDEO"),  # outside window
    ]
    mock_meta_sdk_recorded["api_call"].side_effect = lambda *a, **k: _biz_response(items)
    recorder = Recorder()
    competitor_content.register(recorder, TEST_SERVICES)

    out = json.loads(recorder.tools["analyze_competitor_cadence"](handle="elegant.po1", days=30))

    assert out["fetched_posts"] == 5
    assert out["posts_in_window"] == 4
    assert out["active_days"] == 2
    assert out["avg_posts_per_active_day"] == 2.0
    types = {r["media_type"]: r for r in out["by_media_type"]}
    assert types["VIDEO"]["avg_engagement"] == 330.0
    assert types["IMAGE"]["avg_engagement"] == 4.5  # (6 + 3) / 2
    assert "VIDEO" in out["insight"]
    assert out["best_days"][0]["avg_engagement"] >= out["worst_days"][0]["avg_engagement"]


def test_cadence_analysis_requires_handle(mock_meta_sdk_recorded):
    recorder = Recorder()
    competitor_content.register(recorder, TEST_SERVICES)
    assert "error" in json.loads(recorder.tools["analyze_competitor_cadence"](handle=""))


# ---------------------------------------------------------------------------
# registration surface
# ---------------------------------------------------------------------------


def test_module_registers_tools_resources_prompts():
    recorder = Recorder()
    competitor_content.register(recorder, TEST_SERVICES)
    assert set(recorder.tools) == {
        "resolve_instagram_post_url",
        "download_top_competitor_posts",
        "analyze_competitor_cadence",
    }
    assert len(recorder.resources) >= 2
    assert len(recorder.prompts) >= 2
