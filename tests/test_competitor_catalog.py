"""Tests for src/competitor_catalog — the competitor -> draft catalog pipeline."""

import json
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from src import competitor_catalog
from tests.conftest import Recorder


def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _post(days_ago: float, likes: int, comments: int, caption: str, mtype: str = "CAROUSEL_ALBUM"):
    return {
        "id": f"p{days_ago}_{likes}",
        "caption": caption,
        "permalink": f"https://www.instagram.com/p/C{days_ago}_{likes}/",
        "timestamp": _iso(days_ago),
        "like_count": likes,
        "comments_count": comments,
        "media_type": mtype,
    }


def _biz(items):
    return {"business_discovery": {"username": "x", "media": {"data": items, "paging": {"cursors": {}}}}}


# ---------------------------------------------------------------------------
# price / name extraction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "caption,expected",
    [
        ("طقم جديد السعر 6500 ريال", 6500.0),
        ("ب12 الف ريال فقط", 12000.0),
        ("السعر السابق ٢٤ الف وسعر العرض ٧ الف", 24000.0),  # first match wins
        ("٧ ألف ضمان سنتين", 7000.0),
        ("سعر خاص 29,900 ريال", 29900.0),
        ("اطلبي الآن بدون سعر", None),
        ("", None),
    ],
)
def test_extract_price_variants(caption, expected):
    assert competitor_catalog._extract_price(caption) == expected


def test_product_name_from_caption():
    assert competitor_catalog._product_name("طقم كارتير المسمار\nتفاصيل أكثر", "x") == "طقم كارتير المسمار"
    assert competitor_catalog._product_name("#وسوم فقط", "shop") == "منتج من shop"
    assert competitor_catalog._product_name("", "shop") == "منتج من shop"


# ---------------------------------------------------------------------------
# build_competitor_catalog — validation
# ---------------------------------------------------------------------------


def test_build_requires_handles(mock_meta_sdk_recorded):
    recorder = Recorder()
    competitor_catalog.register(recorder)
    out = json.loads(recorder.tools["build_competitor_catalog"](handles=""))
    assert "error" in out


def test_build_caps_limits(mock_meta_sdk_recorded):
    recorder = Recorder()
    competitor_catalog.register(recorder)
    assert "error" in json.loads(recorder.tools["build_competitor_catalog"](handles="a", top_n=99))
    assert "error" in json.loads(recorder.tools["build_competitor_catalog"](handles="a", days=-1))
    assert "error" in json.loads(
        recorder.tools["build_competitor_catalog"](handles=",".join(f"s{i}" for i in range(12)))
    )
    assert "error" in json.loads(
        recorder.tools["build_competitor_catalog"](handles="a", push_to_meta=True)
    )  # missing catalog_id


# ---------------------------------------------------------------------------
# build_competitor_catalog — happy path (two stores)
# ---------------------------------------------------------------------------


def test_build_pipeline_creates_folders_reports_and_draft(mock_meta_sdk_recorded, tmp_path):
    store_a = [
        _post(1, 300, 30, "طقم ذهب مُشبّك\nالسعر 7000 ريال"),
        _post(2, 100, 10, "طقم أزرق\nب7 ألف ضمان سنتين"),
        _post(40, 999, 9, "خارج النافذة"),
    ]
    store_b = [
        _post(3, 50, 5, "خواتم زركون 1500 ريال", "IMAGE"),
    ]
    api = mock.MagicMock()
    api.side_effect = lambda method, path, params=None: (
        _biz(store_a) if "elegant.po1" in str(params.get("fields", "")) else _biz(store_b)
    )
    mock_meta_sdk_recorded["api_call"].side_effect = api

    recorder = Recorder()
    competitor_catalog.register(recorder)

    with (
        mock.patch.object(competitor_catalog, "MEDIA_DOWNLOAD_DIR", tmp_path / "media"),
        mock.patch.object(competitor_catalog, "fetch_business_media") as fetch,
        mock.patch.object(competitor_catalog, "oembed_image", return_value="https://scontent/x.jpg"),
        mock.patch.object(
            competitor_catalog,
            "download_image",
            side_effect=lambda url, target: (target.write_bytes(b"x" * 4200), 4200)[1],
        ),
    ):
        fetch.side_effect = lambda handle, **kw: store_a if handle == "elegant.po1" else store_b
        out = json.loads(
            recorder.tools["build_competitor_catalog"](handles="elegant.po1, bood2005moo", days=30, top_n=2)
        )

    # per-store folders + reports
    assert out["stores_requested"] == 2
    assert out["stores_with_data"] == 2
    by_handle = {s["handle"]: s for s in out["stores"]}
    assert by_handle["elegant.po1"]["in_window"] == 2
    assert by_handle["elegant.po1"]["downloaded_images"] == 2
    assert by_handle["bood2005moo"]["in_window"] == 1

    a_folder = tmp_path / "competitors" / "elegant.po1"
    b_folder = tmp_path / "competitors" / "bood2005moo"
    assert (a_folder / "products.txt").exists()
    assert (b_folder / "products.txt").exists()
    assert (a_folder / "01_300likes_C1_300.jpg").exists()

    report = (a_folder / "products.txt").read_text(encoding="utf-8")
    assert "طقم ذهب مُشبّك" in report
    assert "7,000 ريال" in report  # price extracted into the report

    # draft files
    assert out["products_in_draft"] == 3  # 2 + 1
    draft_json = json.loads((tmp_path / "competitors" / "catalog_draft.json").read_text(encoding="utf-8"))
    assert draft_json[0]["price"] == 7000.0
    assert draft_json[0]["source_store"] == "elegant.po1"
    assert draft_json[0]["status"] == "draft"
    assert (tmp_path / "competitors" / "catalog_draft.md").exists()
    assert "مرجعية فقط" in (tmp_path / "competitors" / "catalog_draft.md").read_text(encoding="utf-8")


def test_build_pipeline_handles_store_without_data(mock_meta_sdk_recorded, tmp_path):
    recorder = Recorder()
    competitor_catalog.register(recorder)
    with (
        mock.patch.object(competitor_catalog, "MEDIA_DOWNLOAD_DIR", tmp_path / "media"),
        mock.patch.object(competitor_catalog, "fetch_business_media", return_value=[]),
    ):
        out = json.loads(recorder.tools["build_competitor_catalog"](handles="ghost.store", days=30, top_n=3))
    assert out["stores_with_data"] == 0
    assert "error" in out["stores"][0]
    assert out["products_in_draft"] == 0


# ---------------------------------------------------------------------------
# push to Meta as staging (draft)
# ---------------------------------------------------------------------------


def test_build_push_to_meta_creates_staging_products(mock_meta_sdk_recorded, tmp_path):
    import src.competitor_catalog as _cc
    import src.config as _c
    import src.helpers as _h

    _h.ENABLE_WRITES = True
    _c.ENABLE_WRITES = True
    _cc.ENABLE_WRITES = True
    store = [_post(1, 200, 20, "طقم كارتير استيل 12000 ريال")]
    recorder = Recorder()
    competitor_catalog.register(recorder)

    created = []

    def api(method, path, params=None):
        if method == "POST" and path.endswith("/products"):
            created.append(params)
            return {"id": "prod_123"}
        return {}

    mock_meta_sdk_recorded["api_call"].side_effect = api
    with (
        mock.patch.object(competitor_catalog, "MEDIA_DOWNLOAD_DIR", tmp_path / "media"),
        mock.patch.object(competitor_catalog, "fetch_business_media", return_value=store),
        mock.patch.object(competitor_catalog, "oembed_image", return_value="https://scontent/y.jpg"),
        mock.patch.object(competitor_catalog, "download_image", return_value=1000),
    ):
        out = json.loads(
            recorder.tools["build_competitor_catalog"](
                handles="shop.ye", days=30, top_n=1, push_to_meta=True, catalog_id="cat_999"
            )
        )

    assert len(created) == 1
    assert created[0]["visibility"] == "staging"
    assert created[0]["price"] == "12000.0"
    assert created[0]["brand"] == "Butterfly"
    assert out["pushed_to_meta"][0]["id"] == "prod_123"
    assert out["pushed_to_meta"][0]["visibility"] == "staging"


# ---------------------------------------------------------------------------
# publish / list drafts
# ---------------------------------------------------------------------------


def test_publish_catalog_draft_updates_visibility(mock_meta_sdk_recorded):
    import src.competitor_catalog as _cc
    import src.config as _c
    import src.helpers as _h

    _h.ENABLE_WRITES = True
    _c.ENABLE_WRITES = True
    _cc.ENABLE_WRITES = True
    calls = []

    def api(method, path, params=None):
        calls.append((method, path, params))
        if method == "GET":
            return {"data": [{"id": "p1"}, {"id": "p2"}]}
        return {"success": True}

    mock_meta_sdk_recorded["api_call"].side_effect = api
    recorder = Recorder()
    competitor_catalog.register(recorder)
    out = json.loads(recorder.tools["publish_catalog_draft"](catalog_id="cat_1"))

    assert out["published"] == 2
    posts = [c for c in calls if c[0] == "POST"]
    assert len(posts) == 2
    assert posts[0][2] == {"visibility": "published"}


def test_list_catalog_drafts_filters_staging(mock_meta_sdk_recorded):
    def api(method, path, params=None):
        assert params["filter"] == json.dumps({"visibility": {"eq": "staging"}})
        return {"data": [{"id": "p1", "name": "طقم", "visibility": "staging"}]}

    mock_meta_sdk_recorded["api_call"].side_effect = api
    recorder = Recorder()
    competitor_catalog.register(recorder)
    out = json.loads(recorder.tools["list_catalog_drafts"](catalog_id="cat_1"))
    assert out["draft_count"] == 1
    assert out["products"][0]["visibility"] == "staging"


# ---------------------------------------------------------------------------
# registration surface
# ---------------------------------------------------------------------------


def test_module_registers_tools_resources_prompts():
    recorder = Recorder()
    competitor_catalog.register(recorder)
    assert set(recorder.tools) == {
        "build_competitor_catalog",
        "publish_catalog_draft",
        "list_catalog_drafts",
    }
    assert len(recorder.resources) >= 2
    assert len(recorder.prompts) >= 2
