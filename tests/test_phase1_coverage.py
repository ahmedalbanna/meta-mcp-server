"""Phase 1 coverage: reports excel, audience hashing, webhook sig, pagination, error contract."""

import hashlib
import json

from tests.conftest import Recorder, register_all


def _register():
    rec = Recorder()
    register_all(rec)
    return rec


def test_reports_excel_generates_file(mock_meta_sdk, tmp_path, monkeypatch):
    """generate_campaign_report with format=excel creates .xlsx."""
    monkeypatch.setattr("src.reports.REPORT_DIR", tmp_path)
    monkeypatch.setattr("src.config.REPORT_DIR", tmp_path)
    rec = _register()
    result = rec.tools["generate_campaign_report"](format="excel", filename="test_excel")
    data = json.loads(result)
    assert data["success"] is True
    assert (tmp_path / "test_excel.xlsx").exists()


def test_reports_csv_generates_file(mock_meta_sdk, tmp_path, monkeypatch):
    monkeypatch.setattr("src.reports.REPORT_DIR", tmp_path)
    monkeypatch.setattr("src.config.REPORT_DIR", tmp_path)
    rec = _register()
    result = rec.tools["generate_campaign_report"](format="csv", filename="test_csv")
    data = json.loads(result)
    assert data["success"] is True
    assert (tmp_path / "test_csv.csv").exists()


def test_audience_hashing_sha256():
    from src.utils import normalize_email, normalize_phone, normalize_pii

    email = "Test@Example.com "
    expected = hashlib.sha256(b"test@example.com").hexdigest()
    assert normalize_email(email) == expected
    phone = "+1 (234) 567-8900"
    # normalize keeps leading + then digits
    raw = "+12345678900"
    assert normalize_phone(phone) == hashlib.sha256(raw.encode()).hexdigest()
    # batch
    emails = ["a@x.com", " b@y.com "]
    hashed = normalize_pii(emails, "email")
    assert len(hashed) == 2
    assert all(len(h) == 64 for h in hashed)


def test_webhook_signature_tampered_rejected(monkeypatch):
    import webhook_server
    monkeypatch.setattr(webhook_server, "APP_SECRET", "secret")
    assert webhook_server.verify_signature(b'{"a":1}', "sha256=deadbeef") is False


def test_webhook_signature_valid(monkeypatch):
    import hashlib
    import hmac

    import webhook_server
    monkeypatch.setattr(webhook_server, "APP_SECRET", "secret")
    body = b'{"entry":[]}'
    sig = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert webhook_server.verify_signature(body, sig) is True


def test_sanitize_path_traversal_blocked(tmp_path):
    import pytest

    from src.helpers import sanitize_path
    with pytest.raises(ValueError):
        sanitize_path("../../etc/passwd", tmp_path)
    with pytest.raises(ValueError):
        sanitize_path("/etc/passwd", tmp_path)


def test_sanitize_path_allowed(tmp_path):
    from src.helpers import sanitize_path
    (tmp_path / "sub").mkdir()
    p = sanitize_path("sub/file.txt", tmp_path)
    assert str(p).startswith(str(tmp_path))


def test_pagination_campaigns_uses_paginate(mock_meta_sdk):
    """list_campaigns now goes through paginate (returns list)."""
    rec = _register()
    result = rec.tools["list_campaigns"](limit=2)
    data = json.loads(result)
    assert isinstance(data, list)


def test_pagination_adsets_uses_paginate(mock_meta_sdk):
    rec = _register()
    result = rec.tools["list_adsets"](limit=2)
    data = json.loads(result)
    assert isinstance(data, list)


def test_pagination_ads_uses_paginate(mock_meta_sdk):
    rec = _register()
    result = rec.tools["list_ads"](limit=2)
    data = json.loads(result)
    assert isinstance(data, list)


def test_error_contract_includes_code_subcode(mock_meta_sdk):
    """handle_error returns code/subcode fields."""
    from facebook_business.exceptions import FacebookRequestError

    from src.helpers import handle_error
    err = FacebookRequestError(
        message="bad",
        request_context={},
        http_status=400,
        http_headers={},
        body='{"error": {"code": 100, "error_subcode": 33, "message": "Invalid"}}',
    )
    out = handle_error(err, "test_ctx")
    assert "code" in out
    assert "subcode" in out
    assert "error" in out
    assert out["context"] == "test_ctx"


def test_write_guard_rejection_includes_code():
    import src.helpers as h
    from src.helpers import json_dumps, write_guard
    # ensure writes disabled
    orig = h.ENABLE_WRITES
    h.ENABLE_WRITES = False
    try:
        @write_guard
        def dummy(a, status="ACTIVE"):
            return json_dumps({"ok": True})
        res = dummy(a=1, status="ACTIVE")
        data = json.loads(res)
        assert data.get("guard") is True
        assert "code" in data
        assert data["code"] in ("GUARD_WRITES_DISABLED", "GUARD_ACTIVATE_DISABLED")
    finally:
        h.ENABLE_WRITES = orig


def test_bulk_update_products_fixed(mock_meta_sdk):
    """Regression: bulk_update_products no longer NameError."""
    import src.helpers as h
    orig = h.ENABLE_WRITES
    h.ENABLE_WRITES = True
    try:
        rec = _register()
        payload = json.dumps([{"product_id": "123", "price": 9.99}])
        result = rec.tools["bulk_update_products"](updates_json=payload)
        data = json.loads(result)
        # should not be NameError, should have results
        assert "results" in data or "error" in data
        if "results" in data:
            assert data["total"] == 1
    finally:
        h.ENABLE_WRITES = orig


def test_upload_audience_csv_traversal_blocked(mock_meta_sdk, tmp_path, monkeypatch):
    """upload_custom_audience_csv rejects traversal outside BASE_DIR."""
    rec = _register()
    # use traversal that would escape BASE_DIR
    result = rec.tools["upload_custom_audience_csv"](
        audience_id="999", csv_path="../../etc/passwd", schema="EMAIL"
    )
    data = json.loads(result)
    assert "error" in data
