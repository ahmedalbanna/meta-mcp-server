"""Verify that importing server.py and registering every module works offline."""

import importlib

import pytest

from tests.conftest import TEST_SERVICES, TOOL_MODULES, Recorder, register_all


def _import_module(name):
    return importlib.import_module(f"src.{name}")


def test_server_imports_without_network():
    import server  # noqa: F401


def test_all_modules_register():
    recorder = register_all(Recorder())
    assert len(recorder.tools) > 0
    assert len(recorder.resources) >= 3
    assert len(recorder.prompts) >= 2


def test_tool_count():
    recorder = register_all(Recorder())
    assert len(recorder.tools) >= 155


def test_every_module_registers_at_least_one_tool():
    for module_name in TOOL_MODULES:
        recorder = Recorder()
        _import_module(module_name).register(recorder, TEST_SERVICES)
        assert recorder.tools, f"module {module_name} registered no tools"


@pytest.mark.parametrize("module_name", TOOL_MODULES)
def test_no_duplicate_tool_names(module_name):
    recorder = Recorder()
    _import_module(module_name).register(recorder, TEST_SERVICES)
    names = list(recorder.tools)
    assert len(names) == len(set(names)), f"duplicate tools in {module_name}"
