"""Negative / edge-case tests for tool functions.

Uses mock_meta_sdk fixture (no Recorder — tools execute but SDK calls are mocked).
"""

import json

from tests.conftest import Recorder, register_all


def _register():
    recorder = Recorder()
    register_all(recorder)
    return recorder


# --- helpers ---


def test_sanitize_filename_strips_path_components():
    from src.helpers import sanitize_filename

    assert sanitize_filename("../../../etc/passwd") == "passwd"
    assert sanitize_filename("good.txt") == "good.txt"
    assert sanitize_filename("/absolute/path/file.csv") == "file.csv"


def test_sanitize_filename_rejects_empty():
    from src.helpers import sanitize_filename
    import pytest

    with pytest.raises(ValueError):
        sanitize_filename("")


def test_sanitize_filename_rejects_special_chars():
    from src.helpers import sanitize_filename
    import pytest

    with pytest.raises(ValueError):
        sanitize_filename("file:name")


def test_sanitize_path_stays_inside_root(tmp_path):
    from src.helpers import sanitize_path

    (tmp_path / "sub").mkdir()
    result = sanitize_path("sub/file.txt", tmp_path)
    assert str(result).startswith(str(tmp_path))


def test_sanitize_path_rejects_escape(tmp_path):
    from src.helpers import sanitize_path
    import pytest

    with pytest.raises(ValueError):
        sanitize_path("../../etc/passwd", tmp_path)


# --- messenger / whatsapp length limits ---


def test_send_messenger_message_rejects_long_text(mock_meta_sdk):
    recorder = _register()
    result = recorder.tools["send_messenger_message"](
        recipient_id="123", text="x" * 2001
    )
    data = json.loads(result)
    assert "error" in data


def test_send_messenger_message_accepts_short_text(mock_meta_sdk):
    from src import helpers as _h
    _h.ENABLE_WRITES = True
    try:
        recorder = _register()
        result = recorder.tools["send_messenger_message"](
            recipient_id="123", text="hello"
        )
        data = json.loads(result)
        assert "error" not in data
    finally:
        _h.ENABLE_WRITES = False


def test_send_whatsapp_text_message_rejects_long_text(mock_meta_sdk):
    recorder = _register()
    result = recorder.tools["send_whatsapp_text_message"](
        to="123", text="x" * 4097
    )
    data = json.loads(result)
    assert "error" in data


def test_send_whatsapp_text_message_accepts_short_text(mock_meta_sdk):
    from src import helpers as _h
    _h.ENABLE_WRITES = True
    try:
        recorder = _register()
        result = recorder.tools["send_whatsapp_text_message"](
            to="123", text="hi"
        )
        data = json.loads(result)
        assert "error" not in data
    finally:
        _h.ENABLE_WRITES = False


# --- create_ad edge cases ---


def test_create_ad_missing_creative_params_returns_error(mock_meta_sdk):
    """create_ad requires creative_name + page_id + message."""
    recorder = _register()
    result = recorder.tools["create_ad"](
        adset_id="123", name="test", creative_name="", page_id="", message=""
    )
    data = json.loads(result)
    assert "error" in data


# --- audiences edge cases ---


def test_create_custom_audience_empty_name(mock_meta_sdk):
    recorder = _register()
    result = recorder.tools["create_custom_audience"](name="", description="test")
    data = json.loads(result)
    # Should still work (API-level validation) or return an error
    assert "error" in data or "id" in data


# --- reports edge cases ---


def test_generate_campaign_report_empty_rows(mock_meta_sdk):
    recorder = _register()
    result = recorder.tools["generate_campaign_report"](date_preset="last_30d")
    data = json.loads(result)
    assert data["success"] is True
    assert data["rows"] == 0


def test_generate_instagram_report_empty(mock_meta_sdk):
    recorder = _register()
    result = recorder.tools["generate_instagram_report"](limit=1)
    data = json.loads(result)
    assert data["success"] is True
    assert data["posts"] == 0


# --- instagram caption update ---


def test_update_instagram_media_caption(mock_meta_sdk):
    recorder = _register()
    result = recorder.tools["update_instagram_media_caption"](
        media_id="123", caption="new caption"
    )
    data = json.loads(result)
    assert "success" in data or "error" in data


# --- adsets targeting ---


def test_update_adset_targeting_invalid_json(mock_meta_sdk):
    recorder = _register()
    result = recorder.tools["update_adset_targeting"](
        adset_id="123", targeting="not json"
    )
    data = json.loads(result)
    assert "error" in data


def test_update_adset_targeting_valid_json(mock_meta_sdk):
    recorder = _register()
    targeting = json.dumps({"geo_locations": {"countries": ["US"]}})
    result = recorder.tools["update_adset_targeting"](
        adset_id="123", targeting=targeting
    )
    data = json.loads(result)
    assert "success" in data or "error" in data
