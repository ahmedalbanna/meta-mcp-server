import json

from tests.conftest import TEST_SERVICES, Recorder


def test_reels_account_insights_requires_ig_id():
    recorder = Recorder()
    from src import instagram

    instagram.register(recorder, TEST_SERVICES)
    # simulate unconfigured
    original = TEST_SERVICES.config.instagram_business_id
    TEST_SERVICES.config.fb_ig_user_id = ""
    try:
        out = json.loads(recorder.tools["get_instagram_reels_account_insights"]())
        assert "error" in out
    finally:
        TEST_SERVICES.config.fb_ig_user_id = original


def test_reels_account_insights_aggregates(mock_meta_sdk_recorded):
    def api(method, path, params=None):
        if str(path).endswith("/media"):
            return {
                "data": [
                    {
                        "id": "r1",
                        "media_type": "VIDEO",
                        "media_product_type": "REELS",
                        "permalink": "https://ig/r1",
                        "timestamp": "2026-10-20T18:00:00+0000",
                        "like_count": 10,
                        "comments_count": 2,
                        "caption": "reel one",
                    },
                    {
                        "id": "f1",
                        "media_type": "IMAGE",
                        "media_product_type": "FEED",
                        "permalink": "https://ig/f1",
                        "timestamp": "2026-10-20T18:00:00+0000",
                        "like_count": 5,
                        "comments_count": 1,
                    },
                ]
            }
        if str(path).endswith("/insights"):
            return {
                "data": [{"name": "plays", "values": [{"value": 100}]}, {"name": "reach", "values": [{"value": 80}]}]
            }
        return {"data": []}

    mock_meta_sdk_recorded["api_call"].side_effect = api
    recorder = Recorder()
    from src import instagram

    instagram.register(recorder, TEST_SERVICES)
    out = json.loads(recorder.tools["get_instagram_reels_account_insights"](limit=5, days=30))
    assert out["totals"]["reels_analysed"] == 1
    assert out["totals"]["plays"] == 100
    assert out["totals"]["reach"] == 80
    assert out["top_reels"][0]["media_id"] == "r1"
    assert out["top_reels"][0]["plays"] == 100
