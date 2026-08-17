"""Unit tests for src/config.py — covers _get, _get_int, _get_bool, validate_config."""

import os
from unittest import mock

from src import config


def test_get_returns_first_set_env():
    with mock.patch.dict(os.environ, {"A": "val_a", "B": ""}, clear=False):
        assert config._get("A", "B") == "val_a"


def test_get_falls_back_to_second_env():
    with mock.patch.dict(os.environ, {"A": "", "B": "val_b"}, clear=False):
        assert config._get("A", "B") == "val_b"


def test_get_returns_default_when_none_set():
    with mock.patch.dict(os.environ, {}, clear=True):
        # Remove any leftover keys
        for k in ("X_MISSING_A", "X_MISSING_B"):
            os.environ.pop(k, None)
        assert config._get("X_MISSING_A", "X_MISSING_B", default="fallback") == "fallback"


def test_get_strips_whitespace():
    with mock.patch.dict(os.environ, {"C": "  spaced  "}, clear=False):
        assert config._get("C") == "spaced"


def test_get_int_parses_valid_int():
    with mock.patch.dict(os.environ, {"N": "42"}, clear=False):
        assert config._get_int("N") == 42


def test_get_int_returns_default_on_bad_value():
    with mock.patch.dict(os.environ, {"N": "not_a_number"}, clear=False):
        assert config._get_int("N", default=7) == 7


def test_get_int_returns_default_when_missing():
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("X_ABSENT_INT", None)
        assert config._get_int("X_ABSENT_INT", default=99) == 99


def test_get_bool_true_values():
    for val in ("1", "true", "yes", "on", "True", "YES"):
        with mock.patch.dict(os.environ, {"B": val}, clear=False):
            assert config._get_bool("B") is True, f"expected True for {val!r}"


def test_get_bool_false_values():
    for val in ("0", "false", "no", "off", "random", ""):
        with mock.patch.dict(os.environ, {"B": val}, clear=False):
            assert config._get_bool("B") is False, f"expected False for {val!r}"


def test_validate_config_missing_token():
    from src import config as _cfg
    _cfg.REQUIRED_KEYS = {"FB_ACCESS_TOKEN": ""}
    missing = _cfg.validate_config()
    assert "FB_ACCESS_TOKEN" in missing


def test_validate_config_ok():
    with mock.patch.dict(os.environ, {"FB_ACCESS_TOKEN": "tok"}, clear=False):
        from src import config as _cfg
        _cfg.REQUIRED_KEYS = {"FB_ACCESS_TOKEN": "tok"}
        missing = _cfg.validate_config()
        assert "FB_ACCESS_TOKEN" not in missing
