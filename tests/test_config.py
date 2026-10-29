"""Unit tests for src.core.config — covers Config, validate_config, resolve_ad_account_id, ensure_report_dir."""


from src.core import config


def test_validate_config_missing_token():
    cfg = config.Config()
    # force empty token
    object.__setattr__(cfg, "fb_access_token", "")
    # validate_config uses module-level CONFIG/REQUIRED_KEYS; patch module
    config.REQUIRED_KEYS = {"FB_ACCESS_TOKEN": ""}
    missing = config.validate_config()
    assert "FB_ACCESS_TOKEN" in missing


def test_validate_config_ok():
    config.REQUIRED_KEYS = {"FB_ACCESS_TOKEN": "tok"}
    missing = config.validate_config()
    assert "FB_ACCESS_TOKEN" not in missing


def test_resolve_ad_account_id_override():
    cfg = config.Config()
    assert cfg.resolve_ad_account_id("act_override") == "act_override"


def test_ensure_report_dir_creates_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REPORT_DIR", tmp_path / "reports")
    config.ensure_report_dir()
    assert (tmp_path / "reports").exists()
