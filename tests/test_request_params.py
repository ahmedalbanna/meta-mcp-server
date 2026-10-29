"""Tests that assert the exact request params/URLs sent to the mocked Meta API.

These catch the operator-precedence, sender_action, and waba_id bugs that the
plain smoke tests (JSON-parse only) missed.
"""

from unittest import mock

from tests.conftest import Recorder, register_all


def _register():
    recorder = Recorder()
    register_all(recorder)
    return recorder


def _call(tool_name, **kwargs):
    with mock.patch("src.utils.ENABLE_WRITES", True):
        return _register().tools[tool_name](**kwargs)


def test_pages_operator_precedence_keeps_suffix(mock_meta_sdk_recorded):
    _call("create_page_event", name="evt", start_time="2026-09-01T18:00:00+0300", page_id="123")
    calls = mock_meta_sdk_recorded["api_call"].call_args_list
    assert calls, "api_call was not called"
    endpoint = calls[-1].args[1]
    assert endpoint == "123/events", f"expected '123/events', got {endpoint!r}"


def test_messenger_sender_action_is_string(mock_meta_sdk_recorded):
    _call("mark_messenger_seen", recipient_id="456")
    calls = mock_meta_sdk_recorded["page_api_call"].call_args_list
    assert calls, "page_api_call was not called"
    params = calls[-1].args[2]
    assert params.get("sender_action") == "mark_seen", (
        f"sender_action should be a string, got {params.get('sender_action')!r}"
    )


def test_messenger_typing_sender_action_is_string(mock_meta_sdk_recorded):
    _call("set_messenger_typing", recipient_id="456", typing=False)
    calls = mock_meta_sdk_recorded["page_api_call"].call_args_list
    assert calls, "page_api_call was not called"
    params = calls[-1].args[2]
    assert params.get("sender_action") == "typing_off", (
        f"sender_action should be 'typing_off', got {params.get('sender_action')!r}"
    )


def test_whatsapp_template_falls_back_to_env_waba(mock_meta_sdk_recorded):
    from src.core.config import WABA_ID

    _call("create_whatsapp_message_template", name="test")
    calls = mock_meta_sdk_recorded["api_call"].call_args_list
    assert calls, "api_call was not called"
    endpoint = calls[-1].args[1]
    assert endpoint.startswith(WABA_ID), f"expected endpoint to start with WABA_ID {WABA_ID!r}, got {endpoint!r}"
