"""Offline tests for the FastAPI webhook receiver (pure functions only)."""

import json

import pytest


def test_verify_token_accepts_matching_token(monkeypatch):
    import webhook_server

    monkeypatch.setattr(webhook_server, "META_WEBHOOK_VERIFY_TOKEN", "secret123")
    assert webhook_server.verify_webhook_token("subscribe", "secret123") is True


def test_verify_token_rejects_bad_values(monkeypatch):
    import webhook_server

    monkeypatch.setattr(webhook_server, "META_WEBHOOK_VERIFY_TOKEN", "secret123")
    assert webhook_server.verify_webhook_token("subscribe", "wrong") is False
    assert webhook_server.verify_webhook_token("unsubscribe", "secret123") is False
    assert webhook_server.verify_webhook_token("", "") is False


def test_save_webhook_event_writes_json(tmp_path):
    import webhook_server

    payload = {"entry": [{"id": "123", "changes": []}]}
    saved = webhook_server.save_webhook_event(payload, report_dir=tmp_path)
    assert saved.startswith(str(tmp_path))
    data = json.loads(open(saved, encoding="utf-8").read())
    assert data["entry"][0]["id"] == "123"


def test_verify_signature_accepts_valid_hmac(monkeypatch):
    import hashlib
    import hmac

    import webhook_server

    monkeypatch.setattr(webhook_server, "APP_SECRET", "appsecret")
    body = b'{"entry":[]}'
    expected = "sha256=" + hmac.new(b"appsecret", body, hashlib.sha256).hexdigest()
    assert webhook_server.verify_signature(body, expected) is True


def test_verify_signature_rejects_tampered_body(monkeypatch):
    import webhook_server

    monkeypatch.setattr(webhook_server, "APP_SECRET", "appsecret")
    assert webhook_server.verify_signature(b'{"entry":[]}', "sha256=deadbeef") is False


def test_verify_signature_skipped_without_secret(monkeypatch):
    import webhook_server

    monkeypatch.setattr(webhook_server, "APP_SECRET", "")
    assert webhook_server.verify_signature(b"x", "sha256=anything") is True
